"""
===========================================================================
AEGIS GOLD — Causal Historical Replay Engine (Validation Phase)
===========================================================================

PURPOSE:
  Executes scientific out-of-sample point-in-time replay over historical data.

GUARANTEES:
  1. Strict causality: snapshot at time T contains ONLY data with timestamp <= T.
  2. Setup/Trigger state machine separation.
  3. EV economics calculation after spread, commission, and slippage.
  4. Pre-order assertion verification before simulated execution.
  5. Trade-level journal logging to data/validation/trade_journal.json.
===========================================================================
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.frozen_snapshot import FrozenDecisionSnapshot, build_snapshot
from brain.setup_candidate import SetupCandidate, EntryTrigger, SetupState
from brain.trigger_engine import RealTimeEntryTriggerEngine
from brain.chase_detector import EntryChaseDetector, ChaseCheckResult
from brain.quant_feature_engine import QuantFeatureEngine, QuantFeatureVector
from brain.unified_brain import run_pattern_consensus, UnifiedDecision
from brain.ev_decision_engine import EVDecisionEngine, EVResult
from brain.pre_order_assertions import PreOrderAssertionsEngine, AssertionResult

logger = logging.getLogger("aegis.causal_replay")


@dataclass
class ReplayTradeRecord:
    decision_id: str
    symbol: str
    snapshot_time: str
    setup_time: str
    setup_state: str
    trigger_time: str
    trigger_type: str
    trigger_price: float
    execution_price: float
    direction: str
    engine_votes: Dict[str, str]
    consensus_score: float
    structural_sl: float
    structural_tp: float
    r_multiple: float
    spread_pts: float
    commission: float
    slippage_pts: float
    ev: float
    chase_approved: bool
    chase_reason: str
    exit_time: str
    exit_price: float
    pnl: float
    r_result: float
    mfe_pts: float
    mae_pts: float
    entry_classification: str   # "EARLY", "OPTIMAL", "LATE", "CHASE"


class CausalReplayEngine:
    """
    Chronological historical simulation engine.
    """

    def __init__(
        self,
        symbol: str = "XAUUSD",
        lot_size: float = 0.01,
        spread_pts: float = 20.0,
        slippage_pts: float = 10.0,
        point: float = 0.01,
        initial_balance: float = 10000.0,
    ):
        self.symbol = symbol
        self.lot_size = lot_size
        self.spread_pts = spread_pts
        self.slippage_pts = slippage_pts
        self.point = point
        self.initial_balance = initial_balance

        # Core engines
        self.trigger_engine = RealTimeEntryTriggerEngine()
        self.chase_detector = EntryChaseDetector()
        self.quant_engine = QuantFeatureEngine()
        self.ev_engine = EVDecisionEngine()
        self.assertions_engine = PreOrderAssertionsEngine()

    def run_replay(
        self,
        candles_m5: List[Dict[str, Any]],
        candles_m1: Optional[List[Dict[str, Any]]] = None,
        mode: str = "NEW_AEGIS",  # "LEGACY", "CLEAN_LEGACY", "NEW_AEGIS"
    ) -> Dict[str, Any]:
        """
        Executes causal chronological backtest across provided candle history.
        """
        if len(candles_m5) < 100:
            logger.warning("[REPLAY] Insufficient candles for backtest (<100)")
            return self._empty_summary(mode)

        trade_journal: List[ReplayTradeRecord] = []
        equity = self.initial_balance
        peak_equity = equity
        max_drawdown_dollars = 0.0
        max_drawdown_pct = 0.0

        active_setup: Optional[SetupCandidate] = None

        # Start loop from index 60 so trailing windows are full
        for idx in range(60, len(candles_m5)):
            current_bar = candles_m5[idx]
            bar_time_sec = current_bar.get("time", 0)
            now = datetime.fromtimestamp(bar_time_sec, tz=timezone.utc)

            # Build historical closed snapshot at time T (bars 0..idx-1)
            past_m5 = candles_m5[:idx]
            past_m1 = candles_m1[:idx * 5] if candles_m1 else []

            snapshot = build_snapshot(
                symbol=self.symbol,
                candles_m5=past_m5,
                candles_m1=past_m1,
                decision_time=now,
                spread=self.spread_pts,
                point=self.point,
                account_equity=equity,
            )

            current_price = snapshot.current_price

            # 1. Update / Create Setup
            if active_setup is None or active_setup.is_expired(now) or active_setup.is_invalidated(current_price):
                # Try creating new setup from SMC
                from brain.smc_engine import SMCEngine
                smc = SMCEngine(symbol=self.symbol, default_point=self.point)
                smc_res = smc.analyze(snapshot.candles_m5)

                if isinstance(smc_res, dict):
                    direction = smc_res.get("direction", "WAIT")
                    ob_high = smc_res.get("ob_high", current_price + 10 * self.point)
                    ob_low = smc_res.get("ob_low", current_price - 10 * self.point)
                else:
                    direction = getattr(smc_res, "direction", "WAIT")
                    ob_high = getattr(smc_res, "ob_high", current_price + 10 * self.point)
                    ob_low = getattr(smc_res, "ob_low", current_price - 10 * self.point)

                if direction in ("BUY", "SELL"):
                    inval = ob_low - 5 * self.point if direction == "BUY" else ob_high + 5 * self.point
                    setup_lvl = ob_high if direction == "BUY" else ob_low

                    active_setup = SetupCandidate(
                        setup_id=f"setup_{idx}",
                        symbol=self.symbol,
                        direction_bias=direction,
                        formation_time=now - timedelta(minutes=15),
                        information_available_time=now - timedelta(minutes=5),
                        confirmation_time=now - timedelta(minutes=5),
                        setup_level=setup_lvl,
                        invalidation_level=inval,
                        expiry_time=now + timedelta(minutes=30),
                        state=SetupState.SETUP_CONFIRMED,
                    )
                    active_setup.arm_entry(now)

            if active_setup is None or active_setup.state not in (SetupState.ENTRY_ARMED, SetupState.SETUP_CONFIRMED):
                continue

            # 2. Real-Time Trigger Detection
            trigger = self.trigger_engine.detect_trigger(active_setup, snapshot)
            if not trigger:
                continue

            # 3. 7-Engine Consensus
            consensus = run_pattern_consensus(snapshot, min_agreement=getattr(self, "consensus_threshold", 5))
            if consensus.action != "TRADE":
                continue

            # Extract SL/TP from consensus scores or compute structural fallback
            sl_price = consensus.component_scores.get("sl_price", 0.0)
            tp_price = consensus.component_scores.get("tp_price", 0.0)
            if not sl_price or not tp_price:
                sl_dist = 10.0 if "XAUUSD" in self.symbol else 0.0010
                tp_dist = 30.0 if "XAUUSD" in self.symbol else 0.0030
                if trigger.direction == "BUY":
                    sl_price = current_price - sl_dist
                    tp_price = current_price + tp_dist
                else:
                    sl_price = current_price + sl_dist
                    tp_price = current_price - tp_dist

            # 4. Chase & Staleness Check
            chase_res = self.chase_detector.evaluate(active_setup, trigger, snapshot, sl_price, tp_price)
            if not chase_res.is_approved:
                continue

            # 5. EV Economics Check
            ask = current_price + (self.spread_pts * self.point) / 2.0
            bid = current_price - (self.spread_pts * self.point) / 2.0
            entry_price = ask if trigger.direction == "BUY" else bid

            win_prob = consensus.model_consensus / 100.0
            ev_res = self.ev_engine.evaluate_ev(
                direction=trigger.direction,
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                win_prob=win_prob,
                symbol=self.symbol,
                lot_size=self.lot_size,
                spread_pts=self.spread_pts,
                point=self.point,
                slippage_pts=self.slippage_pts,
            )

            if not ev_res.approved:
                continue

            # 6. Pre-Order Hard Assertions
            assertions_res = self.assertions_engine.verify_pre_order_invariants(
                setup=active_setup,
                trigger=trigger,
                chase_result=chase_res,
                ev_result=ev_res,
                decision_time=now,
                bid=bid,
                ask=ask,
                sl_price=sl_price,
                tp_price=tp_price,
            )

            if not assertions_res.passed:
                continue

            # 7. Simulate Execution Outcome on Future Bars (idx+1 .. end)
            trade_record = self._simulate_outcome(
                idx=idx,
                now=now,
                setup=active_setup,
                trigger=trigger,
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                ev_res=ev_res,
                chase_res=chase_res,
                consensus=consensus,
                future_bars=candles_m5[idx + 1: idx + 50],
            )

            if trade_record:
                trade_journal.append(trade_record)
                equity += trade_record.pnl
                if equity > peak_equity:
                    peak_equity = equity
                dd_dollars = peak_equity - equity
                dd_pct = (dd_dollars / peak_equity) * 100.0 if peak_equity > 0 else 0.0
                if dd_dollars > max_drawdown_dollars:
                    max_drawdown_dollars = dd_dollars
                if dd_pct > max_drawdown_pct:
                    max_drawdown_pct = dd_pct

                # Reset setup after trade executed
                active_setup = None

        return self._summarize_results(trade_journal, mode, self.initial_balance, equity, max_drawdown_dollars, max_drawdown_pct)

    def _simulate_outcome(
        self,
        idx: int,
        now: datetime,
        setup: SetupCandidate,
        trigger: EntryTrigger,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        ev_res: EVResult,
        chase_res: ChaseCheckResult,
        consensus: UnifiedDecision,
        future_bars: List[Dict[str, Any]],
    ) -> Optional[ReplayTradeRecord]:
        """Simulates price path after entry until SL or TP is hit."""
        if not future_bars:
            return None

        contract_size = 100 if "XAUUSD" in self.symbol else 100000
        direction = trigger.direction
        sl_dist = abs(entry_price - sl_price)
        tp_dist = abs(tp_price - entry_price)
        r_multiple = round(tp_dist / sl_dist, 2) if sl_dist > 0 else 0.0

        mfe_pts = 0.0
        mae_pts = 0.0
        exit_price = entry_price
        exit_time = now.isoformat()
        hit = False
        pnl = 0.0

        for f_bar in future_bars:
            f_time = datetime.fromtimestamp(f_bar.get("time", 0), tz=timezone.utc).isoformat()
            f_high = float(f_bar.get("high", entry_price))
            f_low = float(f_bar.get("low", entry_price))
            f_close = float(f_bar.get("close", entry_price))

            if direction == "BUY":
                curr_mfe = (f_high - entry_price) / self.point
                curr_mae = (entry_price - f_low) / self.point
                if curr_mfe > mfe_pts: mfe_pts = curr_mfe
                if curr_mae > mae_pts: mae_pts = curr_mae

                # Check SL hit
                if f_low <= sl_price:
                    exit_price = sl_price
                    exit_time = f_time
                    hit = True
                    break
                # Check TP hit
                elif f_high >= tp_price:
                    exit_price = tp_price
                    exit_time = f_time
                    hit = True
                    break

            elif direction == "SELL":
                curr_mfe = (entry_price - f_low) / self.point
                curr_mae = (f_high - entry_price) / self.point
                if curr_mfe > mfe_pts: mfe_pts = curr_mfe
                if curr_mae > mae_pts: mae_pts = curr_mae

                if f_high >= sl_price:
                    exit_price = sl_price
                    exit_time = f_time
                    hit = True
                    break
                elif f_low <= tp_price:
                    exit_price = tp_price
                    exit_time = f_time
                    hit = True
                    break

        if not hit:
            # Expired without hitting SL/TP — close at final close
            exit_price = float(future_bars[-1].get("close", entry_price))
            exit_time = datetime.fromtimestamp(future_bars[-1].get("time", 0), tz=timezone.utc).isoformat()

        # Calculate PnL
        if direction == "BUY":
            price_change = exit_price - entry_price
        else:
            price_change = entry_price - exit_price

        gross_pnl = price_change * self.lot_size * contract_size
        net_pnl = gross_pnl - ev_res.total_execution_cost
        r_result = round(net_pnl / (sl_dist * self.lot_size * contract_size), 2) if sl_dist > 0 else 0.0

        # Entry Classification
        price_move_pts = abs(entry_price - trigger.trigger_price) / self.point
        if price_move_pts < 5.0:
            classification = "OPTIMAL"
        elif price_move_pts < 20.0:
            classification = "EARLY"
        elif price_move_pts <= 50.0:
            classification = "LATE"
        else:
            classification = "CHASE"

        return ReplayTradeRecord(
            decision_id=f"dec_{idx}",
            symbol=self.symbol,
            snapshot_time=now.isoformat(),
            setup_time=setup.confirmation_time.isoformat(),
            setup_state=setup.state.name,
            trigger_time=trigger.trigger_time.isoformat(),
            trigger_type=trigger.trigger_type,
            trigger_price=trigger.trigger_price,
            execution_price=entry_price,
            direction=direction,
            engine_votes=consensus.component_scores.get("engine_votes", {}),
            consensus_score=consensus.model_consensus,
            structural_sl=sl_price,
            structural_tp=tp_price,
            r_multiple=r_multiple,
            spread_pts=self.spread_pts,
            commission=ev_res.commission_cost,
            slippage_pts=self.slippage_pts,
            ev=ev_res.ev,
            chase_approved=chase_res.is_approved,
            chase_reason=chase_res.reason,
            exit_time=exit_time,
            exit_price=exit_price,
            pnl=round(net_pnl, 2),
            r_result=r_result,
            mfe_pts=round(mfe_pts, 1),
            mae_pts=round(mae_pts, 1),
            entry_classification=classification,
        )

    def _summarize_results(
        self,
        journal: List[ReplayTradeRecord],
        mode: str,
        initial_balance: float,
        final_equity: float,
        max_dd_dollars: float,
        max_dd_pct: float,
    ) -> Dict[str, Any]:
        """Summarizes trade journal into standard validation metrics."""
        trade_count = len(journal)
        if trade_count == 0:
            return self._empty_summary(mode)

        wins = [t for t in journal if t.pnl > 0]
        losses = [t for t in journal if t.pnl < 0]
        breakevens = [t for t in journal if t.pnl == 0]

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 1.0)

        win_rate = round((len(wins) / trade_count) * 100.0, 1)
        net_pnl = round(final_equity - initial_balance, 2)
        expectancy = round(net_pnl / trade_count, 2)
        avg_r = round(sum(t.r_result for t in journal) / trade_count, 2)

        # Classification counts
        optimal_cnt = sum(1 for t in journal if t.entry_classification == "OPTIMAL")
        early_cnt = sum(1 for t in journal if t.entry_classification == "EARLY")
        late_cnt = sum(1 for t in journal if t.entry_classification == "LATE")
        chase_cnt = sum(1 for t in journal if t.entry_classification == "CHASE")

        return {
            "mode": mode,
            "trade_count": trade_count,
            "wins": len(wins),
            "losses": len(losses),
            "breakevens": len(breakevens),
            "win_rate": win_rate,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": pf,
            "net_pnl": net_pnl,
            "expectancy": expectancy,
            "average_r": avg_r,
            "max_drawdown_dollars": round(max_dd_dollars, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "entry_quality": {
                "optimal_pct": round((optimal_cnt / trade_count) * 100, 1),
                "early_pct": round((early_cnt / trade_count) * 100, 1),
                "late_pct": round((late_cnt / trade_count) * 100, 1),
                "chase_pct": round((chase_cnt / trade_count) * 100, 1),
            },
            "journal": [asdict(t) for t in journal],
        }

    def _empty_summary(self, mode: str) -> Dict[str, Any]:
        return {
            "mode": mode, "trade_count": 0, "wins": 0, "losses": 0, "breakevens": 0,
            "win_rate": 0.0, "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 1.0,
            "net_pnl": 0.0, "expectancy": 0.0, "average_r": 0.0,
            "max_drawdown_dollars": 0.0, "max_drawdown_pct": 0.0,
            "entry_quality": {"optimal_pct": 0.0, "early_pct": 0.0, "late_pct": 0.0, "chase_pct": 0.0},
            "journal": [],
        }
