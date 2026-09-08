"""
===========================================================================
Shadow Run Report -- Challenger vs Champion Comparison
===========================================================================

PURPOSE:
--------
Reads data/model_arena.json and data/challenger_decisions_by_ticket.json
to print a live comparison of:
  1. Champion vs Challenger: WR, PF, Sharpe, max_dd
  2. BUY vs SELL trade frequency split (direction balance check)
  3. OVERLAP session trade counts (OVERLAP gate effectiveness check)
  4. OMEGA threshold sensitivity: overall trade volume before/after fix

USAGE:
------
  .venv_cuda\\Scripts\\python.exe scripts/shadow_run_report.py

Recommended: Run after every 50+ closed trades during shadow period.
===========================================================================
"""

import json
import os
import sys
# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent
ARENA_PATH    = BASE_DIR / "data" / "model_arena.json"
SHADOW_PATH   = BASE_DIR / "data" / "challenger_shadow_decisions.json"
TICKETS_PATH  = BASE_DIR / "data" / "challenger_decisions_by_ticket.json"
SEP = "─" * 70


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"  ⚠  Could not load {path.name}: {e}")
        return {}


def pf_str(pf: float) -> str:
    if pf == float("inf"):
        return "∞ (no losses yet)"
    return f"{pf:.3f}"


def print_model_block(label: str, m: dict):
    if not m:
        print(f"  {label}: NOT REGISTERED YET")
        return
    wr   = m.get("win_rate", 0.0)
    wins = m.get("shadow_wins", 0)
    losses = m.get("shadow_losses", 0)
    bes  = m.get("shadow_breakevens", 0)
    pf_val = m.get("profit_factor", 0.0) or 0.0
    sharpe = m.get("sharpe_proxy", 0.0) or 0.0
    dd   = m.get("max_drawdown", 0.0)
    pnl  = m.get("cumulative_pnl", 0.0)
    total = wins + losses
    print(f"  {label}:  {m.get('name', '?')}")
    print(f"    WR:          {wr:.1f}%  ({wins}W / {losses}L / {bes}BE | {total} rated trades)")
    print(f"    PF:          {pf_str(pf_val)}")
    print(f"    Sharpe:      {sharpe:.4f}")
    print(f"    Max DD:      ${dd:.2f}")
    print(f"    Cum PnL:     ${pnl:+.2f}")


def direction_split(tickets: dict):
    """Extract BUY/SELL balance from challenger_shadow_decisions.json records."""
    shadow = load_json(SHADOW_PATH)
    directions = []
    sessions = []
    for sym_data in shadow.values():
        if isinstance(sym_data, dict):
            directions.append(sym_data.get("direction", "UNKNOWN"))
            sessions.append(sym_data.get("session", "UNKNOWN"))
    return directions, sessions


