# Forward Validation Plan — Aegis-Gold Phase 2 (ATR-Scaled SL/TP)

## Status as of 2026-07-28

Historical backtesting of the ATR-scaled SL/TP changes **cannot be done** with existing data.
Reasons documented in audit:
- `tp_was_hit` / `sl_was_hit` were NULL on all 3,813 closed trades
- `atr` was 0 on all trades
- 67.8% of closed trades had `sl_points = 0`
- All XAUUSD trades before July 2026 were mass-closed at a single timestamp

The data infrastructure fix (commit `7c23775`) resolves this going forward.
This document defines the minimum forward validation required before Phase 2
(ATR-scaled SL/TP) can be considered for live capital.

---

## Stage 1 — Logging Verification (current system, no strategy changes)

**Goal:** Confirm the fixed logging actually works — that new trades write
non-NULL `sl_was_hit`, `tp_was_hit`, and non-zero `atr` — and that these
values match MT5's own trade history for the same tickets.

**Method:**
1. Run the current bot (unchanged strategy) on the demo/paper account.
2. After each session, run `scratch/session_sanity_check.py` and confirm
   all 6 checks pass for new trades.
3. Manually spot-check 5–10 recent closed trades in `trade_memory.db`
   against MT5's own history (History tab → find the same ticket):
   - Does `sl_was_hit = 1` match MT5 showing "sl" as the close reason?
   - Does `tp_was_hit = 1` match MT5 showing "tp" as the close reason?
   - Is `atr` > 0 and within a plausible range for the symbol/timeframe?

**Minimum sample before advancing:** 50 cleanly-logged closed trades with
`session_sanity_check.py` passing (exit code 0) after each session.

**Gate:** If any session_sanity_check.py warning fires on new trades (not
historical), find and fix the logging bug before proceeding. Do not advance
to Stage 2 until the check runs clean on >= 50 consecutive new trades.

---

## Stage 2 — Baseline Period (current strategy, verified logging)

**Goal:** Establish a clean baseline PF under fixed logging conditions.
This is the comparison denominator for Stage 3.

**Method:**
1. Continue running current strategy on demo (no Phase 2 changes).
2. Collect a minimum of **100 closed trades** or **2 weeks**, whichever
   comes first.
3. Record from `trade_memory.db`:
   - Gross win / gross loss (PF)
   - Win rate
   - Average win / average loss (the R:R asymmetry)
   - ATR distribution at entry (confirms ATR is actually being set)
   - SL/TP hit rate breakdown (tp_was_hit vs sl_was_hit vs manual)

**Acceptance criteria:** 100+ trades, session_sanity_check.py passes
after every session, no NULL hit flags in the baseline window.

---

## Stage 3 — Phase 2 ATR-Scaled SL/TP (demo only)

**Goal:** Measure real (not simulated) PF impact of ATR-scaled SL/TP
changes from `modules/risk_manager.py` against the Stage 2 baseline.

**Pre-condition:** Stage 2 baseline complete and clean.

**Method:**
1. Enable the Phase 2 ATR-scaled SL/TP logic (`atr_scaled_sl_tp()` in
   `risk_manager.py`) on the DEMO account only.
2. Run for the same minimum sample as Stage 2 (100 trades or 2 weeks).
3. Compare using the same fields from `trade_memory.db`:
   - PF Stage 3 vs PF Stage 2
   - Average win vs average loss (R:R improvement)
   - SL hit rate vs TP hit rate (did wider SL reduce premature exits?)
   - ATR distribution to confirm the new SL is actually ATR-proportional

**Acceptance criteria for live promotion:**
- Stage 3 PF > Stage 2 PF (absolute improvement, not just statistical noise)
- Stage 3 Avg Win / Avg Loss ratio improved vs Stage 2
- No new session_sanity_check.py failures
- Minimum 100 trades in Stage 3 window

**If Stage 3 PF is worse than Stage 2:** report it plainly. The Phase 2
ATR-scaled SL/TP changes do not go to live capital. Investigate why
(e.g., if wider SL just accumulates larger losses on losing trades).

---

## Stage 4 — Live Promotion Decision

**Only after Stage 3 acceptance criteria are met:**
1. Wire Phase 2 changes to `main.py` (they currently sit in `risk_manager.py`
   but are not the live path).
2. Run live for 1 week at reduced position size (50% of normal lot).
3. Compare live PF and R:R to Stage 3 demo results.
4. If live results match demo within tolerance (±15% PF), keep full sizing.

---

## Phase 3 (Consensus Gate) — Status: FROZEN

**Reason:** Held-out fold PF = 0.975 (below 1.0). This is a negative result.
The consensus gate is not validated and cannot be wired until either:
- New signal features with real predictive power are added (smc_score and
  regime_score are currently all-zero and contributed nothing), OR
- The held-out PF clears > 1.0 under the corrected disjoint-fold protocol
  in `scratch/audit_task2_consensus.py`.

## Phase 4 (Hurst / Pro Trend) — Status: FROZEN

**Reason:** Hurst calculation had a key name bug (`'hurst'` vs `'hurst_100'`).
No valid H1/H4 Hurst estimate exists. To unfreeze:
1. Connect MT5 and pull 200 consecutive H1 bars via `copy_rates_from_pos`.
2. Run `QuantFeatureEngine.calculate_hurst()` on the H1 close array.
3. Report H with the input array summary (length, first/last 5 values).
4. Only if H > 0.55 (persistent) on H1 AND H4 separately does Pro Trend
   mode have a statistical basis for wiring.
