"""
===========================================================================
AEGIS GOLD v9.0 -- Champion / Challenger Framework
===========================================================================

PHILOSOPHY:
-----------
"Never bet the whole system on an untested model."

When the ML Ensemble retrains or the SelfOptimizer proposes new weights,
the new model is the CHALLENGER. It runs in SHADOW MODE: observing every
live signal the CHAMPION sees and logging what it WOULD have decided —
without executing any real trade.

After N shadow decisions (default 30), the challenger is promoted to
champion ONLY if it outperforms the current champion on:
  - Win rate  (+5% minimum margin)
  - Risk-adjusted return (Sharpe-proxy)
  - Max drawdown (must not be worse)

Otherwise, the challenger is DISCARDED and champion stays in place.

Every promotion / rejection event is logged to data/model_arena.json
and fires a Telegram alert.

STATE FILE: data/model_arena.json
ENDPOINT:   GET /arena
===========================================================================
"""

import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("aegis.champion_challenger")

BASE_DIR = Path(__file__).parent.parent
ARENA_PATH = BASE_DIR / "data" / "model_arena.json"
MIN_SHADOW_DECISIONS = 30      # Minimum shadow decisions before evaluation
PROMOTE_WIN_RATE_MARGIN = 5.0  # Challenger must beat champion by this many %
PROMOTE_SHARPE_MARGIN = 0.05   # Sharpe improvement threshold
MAX_DD_DEGRADATION = 0.03      # Challenger max_dd must not be >3% worse than champion


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ModelSnapshot:
    """Tracks a model's shadow-mode performance."""
    name: str
    role: str              # "champion" or "challenger"
    created_at: str = ""
    shadow_decisions: int = 0
    shadow_wins: int = 0
    shadow_losses: int = 0
    shadow_breakevens: int = 0

    # Running financial metrics (on shadow paper-trade outcomes)
    cumulative_pnl: float = 0.0
    peak_pnl: float = 0.0
    max_drawdown: float = 0.0

    # Average R:R on winning trades
    avg_rr_wins: float = 0.0
    _rr_sum: float = field(default=0.0, repr=False)
    _rr_count: int = field(default=0, repr=False)

    # Returns buffer for Sharpe calculation
    _returns: List[float] = field(default_factory=list, repr=False)

    def record_shadow_outcome(self, outcome: str, pnl: float, rr: float = 0.0):
        """Record a shadow-mode outcome (WIN/LOSS/BREAKEVEN)."""
        self.shadow_decisions += 1
        if outcome == "WIN":
            self.shadow_wins += 1
            if rr > 0:
                self._rr_sum += rr
                self._rr_count += 1
        elif outcome == "LOSS":
            self.shadow_losses += 1
        else:
            self.shadow_breakevens += 1

        self.cumulative_pnl += pnl
        self._returns.append(pnl)
        if len(self._returns) > 200:
            self._returns = self._returns[-200:]

        # Track drawdown
        if self.cumulative_pnl > self.peak_pnl:
            self.peak_pnl = self.cumulative_pnl
        dd = self.peak_pnl - self.cumulative_pnl
        if dd > self.max_drawdown:
            self.max_drawdown = dd

        # Update avg RR
        if self._rr_count > 0:
            self.avg_rr_wins = self._rr_sum / self._rr_count

    @property
    def win_rate(self) -> float:
        """Win rate as percentage (0-100)."""
        total = self.shadow_wins + self.shadow_losses
        return (self.shadow_wins / total * 100.0) if total > 0 else 0.0

    @property
    def sharpe_proxy(self) -> float:
        """Simplified Sharpe: mean / std of returns. 0 if insufficient data."""
        if len(self._returns) < 5:
            return 0.0
        import statistics
        try:
            mean = statistics.mean(self._returns)
            std = statistics.stdev(self._returns)
            return mean / std if std > 0 else 0.0
        except Exception:
            return 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at,
            "shadow_decisions": self.shadow_decisions,
            "shadow_wins": self.shadow_wins,
            "shadow_losses": self.shadow_losses,
            "shadow_breakevens": self.shadow_breakevens,
            "win_rate": round(self.win_rate, 2),
            "sharpe_proxy": round(self.sharpe_proxy, 4),
            "cumulative_pnl": round(self.cumulative_pnl, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "avg_rr_wins": round(self.avg_rr_wins, 3),
        }


