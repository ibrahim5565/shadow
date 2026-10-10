"""Loader self-test: builds a 169-bar MT5-format sample (\r\n) mirroring
XAUUSD_M5_202610090100_202610091500.csv, proves load_mt5_csv + validation
parse it, and proves the per-timeframe bar gates ABORT (loader-test ONLY).

Per-TF gates: M5>=60,000, M15>=20,000, H1>=5,000; span>=12m caps verdict
at NEEDS_MORE_DATA.

Run: python -m quant_ai.test_loader_sample  (from Aegis_Gold/)
"""
from __future__ import annotations
import os, tempfile
from datetime import datetime, timedelta
from quant_ai.data_mt5 import (load_mt5_csv, validate_bars, require_min_bars,
    require_audit_ready, InsufficientRealDataError, MIN_BARS_PER_TF,
    MIN_SPAN_MONTHS, VERDICT_ABORT, VERDICT_NEEDS_MORE_DATA)
HDR = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"
def build_sample(n: int = 169,
                 start: datetime = datetime(2026, 10, 9, 1, 0),
                 step_minutes: int = 5) -> str:
    lines = [HDR]
    px = 4000.00
    for i in range(n):
        ts = start + timedelta(minutes=step_minutes * i)
        o = px; c = px + 0.35; h = max(o, c) + 0.12; l = min(o, c) - 0.10
        lines.append(f"{ts:%Y.%m.%d}\t{ts:%H:%M}\t{o:.2f}\t{h:.2f}\t"
                     f"{l:.2f}\t{c:.2f}\t120\t0\t35")
        px = c
    return "\r\n".join(lines) + "\r\n"
def main() -> int:
    print(f"MIN_BARS_PER_TF={MIN_BARS_PER_TF} MIN_SPAN_MONTHS={MIN_SPAN_MONTHS}")
    assert MIN_BARS_PER_TF == {"M5": 60_000, "M15": 20_000, "H1": 5_000}
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "XAUUSD_M5_202610090100_202610091500.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(build_sample())
        df = load_mt5_csv(p, timeframe="M5")
        assert len(df) == 169, len(df)
        assert list(df.columns) == ["open","high","low","close","tickvol",
                                    "vol","spread","volume"]
        rep = validate_bars(df, "M5", path=p, symbol="XAUUSD")
        assert rep.n_bars == 169 and rep.first_ts.startswith("2026-10-09")
        assert rep.pct_spread_gt0 == 100.0, rep.pct_spread_gt0
        assert rep.min_bars == 60_000, rep.min_bars
        assert rep.span_months < 12.0, rep.span_months
        assert rep.verdict == VERDICT_ABORT, rep.verdict
        try:
            require_min_bars(rep)
        except InsufficientRealDataError as exc:
            print(f"EXPECTED ABORT (169 < 60000 M5): {exc}")
        else:
            raise AssertionError("M5 60k gate did NOT abort on 169 bars")
        # H1 gate is 5,000: same 169 bars must still ABORT there too.
        rep_h1 = validate_bars(df, "H1", path=p, symbol="XAUUSD")
        assert rep_h1.min_bars == 5_000 and rep_h1.verdict == VERDICT_ABORT
        # Span cap: enough H1 bars (6,000 x 60min) over ~8 months -> NEEDS_MORE_DATA.
        big = build_sample(n=6000, start=datetime(2026, 1, 5, 0, 0),
                           step_minutes=60)
        p2 = os.path.join(td, "XAUUSD_H1_probe.csv")
        with open(p2, "w", encoding="utf-8", newline="") as f:
            f.write(big)
        df2 = load_mt5_csv(p2, timeframe="H1")
        rep2 = validate_bars(df2, "H1", path=p2, symbol="XAUUSD")
        assert rep2.n_bars == 6000 >= 5_000, rep2.n_bars
        assert rep2.verdict == VERDICT_NEEDS_MORE_DATA, rep2.verdict
        try:
            require_audit_ready(rep2)
        except InsufficientRealDataError as exc:
            print(f"EXPECTED NEEDS_MORE_DATA (span {rep2.span_months}m < 12m)")
        else:
            raise AssertionError("span cap did NOT trigger NEEDS_MORE_DATA")
    print("LOADER SELF-TEST PASS: tab/\\r\\n/header/date/spread OK; per-TF "
          "bars print vs minimum; span prints in months; 169-bar sample "
          "ABORTS; short-span file caps at NEEDS_MORE_DATA.")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
