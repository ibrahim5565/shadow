AEGIS GOLD QUANT TRADING SYSTEM - COMPLETE TECHNICAL SYSTEM SPECIFICATION & DOCUMENTATION

==================================================
1. PROJECT OVERVIEW
==================================================

Project Name: Aegis Gold (Quant X Architecture)
Version: v9.0 Institutional AI Edition
Purpose: Autonomous multi-asset quantitative trading engine specializing in high-frequency scalping, institutional Smart Money Concepts (SMC), statistical arbitrage, multi-timeframe regime analysis, and deep reinforcement learning execution on MetaTrader 5.
Objectives:
  - Deliver positive mathematical expectation (+EV) through multi-engine decision fusion.
  - Enforce zero-bypass risk management (hard stop-loss floors, equity protection, drawdown limits).
  - Execute ultra-low-latency market scanning (sub-50ms signal-to-order pipeline).
  - Continuous online learning via Proximal Policy Optimization (PPO), Deep Q-Networks (DQN), and GRPO-refined LLM macro analysts.
Trading Style: Hybrid Scalping, Day Trading, SMC Liquidity Sweeps, Structural Breakdown/Breakout.
Target Markets: Spot Forex & Spot Precious Metals.
Supported Symbols: XAUUSD (Gold vs US Dollar), EURUSD (Euro vs US Dollar).
Supported Brokers: MetaTrader 5 compatible brokers (Exness, FTMO, IC Markets, Pepperstone, etc.).
Operating System: Windows 10 / Windows 11 / Windows Server 2022.
Programming Language: Python 3.11 / Python 3.12 (compatible with Python 3.14).
Libraries & Frameworks:
  - Core Logic: Python Standard Library, NumPy, Pandas, SciPy, Scikit-learn.
  - Machine Learning & Deep Learning: PyTorch (CUDA acceleration), PyTorch Lightning, LightGBM, XGBoost, ONNX Runtime.
  - Reinforcement Learning: Stable-Baselines3, Custom Gymnasium Environments.
  - Execution & Broker Interface: MetaTrader5 Python API.
  - Persistence & Storage: SQLite3, JSON, CSV.
  - Network & Notifications: Requests, WebSockets, Python-Telegram-Bot.
Folder Structure:
  - root/ (d:\Trading)
    - Aegis_Gold/
      - brain/ (AI models, feature pipeline, statistical engines, RL agents, SMC engines)
      - config/ (System parameters, Quant X thresholds, environment variables)
      - core/ (Main orchestrator, event loop, trade cycle manager)
      - data/ (SQLite databases: performance, decision records, trade memory, attribution)
      - kronos_engine/ (Transformer/Kronos forecaster sub-system)
      - logs/ (System logs, trade logs, error tracebacks, watchdog logs)
      - models/ (PyTorch weights, LightGBM models, ONNX exports, RL checkpoints)
      - modules/ (MT5 gateway, local AI, risk manager, feature factory, telegram bot)
      - persistence/ (Service scripts, autostart runners, watchdog scripts)
      - scratch/ (Utility diagnostic scripts, ad-hoc analysis tools)
      - tests/ (Unit tests, stress tests, verification scripts)
      - utils/ (PID file lock utilities)
Dependencies: MetaTrader5, torch, torchvision, numpy, pandas, scipy, scikit-learn, lightgbm, xgboost, onnxruntime, gym/gymnasium, requests, python-telegram-bot.
Hardware Requirements:
  - Minimum: 8-core x86_64 CPU, 16 GB DDR4 RAM, NVIDIA GTX 1660 / RTX 2060 (6GB VRAM), 50 GB NVMe SSD.
  - Recommended: 16-core CPU (Intel i7/i9 or AMD Ryzen 9), 32 GB DDR5 RAM, NVIDIA RTX 3080 / RTX 4080 (12GB+ VRAM), 100 GB NVMe SSD.
GPU Requirements: CUDA Compute Capability 7.5+, CUDA Toolkit 11.8/12.1, cuDNN 8.x+.
CPU Requirements: Multi-threaded x86_64 processor supporting AVX2 instructions.
RAM Requirements: 16 GB minimum, 32 GB for concurrent online GPU training & multi-timeframe feature calculation.
Storage Requirements: High-speed PCIe Gen4 NVMe SSD for fast SQLite logging and tick data buffer reads.
Python Version: 3.10+ (Recommended: 3.11 / 3.12).
CUDA Version: 11.8 / 12.1.
PyTorch Version: 2.1.0+ (with CUDA support enabled).


==================================================
2. COMPLETE SYSTEM ARCHITECTURE
==================================================

Architecture Overview:
Aegis Gold is structured as an asynchronous, modular event-driven multi-engine system built on a decoupled pipeline architecture. The system separates Market Data Ingestion, Technical Feature Computation, Deep Machine Learning Prediction, Macro/SMC Structural Analysis, Risk Compliance Enforcements, and Order Execution into dedicated, fault-tolerant layers.

Module Categorization & Folder Descriptions:
1. Core Layer (`core/main.py`, `start_aegis.py`):
   - Initializes system dependencies, launches background service threads, manages the main event loop, and orchestrates tick fetching to order dispatching.
2. Configuration Layer (`config/settings.py`, `config/quant_x_config.py`):
   - Centralized repository of all system parameters, dynamic thresholds, feature list definitions, broker constraints, and risk limits.
3. Intelligence & Brain Layer (`brain/`):
   - Ensemble Machine Learning (`ml_ensemble.py`): LightGBM, PyTorch Neural Networks, Random Forests.
   - Deep Reinforcement Learning (`reinforcement_agent.py`, `offline_rl_agent.py`, `rl_inference.py`): PPO and DQN policy inference.
   - Institutional SMC Engine (`smc_engine.py`, `smc_pattern_engine.py`): Break of Structure (BOS), Change of Character (CHoCH), Order Blocks (OB), Fair Value Gaps (FVG), PO3 Liquidity Sweeps.
   - Multi-Timeframe Engine (`multi_timeframe_analyzer.py`): Synchronized M1, M5, M15, H1, H4 candles.
   - Kronos Transformer Forecaster (`kronos_forecaster.py`, `kronos_engine/`): Deep sequence prediction of future price movement.
   - LLM & Reasoning Engine (`llm_analyst.py`, `gpt_core.py`): Rule-guided trade setup validation and qualitative trade critique.
   - Statistical Engine (`statistical_engine.py`): EGARCH volatility modeling, Hurst exponent calculations, HMM regime classification.
   - Confidence Engine (`confidence_engine.py`): Multi-vector decision fusion producing a unified confidence score (0-100%).