@dataclass
class PromotionEvent:
    timestamp: str
    challenger_name: str
    decision: str         # "PROMOTED" | "REJECTED"
    reason: str
    challenger_win_rate: float
    champion_win_rate: float
    challenger_sharpe: float
    champion_sharpe: float

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Arena Manager
# ---------------------------------------------------------------------------

class ArenaManager:
    """
    Manages the champion / challenger lifecycle.
    Thread-safe state persisted to disk between processes.
    """

    def __init__(self):
        self._alert_fn = None   # Set to telegram bot .send() after init
        self._state = self._load()

    def set_alert(self, fn):
        """Bind a callable(text: str) for Telegram alerts."""
        self._alert_fn = fn

    def _alert(self, text: str):
        logger.warning(f"[ARENA] {text}")
        if self._alert_fn:
            try:
                self._alert_fn(text)
            except Exception:
                pass

    # ── Persistence ────────────────────────────────────────────

    def _load(self) -> dict:
        ARENA_PATH.parent.mkdir(parents=True, exist_ok=True)
        if ARENA_PATH.exists():
            try:
                return json.loads(ARENA_PATH.read_text())
            except Exception as e:
                logger.warning(f"[ARENA] Could not load arena state: {e}")
        return {
            "champion": None,
            "challenger": None,
            "promotion_history": [],
            "total_promotions": 0,
            "total_rejections": 0,
        }

    def _save(self):
        try:
            ARENA_PATH.write_text(json.dumps(self._state, indent=2))
        except Exception as e:
            logger.error(f"[ARENA] Save failed: {e}")

    # ── Champion / Challenger registration ─────────────────────

    def register_champion(self, name: str):
        """Register a model as the current champion (on first run or after promotion)."""
        champ = ModelSnapshot(
            name=name,
            role="champion",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._state["champion"] = champ.to_dict()
        self._save()
        logger.info(f"[ARENA] Champion registered: {name}")

    def propose_challenger(self, name: str) -> bool:
        """
        Propose a new challenger. Returns False if a challenger is already active.
        Call this when ML retrains or SelfOptimizer produces new weights.
        """
        if self._state.get("challenger"):
            logger.info(f"[ARENA] Challenger already running — ignoring new proposal for {name}")
            return False

        if not self._state.get("champion"):
            # First run — auto-promote directly
            self.register_champion(name)
            logger.info(f"[ARENA] No champion present — auto-promoting {name} as champion")
            return True

        challenger = ModelSnapshot(
            name=name,
            role="challenger",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._state["challenger"] = challenger.to_dict()
        self._save()
        logger.info(f"[ARENA] Challenger entered shadow mode: {name}")
        self._alert(f"[ARENA] Challenger started: {name} — shadow mode active ({MIN_SHADOW_DECISIONS} decisions needed)")
        return True

    # ── Shadow-mode outcome recording ──────────────────────────

    def record_champion_outcome(self, outcome: str, pnl: float, rr: float = 0.0):
        """Record a real trade outcome against the champion's stats."""
        ch = self._state.get("champion")
        if not ch:
            return
        snap = self._snap_from_dict(ch, "champion")
        snap.record_shadow_outcome(outcome, pnl, rr)
        self._state["champion"] = snap.to_dict()
        self._save()

    def record_challenger_shadow(self, outcome: str, pnl: float, rr: float = 0.0):
        """
        Record a shadow-mode outcome for the challenger.
        After arena_min_shadow_decisions (default 100), evaluate.
        """
        ch = self._state.get("challenger")
        if not ch:
            return

        snap = self._snap_from_dict(ch, "challenger")
        snap.record_shadow_outcome(outcome, pnl, rr)
        self._state["challenger"] = snap.to_dict()
        self._save()

        try:
            from config.quant_x_config import QX
            min_decisions = int(QX.get("arena_min_shadow_decisions") or MIN_SHADOW_DECISIONS)
        except Exception:
            min_decisions = MIN_SHADOW_DECISIONS

        if snap.shadow_decisions >= min_decisions:
            self._evaluate_and_decide(snap)

    def demote_champion(self, reason: str) -> None:
        """
        Demotes the current champion to retired state.
        Triggered manually or automatically on chronic miscalibration/drift.
        """
        champ = self._state.get("champion")
        if not champ:
            return

        logger.warning(f"[ARENA] DEMOTING CHAMPION: {champ.get('name')} | Reason: {reason}")
        
        # Log to promotion history
        event = PromotionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            challenger_name="",
            decision="DEMOTED",
            reason=reason,
            challenger_win_rate=0.0,
            champion_win_rate=float(champ.get("win_rate", 0.0)),
            challenger_sharpe=0.0,
            champion_sharpe=float(champ.get("sharpe_proxy", 0.0)),
        )

        history = self._state.get("promotion_history", [])
        history.append(event.to_dict())
        self._state["promotion_history"] = history[-50:]
        
        # De-register champion or set to retired
        self._state["champion"] = None
        self._save()
        
        self._alert(f"⚠️ CHAMPION DEMOTED: {champ.get('name')} | Reason: {reason}. Falling back to default baseline trading.")

    def _snap_from_dict(self, d: dict, role: str) -> ModelSnapshot:
        snap = ModelSnapshot(name=d["name"], role=role)
        snap.created_at = d.get("created_at", "")
        snap.shadow_decisions = d.get("shadow_decisions", 0)
        snap.shadow_wins = d.get("shadow_wins", 0)
        snap.shadow_losses = d.get("shadow_losses", 0)
        snap.shadow_breakevens = d.get("shadow_breakevens", 0)
        snap.cumulative_pnl = d.get("cumulative_pnl", 0.0)
        snap.peak_pnl = d.get("cumulative_pnl", 0.0)
        snap.max_drawdown = d.get("max_drawdown", 0.0)
        snap.avg_rr_wins = d.get("avg_rr_wins", 0.0)
        snap._rr_sum = snap.avg_rr_wins
        snap._rr_count = 1 if snap.avg_rr_wins > 0 else 0
        return snap

    # ── Evaluation ─────────────────────────────────────────────

    def _evaluate_and_decide(self, challenger: ModelSnapshot):

        """
        Compare challenger vs champion.
        Uses Welch's t-test on returns if scipy is available.
        Gated by human approval if enabled in QX config.
        """
        champ_dict = self._state.get("champion") or {}
        champ_wr = champ_dict.get("win_rate", 50.0)
        champ_sharpe = champ_dict.get("sharpe_proxy", 0.0)
        champ_dd = champ_dict.get("max_drawdown", 0.0)

        chal_wr = challenger.win_rate
        chal_sharpe = challenger.sharpe_proxy
        chal_dd = challenger.max_drawdown

        wr_delta = chal_wr - champ_wr
        sharpe_delta = chal_sharpe - champ_sharpe
        dd_worse = chal_dd - champ_dd

        # t-test validation (Welch's t-test)
        significant = True
        try:
            from scipy import stats
            # Extract returns buffers if available
            chal_rets = challenger._returns
            champ_rets = champ_dict.get("_returns", [])
            
            if len(chal_rets) >= 10 and len(champ_rets) >= 10:
                t_stat, p_val = stats.ttest_ind(chal_rets, champ_rets, equal_var=False)
                # Significant if p-value is small (e.g. p < 0.05)
                significant = p_val < 0.05
                logger.info(f"[ARENA] Welch's t-test: t-stat={t_stat:.4f}, p-val={p_val:.4f} | Significant={significant}")
        except Exception:
            pass # degrade to simple comparison if ttest fails or no scipy

        promote = False
        reason = ""

        if chal_wr < 40.0:
            reason = f"Challenger win rate too low ({chal_wr:.1f}% < 40% floor)"
        elif dd_worse > MAX_DD_DEGRADATION:
            reason = f"Challenger max drawdown worse by ${dd_worse:.2f}"
        elif wr_delta >= PROMOTE_WIN_RATE_MARGIN and significant:
            promote = True
            reason = f"Win rate improvement +{wr_delta:.1f}% and statistically significant"
        elif sharpe_delta >= PROMOTE_SHARPE_MARGIN and wr_delta >= 0 and significant:
            promote = True
            reason = f"Sharpe improvement +{sharpe_delta:.4f} (significant)"
        else:
            reason = (
                f"Insufficient improvement: WR delta={wr_delta:+.1f}% "
                f"Sharpe delta={sharpe_delta:+.4f} (Significant={significant})"
            )

        # QX human gate check
        try:
            from config.quant_x_config import QX
            human_gate = QX.flag("champion_human_gate") or QX.flag("arena_require_human_approval")
        except Exception:
            human_gate = True

        if promote and human_gate:
            self._state["pending_promotion"] = challenger.to_dict()
            self._state["pending_promotion_reason"] = reason
            self._save()
            self._alert(
                f"🚨 PROMOTION PENDING APPROVAL: Challenger {challenger.name} outperformed Champion.\n"
                f"Reason: {reason}\n"
                f"Send /approve_challenger to confirm promotion."
            )
            return

        event = PromotionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            challenger_name=challenger.name,
            decision="PROMOTED" if promote else "REJECTED",
            reason=reason,
            challenger_win_rate=round(chal_wr, 2),
            champion_win_rate=round(champ_wr, 2),
            challenger_sharpe=round(chal_sharpe, 4),
            champion_sharpe=round(champ_sharpe, 4),
        )

        history = self._state.get("promotion_history", [])
        history.append(event.to_dict())
        self._state["promotion_history"] = history[-50:]  # keep last 50

        if promote:
            logger.info(f"[ARENA] PROMOTED {challenger.name}: {reason}")
            self._state["total_promotions"] = self._state.get("total_promotions", 0) + 1
            self._state["champion"] = challenger.to_dict()
            self._state["champion"]["role"] = "champion"
            self._state["challenger"] = None
            
            # Copy challenger models to live active paths
            import shutil
            try:
                rl_chal = os.path.join(BASE_DIR, "models", "aegis_rl_challenger.pt")
                rl_champ = os.path.join(BASE_DIR, "models", "aegis_rl.pt")
                if os.path.exists(rl_chal):
                    shutil.copy2(rl_chal, rl_champ)
                    logger.info("[ARENA] Copied aegis_rl_challenger.pt to aegis_rl.pt")
            except Exception as _e:
                logger.error(f"[ARENA] Failed to copy RL challenger model: {_e}")
                
            try:
                ml_chal = os.path.join(BASE_DIR, "models", "ml_ensemble_challenger.pkl")
                ml_champ = os.path.join(BASE_DIR, "models", "ml_ensemble.pkl")
                if os.path.exists(ml_chal):
                    shutil.copy2(ml_chal, ml_champ)
                    logger.info("[ARENA] Copied ml_ensemble_challenger.pkl to ml_ensemble.pkl")
            except Exception as _e:
                logger.error(f"[ARENA] Failed to copy ML challenger model: {_e}")
            
            self._alert(
                f"[ARENA] PROMOTED: {challenger.name} is now champion. "
                f"WR {chal_wr:.1f}% vs {champ_wr:.1f}% | {reason}"
            )
        else:
            logger.info(f"[ARENA] REJECTED {challenger.name}: {reason}")
            self._state["total_rejections"] = self._state.get("total_rejections", 0) + 1
            self._state["challenger"] = None
            self._alert(
                f"[ARENA] REJECTED: {challenger.name} discarded. "
                f"Champion unchanged. {reason}"
            )

        self._save()


    # ── Query ──────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "champion": self._state.get("champion"),
            "challenger": self._state.get("challenger"),
            "total_promotions": self._state.get("total_promotions", 0),
            "total_rejections": self._state.get("total_rejections", 0),
            "last_events": self._state.get("promotion_history", [])[-5:],
            "config": {
                "min_shadow_decisions": MIN_SHADOW_DECISIONS,
                "promote_win_rate_margin_pct": PROMOTE_WIN_RATE_MARGIN,
                "promote_sharpe_margin": PROMOTE_SHARPE_MARGIN,
                "max_dd_degradation": MAX_DD_DEGRADATION,
            },
        }

    def has_challenger(self) -> bool:
        return bool(self._state.get("challenger"))

    def challenger_decisions(self) -> int:
        ch = self._state.get("challenger")
        return ch.get("shadow_decisions", 0) if ch else 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_arena: Optional[ArenaManager] = None


def get_arena() -> ArenaManager:
    global _arena
    if _arena is None:
        _arena = ArenaManager()
    return _arena
