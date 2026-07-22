"""
===========================================================================
AEGIS GOLD v8.0 -- Decision Explainability Engine
===========================================================================

PURPOSE:
--------
Every trade decision must be measurable, explainable, and auditable.
This engine converts raw scores from all sub-engines into a structured,
human-readable explanation that is:

  1. Stored in trade_memory.db alongside each trade.
  2. Sent via Telegram on every signal.
  3. Used by the self-improvement loop for performance attribution.
  4. Made available on the dashboard API.

PHILOSOPHY:
-----------
"A system that cannot explain its decisions cannot learn from them."

Institutional AI does not make black-box decisions. Every action must be
traceable to specific market evidence, and that evidence must be recorded
so the system can retrospectively determine what worked.

OUTPUT FORMAT:
--------------
{
    "trade_id": ...,
    "timestamp": ...,
    "direction": "BUY" | "SELL",
    "final_confidence": int,  # 0-100
    "action": "TRADE" | "WAIT",
    "grade": "A+" | "A" | "B" | "C" | "D" | "F",
    "signal_sources": {
        "SCALP": { "score": int, "passed": bool, "reason": str },
        "SMC":   { "score": int, "passed": bool, "reason": str },
        "ML":    { "score": int, "passed": bool, "reason": str },
        "RL":    { "action": str, "confidence": int }
    },
    "component_breakdown": {
        "structure": { "score": int, "weight": 0.10, "contribution": float },
        "smc":       { "score": int, "weight": 0.12, "contribution": float },
        "mtf":       { "score": int, "weight": 0.15, "contribution": float },
        "statistical": { ... },
        "ml":        { ... },
        "momentum":  { ... },
        ...
    },
    "veto_checks": [
        { "name": "spread_veto", "triggered": bool, "value": float, "threshold": float },
        { "name": "news_veto", "triggered": bool },
        { "name": "drawdown_veto", "triggered": bool, "value": float }
    ],
    "market_context": {
        "regime": str, "session": str, "adx": float, "rsi": float,
        "atr": float, "spread": float, "trend": str
    },
    "risk_assessment": {
        "lot": float, "sl_points": int, "tp_points": int,
        "rr_ratio": float, "max_loss_usd": float
    },
    "plain_english": str  # 3-5 sentence human explanation
}
===========================================================================
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("aegis.explainability")

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "trade_memory.db"
EXPLAIN_DB_PATH = BASE_DIR / "data" / "explanations.db"


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def _init_explain_db():
    """Create explanations table if it doesn't exist."""
    EXPLAIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(EXPLAIN_DB_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS explanations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id      TEXT,
                timestamp     TEXT,
                symbol        TEXT,
                direction     TEXT,
                action        TEXT,
                confidence    INTEGER,
                grade         TEXT,
                signal_json   TEXT,
                breakdown_json TEXT,
                veto_json     TEXT,
                context_json  TEXT,
                risk_json     TEXT,
                plain_english TEXT,
                outcome       TEXT DEFAULT NULL,
                outcome_pnl   REAL DEFAULT NULL,
                attribution_json TEXT DEFAULT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_id ON explanations(trade_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON explanations(timestamp)")
        conn.commit()
    finally:
        conn.close()


_init_explain_db()


# ---------------------------------------------------------------------------
# Grade mapping
# ---------------------------------------------------------------------------

def _confidence_to_grade(confidence: int) -> str:
    if confidence >= 90:
        return "A+"
    elif confidence >= 80:
        return "A"
    elif confidence >= 70:
        return "B+"
    elif confidence >= 60:
        return "B"
    elif confidence >= 50:
        return "C"
    elif confidence >= 40:
        return "D"
    else:
        return "F"


# ---------------------------------------------------------------------------
# Plain-English Narrative Generator
# ---------------------------------------------------------------------------

def _build_plain_english(
    direction: str,
    action: str,
    confidence: int,
    market_context: dict,
    signal_sources: dict,
    veto_checks: list,
    risk: dict
) -> str:
    """Generate a concise human-readable explanation of the decision."""
    regime = market_context.get("regime", "UNKNOWN")
    session = market_context.get("session", "UNKNOWN")
    adx = market_context.get("adx", 0.0)
    rsi = market_context.get("rsi", 50.0)
    spread = market_context.get("spread", 0.0)

    triggered_vetos = [v["name"] for v in veto_checks if v.get("triggered")]

    if action == "WAIT":
        if triggered_vetos:
            veto_str = ", ".join(triggered_vetos)
            return (
                f"No trade was placed. Active veto conditions blocked execution: {veto_str}. "
                f"The market is in a {regime} regime during the {session} session with "
                f"ADX={adx:.1f} and RSI={rsi:.1f}. Confidence scored {confidence}%, "
                f"which is below the minimum threshold required for entry."
            )
        return (
            f"No trade taken. Confidence of {confidence}% was insufficient for a "
            f"{direction} entry. The {regime} regime in the {session} session had "
            f"ADX={adx:.1f} and RSI={rsi:.1f}. All conditions were evaluated but "
            f"no strong enough convergence was found across signal sources."
        )

    # Trade was taken
    sources_ok = [k for k, v in signal_sources.items() if v.get("passed")]
    sources_fail = [k for k, v in signal_sources.items() if not v.get("passed") and k != "RL"]
    rr = risk.get("rr_ratio", 0.0)
    lot = risk.get("lot", 0.0)
    sl = risk.get("sl_points", 0)
    tp = risk.get("tp_points", 0)

    source_summary = (
        f"Confirmed by: {', '.join(sources_ok)}." if sources_ok else "No strong source confirmed."
    )
    reject_summary = (
        f"Weak signals from: {', '.join(sources_fail)}." if sources_fail else ""
    )

    return (
        f"A {direction} trade was placed with {confidence}% confidence (Grade: {_confidence_to_grade(confidence)}). "
        f"The market is in a {regime} regime during the {session} session. "
        f"{source_summary} {reject_summary} "
        f"Risk/Reward ratio is {rr:.2f}:1 — entry at {lot} lot with SL={sl}pts and TP={tp}pts. "
        f"ADX={adx:.1f} (trend strength), RSI={rsi:.1f} (momentum bias)."
    )


# ---------------------------------------------------------------------------
# Core Explanation Builder
# ---------------------------------------------------------------------------

def build_explanation(
    trade_id: Optional[str],
    symbol: str,
    direction: str,
    action: str,
    confidence: int,
    signal_sources: Optional[Dict] = None,
    component_breakdown: Optional[Dict] = None,
    veto_checks: Optional[List] = None,
    market_context: Optional[Dict] = None,
    risk_assessment: Optional[Dict] = None,
    shap_values: Optional[Dict] = None,
) -> dict:
    """
    Builds a complete structured explanation for a trade decision.
    QUANT X: Enriched with calibration metrics, model card info, and SHAP attributions.
    """
    signal_sources = signal_sources or {}
    component_breakdown = component_breakdown or {}
    veto_checks = veto_checks or []
    market_context = market_context or {}
    risk_assessment = risk_assessment or {}

    grade = _confidence_to_grade(confidence)
    plain_english = _build_plain_english(
        direction, action, confidence, market_context,
        signal_sources, veto_checks, risk_assessment
    )

    # QUANT X: Fetch calibration metrics
    calibration_metrics = {}
    try:
        from brain.calibration import get_calibration_monitor
        cal_status = get_calibration_monitor().get_status()
        calibration_metrics = {
            "brier_score": cal_status.get("brier_score"),
            "ece": cal_status.get("ece"),
            "threshold_penalty": cal_status.get("threshold_penalty", 0)
        }
    except Exception:
        pass

    # QUANT X: Fetch model version information
    model_card = {}
    try:
        from brain.champion_challenger import get_arena
        status = get_arena().get_status()
        active_champ = status.get("champion", {})
        if active_champ:
            model_card = {
                "name": active_champ.get("name"),
                "created_at": active_champ.get("created_at"),
                "win_rate": active_champ.get("win_rate"),
                "sharpe_proxy": active_champ.get("sharpe_proxy")
            }
    except Exception:
        pass

    explanation = {
        "trade_id": trade_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "direction": direction,
        "action": action,
        "final_confidence": confidence,
        "grade": grade,
        "signal_sources": signal_sources,
        "component_breakdown": component_breakdown,
        "veto_checks": veto_checks,
        "market_context": market_context,
        "risk_assessment": risk_assessment,
        "plain_english": plain_english,
        # ── QUANT X Enriched Fields ─────────────────────────
        "shap_values": shap_values or {},
        "calibration_metrics": calibration_metrics,
        "model_card": model_card
    }

    return explanation



# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_explanation(explanation: dict) -> int:
    """Persist explanation to SQLite. Returns row id."""
    try:
        conn = sqlite3.connect(str(EXPLAIN_DB_PATH))
        cursor = conn.execute("""
            INSERT INTO explanations (
                trade_id, timestamp, symbol, direction, action,
                confidence, grade, signal_json, breakdown_json,
                veto_json, context_json, risk_json, plain_english
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(explanation.get("trade_id") or ""),
            explanation.get("timestamp", ""),
            explanation.get("symbol", ""),
            explanation.get("direction", ""),
            explanation.get("action", ""),
            explanation.get("final_confidence", 0),
            explanation.get("grade", "F"),
            json.dumps(explanation.get("signal_sources", {})),
            json.dumps(explanation.get("component_breakdown", {})),
            json.dumps(explanation.get("veto_checks", [])),
            json.dumps(explanation.get("market_context", {})),
            json.dumps(explanation.get("risk_assessment", {})),
            explanation.get("plain_english", ""),
        ))
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id
    except Exception as e:
        logger.error(f"[EXPLAIN] Failed to save explanation: {e}")
        return -1


def update_outcome(trade_id: str, outcome: str, pnl: float, attribution: dict = None):
    """
    After a trade closes, record the outcome and attribution breakdown.
    This feeds the performance attribution analysis.
    """
    try:
        conn = sqlite3.connect(str(EXPLAIN_DB_PATH))
        conn.execute("""
            UPDATE explanations
            SET outcome = ?, outcome_pnl = ?, attribution_json = ?
            WHERE trade_id = ?
        """, (
            outcome,
            pnl,
            json.dumps(attribution or {}),
            str(trade_id)
        ))
        conn.commit()
        conn.close()
        logger.info(f"[EXPLAIN] Updated outcome for trade {trade_id}: {outcome} PnL={pnl:.2f}")
    except Exception as e:
        logger.error(f"[EXPLAIN] Failed to update outcome: {e}")


def get_recent_explanations(limit: int = 20) -> list:
    """Return the N most recent explanations."""
    try:
        conn = sqlite3.connect(str(EXPLAIN_DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM explanations ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[EXPLAIN] Failed to load explanations: {e}")
        return []


def get_explanation_for_trade(trade_id: str) -> Optional[dict]:
    """Return explanation for a specific trade id."""
    try:
        conn = sqlite3.connect(str(EXPLAIN_DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT * FROM explanations WHERE trade_id = ? ORDER BY id DESC LIMIT 1
        """, (str(trade_id),)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"[EXPLAIN] Failed to get explanation: {e}")
        return None


# ---------------------------------------------------------------------------
# Module 6: Permutation Feature Importance (SHAP-style, no external library)
# ---------------------------------------------------------------------------

def compute_shap_top3(
    market_context: dict,
    signal_sources: dict,
    base_confidence: int,
    top_n: int = 3,
) -> list:
    """
    Compute top-N feature attributions using permutation feature importance.

    No SHAP library required — uses stdlib + simple numpy arithmetic.
    For each feature, the baseline confidence is re-estimated with that
    feature zeroed out; the delta measures its marginal contribution.

    Parameters
    ----------
    market_context  : dict from explanation['market_context'] with keys
                      like regime, session, adx, rsi, spread, atr.
    signal_sources  : dict from explanation['signal_sources'] with keys
                      SCALP, SMC (each containing 'passed': bool).
    base_confidence : The final stated confidence (0–100).
    top_n           : Number of top features to return.

    Returns
    -------
    list of dicts — top_n features sorted by abs(impact) descending:
        [{"feature": "adx", "value": 24.5, "impact": +8}, ...]
    """
    try:
        from config.quant_x_config import QX
        if not QX.flag("shap_explainability"):
            return []
    except Exception:
        return []

    try:
        # Reconstruct a simple confidence estimate from features
        # Uses the same relative weights as the core brain layer
        adx    = float(market_context.get("adx")    or 20.0)
        rsi    = float(market_context.get("rsi")    or 50.0)
        spread = float(market_context.get("spread") or 5.0)
        atr    = float(market_context.get("atr")    or 0.0)

        regime  = str(market_context.get("regime") or "").upper()
        session = str(market_context.get("session") or "").upper()

        scalp_pass = bool(signal_sources.get("SCALP", {}).get("passed", False))
        smc_pass   = bool(signal_sources.get("SMC",   {}).get("passed", False))

        # Feature vector (name, current_value, zeroed_value)
        features = [
            ("adx",          adx,     0.0),
            ("rsi",          rsi,     50.0),      # neutral RSI = 50
            ("spread",       spread,  0.0),
            ("atr",          atr,     0.0),
            ("scalp_signal", float(scalp_pass), 0.0),
            ("smc_signal",   float(smc_pass),   0.0),
            ("trending",     float("TREND" in regime),  0.0),
            ("london_session", float("LONDON" in session), 0.0),
        ]

        def _estimate_conf(feat_vals: dict) -> float:
            """
            Lightweight confidence re-estimator.
            Approximates the decision engine's scoring without running the full brain.
            """
            score = 40.0  # base

            # ADX contribution: 0–25 range = 0–15pts
            _adx = feat_vals.get("adx", 0.0)
            score += min(15.0, max(0.0, (_adx - 10) / 1.5))

            # RSI: rewarded when trending away from 50, penalised when near 50
            _rsi = feat_vals.get("rsi", 50.0)
            score += abs(_rsi - 50) / 5.0  # max ~10 pts when RSI at 0 or 100

            # Spread penalty (high spread = low confidence)
            _spr = feat_vals.get("spread", 0.0)
            score -= min(10.0, _spr * 0.5)

            # Signal source bonuses
            score += feat_vals.get("scalp_signal", 0.0) * 10.0
            score += feat_vals.get("smc_signal",   0.0) * 8.0

            # Regime bonus
            score += feat_vals.get("trending", 0.0) * 5.0

            # Session bonus
            score += feat_vals.get("london_session", 0.0) * 5.0

            return max(0.0, min(100.0, score))

        # Build baseline dict
        baseline_vals = {f[0]: f[1] for f in features}
        baseline_est  = _estimate_conf(baseline_vals)

        # Scale factor: align our estimate to the actual stated confidence
        scale = (float(base_confidence) / baseline_est) if baseline_est > 0 else 1.0

        impacts = []
        for name, current_val, zeroed_val in features:
            # Zero out this feature
            modified = dict(baseline_vals)
            modified[name] = zeroed_val
            modified_est   = _estimate_conf(modified) * scale

            impact = round(float(base_confidence) - modified_est, 1)
            impacts.append({
                "feature": name,
                "value":   round(current_val, 3),
                "impact":  round(impact, 1),
            })

        # Sort by absolute impact, return top N
        impacts.sort(key=lambda x: abs(x["impact"]), reverse=True)
        return impacts[:top_n]

    except Exception as exc:
        logger.debug("[EXPLAIN] compute_shap_top3 failed: %s", exc)
        return []
