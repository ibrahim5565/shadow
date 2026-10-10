"""AEGIS QUANT AI - command line entry (stdlib argparse only).

Commands
--------
  env         measured machine / package snapshot
  models      raw prediction from every configured adapter
  decide      one full pipeline decision (DEMO-safe; NEVER sends an order)
  paper       event-driven PAPER run over real MT5 / CSV history (NO synthetic)
  tournament  walk-forward model leaderboard vs the naive baselines
  matrix      measured model matrix -> docs/model_matrix.json

Every command is read-only with respect to trading: no command calls
``mt5.order_send``.  ``decide`` and ``paper`` only ever produce/consume local
signals.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _print(obj) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2, default=str))
    else:
        print(obj)


_SYNTH_DISABLED = (
    "SYNTHETIC DATA DISABLED (Oct 2026 real-data-only policy). No real MT5 "
    "export found, so the audit REFUSES to run. Supply the 12-month MT5 "
    "exports for M5, M15, H1. Previous funnel results (48,018 patterns / "
    "4 trades) are INVALID (synthetic data) and must not be used.")
# PREVIOUS FUNNEL RESULTS: INVALID (synthetic data).
# 48,018 patterns / 4 trades must NOT be used for any decision.
# Real-data-only policy (Oct 2026): audit refuses to run without
# 12-month MT5 exports for M5, M15, H1 (>=20,000 bars each).
SYNTHETIC_FUNNEL_INVALID = True
FUNNEL_INVALIDATION_NOTE = _SYNTH_DISABLED
INVALID_RESULTS = {"patterns_48018": "INVALID (synthetic)",
                   "trades_4": "INVALID (synthetic)"}





def cmd_env(args) -> int:
    from quant_ai.performance import probe_environment, installed_packages
    _print({"environment": probe_environment(),
            "packages": installed_packages()})
    return 0


def cmd_models(args) -> int:
    from quant_ai.aegis_bridge import fetch_mt5_history
    from quant_ai.pipeline import QuantAIPipeline
    from quant_ai.data_mt5 import load_mt5_csv, validate_bars, find_real_files
    df = None
    src = "none"
    if args.csv:
        df = load_mt5_csv(args.csv, timeframe=args.timeframe)
        validate_bars(df, args.timeframe, path=args.csv, symbol=args.symbol)
        src = f"csv:{args.csv}"
    elif not args.synthetic:
        df = fetch_mt5_history(args.symbol, args.timeframe, bars=args.bars)
        if df is not None:
            print(f"[data] MT5 {args.symbol} {args.timeframe} bars={len(df)}")
            src = "mt5"
    if df is None and not args.synthetic:
        # REAL-DATA-ONLY: try MT5 export files before refusing.
        found = find_real_files(symbol=args.symbol)
        cands = found.get(args.timeframe.upper(), [])
        if cands:
            df = load_mt5_csv(cands[0], timeframe=args.timeframe)
            validate_bars(df, args.timeframe, path=cands[0], symbol=args.symbol)
            src = f"csv:{cands[0]}"
    if df is None:
        print("[data] REAL DATA MISSING: no MT5 terminal data, no --csv, "
              "and no XAUUSD_<TF>_*.csv export found. Refusing to run - "
              "synthetic generation is DISABLED. Supply the 12-month MT5 "
              "exports for M5, M15, H1. Previous funnel results "
              "(48,018 patterns / 4 trades) are INVALID (synthetic).")
        return 2
    print(f"[data] source={src} bars={len(df)}")
    pipe = QuantAIPipeline(store=None)
    models = pipe.build_models(args.symbol, args.timeframe)
    print(f"[models] {len(models)} adapters configured")
    preds = pipe._predict_all(models, df, args.horizon, args.symbol, args.timeframe)
    for p in preds:
        print(f"  {p.model:<24} {p.status.value:<18} "
              f"dir={p.direction.value:<7} fc={p.forecast_price} "
              f"p_up={p.probability_up} lat={p.latency_ms}ms")
    return 0


def cmd_decide(args) -> int:
    from quant_ai.aegis_bridge import AegisQuantBridge
    from quant_ai.data_mt5 import load_mt5_csv
    llm = None
    if args.llm:
        from quant_ai.llm.reasoner import OllamaReasoner
        llm = OllamaReasoner(model=args.llm_model)
        print(f"[llm] optional: {args.llm_model} available={llm.health_check()}")
    bridge = AegisQuantBridge(llm=llm)
    df = load_mt5_csv(args.csv, timeframe=args.timeframe) if args.csv else None
    if args.synthetic and df is None:
        print("[decide] REFUSED: --synthetic is DISABLED under the Oct 2026 "
              "real-data-only policy. Pass --csv <MT5 export> or connect MT5. "
              "Previous funnel results (48,018 patterns / 4 trades) are "
              "INVALID (synthetic).")
        return 2
    sig = bridge.analyze(args.symbol, args.timeframe, bars=args.bars,
                         equity=args.equity, df=df)
    _print(sig.to_dict())
    print(f"\nACTION={sig.action}  tradable={sig.tradable}")
    print("NOTE: no order was sent. Execution stays with the legacy AEGIS "
          "gateway which re-validates risk/execution/demo guard.")
    return 0


def cmd_paper(args) -> int:
    from quant_ai.aegis_bridge import fetch_mt5_history
    from quant_ai.config import QAIConfig
    from quant_ai.paper_trading import PaperBroker, PaperBrokerConfig
    from quant_ai.pipeline import QuantAIPipeline, symbol_profile
    from quant_ai.risk.risk_engine import RiskManager
    prof = symbol_profile(args.symbol)
    from quant_ai.data_mt5 import load_mt5_csv, find_real_files
    df = load_mt5_csv(args.csv, timeframe=args.timeframe) if args.csv else None
    src = f"csv:{args.csv}" if df is not None else "none"
    if df is None:
        df = fetch_mt5_history(args.symbol, args.timeframe, bars=args.bars)
        src = "mt5" if df is not None else "none"
    if df is None:
        cands = find_real_files(symbol=args.symbol).get(args.timeframe.upper(), [])
        if cands:
            df = load_mt5_csv(cands[0], timeframe=args.timeframe)
            src = f"csv:{cands[0]}"
    if df is None:
        print("[paper] REAL DATA MISSING: no --csv, no MT5 terminal data, "
              "no XAUUSD_<TF>_*.csv export. Refusing to run - synthetic "
              "generation is DISABLED. Supply 12-month M5, M15, H1 exports.")
        return 2
    print(f"[paper] source={src} bars={len(df)} symbol={args.symbol} "
          f"timeframe={args.timeframe}")
    cfg = QAIConfig()
    risk = RiskManager(cfg)
    broker = PaperBroker(PaperBrokerConfig(
        symbol=args.symbol, point=prof["point"], digits=prof["digits"],
        spread_points=prof["spread_points"],
        commission_per_lot=cfg.commission_per_lot_usd.get(args.symbol, 7.0),
        slippage_points=cfg.slippage_points.get(args.symbol, 1)), risk=risk)
    pipe = QuantAIPipeline(config=cfg, store=None)
    models = pipe.build_models(args.symbol, args.timeframe)
    horizon = cfg.forecast_horizon.get(args.timeframe, 12)
    step = max(1, args.step)
    for i in range(120, len(df) - 2, step):
        window = df.iloc[: i + 1]
        if broker.position is not None:
            broker.manage(index=i, ts=str(window.index[-1]),
                          high=float(window["high"].iloc[-1]),
                          low=float(window["low"].iloc[-1]),
                          close=float(window["close"].iloc[-1]))
            continue
        d = pipe.decide(window, symbol=args.symbol, timeframe=args.timeframe,
                        horizon=horizon,
                        equity=broker.mark_to_market(float(window["close"].iloc[-1])),
                        spread_pts=prof["spread_points"], session="LONDON",
                        models=models)
        if d.action in ("BUY", "SELL"):
            pos = d.position
            broker.try_open(side=d.action, price=float(window["close"].iloc[-1]),
                            sl=pos["sl"], tp=pos["tp"], lot=pos["lot"],
                            index=i, ts=str(window.index[-1]))
    if broker.position is not None:
        last = df.iloc[-1]
        broker.force_close(index=len(df) - 1, ts=str(df.index[-1]),
                           price=float(last["close"]), reason="EOD")
    _print(broker.summary())
    print("NOTE: PAPER only. No real MT5 order was sent.")
    return 0


def cmd_tournament(args) -> int:
    from quant_ai.aegis_bridge import fetch_mt5_history
    from quant_ai.pipeline import QuantAIPipeline
    from quant_ai.storage.db import QuantAIStore
    from quant_ai.validation.tournament import ModelTournament
    from quant_ai.data_mt5 import load_mt5_csv, find_real_files
    df = load_mt5_csv(args.csv, timeframe=args.timeframe) if args.csv else None
    source = f"csv:{args.csv}" if df is not None else "none"
    if df is None:
        df = fetch_mt5_history(args.symbol, args.timeframe, bars=args.bars)
        source = "mt5" if df is not None else "none"
    if df is None:
        cands = find_real_files(symbol=args.symbol).get(args.timeframe.upper(), [])
        if cands:
            df = load_mt5_csv(cands[0], timeframe=args.timeframe)
            source = f"csv:{cands[0]}"
    if df is None:
        print("[tournament] REAL DATA MISSING: no --csv, no MT5 terminal "
              "data, no XAUUSD_<TF>_*.csv export. Refusing to run - "
              "synthetic generation is DISABLED. Previous funnel results "
              "(48,018 patterns / 4 trades) are INVALID (synthetic).")
        return 2
    print(f"[tournament] source={source} bars={len(df)} "
          f"{args.symbol} {args.timeframe} horizon={args.horizon}")
    pipe = QuantAIPipeline(store=None)
    store = QuantAIStore()
    models = pipe.build_models(args.symbol, args.timeframe)
    t = ModelTournament(store=store)
    lb = t.run(models, df, args.horizon, symbol=args.symbol,
               timeframe=args.timeframe, step=args.step)
    print(ModelTournament.print_leaderboard(lb))
    print("\nInterpretation: a model is only useful if it beats "
          "baseline_previous_close / baseline_random_walk out-of-sample. "
          "High raw accuracy alone is NOT promotion evidence.")
    return 0


def cmd_validate(args) -> int:
    import re
    from quant_ai.data_mt5 import (find_real_files, load_mt5_csv,
                                   validate_bars, require_min_bars,
                                   RealDataMissing, InsufficientRealDataError)
    print("PREVIOUS FUNNEL RESULTS: INVALID (synthetic data) - "
          "48,018 patterns / 4 trades must NOT be used.")
    paths: list = []
    if args.csv:
        paths = list(args.csv)
    else:
        found = find_real_files([args.dir] if args.dir else None,
                                symbol=args.symbol)
        for tf in ("M5", "M15", "H1"):
            paths += found.get(tf, [])
    if not paths:
        print(f"REAL DATA MISSING for {args.symbol}: no MT5 export found. "
              "Refusing to run - synthetic generation is DISABLED. "
              "Supply the 12-month MT5 exports for M5, M15, H1 "
              "(put XAUUSD_M5_*.csv / XAUUSD_M15_*.csv / XAUUSD_H1_*.csv "
              "in d:\\Trading\\data_mt5).")
        return 2
    rc = 0
    for p in paths:
        m = re.search(r"_(M5|M15|H1|M1|M30|H4|D1)(?:_|$|\.)",
                      p.upper().replace("-", "_"))
        tf = m.group(1) if m else "M5"
        try:
            df = load_mt5_csv(p, timeframe=tf)
            require_min_bars(validate_bars(df, tf, path=p,
                                           symbol=args.symbol))
        except (RealDataMissing, InsufficientRealDataError,
                ValueError) as exc:
            print(f"[validate] ABORT {tf} {p}: {exc}")
            rc = 2
    if rc == 0:
        print("[validate] OK: all supplied files are audit-grade "
              "(>=20,000 bars each). Waiting on full 12-month M5/M15/H1 "
              "exports before any audit runs.")
    return rc


def cmd_matrix(args) -> int:
    import runpy
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts", "run_model_matrix.py")
    runpy.run_path(path, run_name="__main__")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quant_ai", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, bars_default=700):
        sp.add_argument("--symbol", default="XAUUSD")
        sp.add_argument("--timeframe", default="M5")
        sp.add_argument("--bars", type=int, default=bars_default)
        sp.add_argument("--csv", default=None,
                        help="real MT5 tab-separated export "
                        "(<DATE>\\t<TIME>\\t<OPEN>\\t<HIGH>\\t<LOW>\\t<CLOSE>"
                        "\\t<TICKVOL>\\t<VOL>\\t<SPREAD>)")
        sp.add_argument("--synthetic", action="store_true",
                        help="DISABLED: kept only to refuse clearly "
                        "(real-data-only policy)")
        return sp

    common(sub.add_parser("env", help="measured environment snapshot"))
    v = sub.add_parser("validate", help="validate real MT5 export(s); "
                       "aborts if bars < 20,000 per timeframe")
    v.add_argument("--symbol", default="XAUUSD")
    v.add_argument("--csv", action="append", default=[],
                   help="explicit MT5 export file (repeatable); "
                   "timeframe inferred from _M5/_M15/_H1 in name")
    v.add_argument("--dir", default=None,
                   help="directory to scan for XAUUSD_<TF>_*.csv")
    m = common(sub.add_parser("models", help="raw adapter predictions"))
    m.add_argument("--horizon", type=int, default=12)
    d = common(sub.add_parser("decide", help="one full pipeline decision"))
    d.add_argument("--equity", type=float, default=10_000.0)
    d.add_argument("--llm", action="store_true", help="enable optional Ollama")
    d.add_argument("--llm-model", default="qwen2.5:7b")
    pa = common(sub.add_parser("paper", help="event-driven PAPER run"))
    pa.add_argument("--step", type=int, default=10)
    t = common(sub.add_parser("tournament", help="walk-forward leaderboard"))
    t.add_argument("--horizon", type=int, default=12)
    t.add_argument("--step", type=int, default=25)
    sub.add_parser("matrix", help="measured model matrix -> docs/model_matrix.json")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {"env": cmd_env, "models": cmd_models, "decide": cmd_decide,
                "paper": cmd_paper, "tournament": cmd_tournament,
                "matrix": cmd_matrix, "validate": cmd_validate}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())