4. Risk Management Layer (`modules/risk_manager.py`, `brain/risk_eval.py`):
   - Validates every candidate order against hard stop-loss floors, position sizing limits, daily drawdown maximums, maximum concurrent open trades, and current market spread thresholds.
5. Market Gateway Layer (`modules/mt5_gateway.py`, `brain/mt5_connector.py`):
   - Wraps the native MetaTrader 5 API for tick stream polling, historical candle fetching, order execution, position tracking, trailing stop modification, and account status retrieval.
6. Persistence & Data Layer (`data/`, `brain/trade_memory.py`, `brain/attribution_writer.py`):
   - Manages SQLite databases (`performance.db`, `decision_records.db`, `trade_memory.db`, `attribution.db`) for post-trade attribution, continuous evaluation, and shadow auditing.
7. Telemetry & Observability Layer (`brain/observability.py`, `brain/telegram_controller.py`, `modules/telegram_bot.py`):
   - Real-time event broadcasting to Telegram channels, system health metric logging, and error tracking.

Inter-Module Communication:
  - Modules interact in-memory via direct reference passing and typed structured records (e.g. `DecisionRecord`, `TradeSetup`).
  - Thread-safe queues are used for Telegram notifications and continuous SQLite logging to prevent blocking the main trading loop.

Initialization Sequence:
1. `start_aegis.py` checks PID lock file (`utils/pid_lock.py`) to prevent duplicate instances.
2. `config/settings.py` loads environment variables (`.env`) and static configuration defaults.
3. `brain/mt5_connector.py` initializes connection to the MetaTrader 5 terminal.
4. `data/` SQLite database connection pools and table schemas are verified/created.
5. Model weights (PyTorch, LightGBM, ONNX, RL checkpoints) are loaded into RAM/VRAM memory.
6. `brain/never_pause_enforcer.py` and `watchdog.py` launch background monitoring threads.
7. The system enters the main infinite trading loop in `core/main.py`.

Shutdown Sequence:
1. Signal traps (`SIGINT`, `SIGTERM`) trigger graceful shutdown handler in `core/main.py`.
2. Active open positions are evaluated; if hard-stop flags are set, positions are closed or verified to have valid SL/TP.
3. SQLite database transactions are committed and connections cleanly closed.
4. Background threads (Watchdog, Telegram, Training) receive cancellation tokens.
5. `mt5.shutdown()` is called to disconnect from MetaTrader 5 terminal.
6. PID lock file is released and process terminates.

Execution Flow:
Tick Event -> Candle Synchronization -> Feature Extraction -> Technical/SMC Signal Generation -> Machine Learning / RL / Kronos Inference -> Decision Fusion & Confidence Calculation -> Risk Validation & Position Sizing -> MT5 Order Execution -> Asynchronous Trade Monitoring & Trailing Stop Update -> Database Attribution & Continuous Learning.


==================================================
3. PROJECT DIRECTORY TREE
==================================================

