"""Loader self-test: builds a 169-bar MT5-format sample (\\r\\n) mirroring
XAUUSD_M5_202610090100_202610091500.csv, proves load_mt5_csv + validation
parse it, and proves the 20,000-bar gate ABORTS (loader-test ONLY).

Run: python -m quant_ai.test_loader_sample  (from Aegis_Gold/)
"""
from __future__ import annotations
import os, tempfile
from datetime import datetime, timedelta
from quant_ai.data_mt5 import (load_mt5_csv, validate_bars, require_min_bars,
    InsufficientRealDataError, MIN_BARS_PER_TIMEFRAME)
HDR = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"
def build_sample(n: int = 169,
                 start: datetime = datetime(2026, 10, 9, 1, 0)) -> str:
    lines = [HDR]
    px = 4000.00
    for i in range(n):
        ts = start + timedelta(minutes=5 * i)
        o = px; c = px + 0.35; h = max(o, c) + 0.12; l = min(o, c) - 0.10
        lines.append(f"{ts:%Y.%m.%d}\t{ts:%H:%M}\t{o:.2f}\t{h:.2f}\t"
                     f"{l:.2f}\t{c:.2f}\t120\t0\t35")
        px = c
    return "\r\n".join(lines) + "\r\n"
def main() -> int:
    print(f"MIN_BARS_PER_TIMEFRAME={MIN_BARS_PER_TIMEFRAME}")
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
        try:
            require_min_bars(rep)
        except InsufficientRealDataError as exc:
            print(f"EXPECTED ABORT (169 < 20000): {exc}")
        else:
            raise AssertionError("20k gate did NOT abort on 169 bars")
    print("LOADER SELF-TEST PASS: tab/\\r\\n/header/date/spread OK; 169-bar "
          "sample correctly REFUSED as non-audit-grade.")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
