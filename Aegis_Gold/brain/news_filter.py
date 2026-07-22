"""
Aegis-Gold — Forex Factory News Filter
Fetches the public FF RSS feed and blocks trading during high-impact news windows.
Cached for 30 minutes. Fails OPEN (allows trading) if internet unavailable.
"""
import logging
import time
import threading
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

logger = logging.getLogger("aegis.news_filter")

# Impact keywords in FF feed
_HIGH_IMPACT_KEYWORDS = ["high", "🔴", "red"]

# Currencies we care about
_WATCHED_CURRENCIES = {"USD", "EUR", "XAU", "GOLD", "GBP"}

# Cache — single fetch per hour, shared across all calls
_cache_lock = threading.Lock()
_last_fetch_time = 0.0
_cached_events: list = []
_CACHE_TTL = 3600  # 1 hour
_fetching = False

def _get_cached_events() -> list:
    """Return cached events, refreshing if stale. Thread-safe. Never fetches more than once per hour."""
    global _last_fetch_time, _cached_events, _fetching
    now = time.time()

    # Fast path — return cache if still fresh
    if _cached_events is not None and (now - _last_fetch_time) < _CACHE_TTL:
        return _cached_events

    with _cache_lock:
        # Double-check after acquiring lock
        if (time.time() - _last_fetch_time) < _CACHE_TTL and _cached_events is not None:
            return _cached_events
        if _fetching:
            return _cached_events or []
        _fetching = True

    try:
        logger.debug("News filter: refreshing calendar (1-hour cache)...")
        new_events = _fetch_ff_events()
        _cached_events = new_events
        _last_fetch_time = time.time()
    except Exception as e:
        logger.warning(f"News filter refresh error: {e}")
    finally:
        _fetching = False

    return _cached_events or []


def _fetch_ff_events() -> list:
    """Fetch and parse Forex Factory RSS calendar feed. Returns list of event dicts."""
    events = []
    try:
        import requests
        resp = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 AegisBot/6.0"}
        )
        if resp.ok:
            data = resp.json()
            for item in data:
                try:
                    impact = item.get("impact", "").lower()
                    if impact != "high":
                        continue
                    currency = item.get("currency", "").upper()
                    if currency not in _WATCHED_CURRENCIES:
                        continue
                    date_str = item.get("date", "")
                    time_str = item.get("time", "")
                    # Parse time — FF JSON uses ISO 8601 or "2025-06-12T13:30:00-04:00"
                    dt = None
                    try:
                        dt = datetime.fromisoformat(date_str)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        pass
                    if dt:
                        events.append({
                            "title": item.get("title", "Unknown"),
                            "currency": currency,
                            "impact": "HIGH",
                            "time": dt,
                        })
                except Exception:
                    continue
        logger.info(f"News filter: fetched {len(events)} high-impact events from FF")
    except Exception as exc:
        logger.warning(f"News filter: could not fetch FF calendar ({exc}). Failing open.")
    return events


def is_news_blackout(symbol: str, blackout_minutes: int = 15) -> tuple[bool, str]:
    """
    Check if current time is within ±blackout_minutes of a HIGH impact news event
    relevant to the given symbol.

    Returns:
        (True, reason_str)  — if in blackout period (DO NOT TRADE)
        (False, "")         — if clear to trade
    """
    try:
        events = _get_cached_events()
        if not events:
            return False, ""  # Fail open

        now = datetime.now(timezone.utc)
        window = timedelta(minutes=blackout_minutes)

        # Which currencies are relevant for this symbol?
        sym_upper = symbol.upper()
        relevant_currencies = set()
        if "EUR" in sym_upper:
            relevant_currencies.add("EUR")
        if "USD" in sym_upper or "GOLD" in sym_upper or "XAU" in sym_upper:
            relevant_currencies.add("USD")
        if "XAU" in sym_upper or "GOLD" in sym_upper:
            relevant_currencies.add("XAU")
            relevant_currencies.add("GOLD")
        if "GBP" in sym_upper:
            relevant_currencies.add("GBP")

        for event in events:
            if event["currency"] not in relevant_currencies:
                continue
            event_time = event["time"]
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
            diff = event_time - now
            abs_diff_min = abs(diff.total_seconds()) / 60

            if abs_diff_min <= blackout_minutes:
                direction = "in" if diff.total_seconds() > 0 else "ago"
                mins = int(abs_diff_min)
                reason = (
                    f"📰 NEWS BLACKOUT: [{event['currency']}] {event['title']} "
                    f"({mins}min {direction}) — pausing trade"
                )
                logger.info(f"News filter ACTIVE for {symbol}: {reason}")
                return True, reason

        return False, ""

    except Exception as exc:
        logger.error(f"News filter error: {exc}. Failing open.")
        return False, ""


def get_upcoming_events(hours: int = 2) -> list:
    """Return upcoming high-impact events within the next N hours."""
    events = _get_cached_events()
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours)
    upcoming = []
    for ev in events:
        et = ev["time"]
        if et.tzinfo is None:
            et = et.replace(tzinfo=timezone.utc)
        if now <= et <= cutoff:
            upcoming.append(ev)
    return sorted(upcoming, key=lambda e: e["time"])


def format_news_report(hours: int = 2) -> str:
    """Format a human-readable upcoming news report for Telegram."""
    events = get_upcoming_events(hours)
    if not events:
        return f"📰 <b>No HIGH impact news</b> in next {hours} hours. Markets clear."
    lines = [f"📰 <b>HIGH IMPACT NEWS — Next {hours} Hours</b>"]
    lines.append("─────────────────────────")
    for ev in events:
        et = ev["time"]
        if et.tzinfo is None:
            et = et.replace(tzinfo=timezone.utc)
        time_str = et.strftime("%H:%M UTC")
        now = datetime.now(timezone.utc)
        mins_from_now = int((et - now).total_seconds() / 60)
        lines.append(
            f"🔴 [{ev['currency']}] {ev['title']}\n"
            f"   🕐 {time_str} (in {mins_from_now} min)"
        )
    return "\n".join(lines)