d:\Trading\
├── Aegis_Gold/
│   ├── brain/                        # Core AI, Statistical, SMC & Signal Engines
│   │   ├── ABSOLUTE_NEVER_PAUSE_ENFORCER.py # Hard-coded continuous running watchdog
│   │   ├── adaptive_learning.py      # Real-time online parameter adaptation engine
│   │   ├── advanced_neural_architecture.py # PyTorch Transformer/LSTM deep neural nets
│   │   ├── ai_supervisor.py          # AI model orchestration supervisor
│   │   ├── attribution_writer.py     # Trade attribution logging to SQLite
│   │   ├── backtest_runner.py        # Vectorized backtesting framework
│   │   ├── brain.py                  # Central intelligence processing engine
│   │   ├── brain_logger.py           # Sub-system logger helper
│   │   ├── calibration.py            # Probability calibration (Platt/Isotonic)
│   │   ├── candle_ai.py              # Candlestick pattern ML classifier
│   │   ├── candle_utils.py           # Candle structure transformation utilities
│   │   ├── champion_challenger.py    # Automated A/B model validation system
│   │   ├── chaos_tester.py           # Fault injection & market stress simulator
│   │   ├── confidence_engine.py      # Multi-vector signal fusion & scoring
│   │   ├── data_integrity.py         # Data sanity and nan/inf validator
│   │   ├── decision_fusion.py        # Ensemble decision combining module
│   │   ├── diagnostics.py            # System runtime health checks
│   │   ├── drift_monitor.py          # Concept & data drift detection
│   │   ├── entry.py                  # Trade entry trigger evaluator
│   │   ├── entry_engine.py           # High-precision entry timing engine
│   │   ├── execution_integrity.py    # Pre-execution order sanity verification
│   │   ├── exit_engine.py            # Dynamic exit & profit take engine
│   │   ├── explainability.py         # SHAP feature importance calculation
│   │   ├── feature_pipeline.py       # Technical & mathematical feature calculation
│   │   ├── gpt_brain.py              # GPT LLM brain adapter
│   │   ├── gpt_core.py               # Core LLM prompt & reasoning engine
│   │   ├── indicators.py             # Pure NumPy technical indicator routines
│   │   ├── kelly_sizer.py            # Fractional Kelly Criterion position sizer
│   │   ├── kronos_forecaster.py      # Kronos sequence forecaster interface
│   │   ├── llm_analyst.py            # Structured LLM trade setup validator
│   │   ├── macro_context.py          # Economic news & macro bias filter
│   │   ├── meta_decision_engine.py   # Meta-learning decision gating
│   │   ├── ml_ensemble.py            # LightGBM + PyTorch ML Ensemble predictor
│   │   ├── model_reliability.py      # Historical model accuracy metrics tracker
│   │   ├── model_version_manager.py  # Model checkpoint version controller
│   │   ├── momentum_engine.py        # Relative strength & momentum scanner
│   │   ├── mt5_connector.py          # Direct MT5 API wrapper interface
│   │   ├── multi_timeframe_analyzer.py # Multi-timeframe trend & alignment aggregator
│   │   ├── naked_position_monitor.py # Guard rail for positions missing SL
│   │   ├── never_pause_enforcer.py   # Unstoppable runtime thread runner
│   │   ├── news_filter.py            # High-impact news event filter
│   │   ├── observability.py          # System telemetry & structured metric logger
│   │   ├── offline_rl_agent.py       # Conservative offline RL agent
│   │   ├── pattern_recognition.py    # Classic technical chart pattern scanner
│   │   ├── performance_attribution.py # Trade performance breakdown engine
│   │   ├── position_supervisor.py    # Live open position manager & trail engine
│   │   ├── quant_feature_engine.py   # Advanced quant features (Hurst, EGARCH)
│   │   ├── recovery_daemon.py        # Sub-process failure recovery engine
│   │   ├── regime.py                 # Market regime classification (Trend/Range)
│   │   ├── regime_switcher.py        # Dynamic strategy weight adjustor per regime
│   │   ├── reinforcement_agent.py    # Deep Q-Network & PPO RL Trading Agent
│   │   ├── risk_eval.py              # Microsecond risk evaluator
│   │   ├── risk_manager.py           # Brain-level risk validation checks
│   │   ├── rl_inference.py           # Fast RL model inference pipeline
│   │   ├── secrets_audit.py          # Security credentials inspector
│   │   ├── self_optimizer.py         # Autonomous hyperparameter tuner
│   │   ├── shadow_auditor.py         # Parallel shadow model evaluator
│   │   ├── shadow_validate_analyst.py # Shadow LLM analyst validator
│   │   ├── smc_engine.py             # Smart Money Concepts (BOS/CHoCH/OB/FVG)
│   │   ├── smc_pattern_engine.py     # SMC sub-pattern scanner
│   │   ├── spread_filter.py          # Real-time spread anomaly filter
│   │   ├── statistical_engine.py     # Statistical arbitrage & volatility engine
│   │   ├── stress_tester.py          # Synthetic slippage & latency tester
│   │   ├── structure.py              # Market structure high/low pivot finder
│   │   ├── telegram_controller.py    # Interactive Telegram command handler
│   │   ├── trade_memory.py           # Historical trade memory & SQLite database
│   │   ├── train_analyst_dataset.py  # LLM training dataset builder
│   │   ├── train_analyst_grpo.py     # LLM GRPO fine-tuning runner
│   │   ├── train_calibration.py      # Model confidence calibration trainer
│   │   ├── train_egarch.py           # EGARCH volatility model trainer
│   │   ├── train_gpt.py              # Local GPT model fine-tuner
│   │   ├── train_hmm_regime.py       # Hidden Markov Model regime trainer
│   │   ├── train_reinforcement.py    # GPU-accelerated RL training pipeline
│   │   ├── trend_detector.py         # Multi-scale trend direction filter
│   │   ├── unified_brain.py          # Unified Multi-Model Brain Aggregator
│   │   ├── volatility_engine.py      # Volatility expansion/contraction monitor
│   │   └── walk_forward_validator.py # Out-of-sample walk-forward validator
│   ├── config/                       # System Settings & Parameter Definitions
│   │   ├── advanced_config.json      # Dynamic JSON override parameters
│   │   ├── quant_x_config.py         # Quant X core system parameters
│   │   ├── quant_x_flags.json        # Dynamic feature flag toggles
│   │   └── settings.py               # Master configuration & system defaults
│   ├── core/                         # Orchestrator & Core Processing Loop
│   │   └── main.py                   # Main trading loop, state machine & event dispatcher
│   ├── data/                         # Persistent SQLite Databases
│   │   ├── attribution.db            # Trade attribution data
│   │   ├── decision_records.db       # Log of all evaluated candidate setups
│   │   ├── explanations.db           # SHAP explainability logs
│   │   ├── model_reliability.sqlite  # Model accuracy & reliability history
│   │   ├── performance.db            # Main historical trade performance database
│   │   ├── shadow_validation.db      # Shadow model validation runs
│   │   └── trade_memory.db           # Persistent trade memory buffer
│   ├── kronos_engine/                # Transformer Forecaster Module
│   │   ├── calibration_audit.py      # Kronos model confidence auditor
│   │   ├── data_pipeline.py          # Time-series data formatting engine
│   │   ├── kronos_brain.py           # Kronos sequence prediction brain
│   │   ├── main_execution.py         # Kronos standalone execution launcher
│   │   └── risk_manager.py           # Kronos risk interface
│   ├── logs/                         # File System Logs
│   │   ├── aegis.log                 # Main system operational log
│   │   ├── errors.log                # Tracebacks and error logs
│   │   ├── trades.log                # JSON-formatted trade execution log
│   │   └── watchdog.log              # Watchdog heartbeat log
│   ├── models/                       # Trained AI Weight Files (.pth, .pkl, .onnx)
│   ├── modules/                      # Operational Infrastructure Modules
│   │   ├── feature_factory.py        # Technical feature construction factory
│   │   ├── local_ai.py               # Local AI model execution harness
│   │   ├── mt5_gateway.py            # Primary MT5 API gateway implementation
│   │   ├── performance.py            # Real-time performance tracking metrics
│   │   ├── proxy_manager.py          # Network proxy failover manager
│   │   ├── risk_manager.py           # Zero-Bypass Core Risk Manager
│   │   └── telegram_bot.py           # Real-time Telegram alerting bot
│   ├── persistence/                  # Service Management Scripts
│   │   └── start_persistent.bat      # Autostart loop script
│   ├── scratch/                      # Diagnostic and Verification Scripts
│   ├── utils/                        # System Utility Modules
│   │   └── pid_lock.py               # Single-instance process lock mechanism
│   ├── watchdog.py                   # External process supervisor & autostart monitor
│   ├── start_aegis.py                # System entry point launcher script
│   └── mt5_rsi_bot.py                # Standalone fallback RSI trading bot engine


==================================================
4. FILE-BY-FILE DOCUMENTATION
==================================================

Below is the technical specification of the primary operational files:

--------------------------------------------------
File: Aegis_Gold/start_aegis.py
--------------------------------------------------
Purpose: Entry point script for initializing environment paths, loading configurations, checking single instance locks, and starting `core/main.py`.
Classes: None.
Functions:
  - `main()`: Ingests command line arguments, verifies environment variables, acquires PID lock, and executes `core.main.run()`.
Inputs: CLI flags (`--demo`, `--live`, `--symbol`).
Outputs: Process execution state.
Dependencies: `sys`, `os`, `utils.pid_lock`, `core.main`.
Global Variables: `APP_NAME`, `VERSION`.
Execution Order: 1 (Primary System Launch).
Performance Impact: Low (<10ms execution).
Memory Usage: ~15 MB.
Potential Risks: None.
Improvement Suggestions: Add structured CLI parser via `argparse`.

--------------------------------------------------
File: Aegis_Gold/core/main.py
--------------------------------------------------
Purpose: Main orchestrator of the trading bot. Manages system loop, tick polling, multi-timeframe synchronization, feature extraction, signal collection, decision fusion, risk evaluation, MT5 order dispatching, position trailing, and error handling.
Classes:
  - `AegisEngine`: Main engine class encapsulating all sub-system instances.
Functions:
  - `initialize()`: Sets up MT5 connection, loads ML models, establishes database connections.
  - `run_cycle()`: Executes single tick scan cycle (M1 candle check -> feature generation -> AI inference -> order check -> trailing stop update).
  - `execute_trade(setup)`: Sends validated trade setup to MT5 Gateway.
  - `manage_open_positions()`: Evaluates open trades for trailing stop adjustment, partial profit taking, or invalidation close.
  - `shutdown()`: Cleans up resources.
