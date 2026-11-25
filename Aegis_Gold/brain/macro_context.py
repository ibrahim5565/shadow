"""
AEGIS QUANT X — Macro & Event Context Layer
============================================
Provides:
  1. Economic calendar ingestion (ForexFactory RSS — no API key required;
     FMP API as optional upgrade via config).
  2. Blackout / reduced-size windows around high-impact releases.
  3. Cross-asset context features: DXY, US 10Y yield (via MT5 symbols
     when available on the broker; silently degrades to None if absent).

PHILOSOPHY
----------
Gold is a macro-driven instrument.  A purely price-derived feature set is
structurally incomplete for XAUUSD.  NFP, CPI, FOMC, and real-yield
movements routinely override every technical pattern in the book.
The model trained on the blend misjudges both event and non-event regimes
unless bars are tagged for what they are.

SAFETY CONTRACT
---------------
  - Every method returns a safe default on any exception.
  - Missing calendar data → blackout=False, minutes_to_next=9999.
  - Missing cross-asset data → None values in MacroContextFeatures.
  - Never blocks the trading loop; network calls time out in < 5 s.

FEATURE FLAG
-----------
  QX["macro_event_context"].  When off, get_event_context() and
  get_macro_features() return safe-default objects instantly.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from xml.etree import ElementTree

logger = logging.getLogger("aegis.macro_context")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EconomicEvent:
    title:      str
    currency:   str         # "USD", "EUR", etc.
    impact:     str         # "HIGH", "MEDIUM", "LOW"
    utc_time:   datetime
    actual:     str = ""
    forecast:   str = ""
    previous:   str = ""


@dataclass
class EventContext:
    """Snapshot of macro event state at a given decision moment."""
    blackout:                  bool    = False
    reduced_size:              bool    = False
    reduced_size_factor:       float   = 1.0   # multiply lot by this (< 1 near events)
    minutes_to_next_high:      int     = 9999
    current_event_name:        str     = ""
    current_event_minutes_ago: int     = 0
    upcoming_events_24h:       int     = 0
    blackout_reason:           str     = ""


@dataclass
class MacroContextFeatures:
    """Cross-asset macro features for model input."""
    dxy:              Optional[float] = None    # DXY / USD index level
    dxy_change_pct:   Optional[float] = None    # % change from prev close
    us10y:            Optional[float] = None    # US 10Y nominal yield proxy
    real_yield_proxy: Optional[float] = None    # 10Y − 2Y spread proxy
    gold_dxy_corr_30d: Optional[float] = None  # Rolling 30-day correlation
    available:        bool             = False   # False → broker lacks symbols


# High-impact keywords — match case-insensitive against event title
HIGH_IMPACT_EVENTS = [
    "Non-Farm", "NFP", "CPI", "Fed", "FOMC", "Interest Rate",
    "Federal Funds", "PCE", "GDP", "PMI Flash", "Unemployment Rate",
    "ISM Manufacturing", "Retail Sales",
]

MEDIUM_IMPACT_EVENTS = [
    "PMI", "ADP", "Producer Price", "PPI", "Consumer Confidence",
    "Trade Balance", "Building Permits", "Durable Goods",
]


# ---------------------------------------------------------------------------
# MacroContext manager
# ---------------------------------------------------------------------------

class MacroContext:
    """
    Singleton-friendly macro context manager.
    Maintains a rolling 48-hour event cache refreshed in a background thread.
    """

    def __init__(self):
        self._events: List[EconomicEvent] = []
        self._last_refresh: float         = 0.0
        self._refresh_lock                = threading.Lock()
        self._mt5_available               = False
        self._cross_asset_history: Dict[str, List[float]] = {
            "dxy": [], "us10y": []
        }

    # ── Public API ──────────────────────────────────────────────────────────

    def get_event_context(self,
                          symbol: str = "XAUUSD",
                          utc_now: Optional[datetime] = None) -> EventContext:
        """
        Return the event context for the current moment.
        Safe: any failure returns EventContext() with blackout=False.
        """
        from config.quant_x_config import QX
        if not QX.flag("macro_event_context"):
            return EventContext()

        try:
            return self._compute_event_context(symbol, utc_now or datetime.now(timezone.utc))
        except Exception as exc:
            logger.warning("[MACRO] get_event_context failed: %s", exc)
            return EventContext()

    def get_macro_features(self) -> MacroContextFeatures:
        """
        Return cross-asset features.  Attempts MT5 symbol poll; degrades
        gracefully if symbols unavailable.
        """
        from config.quant_x_config import QX
        if not QX.flag("macro_event_context"):
            return MacroContextFeatures()

        try:
            return self._poll_cross_asset()
        except Exception as exc:
            logger.warning("[MACRO] get_macro_features failed: %s", exc)
            return MacroContextFeatures()

    def get_bar_tags(self, bar_time: float) -> dict:
        """
        Convenience method: returns a flat dict of tags for a given bar
        timestamp (Unix seconds).  Consumed by FeaturePipeline.
        """
        utc = datetime.fromtimestamp(bar_time, tz=timezone.utc)
        ctx = self.get_event_context(utc_now=utc)
        feat = self.get_macro_features()
        return {
            "event_blackout":           ctx.blackout,
            "event_reduced_size":       ctx.reduced_size,
            "event_reduced_factor":     ctx.reduced_size_factor,
            "minutes_to_next_high":     ctx.minutes_to_next_high,
            "upcoming_events_24h":      ctx.upcoming_events_24h,
            "macro_dxy":                feat.dxy,
            "macro_dxy_chg":            feat.dxy_change_pct,
            "macro_us10y":              feat.us10y,
            "macro_real_yield":         feat.real_yield_proxy,
            "macro_gold_dxy_corr":      feat.gold_dxy_corr_30d,
        }

    def refresh_calendar(self) -> None:
        """
        Force-refresh the event calendar now.
        Called by the background refresh thread and on startup.
        """
        from config.quant_x_config import QX
        source = QX.get("calendar_source") or "forexfactory_rss"
        try:
            if source == "forexfactory_rss":
                events = self._fetch_forexfactory_rss()
            else:
                events = []
                logger.warning("[MACRO] Unknown calendar_source '%s'", source)

            with self._refresh_lock:
                self._events = events
                self._last_refresh = time.time()

            logger.info("[MACRO] Calendar refreshed: %d events loaded", len(events))
        except Exception as exc:
            logger.warning("[MACRO] Calendar refresh failed: %s", exc)

    def start_background_refresh(self) -> None:
        """Start a daemon thread that refreshes the calendar periodically."""
        def _loop():
            from config.quant_x_config import QX
            while True:
                try:
                    refresh_min = QX.get("calendar_refresh_minutes") or 60
                    if time.time() - self._last_refresh > refresh_min * 60:
                        self.refresh_calendar()
                except Exception as exc:
                    logger.warning("[MACRO] Background refresh error: %s", exc)
                time.sleep(300)  # check every 5 minutes

        t = threading.Thread(target=_loop, daemon=True, name="macro_calendar_refresh")
        t.start()
        logger.info("[MACRO] Background calendar refresh thread started")

    # ── Internal — event context computation ────────────────────────────────

    def _compute_event_context(self, symbol: str,
                                now: datetime) -> EventContext:
        from config.quant_x_config import QX

        # Auto-refresh if stale
        refresh_min = QX.get("calendar_refresh_minutes") or 60
        if time.time() - self._last_refresh > refresh_min * 60:
            self.refresh_calendar()

        with self._refresh_lock:
            events = list(self._events)

        # Only USD events matter for XAUUSD (and EURUSD to a lesser extent)
        relevant_currencies = {"USD"}
        if symbol == "EURUSD":
            relevant_currencies.add("EUR")

        high_impact = [
            e for e in events
            if e.impact == "HIGH" and e.currency in relevant_currencies
        ]
        all_upcoming_24h = [
            e for e in high_impact
            if 0 <= (e.utc_time - now).total_seconds() <= 86400
        ]

        ctx = EventContext(upcoming_events_24h=len(all_upcoming_24h))

        # Find the nearest upcoming high-impact event
        upcoming = sorted(
            [e for e in high_impact if e.utc_time > now],
            key=lambda e: e.utc_time
        )
        if upcoming:
            nearest        = upcoming[0]
            mins_to_next   = int((nearest.utc_time - now).total_seconds() / 60)
            ctx.minutes_to_next_high = mins_to_next
        else:
            mins_to_next = 9999

        # Find the most recent past high-impact event
        recent_past = sorted(
            [e for e in high_impact if e.utc_time <= now],
            key=lambda e: e.utc_time, reverse=True
        )
        mins_since_last = 9999
        if recent_past:
            mins_since_last = int((now - recent_past[0].utc_time).total_seconds() / 60)
            ctx.current_event_name        = recent_past[0].title
            ctx.current_event_minutes_ago = mins_since_last

        # Determine blackout windows per event type
        blackout_map = {
            "nfp":    QX.get("blackout_nfp_minutes")   or 30,
            "fomc":   QX.get("blackout_fomc_minutes")  or 60,
            "cpi":    QX.get("blackout_cpi_minutes")   or 20,
            "default": QX.get("blackout_default_minutes") or 15,
        }

        def _blackout_window(event: EconomicEvent) -> int:
            t = event.title.lower()
            if any(k in t for k in ["non-farm", "nfp"]):
                return blackout_map["nfp"]
            if any(k in t for k in ["fomc", "federal funds", "interest rate", "fed rate"]):
                return blackout_map["fomc"]
            if "cpi" in t or "consumer price" in t:
                return blackout_map["cpi"]
            return blackout_map["default"]

        # Check whether we are inside any blackout window
        for event in high_impact:
            bw = _blackout_window(event)
            mins_to_event   = (event.utc_time - now).total_seconds() / 60
            mins_from_event = (now - event.utc_time).total_seconds() / 60

            inside = (-bw <= mins_to_event <= 0) or (0 <= mins_from_event <= bw)
            if inside:
                ctx.blackout       = True
                ctx.blackout_reason = (
                    f"{event.title} ±{bw}min window "
                    f"({'in {:.0f}min'.format(mins_to_event) if mins_to_event > 0 else 'passed {:.0f}min ago'.format(mins_from_event)})"
                )
                break

        # Reduced-size window: approaching within 2× blackout window
        reduced_factor = float(QX.get("reduced_size_factor") or 0.5)
        for event in upcoming[:3]:
            bw = _blackout_window(event)
            mins_to_event = (event.utc_time - now).total_seconds() / 60
            if mins_to_event <= bw * 2 and not ctx.blackout:
                ctx.reduced_size        = True
                ctx.reduced_size_factor = reduced_factor
                break

        if not ctx.reduced_size:
            ctx.reduced_size_factor = 1.0

        return ctx

    # ── Internal — ForexFactory RSS fetch ───────────────────────────────────

    def _fetch_forexfactory_rss(self) -> List[EconomicEvent]:
        """Offline-only mode: never fetch economic-calendar data over the internet.

        If a local calendar cache is added later, it must be timestamped and
        validated before it can influence a decision. No network fallback.
        """
        logger.info("[MACRO] External calendar fetch disabled by offline prediction policy")
        return []

    # ── Internal — Cross-asset polling ──────────────────────────────────────

    def _poll_cross_asset(self) -> MacroContextFeatures:
        """
        Poll MT5 for DXY and US10Y proxy symbols.
        Silently returns unavailable=True if symbols not found.
        """
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return MacroContextFeatures()

        feat = MacroContextFeatures()

        # DXY candidates (broker-dependent naming)
        dxy_candidates = ["USDX", "DXY", "USDIndex", "DXYUSD"]
        dxy_tick = None
        for sym in dxy_candidates:
            try:
                tick = mt5.symbol_info_tick(sym)
                if tick is not None:
                    dxy_tick = tick
                    break
            except Exception:
                pass

        # US10Y proxy: some brokers list it as a CFD
        us10y_candidates = ["US10Y", "TNX", "US10YR", "TNOTE"]
        us10y_tick = None
        for sym in us10y_candidates:
            try:
                tick = mt5.symbol_info_tick(sym)
                if tick is not None:
                    us10y_tick = tick
                    break
            except Exception:
                pass

        if dxy_tick is None and us10y_tick is None:
            return MacroContextFeatures(available=False)

        feat.available = True

        if dxy_tick is not None:
            current_dxy = (dxy_tick.bid + dxy_tick.ask) / 2
            feat.dxy = round(current_dxy, 4)
            hist = self._cross_asset_history["dxy"]
            if hist:
                prev = hist[-1]
                feat.dxy_change_pct = round((current_dxy - prev) / prev * 100, 4) if prev > 0 else 0.0
            hist.append(current_dxy)
            if len(hist) > 200:
                self._cross_asset_history["dxy"] = hist[-200:]

        if us10y_tick is not None:
            current_10y = (us10y_tick.bid + us10y_tick.ask) / 2
            feat.us10y = round(current_10y, 4)
            hist = self._cross_asset_history["us10y"]
            hist.append(current_10y)
            if len(hist) > 200:
                self._cross_asset_history["us10y"] = hist[-200:]
            # Real yield proxy: crude approximation using 10Y alone
            # (proper real yield = nominal − breakeven, but breakeven unavailable)
            feat.real_yield_proxy = round(current_10y, 4)

        # Gold-DXY correlation (30-day rolling, if enough data)
        if len(self._cross_asset_history["dxy"]) >= 30:
            try:
                dxy_vals = self._cross_asset_history["dxy"][-30:]
                feat.gold_dxy_corr_30d = _rolling_corr_stub(dxy_vals)
            except Exception:
                pass

        return feat


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _xml_text(element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_ff_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """
    Parse ForexFactory date ("07-15-2026") + time ("8:30am") → UTC datetime.
    FF publishes in US Eastern time (EST = UTC-5, EDT = UTC-4).
    We use a simple -5 offset (conservative).
    """
    try:
        dt = datetime.strptime(date_str, "%m-%d-%Y")
    except ValueError:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

    if not time_str or time_str.lower() in ("tentative", "all day", ""):
        # No fixed time — place at noon EST as conservative estimate
        dt = dt.replace(hour=17, tzinfo=timezone.utc)  # noon EST = 17:00 UTC
        return dt

    try:
        ts = time_str.strip().lower()
        ampm = "am" if "am" in ts else "pm"
        ts_clean = ts.replace("am", "").replace("pm", "").strip()
        parts = ts_clean.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        # Convert EST (UTC-5) to UTC
        est_dt = dt.replace(hour=hour, minute=minute, tzinfo=None)
        utc_dt = est_dt + timedelta(hours=5)
        return utc_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _rolling_corr_stub(series: List[float]) -> Optional[float]:
    """
    Returns a simple correlation stub for DXY history.
    A proper gold-DXY correlation requires gold price history too;
    that requires MT5 historical bars which would make this call slow.
    We return the DXY momentum direction as a signed proxy instead.
    """
    if len(series) < 5:
        return None
    try:
        import statistics
        recent  = series[-5:]
        earlier = series[-10:-5]
        dxy_momentum = statistics.mean(recent) - statistics.mean(earlier)
        # Gold is negatively correlated with DXY typically
        return round(-1.0 if dxy_momentum > 0 else 1.0, 2)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_ctx: Optional[MacroContext] = None


def get_macro_context() -> MacroContext:
    global _ctx
    if _ctx is None:
        _ctx = MacroContext()
    return _ctx
