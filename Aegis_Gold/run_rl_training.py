"""
════════════════════════════════════════════════════════════════════
🧠 AEGIS REINFORCEMENT LEARNING TRAINING RUNNER
════════════════════════════════════════════════════════════════════

Continuously trains the Aegis RL Q-Network + all institutional AI
engines (ML Ensemble, Self-Optimizer, Statistical Engine,
Confidence Engine) in a background CMD process.

Usage:
  python run_rl_training.py              → runs continuous loop
  python run_rl_training.py --once       → single training cycle then exit
  python run_rl_training.py --interval 120  → train every 120 seconds

════════════════════════════════════════════════════════════════════
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime

# ── Path fix ─────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Logging setup ─────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/rl_training.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("RL_TRAINER")

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║   AEGIS REINFORCEMENT LEARNING TRAINER — BACKEND ENGINE          ║
║   Trains: RL Q-Network | ML Ensemble | Self-Optimizer            ║
║   Statistical Engine | Confidence Engine | Replay Buffer         ║
╚══════════════════════════════════════════════════════════════════╝
"""


def check_gpu():
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"[OK] GPU Available: {gpu_name} (CUDA {torch.version.cuda})")
            return True
        else:
            logger.warning("[WARN] GPU not available — training on CPU")
            return False
    except ImportError:
        logger.error("[ERR] PyTorch not installed — cannot train RL network")
        return False


def run_single_cycle(trainer) -> dict:
    logger.info("=" * 65)
    logger.info(f"[CYCLE] TRAINING CYCLE #{trainer.training_count + 1} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 65)
    results = trainer.train_cycle()
    logger.info("=" * 65)
    logger.info(f"[RESULT] ML Ensemble : {'TRAINED' if results.get('ml_trained') else 'SKIPPED'}")
    logger.info(f"[RESULT] Self-Opt    : {'OPTIMIZED' if results.get('optimized') else 'SKIPPED'}")
    logger.info(f"[RESULT] Statistics  : {'UPDATED' if results.get('stats_updated') else 'SKIPPED'}")
    logger.info(f"[RESULT] RL Network  : {'TRAINED' if results.get('rl_trained') else 'SKIPPED'}")
    logger.info("=" * 65)
    return results


def continuous_loop(trainer, interval_seconds: int):
    logger.info(f"[START] Continuous RL training loop (interval: {interval_seconds}s)")
    cycle = 0
    while True:
        try:
            cycle += 1
            run_single_cycle(trainer)
        except KeyboardInterrupt:
            logger.info("[STOP] Training stopped by user (Ctrl+C)")
            break
        except Exception as exc:
            logger.error(f"[ERR] Cycle #{cycle} error: {exc}", exc_info=True)

        logger.info(f"[WAIT] Next training cycle in {interval_seconds}s... (Ctrl+C to stop)")
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("[STOP] Training stopped by user (Ctrl+C)")
            break


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(description="Aegis RL Training Backend")
    parser.add_argument("--once", action="store_true", help="Run single cycle then exit")
    parser.add_argument("--interval", type=int, default=300,
                        help="Seconds between training cycles (default: 300)")
    parser.add_argument("--gpu", action="store_true", help="Force GPU usage")
    args = parser.parse_args()

    gpu_ok = check_gpu()

    try:
        from train_institutional_ai import InstitutionalAITrainer
        from config import settings as cfg

        use_gpu = args.gpu or getattr(cfg, 'ML_USE_GPU', True)
        trainer = InstitutionalAITrainer(use_gpu=use_gpu and gpu_ok)

        logger.info(f"[INFO] Min training data : {cfg.ML_MIN_TRAINING_DATA} trades")
        logger.info(f"[INFO] Retrain interval  : {cfg.ML_RETRAIN_INTERVAL} trades")
        logger.info(f"[INFO] Confidence gate   : {cfg.MIN_CONFIDENCE_THRESHOLD}% (LOCKED AT 80%)")

        trade_count = trainer.trade_memory.get_trade_count()
        logger.info(f"[INFO] Trade records     : {trade_count} trades in memory")

        if args.once:
            logger.info("[MODE] Single training cycle mode")
            run_single_cycle(trainer)
            logger.info("[DONE] Single cycle complete. Exiting.")
        else:
            continuous_loop(trainer, args.interval)

    except ImportError as e:
        logger.error(f"[ERR] Import error: {e}")
        logger.error("      Make sure you run from d:\\Trading\\Aegis_Gold\\")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[ERR] Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