Inputs: MT5 live ticks and candles.
Outputs: Executed orders, database records, log entries.
Dependencies: `config.settings`, `brain.*`, `modules.*`.
Global Variables: `RUNNING_FLAG`, `CYCLE_COUNTER`.
Execution Order: 2 (Infinite Event Loop).
Performance Impact: High (Controls main tick loop execution, target cycle time <50ms).
Memory Usage: ~450 MB - 1.2 GB (depending on PyTorch/LightGBM model sizes).
Potential Risks: Unhandled exception in loop could stall execution if not caught by watchdog.
Improvement Suggestions: Refactor long setup evaluation method into smaller pipeline handlers.

--------------------------------------------------
File: Aegis_Gold/config/settings.py
--------------------------------------------------
Purpose: Master parameter configuration file storing trading pairs, risk parameters, feature toggle flags, indicator settings, and file system paths.
Classes:
  - `Settings`: Dataclass holding immutable configuration defaults.
Functions:
  - `load_settings()`: Reads environment variables and `.env` overrides.
Inputs: `.env` file, OS environment variables.
Outputs: Configuration object.
Dependencies: `os`, `dataclasses`, `dotenv`.
Global Variables: `SETTINGS`.
Execution Order: Pre-Initialization.
Performance Impact: Negligible.
Memory Usage: <1 MB.
Potential Risks: Misconfiguration of risk keys (e.g. `MAX_DRAWDOWN_PCT`) could lead to unsafe trading parameters.
Improvement Suggestions: Implement schema validation using `pydantic`.

--------------------------------------------------
File: Aegis_Gold/brain/ml_ensemble.py
--------------------------------------------------
Purpose: Machine learning prediction ensemble combining LightGBM, Random Forest, PyTorch Neural Networks, and ONNX models to produce directional direction probabilities (BUY/SELL/WAIT) and model consensus.
Classes:
  - `MLEnsemble`: Handles loading, feature scaling, inference, and prediction voting across ML models.
Functions:
  - `load_models()`: Deserializes trained model artifacts from `models/` folder.
  - `predict(features)`: Runs inference across all loaded models and aggregates weighted confidence probabilities.
Inputs: Dictionary/DataFrame of normalized numerical features.
Outputs: `PredictionResult` (Direction: BUY/SELL/WAIT, Probability: 0.0-1.0, Agreement Score).
Dependencies: `lightgbm`, `torch`, `numpy`, `pandas`, `joblib`.
Global Variables: `MODEL_CACHE`.
Execution Order: Per Tick/Candle Scan.
Performance Impact: Medium (PyTorch/LightGBM inference takes ~5-15ms on GPU/CPU).
Memory Usage: ~250 MB.
Potential Risks: Feature mismatch between training and live inference can cause erroneous output.
Improvement Suggestions: Implement real-time ONNX Runtime execution for sub-millisecond inference.

--------------------------------------------------
File: Aegis_Gold/brain/smc_engine.py
--------------------------------------------------
Purpose: Implements institutional Smart Money Concepts (SMC) analyzing market structure, identifying Break of Structure (BOS), Change of Character (CHoCH), Order Blocks (OB), Fair Value Gaps (FVG), and Power of 3 (PO3) liquidity sweeps.
Classes:
  - `SMCEngine`: Main SMC analysis engine.
Functions:
  - `analyze_structure(candles)`: Detects swing highs/lows, BOS, and CHoCH.
  - `find_order_blocks(candles)`: Locates bullish and bearish order blocks with unmitigated liquidity.
  - `find_fvg(candles)`: Identifies 3-candle imbalance gaps (Fair Value Gaps).
  - `detect_liquidity_sweep(candles)`: Identifies stop hunts above/below key structural levels.
Inputs: High-frequency OHLC candle arrays.
Outputs: SMC Signal object containing signal direction, confidence, invalidation level (SL), and target (TP).
Dependencies: `numpy`, `pandas`.
Execution Order: Per Candle Complete (M1/M5/M15).
Performance Impact: Medium (~10-20ms per scan).
Memory Usage: ~50 MB.
Potential Risks: Outdated candle history may delay detection of rapid liquidity sweeps.
Improvement Suggestions: Vectorize FVG and Order Block scanning loops using NumPy slicing.

--------------------------------------------------
File: Aegis_Gold/brain/confidence_engine.py
--------------------------------------------------
Purpose: Fuses signals from Machine Learning, SMC, Multi-Timeframe Trend, Statistical EGARCH Volatility, RL Agent, and Kronos Forecaster into a unified confidence score (0 - 100%).
Classes:
  - `ConfidenceEngine`: Central fusion system.
Functions:
  - `calculate_confidence(signals, market_state)`: Computes weighted linear and non-linear confidence matrix based on engine agreement, trend alignment, and spread conditions.
Inputs: Outputs from ML Ensemble, SMC Engine, Multi-Timeframe Analyzer, Volatility Engine, RL Agent.
Outputs: `ConfidenceResult` (Final Confidence Score %, Approved Flag, Weight Breakdown).
Dependencies: `numpy`.
Execution Order: Per Trade Evaluation.
Performance Impact: Low (~2ms).
Memory Usage: <10 MB.
Potential Risks: Over-weighting a single failing engine during regime shifts.
Improvement Suggestions: Use dynamic Bayesian adaptive weighting based on recent engine performance.

--------------------------------------------------
File: Aegis_Gold/modules/risk_manager.py
--------------------------------------------------
Purpose: Zero-bypass risk enforcer validating lot sizing, hard SL floors, daily loss limits, equity protection, spread filters, and max trade counts prior to order dispatch.
Classes:
  - `ZeroBypassRiskManager`: Primary risk validation class.
Functions:
  - `validate_trade(order_request)`: Evaluates order against 12 strict risk filters.
  - `calculate_lot_size(account, sl_pips, risk_pct)`: Computes risk-adjusted position size.
  - `check_daily_loss(account)`: Blocks trading if daily drawdown threshold is reached.
Inputs: Proposed Order Request, MT5 Account Info, Active Positions.
Outputs: Boolean (Approved/Rejected), Rejection Reason, Adjusted Lot Size, Hard SL.
Dependencies: `config.settings`, `MetaTrader5`.
Execution Order: Immediate Pre-Order Execution.
Performance Impact: Extremely Low (<1ms).
Memory Usage: <5 MB.
Potential Risks: Incorrect balance calculation due to unclosed swap/commission fees.
Improvement Suggestions: Implement per-symbol correlation exposure checks.

