"""AEGIS QUANT AI - REAL MT5 export loader (REAL DATA ONLY).
Format: TAB-separated, header <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE>
<TICKVOL> <VOL> <SPREAD>, date YYYY.MM.DD, spread in POINTS, \\r\\n ok.
NO synthetic fallback: missing file -> RealDataMissing, never generate.
"""
from __future__ import annotations
import glob, os
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd
MT5_HEADER = ["<DATE>","<TIME>","<OPEN>","<HIGH>","<LOW>","<CLOSE>",
              "<TICKVOL>","<VOL>","<SPREAD>"]
# Per-timeframe audit gates (Oct 2026): bars are a HARD abort, span is a
# verdict cap (warn below 12 months -> verdict capped at NEEDS_MORE_DATA).
MIN_BARS_PER_TF = {"M5": 60_000, "M15": 20_000, "H1": 5_000}
MIN_BARS_PER_TIMEFRAME = MIN_BARS_PER_TF["M5"]  # legacy alias (strictest)
MIN_SPAN_MONTHS = 12.0
VERDICT_OK = "OK"
VERDICT_NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
VERDICT_ABORT = "ABORT"
TIMEFRAME_MINUTES = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":60,"H4":240,"D1":1440}
class RealDataMissing(RuntimeError): pass
class InsufficientRealDataError(RuntimeError): pass
def _expected_minutes(tf: str) -> int:
    return TIMEFRAME_MINUTES.get(tf.upper(), 5)
def load_mt5_csv(path: str, timeframe: str = "M5") -> pd.DataFrame:
    if not os.path.isfile(path):
        raise RealDataMissing(
            f"REAL DATA MISSING: not found: {path}. Refusing to run - "
            "synthetic generation is DISABLED. Supply 12-month MT5 "
            "exports for M5, M15, H1.")
    with open(path, "r", encoding="utf-8-sig", newline=None) as f:
        header = f.readline().strip().split("\t")
    if header != MT5_HEADER:
        raise ValueError(f"BAD MT5 HEADER in {path}: got {header!r}, "
                         f"expected TAB-separated {MT5_HEADER!r}.")
    raw = pd.read_csv(path, sep="\t", encoding="utf-8-sig",
                      engine="python", dtype=str, keep_default_na=False)
    raw.columns = [c.strip() for c in raw.columns]
    if list(raw.columns) != MT5_HEADER:
        raise ValueError(f"BAD MT5 HEADER in {path}: {list(raw.columns)!r}.")
    try:
        ts = pd.to_datetime(raw["<DATE>"].str.strip() + " "
                            + raw["<TIME>"].str.strip(),
                            format="%Y.%m.%d %H:%M")
    except Exception as exc:
        raise ValueError(f"DATE/TIME parse failed for {path}: {exc}") from exc
    out = pd.DataFrame({
        "open": pd.to_numeric(raw["<OPEN>"], errors="coerce"),
        "high": pd.to_numeric(raw["<HIGH>"], errors="coerce"),
        "low": pd.to_numeric(raw["<LOW>"], errors="coerce"),
        "close": pd.to_numeric(raw["<CLOSE>"], errors="coerce"),
        "tickvol": pd.to_numeric(raw["<TICKVOL>"], errors="coerce"),
        "vol": pd.to_numeric(raw["<VOL>"], errors="coerce"),
        "spread": pd.to_numeric(raw["<SPREAD>"], errors="coerce")})
    out.index = pd.DatetimeIndex(ts, name="time")
    if out.isna().any().any():
        raise ValueError(f"NON-NUMERIC rows in {path}: "
                         f"{int(out.isna().any(axis=1).sum())} rows.")
    bad_geo = ((out["high"] < out[["open","close"]].max(axis=1)) |
               (out["low"] > out[["open","close"]].min(axis=1)) |
               (out["high"] < out["low"]))
    if bool(bad_geo.any()):
        raise ValueError(f"CANDLE GEOMETRY VIOLATION in {path}: "
                         f"{int(bad_geo.sum())} rows.")
    out = out.sort_index(kind="mergesort")
    if bool(out.index.duplicated().any()):
        raise ValueError(f"DUPLICATE TIMESTAMPS in {path}: "
                         f"{int(out.index.duplicated().sum())} rows.")
    out["volume"] = out["tickvol"]
    return out[["open","high","low","close","tickvol","vol","spread","volume"]]
