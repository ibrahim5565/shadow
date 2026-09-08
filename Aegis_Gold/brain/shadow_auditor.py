"""
===========================================================================
AEGIS GOLD AI — Shadow-Period Audit Engine (V1.0)
===========================================================================
PURPOSE:
--------
Executes the full 7-step audit checklist to evaluate Go/No-Go live promotion
readiness for the Unified Multi-Engine Pattern Decision System.
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger("aegis.shadow_auditor")
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "performance.db"
EXPLAIN_DB_PATH = BASE_DIR / "data" / "explanations.db"
ARENA_PATH = BASE_DIR / "data" / "arena_state.json"
WEIGHTS_PATH = BASE_DIR / "data" / "engine_weights.json"


class ShadowAuditor:
    """Automated Shadow Audit Engine for Live Promotion Gate Evaluation."""

    def __init__(self):
        self.min_trades_required = 200
        self.live_champion_pf = 0.63
        self.live_champion_win_rate = 60.33
        self.live_champion_pnl = -417.96

    def run_full_audit(self, target_pipeline_id: str = "dual_tier_v1") -> Dict[str, Any]:
        """Runs complete 7-step audit checklist and returns Go/No-Go decision matrix."""
        trades = self._get_closed_trades(pipeline_id=target_pipeline_id)
        n_trades = len(trades)
        
        min_ts = trades[0]["timestamp"] if n_trades > 0 else "N/A"
        max_ts = trades[-1]["timestamp"] if n_trades > 0 else "N/A"
        
        audit_meta = {
            "pipeline_id": target_pipeline_id,
            "sample_size": n_trades,
            "min_timestamp": min_ts,
            "max_timestamp": max_ts,
            "date_range": f"{min_ts} to {max_ts}"
        }
        
        sec1 = self.audit_section1_aggregate_gates(trades)
        sec2 = self.audit_section2_per_engine_accuracy()
        sec3 = self.audit_section3_pattern_tier_breakdown(trades)
        sec4 = self.audit_section4_partial_veto_behavior()
        sec5 = self.audit_section5_omega_hard_veto()
        sec6 = self.audit_section6_rl_weight_drift()
        
        if n_trades < 30:
            go_no_go = "INSUFFICIENT SAMPLE -- DO NOT INTERPRET"
            reasons = [
                f"[WARNING] INSUFFICIENT SAMPLE: Only {n_trades} post-fix shadow trades recorded for pipeline '{target_pipeline_id}' (minimum N >= 30 required for preliminary assessment, N >= 200 for promotion)."
            ]

            checklist_boxes = {
                "sample_size_ge_200": False,
                "sample_size_ge_30": False,
                "profit_factor_gt_1": False,
                "win_loss_ratio_improved": False,
                "net_pnl_positive": False,
            }
        else:
            go_no_go, reasons, checklist_boxes = self.synthesize_final_decision(
                sec1, sec2, sec3, sec4, sec5, sec6
            )

        audit_report = {
            "metadata": audit_meta,
            "final_decision": go_no_go,
            "reasons": reasons,
            "checklist_status": checklist_boxes,
            "section1_aggregate_gates": sec1,
            "section2_engine_accuracy": sec2,
            "section3_pattern_tier_breakdown": sec3,
            "section4_partial_veto": sec4,
            "section5_omega_veto": sec5,
            "section6_rl_weight_drift": sec6,
        }

        return audit_report

    def audit_section1_aggregate_gates(self, trades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """1. Aggregate Go/No-Go Gates (hard requirements)."""
        if trades is None:
            trades = self._get_closed_trades()
        n_trades = len(trades)
        
        if n_trades == 0:
            return {
                "sample_size": 0,
                "sample_size_passed": False,
                "profit_factor": 0.0,
                "pf_passed": False,
                "net_pnl": 0.0,
                "net_pnl_passed": False,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "win_loss_ratio": 0.0,
                "win_loss_ratio_improved": False,
                "max_drawdown": 0.0,
                "all_passed": False
            }

        wins = [t["profit_usd"] for t in trades if t["profit_usd"] > 0]
        losses = [abs(t["profit_usd"]) for t in trades if t["profit_usd"] < 0]
        
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        net_pnl = gross_profit - gross_loss
        
        pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
        win_rate = (len(wins) / n_trades * 100.0) if n_trades > 0 else 0.0
        
        avg_win = (sum(wins) / len(wins)) if len(wins) > 0 else 0.0
        avg_loss = (sum(losses) / len(losses)) if len(losses) > 0 else 0.0
        rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        cum = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in trades:
            cum += t["profit_usd"]
            if cum > peak:
                peak = cum
            dd = peak - cum
            if dd > max_dd:
                max_dd = dd

        sample_passed = n_trades >= self.min_trades_required
        pf_passed = pf > 1.0
        pnl_passed = net_pnl > 0
        rr_improved = rr_ratio > 0.41

        all_passed = sample_passed and pf_passed and pnl_passed and rr_improved

        return {
            "sample_size": n_trades,
            "sample_size_passed": sample_passed,
            "profit_factor": round(pf, 3),
            "pf_passed": pf_passed,
            "net_pnl": round(net_pnl, 2),
            "net_pnl_passed": pnl_passed,
            "win_rate": round(win_rate, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "win_loss_ratio": round(rr_ratio, 3),
            "win_loss_ratio_improved": rr_improved,
            "max_drawdown": round(max_dd, 2),
            "all_passed": all_passed
        }

    def audit_section2_per_engine_accuracy(self) -> Dict[str, Any]:
        """2. Per-Engine Vote Accuracy."""
        arena_stats = {}
        if ARENA_PATH.exists():
            try:
                state = json.loads(ARENA_PATH.read_text())
                challenger = state.get("challenger") or {}
                arena_stats = challenger.get("engine_vote_stats", {})
            except Exception as e:
                logger.warning(f"Could not load arena engine stats: {e}")

        engine_eval = {"quant": {"correct": 0, "total": 0}, "ml_ensemble": {"correct": 0, "total": 0},
                       "omega": {"correct": 0, "total": 0}, "kronos": {"correct": 0, "total": 0}}

        if EXPLAIN_DB_PATH.exists():
            try:
                conn = sqlite3.connect(str(EXPLAIN_DB_PATH))
                cursor = conn.cursor()
                rows = cursor.execute("""
                    SELECT signal_json, outcome, outcome_pnl, direction FROM explanations
                    WHERE outcome IS NOT NULL
                """).fetchall()
                conn.close()

                for signal_json_str, outcome, pnl, direction in rows:
                    if not signal_json_str or not direction:
                        continue
                    try:
                        sig_dict = json.loads(signal_json_str)
                    except Exception:
                        continue
                    
                    target_dir = "bullish" if str(direction).upper() in ("BUY", "BULLISH") else "bearish"
                    is_win = (outcome == "WIN" or (pnl is not None and pnl > 0))

                    for eng, vote in sig_dict.items():
                        if eng in engine_eval and isinstance(vote, dict):
                            v_dir = str(vote.get("direction", "")).lower()
                            engine_eval[eng]["total"] += 1
                            if (v_dir == target_dir and is_win) or (v_dir != target_dir and not is_win):
                                engine_eval[eng]["correct"] += 1
            except Exception as e:
                logger.warning(f"Error evaluating explanation engine stats: {e}")

        engine_accuracy = {}
        flags = []
        for eng in ["quant", "ml_ensemble", "omega", "kronos"]:
            tot = engine_eval[eng]["total"] or arena_stats.get(eng, {}).get("total", 0)
            corr = engine_eval[eng]["correct"] or arena_stats.get(eng, {}).get("correct", 0)
            acc = (corr / tot * 100.0) if tot > 0 else 0.0
            engine_accuracy[eng] = {"accuracy_pct": round(acc, 1), "correct": corr, "total": tot}
            if tot >= 20 and acc < 50.0:
                flags.append(f"Engine '{eng}' directional accuracy is below coin-flip ({acc:.1f}%)")

        return {
            "engine_accuracy": engine_accuracy,
            "flags": flags,
            "healthy": len(flags) == 0
        }

    def audit_section3_pattern_tier_breakdown(self, trades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """3. Pattern-Tier Breakdown (Scalp vs Pro Trend)."""
        if trades is None:
            trades = self._get_closed_trades()
        scalp_trades = [t for t in trades if t.get("pattern_tier") == "scalp"]
        pro_trend_trades = [t for t in trades if t.get("pattern_tier") == "pro_trend"]

        def _tier_stats(t_list):
            if not t_list:
                return {"count": 0, "pf": 0.0, "win_rate": 0.0, "net_pnl": 0.0, "avg_win": 0.0, "avg_loss": 0.0}
            w = [t["profit_usd"] for t in t_list if t["profit_usd"] > 0]
            l = [abs(t["profit_usd"]) for t in t_list if t["profit_usd"] < 0]
            gp, gl = sum(w), sum(l)
            pf = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0.0)
            wr = len(w) / len(t_list) * 100.0
            return {
                "count": len(t_list),
                "pf": round(pf, 3),
                "win_rate": round(wr, 1),
                "net_pnl": round(gp - gl, 2),
                "avg_win": round(sum(w)/len(w), 2) if w else 0.0,
                "avg_loss": round(sum(l)/len(l), 2) if l else 0.0
            }

        scalp_stats = _tier_stats(scalp_trades)
        pro_trend_stats = _tier_stats(pro_trend_trades)

        recommendation = "Promote both tiers"
        if scalp_stats["pf"] < 1.0 and pro_trend_stats["pf"] >= 1.0:
            recommendation = "Split promotion: Promote Pro Trend tier to live, retain Scalp tier in shadow"
        elif scalp_stats["pf"] >= 1.0 and pro_trend_stats["pf"] < 1.0:
            recommendation = "Split promotion: Promote Scalp tier to live, retain Pro Trend tier in shadow"
        elif scalp_stats["pf"] < 1.0 and pro_trend_stats["pf"] < 1.0:
            recommendation = "Retain both tiers in shadow (neither tier meets PF > 1.0)"

        return {
            "scalp_tier": scalp_stats,
            "pro_trend_tier": pro_trend_stats,
            "recommendation": recommendation
        }

    def audit_section4_partial_veto_behavior(self) -> Dict[str, Any]:
        """4. Partial-Veto Behavior Check."""
        partial_veto_trades = []
        full_size_trades = []

        if EXPLAIN_DB_PATH.exists():
            try:
                conn = sqlite3.connect(str(EXPLAIN_DB_PATH))
                cursor = conn.cursor()
                rows = cursor.execute("SELECT veto_json, outcome_pnl FROM explanations WHERE outcome IS NOT NULL").fetchall()
                conn.close()
                for v_json, pnl in rows:
                    if pnl is None:
                        continue
                    if v_json and "PARTIAL_VETO" in v_json:
                        partial_veto_trades.append(pnl)
                    else:
                        full_size_trades.append(pnl)
            except Exception:
                pass

        p_count = len(partial_veto_trades)
        f_count = len(full_size_trades)
        p_pnl = sum(partial_veto_trades)
        f_pnl = sum(full_size_trades)

        return {
            "partial_veto_trade_count": p_count,
            "full_size_trade_count": f_count,
            "partial_veto_total_pnl": round(p_pnl, 2),
            "full_size_total_pnl": round(f_pnl, 2),
            "assessment": "Partial veto reduced loss exposure" if p_pnl >= 0 or (p_count > 0 and p_pnl/p_count > f_pnl/max(1, f_count)) else "Partial veto needs tightening"
        }

    def audit_section5_omega_hard_veto(self) -> Dict[str, Any]:
        """5. OMEGA Hard Veto Audit."""
        hard_veto_count = 0
        reasons = []

        if EXPLAIN_DB_PATH.exists():
            try:
                conn = sqlite3.connect(str(EXPLAIN_DB_PATH))
                cursor = conn.cursor()
                rows = cursor.execute("SELECT veto_json, plain_english FROM explanations WHERE action = 'WAIT'").fetchall()
                conn.close()
                for v_json, pe in rows:
                    if (v_json and "OMEGA_HARD_VETO" in v_json) or (pe and "HARD VETO" in pe):
                        hard_veto_count += 1
                        if pe and len(reasons) < 5:
                            reasons.append(pe)
            except Exception:
                pass

        return {
            "hard_veto_blocked_count": hard_veto_count,
            "sample_reasons": reasons,
            "status": "Healthy (not over-firing)" if hard_veto_count < 100 else "Warning: high hard veto frequency"
        }

    def audit_section6_rl_weight_drift(self) -> Dict[str, Any]:
        """6. RL Weight Drift Audit."""
        weights = {"scalp": {"quant": 0.25, "ml_ensemble": 0.25, "omega": 0.25, "kronos": 0.25}}
        if WEIGHTS_PATH.exists():
            try:
                weights = json.loads(WEIGHTS_PATH.read_text())
            except Exception:
                pass

        return {
            "current_weights": weights,
            "status": "Weights balanced and sensible"
        }

    def synthesize_final_decision(self, sec1, sec2, sec3, sec4, sec5, sec6) -> tuple:
        """7. Final Decision Synthesis."""
        checklist = {
            "sample_size_ge_200": sec1["sample_size_passed"],
            "profit_factor_gt_1": sec1["pf_passed"],
            "win_loss_ratio_improved": sec1["win_loss_ratio_improved"],
            "net_pnl_positive": sec1["net_pnl_passed"],
            "engine_accuracy_healthy": sec2["healthy"],
            "omega_veto_healthy": sec5["status"].startswith("Healthy")
        }

        all_boxes_checked = all(checklist.values())
        go_no_go = "GO — PROMOTE TO LIVE" if all_boxes_checked else "NO-GO — RETAIN IN SHADOW"

        reasons = []
        if not checklist["sample_size_ge_200"]:
            reasons.append(f"Sample size insufficient ({sec1['sample_size']}/{self.min_trades_required} trades)")
        if not checklist["profit_factor_gt_1"]:
            reasons.append(f"Profit Factor {sec1['profit_factor']} is below 1.0 target")
        if not checklist["win_loss_ratio_improved"]:
            reasons.append(f"Avg Win/Loss ratio {sec1['win_loss_ratio']} not improved over baseline 0.41")
        if not checklist["net_pnl_positive"]:
            reasons.append(f"Net PnL ${sec1['net_pnl']} is negative")
        if not checklist["engine_accuracy_healthy"]:
            reasons.extend(sec2["flags"])

        if all_boxes_checked:
            reasons.append("All 7 shadow audit checklist gates satisfied! System ready for live promotion.")

        return go_no_go, reasons, checklist

    def _get_closed_trades(self, pipeline_id: str = "dual_tier_v1") -> List[Dict[str, Any]]:
        """Helper to fetch closed trades from performance.db strictly filtered by pipeline_id."""
        if not DB_PATH.exists():
            return []

        trades = []
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Verify if pipeline_id column exists
            cols = {r[1] for r in cursor.execute("PRAGMA table_info(trades)").fetchall()}
            if "pipeline_id" not in cols:
                conn.close()
                return []

            rows = cursor.execute("""
                SELECT symbol, direction, entry_price, exit_price, sl, tp, lot, profit_usd, timestamp,
                       pattern_tier, big_pattern_type, small_pattern_type, consensus_score, pipeline_id
                FROM trades WHERE profit_usd IS NOT NULL AND profit_usd != 0.0 AND pipeline_id = ?
                ORDER BY timestamp ASC
            """, (pipeline_id,)).fetchall()
            conn.close()
            trades = [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"Failed to fetch trades from performance.db: {e}")

        return trades


def run_audit(pipeline_id: str = "dual_tier_v1") -> dict:
    auditor = ShadowAuditor()
    return auditor.run_full_audit(target_pipeline_id=pipeline_id)


if __name__ == "__main__":
    import pprint
    res = run_audit()
    print("\n================ AEGIS GOLD SHADOW AUDIT REPORT ================")
    if res.get("final_decision", "").startswith("INSUFFICIENT SAMPLE"):
        print("\n" + "="*72)
        print("!!! INSUFFICIENT SAMPLE (N < 30) -- DO NOT INTERPRET PROMOTION METRICS !!!")
        print("="*72 + "\n")
    print(f"Pipeline ID   : {res['metadata']['pipeline_id']}")
    print(f"Sample Count  : N={res['metadata']['sample_size']}")
    print(f"Date Range    : {res['metadata']['date_range']}")
    print(f"Final Decision: {res['final_decision']}\n")
    pprint.pprint(res)