--------------------------------------------------
File: Aegis_Gold/modules/mt5_gateway.py
--------------------------------------------------
Purpose: Low-level API interface wrapper for communicating directly with MetaTrader 5 terminal.
Classes:
  - `MT5Gateway`: Wrapper class for MT5 interaction.
Functions:
  - `connect()`: Initializes terminal connection.
  - `get_ticks(symbol, count)`: Retrieves tick stream.
  - `get_candles(symbol, timeframe, count)`: Fetches OHLC dataframe.
  - `send_order(request)`: Submits order request structure to MT5 server.
  - `modify_position(ticket, sl, tp)`: Updates stop loss or take profit.
Inputs: MT5 request dictionaries.
Outputs: MT5 Execution Result, Order Return Codes, Pandas DataFrames.
Dependencies: `MetaTrader5`, `pandas`.
Execution Order: Continuous (Data & Order Execution).
Performance Impact: Dependent on broker network latency (~10-40ms execution time).
Memory Usage: ~30 MB.
Potential Risks: Broker disconnect during order modification.
Improvement Suggestions: Add automatic retry logic for transient network dropouts.


==================================================
5. COMPLETE EXECUTION FLOW
==================================================

1. PROGRAM INITIALIZATION:
   - User or Autostart script executes `python start_aegis.py`.
   - `start_aegis.py` verifies PID lock via `utils/pid_lock.py`.
   - Environment variables are loaded via `config/settings.py`.
   - MT5 Gateway (`modules/mt5_gateway.py`) initializes connection with MetaTrader 5 terminal.
   - SQLite databases (`data/performance.db`, `data/decision_records.db`, `data/trade_memory.db`) are verified and tables initialized.
   - Machine Learning models (LightGBM, PyTorch Neural Nets, RL Checkpoints) are loaded into memory.
   - Watchdog process (`watchdog.py`) starts monitoring process health.

2. MARKET DATA STREAMING & SYNCHRONIZATION:
   - `core/main.py` enters infinite tick scan loop (`while True:`).
   - Ticks are polled from MT5 for target symbols (`XAUUSD`, `EURUSD`).
   - OHLC candles are fetched for multiple timeframes: M1, M5, M15, H1, H4.
   - Data sanity validator (`brain/data_integrity.py`) verifies no missing values, NaN prices, or price zero anomalies exist.

3. FEATURE EXTRACTION & INDICATOR CALCULATION:
   - `brain/feature_pipeline.py` and `modules/feature_factory.py` compute 45+ technical features:
     - Moving Averages (EMA 9, 21, 50, 200).
     - Momentum & Oscillators (RSI 14, MACD 12/26/9, ADX 14, Stochastics).
     - Volatility Metrics (ATR 14, Bollinger Bands 20/2, EGARCH volatility forecast).
     - Statistical Features (Hurst Exponent, Rolling Z-score, Log Returns).
     - Multi-timeframe trend alignment matrix.

4. MULTI-ENGINE SIGNAL GENERATION:
   - Technical Machine Learning Ensemble (`brain/ml_ensemble.py`) generates directional probabilities.
   - Institutional SMC Engine (`brain/smc_engine.py`) scans for BOS, CHoCH, Order Blocks, and FVG Liquidity Sweeps.
   - Deep Reinforcement Learning Agent (`brain/rl_inference.py`) evaluates Q-values/PPO action space (BUY/SELL/HOLD).
   - Kronos Transformer Forecaster (`brain/kronos_forecaster.py`) projects 5-candle forward price path.
   - Statistical Engine (`brain/statistical_engine.py`) determines current market regime (TRENDING / RANGING / HIGH VOLATILITY) via Hidden Markov Models.

5. CONFIDENCE CALCULATION & DECISION FUSION:
   - `brain/confidence_engine.py` aggregates all engine outputs into a normalized confidence score (0-100%).
   - Signal weights are dynamically adjusted based on the active market regime.
   - If confidence is < Minimum Threshold (e.g. 50%), the signal is discarded as `WAIT`.

6. ZERO-BYPASS RISK VALIDATION:
   - If candidate signal is BUY or SELL, `modules/risk_manager.py` executes validation:
     - Check 1: Real-time spread check (spread <= max_spread_pts).
     - Check 2: Account balance & margin check.
     - Check 3: Daily drawdown limit check (daily loss <= max_daily_loss).
     - Check 4: Maximum open trades check (open_positions < max_allowed).
     - Check 5: Position size calculation using Fractional Kelly Criterion / Volatility Parity.
     - Check 6: Hard Stop Loss Floor enforcement (Minimum SL distance guaranteed).

7. ORDER EXECUTION VIA MT5:
   - `modules/mt5_gateway.py` constructs standard `MqlTradeRequest` structure.
   - Order request is dispatched to MT5 broker server via `mt5.order_send()`.
   - Execution result is inspected for return codes (`10009 TRADE_RETCODE_DONE`).
   - If fill fails due to requote/slippage, retry logic handles re-attempt up to max retries.

8. LIVE POSITION MANAGEMENT & EXIT MONITORING:
   - Active position supervisor (`brain/position_supervisor.py`) tracks open trades:
     - Dynamic trailing stop updates based on ATR multiples / SMC structural pivots.
     - Breakeven trigger: Moves SL to entry price once trade reaches target profit threshold.
     - Partial profit taking at key liquidity targets.
     - Invalidation exit if market structure breaks against position.

9. LOGGING, ATTRIBUTION & CONTINUOUS LEARNING:
   - Executed trade details are written to `logs/trades.log` and `data/performance.db`.
   - Decision record (features, model outputs, confidence, outcome) is stored in `data/decision_records.db`.
   - Post-trade performance attribution module (`brain/performance_attribution.py`) logs outcome to update model reliability metrics (`data/model_reliability.sqlite`).
   - Experience buffer accumulates trade samples for online RL fine-tuning (`train_reinforcement.py`).


==================================================
6. CONFIGURATION DOCUMENTATION
==================================================

Config Parameter: `SYMBOL_LIST`
Default Value: `["XAUUSD", "EURUSD"]`
Purpose: Defines the list of active trading symbols monitored by the engine.
Allowed Range: Any valid MT5 broker symbol.
Effect on Trading: Controls market scanning scope.

Config Parameter: `RISK_PER_TRADE_PCT`
Default Value: `1.0` (1% of account equity)
Purpose: Maximum risk allocated to a single trade setup.
Allowed Range: `0.1%` to `3.0%`.
Effect on Trading: Scales lot size dynamically based on stop-loss distance.

Config Parameter: `MIN_CONFIDENCE_THRESHOLD`
Default Value: `50.0` (50%)
Purpose: Minimum fused confidence required to permit trade execution.
Allowed Range: `40.0%` to `80.0%`.
Effect on Trading: Filters low-probability trade signals.