def main():
    print()
    print("=" * 70)
    print("  AEGIS GOLD — Shadow Run Report")
    print(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    arena = load_json(ARENA_PATH)
    champion   = arena.get("champion") or {}
    challenger = arena.get("challenger") or {}
    history    = arena.get("promotion_history", [])

    # ── MODEL PERFORMANCE ─────────────────────────────────────────────────
    print()
    print(SEP)
    print("  MODEL PERFORMANCE COMPARISON")
    print(SEP)
    print_model_block("CHAMPION  ", champion)
    print()
    print_model_block("CHALLENGER", challenger)

    chal_decisions = challenger.get("shadow_decisions", 0)
    from_config = 200  # MIN_SHADOW_DECISIONS default
    remaining   = max(0, from_config - chal_decisions)
    print()
    print(f"  Shadow progress: {chal_decisions}/{from_config} decisions "
          f"({remaining} remaining before promotion evaluation)")
    if remaining == 0:
        print("  ✅ READY FOR PROMOTION EVALUATION")
    else:
        pct = chal_decisions / from_config * 100
        bar_len = int(pct / 2)
        bar = "█" * bar_len + "░" * (50 - bar_len)
        print(f"  Progress: [{bar}] {pct:.0f}%")

    # ── BUY/SELL DIRECTION BALANCE ────────────────────────────────────────
    print()
    print(SEP)
    print("  DIRECTION BALANCE CHECK (post-fix BUY-only bug)")
    print(SEP)

    directions, sessions = direction_split(load_json(TICKETS_PATH))
    if not directions:
        # Fall back to shadow_decisions.json
        shadow = load_json(SHADOW_PATH)
        directions = [v.get("direction", "?") for v in shadow.values() if isinstance(v, dict)]
        sessions   = [v.get("session", "?")   for v in shadow.values() if isinstance(v, dict)]

    if directions:
        dir_counts = Counter(directions)
        total_dir  = sum(dir_counts.values())
        buy_pct  = dir_counts.get("BUY",  0) / total_dir * 100 if total_dir else 0
        sell_pct = dir_counts.get("SELL", 0) / total_dir * 100 if total_dir else 0
        hold_pct = dir_counts.get("HOLD", 0) / total_dir * 100 if total_dir else 0

        print(f"  BUY:   {dir_counts.get('BUY', 0):4d} signals  ({buy_pct:.1f}%)")
        print(f"  SELL:  {dir_counts.get('SELL', 0):4d} signals  ({sell_pct:.1f}%)")
        print(f"  HOLD:  {dir_counts.get('HOLD', 0):4d} signals  ({hold_pct:.1f}%)")
        print()
        if sell_pct < 5.0 and total_dir > 10:
            print("  ⚠️  WARNING: SELL signals still very rare — possible residual BUY bias.")
        elif sell_pct > 15.0:
            print("  ✅ Direction balance looks reasonable (SELL > 15%).")
        else:
            print(f"  ℹ  SELL at {sell_pct:.1f}% — watch for next 20 trades to confirm improvement.")
    else:
        print("  ℹ  No shadow decisions recorded yet — data accumulates as trades execute.")

    # ── SESSION DISTRIBUTION ─────────────────────────────────────────────
    print()
    print(SEP)
    print("  SESSION DISTRIBUTION (OVERLAP gate effectiveness)")
    print(SEP)
    if sessions:
        sess_counts = Counter(sessions)
        total_s = sum(sess_counts.values())
        for sess in ["LONDON", "NY", "OVERLAP", "ASIAN"]:
            cnt = sess_counts.get(sess, 0)
            pct = cnt / total_s * 100 if total_s else 0
            bar = "█" * int(pct / 2)
            note = "  ← OVERLAP trades (should be low-volume, SMC/pro_trend only)" if sess == "OVERLAP" else ""
            print(f"  {sess:<8}: {cnt:4d} ({pct:5.1f}%)  {bar}{note}")
    else:
        print("  ℹ  No session data yet.")

    # ── PROMOTION HISTORY ─────────────────────────────────────────────────
    if history:
        print()
        print(SEP)
        print("  RECENT PROMOTION EVENTS (last 3)")
        print(SEP)
        for ev in history[-3:]:
            ts  = ev.get("timestamp", "")[:10]
            dec = ev.get("decision", "?")
            nm  = ev.get("challenger_name", "?")
            rsn = ev.get("reason", "")[:80]
            icon = "✅" if dec == "PROMOTED" else "❌"
            print(f"  {icon} [{ts}] {dec} — {nm}")
            print(f"       Reason: {rsn}")

    # ── MODE PERFORMANCE BREAKOUT ─────────────────────────────────────────
    print()
    print(SEP)
    print("  PER-MODE PERFORMANCE BREAKOUT (Scalp vs Small Pattern vs Big Pattern)")
    print(SEP)
    try:
        import sqlite3
        perf_db = BASE_DIR / "data" / "performance.db"
        if perf_db.exists():
            conn = sqlite3.connect(perf_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attributions';")
            if cursor.fetchone():
                import pandas as pd
                df_attr = pd.read_sql_query("SELECT * FROM attributions", conn)
                if not df_attr.empty:
                    # Tag mode: check pattern_tier or signal_source or mode
                    def _assign_mode(row):
                        st = str(row.get('signal_source', '')).upper()
                        pt = str(row.get('pattern_tier', '')).lower()
                        mode = str(row.get('mode', '')).upper()
                        if 'BIG' in st or 'PRO_TREND' in st or pt == 'pro_trend' or 'BIG' in mode:
                            return 'Big Pattern (H1/H4)'
                        elif 'SMALL' in st or 'SMC' in st or pt == 'small_pattern' or 'SMALL' in mode:
                            return 'Small Pattern (M5)'
                        return 'Scalp (M1)'

                    df_attr['trade_mode'] = df_attr.apply(_assign_mode, axis=1)
                    df_attr['pnl_num'] = pd.to_numeric(df_attr.get('pnl_usd', 0), errors='coerce').fillna(0.0)

                    for m_name in ['Big Pattern (H1/H4)', 'Small Pattern (M5)', 'Scalp (M1)']:
                        sub_df = df_attr[df_attr['trade_mode'] == m_name]
                        tot = len(sub_df)
                        if tot == 0:
                            print(f"  {m_name:<22}: 0 trades logged")
                            continue
                        wins = len(sub_df[sub_df['outcome'] == 'WIN'])
                        losses = len(sub_df[sub_df['outcome'] == 'LOSS'])
                        wr = (wins / tot * 100) if tot > 0 else 0.0
                        g_prof = sub_df[sub_df['pnl_num'] > 0]['pnl_num'].sum()
                        g_loss = abs(sub_df[sub_df['pnl_num'] < 0]['pnl_num'].sum())
                        pf = (g_prof / g_loss) if g_loss > 0 else (float('inf') if g_prof > 0 else 0.0)
                        net_pnl = sub_df['pnl_num'].sum()
                        print(f"  {m_name:<22}: Trades={tot:4d} | WR={wr:5.1f}% | PF={pf_str(pf):<6s} | Net PnL=${net_pnl:+.2f}")
            conn.close()
    except Exception as _mode_err:
        print(f"  ℹ Could not compute mode breakout: {_mode_err}")

    print()
    print(SEP)
    print("  Next steps:")
    print("  1. Check SELL% above — if still < 5% after 20+ trades, investigate engine_votes log.")
    print("  2. Check OVERLAP row — if OVERLAP% has dropped vs pre-fix, session gate is working.")
    print("  3. Check Per-Mode breakout — verify Big Pattern & Small Pattern lead Scalp in WR & PF.")
    print("  4. After 200 shadow decisions, challenger evaluation fires automatically.")
    print(SEP)
    print()


if __name__ == "__main__":
    main()