@dataclass
class ValidationReport:
    path: str; symbol: str; timeframe: str; n_bars: int
    min_bars: int; first_ts: str; last_ts: str
    span_months: float; min_span_months: float
    per_month: Dict[str,int]
    n_gaps: int; gaps: List[dict]; pct_spread_gt0: float
    verdict: str; ok: bool; error: str = ""
    def text(self) -> str:
        bar_flag = "PASS" if self.n_bars >= self.min_bars else "FAIL"
        span_flag = "PASS" if self.span_months >= self.min_span_months else "WARN"
        ls = ["="*72,
            f"[validate] {self.symbol} {self.timeframe} <- {self.path}",
            f"  bars      : {self.n_bars} vs min {self.min_bars} [{bar_flag}]",
            f"  span      : {self.span_months:.2f} months vs min "
            f"{self.min_span_months:.1f} [{span_flag}]",
            f"  first     : {self.first_ts}",
            f"  last      : {self.last_ts}",
            f"  per-month : {self.per_month}",
            f"  gaps >{self.timeframe}: {self.n_gaps} "
            "(weekend Fri->Mon gaps EXPECTED)",
            f"  spread>0  : {self.pct_spread_gt0:.2f}% of bars",
            f"  verdict   : {self.verdict}"]
        for g in self.gaps[:10]:
            ls.append(f"    gap {g['from']} -> {g['to']} "
                      f"({g['minutes']} min, {g['bars_missing']} missing)")
        if not self.ok: ls.append(f"  ABORT: {self.error}")
        ls.append("="*72)
        return "\n".join(ls)
def span_months(first, last) -> float:
    """Calendar span in months (30.4375-day mean month). 0.0 if <2 bars."""
    try:
        days = (pd.Timestamp(last) - pd.Timestamp(first)).total_seconds() / 86400.0
    except Exception:
        return 0.0
    return round(max(0.0, days) / 30.4375, 2)


def min_bars_for(timeframe: str) -> int:
    return MIN_BARS_PER_TF.get(timeframe.upper(), MIN_BARS_PER_TF["M5"])


def validate_bars(df: pd.DataFrame, timeframe: str, path: str = "",
                  symbol: str = "XAUUSD",
                  min_bars: Optional[int] = None,
                  min_span_months: float = MIN_SPAN_MONTHS) -> ValidationReport:
    tf = timeframe.upper(); exp = _expected_minutes(tf); n = len(df)
    need = min_bars if min_bars is not None else min_bars_for(tf)
    first = str(df.index[0]) if n else "n/a"
    last = str(df.index[-1]) if n else "n/a"
    span = span_months(df.index[0], df.index[-1]) if n > 1 else 0.0
    per: Dict[str,int] = {}
    if n: per = {str(k):int(v) for k,v in
                 df.index.to_period("M").value_counts().sort_index().items()}
    gaps: List[dict] = []
    if n > 1:
        diffs = df.index.to_series().diff().dropna()
        for i, d in enumerate(diffs):
            mins = d.total_seconds()/60.0
            if mins > exp + 1e-9:
                to_ts = diffs.index[i]
                frm = df.index[df.index.get_loc(to_ts)-1]
                gaps.append({"from":str(frm),"to":str(to_ts),
                             "minutes":round(mins,2),
                             "bars_missing":int(round(mins/exp))-1})
    pct = float((df["spread"]>0).mean()*100.0) if n and "spread" in df else 0.0
    ok, err, verdict = True, "", VERDICT_OK
    if n < need:
        ok, verdict = False, VERDICT_ABORT
        err = (f"INSUFFICIENT REAL DATA for {symbol} {tf}: bars={n} < "
               f"required {need}. File {path!r} is loader-test ONLY, "
               "NOT audit-grade. Supply 12-month M5, M15, H1 exports.")
    elif span < min_span_months:
        verdict = VERDICT_NEEDS_MORE_DATA
        err = (f"SPAN WARNING for {symbol} {tf}: span={span:.2f} months < "
               f"required {min_span_months:.1f}; verdict capped at "
               f"{VERDICT_NEEDS_MORE_DATA}. Supply full 12-month exports.")
    rep = ValidationReport(path,symbol,tf,n,need,first,last,span,
                           min_span_months,per,len(gaps),gaps,
                           round(pct,2),verdict,ok,err)
    print(rep.text(), flush=True)
    if verdict == VERDICT_NEEDS_MORE_DATA:
        print(f"  WARNING: {err}", flush=True)
    return rep