Config Parameter: `MAX_SPREAD_XAUUSD`
Default Value: `35` (35 points / 3.5 pips)
Purpose: Maximum allowable spread for Gold trades.
Allowed Range: `10` to `60` points.
Effect on Trading: Prevents trade execution during high-spread news spikes or illiquid session roll-overs.

Config Parameter: `HARD_SL_FLOOR_PTS`
Default Value: `40` (40 points / 4 pips EURUSD)
Purpose: Absolute minimum stop-loss distance enforced by risk engine.
Allowed Range: `20` to `100` points.
Effect on Trading: Protects against dangerously tight stop losses that would be rejected by broker or instantly stopped out by noise.

Config Parameter: `MAX_DAILY_LOSS_PCT`
Default Value: `5.0` (5% of daily starting equity)
Purpose: Circuit breaker that disables trading if total daily loss exceeds limit.
Allowed Range: `2.0%` to `10.0%`.
Effect on Trading: Prevents catastrophic drawdown during adverse market conditions.

Config Parameter: `USE_SMC_ENGINE`
Default Value: `True`
Purpose: Toggle flag for Smart Money Concepts structural analysis.
Allowed Range: `True` / `False`.
Effect on Trading: Enables Order Block, BOS, CHoCH, and FVG signal generation.


==================================================
7. DATABASE DOCUMENTATION
==================================================

1. Database File: `data/performance.db`
   - Purpose: Stores completed trade execution details, financial performance metrics, and outcome labels.
   - Table: `attributions`
     - Columns:
       - `id` (INTEGER, Primary Key, Autoincrement)
       - `ticket` (INTEGER, MT5 Ticket Number, Indexed)
       - `timestamp` (TEXT, ISO-8601 Timestamp)
       - `symbol` (TEXT)
       - `direction` (TEXT: BUY/SELL)
       - `outcome` (TEXT: WIN/LOSS/BREAKEVEN)
       - `pnl_usd` (REAL, Profit/Loss in USD)
       - `holding_min` (REAL, Trade duration in minutes)
       - `signal_source` (TEXT: SCALP, SMC, ML, RL, DUAL_TIER)
       - `session` (TEXT: ASIA, LONDON, NY, OVERLAP)
       - `confidence` (INTEGER, Confidence score %)
       - `historical_edge` (TEXT)
       - `microstructure_quality` (TEXT)

2. Database File: `data/decision_records.db`
   - Purpose: Real-time decision audit trail logging all evaluated market setups (including rejected ones).
   - Table: `decisions`
     - Columns:
       - `id` (INTEGER, Primary Key)
       - `timestamp` (TEXT)
       - `symbol` (TEXT)
       - `action` (TEXT: BUY/SELL/WAIT)
       - `confidence` (REAL)
       - `regime` (TEXT)
       - `features_json` (TEXT)
       - `model_outputs_json` (TEXT)
       - `risk_approved` (INTEGER: 0/1)

3. Database File: `data/trade_memory.db`
   - Purpose: State buffer tracking active live positions for recovery across system restarts.
   - Table: `active_trades`
     - Columns:
       - `ticket` (INTEGER, Primary Key)
       - `symbol` (TEXT)
       - `direction` (TEXT)
       - `open_price` (REAL)
       - `sl` (REAL)
       - `tp` (REAL)
       - `lot_size` (REAL)
       - `open_time` (TEXT)


==================================================
8. MARKET DATA ENGINE
==================================================

Data Ingestion & Multi-Timeframe Synchronization:
  - Ticks are polled continuously via MT5 API (`mt5.copy_ticks_range`).
  - Historical bars are requested for M1, M5, M15, H1, H4 timeframes.
  - Dataframes are indexed by UTC timestamp and resampled to guarantee uniform candle alignment across timeframes.
  - Session Classifier detects active trading session:
    - Asian Session: 00:00 - 08:00 UTC
    - London Session: 07:00 - 16:00 UTC
    - New York Session: 12:00 - 21:00 UTC
    - London/NY Overlap: 12:00 - 16:00 UTC (Peak Liquidity Window)


==================================================
9. FEATURE ENGINEERING
==================================================

Feature List & Calculation Methods:
1. Technical Indicators:
   - Relative Strength Index (`RSI_14`): Normalized momentum oscillator.
   - Average Directional Index (`ADX_14`): Trend strength indicator.
   - Moving Average Convergence Divergence (`MACD_diff`): Histogram difference between 12 and 26 EMA.
   - Average True Range (`ATR_14`): Volatility measurement normalized by price.
2. Microstructure & Statistical Features:
   - Z-Score of Price (`price_zscore`): Standardized distance of close price from 50-period SMA.
   - Rolling Hurst Exponent (`hurst_exponent`): Measures mean-reverting (<0.5) vs trending (>0.5) regime.
   - Log Returns Volatility (`realized_vol_20`): Standard deviation of 20-period log price returns.
3. Feature Normalization & Scaling:
   - Features are standardized using `RobustScaler` / `StandardScaler` fitted on rolling historical windows to prevent data leakage and handle price outliers.


==================================================
10. TECHNICAL ANALYSIS ENGINE
==================================================

Core Technical Analysis Algorithms:
1. Exponential Moving Average (EMA):
   Formula: EMA_t = Price_t * alpha + EMA_{t-1} * (1 - alpha), where alpha = 2 / (N + 1).
2. Smart Money Concepts (SMC):
   - Break of Structure (BOS): Price candle closing beyond prior swing high/low in direction of prevailing trend.
   - Change of Character (CHoCH): Price candle closing beyond prior swing high/low against prevailing trend, signaling reversal.
   - Order Block (OB): The last opposing candle before an aggressive impulse move that breaks structure.
   - Fair Value Gap (FVG): A 3-candle sequence where Candle 1 High < Candle 3 Low (Bullish FVG) or Candle 1 Low > Candle 3 High (Bearish FVG).


==================================================
11. AI SYSTEM
==================================================

Machine Learning Architecture:
1. LightGBM Gradient Boosting Ensemble:
   - Consists of multiple gradient-boosted decision tree models trained on historical technical features to predict binary direction (1 = Price increases > 1.5 ATR in 10 bars, 0 = Otherwise).
2. PyTorch Deep Neural Network (LSTM / Transformer):
   - Accepts sequential bar tensor (batch, seq_len=30, num_features=45).
   - Architecture: 2 LSTM layers (hidden_dim=128, dropout=0.2) + Fully Connected Dense Layer + Softmax output.
3. ONNX Model Runtime Integration:
   - Models are exported to `.onnx` format for fast SIMD CPU/GPU inference.


