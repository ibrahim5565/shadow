# AEGIS GOLD — Legacy File Removal Plan
## Phase 6 Audit & Deactivation Strategy

### Philosophy
"No hard deletes before 200 shadow decisions pass."

To preserve rollback capability during the Champion/Challenger shadow testing phase, all legacy indicator-gated code modules are audited, cataloged, and scheduled for relocation to `archive/` rather than immediate deletion.

---

## Catalog of Legacy Files

| File | Status | Replacement | Reason for Archival |
|---|---|---|---|
| `brain/entry.py` | Candidates for Archive | `brain/engine_vote.py` + `predict_vote()` | Contained early indicator thresholding rules (RSI 55/45, EMA9/21 cross). Fully superseded by consensus. |
| `brain/confidence_engine.py` | Candidates for Archive | `brain/engine_vote.py` + `unified_brain.py` | Calculated indicator-confidence scoring (weighted % sum of RSI/ADX/ATR). Replaced by pattern conviction. |
| `brain/smc_pattern_engine.py` | Candidates for Archive | `brain/smc_engine.py` | Legacy precursor to SMC engine. |
| `brain/momentum_engine.py` | Preserved (Snapshot-Only) | `brain/ai_supervisor.py` (OMEGA) | Retained inside OMEGA vote path as a feature calculator, but indicator threshold gating removed. |
| `brain/indicators.py` | Retained | `brain/ml_ensemble.py` features | RSI, ADX, ATR calculators are retained as ML feature extractors (indicators as inputs, NOT as entry gates). |

---

## Archival Workflow

```
Step 1: Shadow-test Challenger (Pattern Consensus) vs Champion for 200 decisions.
Step 2: Verify zero temporal leakage (0 votes discarded for confirmation_time > T).
Step 3: Verify Profit Factor > 1.5 and Realized R:R > 1.5R.
Step 4: Move candidate files to archive/ folder.
Step 5: Run full test suite (python scratch/run_new_tests.py) to ensure zero broken imports.
```