def require_min_bars(rep: ValidationReport) -> None:
    if rep.verdict == VERDICT_ABORT: raise InsufficientRealDataError(rep.error)
def require_audit_ready(rep: ValidationReport) -> None:
    """Abort on bars; also abort (softer) when span < 12 months."""
    if not rep.ok:
        raise InsufficientRealDataError(rep.error)
    if rep.verdict == VERDICT_NEEDS_MORE_DATA:
        raise InsufficientRealDataError(
            f"{rep.error} Waiting on full 12-month exports.")
def find_real_files(dirs: Optional[List[str]] = None,
                    symbol: str = "XAUUSD") -> Dict[str, List[str]]:
    if dirs is None:
        qai = os.path.dirname(os.path.abspath(__file__))
        root = os.path.abspath(os.path.join(qai,"..","..",".."))
        dirs = [os.path.join(root,"data_mt5"), os.path.join(root,"data"),
                os.path.join(qai,"data_real"), os.getcwd()]
    found: Dict[str,List[str]] = {"M5":[],"M15":[],"H1":[]}
    for d in dirs:
        if not d or not os.path.isdir(d): continue
        for tf in list(found):
            for pat in (f"{symbol}_{tf}_*.csv", f"{symbol}_{tf.lower()}_*.csv"):
                for p in sorted(glob.glob(os.path.join(d,pat))):
                    if p not in found[tf]: found[tf].append(p)
    return found
def load_and_validate_all(dirs: Optional[List[str]] = None,
                          symbol: str = "XAUUSD",
                          timeframes: tuple = ("M5","M15","H1"),
                          min_bars: Optional[Dict[str,int]] = None,
                          min_span_months: float = MIN_SPAN_MONTHS,
                          explicit: Optional[Dict[str,str]] = None):
    found = find_real_files(dirs, symbol=symbol)
    if explicit:
        for tf,p in explicit.items(): found[tf.upper()] = [p] if p else []
    out = {}
    for tf in timeframes:
        tf = tf.upper(); paths = found.get(tf,[])
        if not paths:
            raise RealDataMissing(
                f"REAL DATA MISSING for {symbol} {tf}: no {symbol}_{tf}_*.csv "
                f"in {dirs or 'default dirs'}. Refusing to run - synthetic "
                "generation is DISABLED. Supply 12-month M5, M15, H1 exports.")
        need = (min_bars.get(tf, min_bars_for(tf)) if isinstance(min_bars, dict)
                else (min_bars if min_bars is not None else min_bars_for(tf)))
        df = load_mt5_csv(paths[0], timeframe=tf)
        require_audit_ready(validate_bars(df,tf,path=paths[0],symbol=symbol,
                                          min_bars=need,
                                          min_span_months=min_span_months))
        out[tf] = df
    return out