==================================================
12. REINFORCEMENT LEARNING
==================================================

Deep Reinforcement Learning Framework:
  - Environment: Custom Gymnasium Environment (`AegisTradingEnv`).
  - State Space: Vector containing technical indicators, active position PnL, account margin level, and current market regime (64 dimensions).
  - Action Space: Discrete(3) -> 0: HOLD / WAIT, 1: BUY, 2: SELL.
  - Reward Function: Differential Sharpe Ratio + Realized PnL ($) - Drawdown Penalty - Transaction Cost (Spread + Commission).
  - Algorithm: Proximal Policy Optimization (PPO) and Deep Q-Network (DQN) with Replay Buffer size = 100,000 transitions.


==================================================
13. CONFIDENCE ENGINE
==================================================

Mathematical Formulation of Confidence Score:
Final Confidence Score C is calculated as a weighted sum of constituent vector scores:

  C = w_ML * S_ML + w_SMC * S_SMC + w_MTF * S_MTF + w_RL * S_RL + w_STAT * S_STAT

Where:
  - S_ML: Machine Learning Ensemble Probability (0 - 100%)
  - S_SMC: SMC Structural Confluence Score (0 - 100%)
  - S_MTF: Multi-Timeframe Trend Alignment Score (0 - 100%)
  - S_RL: Reinforcement Learning Action Q-Value Confidence (0 - 100%)
  - S_STAT: Statistical Volatility & Hurst Score (0 - 100%)
  - Weights w_i sum to 1.0 and adjust based on market regime (e.g. higher w_SMC during RANGING markets, higher w_MTF during TRENDING markets).

Penalty Multipliers:
  - If Spread > Typical Average: Multiplier = 0.85
  - If Timeframe Divergence detected: Multiplier = 0.70


==================================================
14. SIGNAL ENGINE
==================================================

Signal Logic:
  - BUY Signal Triggered when: Fused Confidence >= MIN_CONFIDENCE_THRESHOLD, Direction = BUY, and Risk Validation = APPROVED.
  - SELL Signal Triggered when: Fused Confidence >= MIN_CONFIDENCE_THRESHOLD, Direction = SELL, and Risk Validation = APPROVED.
  - WAIT Signal: Issued whenever Confidence < MIN_CONFIDENCE_THRESHOLD or Risk Engine flags rejection.


==================================================
15. RISK MANAGEMENT
==================================================

Zero-Bypass Risk Enforcements:
1. Dynamic Position Sizing:
   Lot Size = (Account Equity * Risk_Pct) / (SL_Distance_In_Pips * Pip_Value)
2. Stop-Loss (SL) & Take-Profit (TP) Logic:
   - Scalp Mode: SL = 1.5 * ATR(14), TP = 3.0 * ATR(14) (Risk Reward Ratio = 1:2).
   - SMC Mode: SL set beyond Order Block / Structural Pivot + 5 points buffer; TP set at unmitigated liquidity target (RR 1:3+).
3. Circuit Breaker Controls:
   - Max Daily Loss: 5% of starting balance.
   - Max Open Positions: 5 concurrent trades.
   - Maximum Spread Limit: Hard cutoff at 35 points for Gold, 20 points for EURUSD.


==================================================
16. EXECUTION ENGINE
==================================================

MT5 Order Routing & Reliability:
  - Fills via `ORDER_FILLING_IOC` (Immediate-or-Cancel) or `ORDER_FILLING_FOK` (Fill-or-Kill) based on broker terminal capability.
  - Retries: Up to 3 execution attempts with exponential backoff (100ms, 300ms, 700ms) upon receiving transient error codes (`10004 REQUOTE`, `10018 MARKET_CLOSED`).


==================================================
17. POSITION MANAGEMENT
==================================================

Live Position Supervisor:
  - Trailing Stop: Moves SL behind price once trade reaches 1.0 * ATR profit, locking in gains.
  - Breakeven Trigger: Automatically shifts SL to `open_price + spread` once profit exceeds 1.5 * ATR.
  - Partial Take Profit: Closes 50% of lot size at 1:1 Risk-Reward ratio, allowing remaining 50% to run to full TP target.


==================================================
18. TRAINING SYSTEM
==================================================

Continuous & Incremental AI Training:
  - Offline Training: Scripts (`train_institutional_ai.py`, `train_unified_gpu_brain.py`) fit PyTorch deep learning models on multi-year M1/M5 historical data using CUDA acceleration.
  - Online Incremental Learning: `brain/adaptive_learning.py` updates LightGBM leaf nodes and RL policy buffers periodically using recently logged trade outcomes.


==================================================
19. PERFORMANCE OPTIMIZATION
==================================================

Optimizations Implemented:
  - PyTorch CUDA GPU Inference: Offloads matrix multiplications to GPU VRAM.
  - Process Vectorization: Replaced Python loops with NumPy vector operations for indicator calculations.
  - Memory Management: Garbage collection enforced after heavy feature generation cycles.
  - Database Indexing: SQLite tables indexed on `ticket`, `timestamp`, and `symbol` columns for instant lookups.


==================================================
20. LOGGING SYSTEM
==================================================

Log Architecture & Files:
1. `logs/aegis.log`: High-level operational events and decision summaries.
2. `logs/trades.log`: Structured JSON logs for every trade signal, order submission, and modification event.
3. `logs/errors.log`: Detailed stack tracebacks for exceptions.
4. Log Rotation: Standard `RotatingFileHandler` with 5 MB max file size and up to 5 backup files.


==================================================
21. SECURITY
==================================================

Security Policies & Practices:
  - Environment Credentials: Broker logins, passwords, and Telegram bot API keys are isolated in `.env` files and excluded from git source control (`.gitignore`).
  - Single Instance Protection: PID file lock (`utils/pid_lock.py`) prevents unauthorized concurrent bot executions on the host system.


==================================================
22. ERROR HANDLING
==================================================

Exception Catching & System Resiliency:
  - MT5 API Failures: Re-initializes MT5 connection automatically upon connection drop.
  - Database Locks: Implements `timeout=10.0` seconds on SQLite connections to handle concurrent write operations without crashing.
  - Invalid Signal Protection: Pre-execution validation checks enforce non-null prices and non-zero stop loss levels.


==================================================
23. MODEL MANAGEMENT
==================================================

Model Lifecycle & Deployment:
  - Champion-Challenger Framework (`brain/champion_challenger.py`): New candidate models are validated in shadow mode (`brain/shadow_auditor.py`) against live market data before replacing active production weights.
  - Rollback Mechanism: Automated rollback restores previous model checkpoint if challenger win rate falls below baseline during evaluation.


==================================================
24. COMPLETE TRADING STRATEGY
==================================================

