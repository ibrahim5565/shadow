"""AEGIS QUANT AI — modular pretrained quantitative AI stack (research grade).

This package is a NEW, additive layer on top of the existing AEGIS trading
system. It does NOT modify existing modules. Components:

    config.py       — QAIConfig (safety-first settings)
    predictions.py  — ModelPrediction / SignalDecision dataclasses
    downloader.py   — ModelDownloader (verify => download => cache => health)
    registry.py     — QuantModelRegistry (lazy load, LRU, device, memory guard)
    models/         — per-model adapters around REAL verified pretrained models
    quant/          — factors, volatility, regime, anomaly engines
    risk/           — independent RiskManager + position sizing
    execution/      — demo guard + SL/TP broker-stops validator (error 10016 fix)
    validation/     — metrics, baselines, walk-forward, tournament, backtest
    storage/        — sqlite persistence of every decision
    rl/             — research RL environment (observable state only)
    pipeline.py     — end-to-end orchestration
    cli.py          — command-line entry

Rule of the package: never fabricate a model, a checkpoint, or a probability.
Every field that a model does not genuinely output stays None and is reported
honestly in the audit trail.
"""

__version__ = "0.1.0"