Strategy Execution Logic:
1. Regime Identification: Hidden Markov Model determines if price is in Trending or Ranging state.
2. Multi-Timeframe Alignment: H1 and M15 trends must agree on direction (e.g. both EMA 21 > EMA 50).
3. SMC Liquidity Setup: Price sweeps prior liquidity high/low and forms an Order Block + FVG on M1/M5.
4. AI Model Confluence: LightGBM and Neural Net output directional probability > 60%.
5. Risk & Spread Check: Real-time spread is below max threshold, account has available margin.
6. Execution & Management: Position opened with hard SL, partial profit taken at 1:1 RR, trailing stop activated to lock in profit.


==================================================
25. COMPLETE MATHEMATICAL FOUNDATION
==================================================

1. Relative Strength Index (RSI):
   RS = Average Gain / Average Loss over N periods.
   RSI = 100 - (100 / (1 + RS))

2. Average True Range (ATR):
   TR = max(High - Low, |High - Close_{prev}|, |Low - Close_{prev}|)
   ATR_t = (ATR_{prev} * (N - 1) + TR_t) / N

3. Fractional Kelly Criterion Sizing:
   f* = (p * b - q) / b
   Where p = Win Rate, q = Loss Rate (1 - p), b = Win/Loss Ratio. Position size is scaled by a conservative fraction (e.g. 0.25 * f*).

4. Hurst Exponent:
   E[R(n)/S(n)] = C * n^H as n -> infinity.
   H < 0.5 indicates mean-reverting series; H > 0.5 indicates trending series.


==================================================
26. COMPLETE AI PIPELINE
==================================================

Raw Market Ticks/Candles -> Feature Engineering & Standardization -> Parallel Engine Inference (ML Ensemble, SMC, RL Agent, Kronos Forecaster) -> Fused Confidence Calculation -> Zero-Bypass Risk Validation -> Order Dispatch to MT5 -> Live Trade Monitoring & Trailing -> Outcome Attribution & SQLite Storage -> Continuous Model Fine-Tuning.


==================================================
27. COMPLETE CALL GRAPH
==================================================

start_aegis.py:main()
  ↓
utils.pid_lock.acquire_lock()
  ↓
core.main.AegisEngine.initialize()
  ├── modules.mt5_gateway.MT5Gateway.connect()
  ├── brain.ml_ensemble.MLEnsemble.load_models()
  └── data.init_databases()
  ↓
core.main.AegisEngine.run_loop()
  ├── modules.mt5_gateway.get_candles()
  ├── brain.feature_pipeline.compute_features()
  ├── brain.smc_engine.analyze_structure()
  ├── brain.ml_ensemble.predict()
  ├── brain.confidence_engine.calculate_confidence()
  ├── modules.risk_manager.validate_trade()
  │     ├── (If Approved) -> modules.mt5_gateway.send_order()
  │     └── (If Rejected) -> brain.observability.log_rejection()
  ├── brain.position_supervisor.manage_positions()
  └── brain.attribution_writer.log_trade_outcome()


==================================================
28. COMPLETE DATA FLOW
==================================================

Market Tick Data (MT5 Terminal)
       │
       ▼
Feature Generation (NumPy / Pandas)
       │
       ▼
Engine Predictions (PyTorch / LightGBM / SMC / RL)
       │
       ▼
Confidence Engine (Fused Score %)
       │
       ▼
Risk Manager (Lot Sizing & SL Floor Checks)
       │
       ▼
Order Request (MqlTradeRequest to MT5 Server)
       │
       ▼
Position Supervisor (Live Trailing & Exit Enforcement)
       │
       ▼
Database Logging (SQLite performance.db & decision_records.db)


==================================================
29. PERFORMANCE BOTTLENECKS
==================================================

Identified Bottlenecks & Solutions:
1. Sequential Technical Feature Calculations:
   - Solution: Pre-allocate memory buffers and utilize vectorized NumPy expressions.
2. SQLite Concurrent Writes:
   - Solution: Enable Write-Ahead Logging (WAL mode) and route write operations through an asynchronous queue thread.
3. MT5 Network Polling Latency:
   - Solution: Use local memory cache for recent candle frames and poll tick updates at 50ms intervals.


==================================================
30. IMPROVEMENT SUGGESTIONS
==================================================

1. Architectural Improvements:
   - Convert tick processing loop to an event-driven `asyncio` architecture.
2. Machine Learning Enhancements:
   - Fully transition all PyTorch models to ONNX Runtime with TensorRT GPU acceleration.
3. Risk Management Enhancements:
   - Add real-time multi-asset correlation matrix analysis to prevent simultaneous exposure to highly correlated pairs.


==================================================
31. FULL DEPENDENCY GRAPH
==================================================

start_aegis.py
  └── core/main.py
       ├── config/settings.py
       ├── modules/mt5_gateway.py
       ├── modules/risk_manager.py
       ├── brain/feature_pipeline.py
       ├── brain/ml_ensemble.py
       │    ├── torch
       │    ├── lightgbm
       │    └── numpy
       ├── brain/smc_engine.py
       ├── brain/confidence_engine.py
       ├── brain/position_supervisor.py
       ├── brain/observability.py
       └── data/ (SQLite3)


==================================================
32. CODE QUALITY REVIEW
==================================================

Codebase Assessment:
  - Modularity: High. Systems are divided cleanly across `brain/`, `core/`, `modules/`, and `config/`.
  - Reliability: High. Multiple safety layers (Zero-Bypass Risk Manager, Hard Stop Floor, PID Lock, Watchdog Process) prevent catastrophic loss or unmonitored runtime crashes.
  - Maintainability: Good. Functions are modular and utilize structured type annotations across core packages.


==================================================
33. FINAL SYSTEM SUMMARY
==================================================

The Aegis Gold Quant Trading System represents an advanced institutional-grade algorithmic trading engine. By unifying classic technical indicators, institutional Smart Money Concepts (BOS, CHoCH, Order Blocks, FVGs), deep machine learning ensembles, sequence forecasting transformers, and reinforcement learning policy agents under a strict Zero-Bypass Risk Manager, Aegis Gold achieves robust, automated execution on MetaTrader 5.

Key System Strengths:
1. Multi-Engine Fusion: Prevents single-model failure by requiring agreement across ML, SMC, and Trend analysis.
2. Uncompromising Risk Management: Absolute enforcement of hard stop-loss floors, lot size rules, and daily drawdown circuit breakers.
3. High Performance: Optimized for low latency with GPU acceleration, ONNX models, and vectorized feature construction.
4. Comprehensive Observability: Full auditing of every decision, signal, and execution in persistent SQLite databases and real-time Telegram alerts.

==================================================
END OF TECHNICAL DOCUMENTATION
==================================================
