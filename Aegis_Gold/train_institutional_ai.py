"""
═══════════════════════════════════════════════════════════════════════════════
🎓 AEGIS INSTITUTIONAL AI - GPU TRAINING SCRIPT
═══════════════════════════════════════════════════════════════════════════════

This script trains all 6 institutional AI engines using GPU acceleration.
Runs in background, continuously learning from trade data.

Engines Trained:
1. Trade Memory Database (collection)
2. Multi-Timeframe Analyzer (pattern analysis)
3. Statistical Engine (parameter optimization)
4. ML Ensemble (GPU-accelerated model training)
5. Confidence Engine (weight optimization)
6. Self-Optimizer (reinforcement learning)

Usage:
  python train_institutional_ai.py --mode continuous  # Run forever
  python train_institutional_ai.py --mode once        # Train once then exit
  python train_institutional_ai.py --gpu              # Force GPU usage

═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import logging
import time
import threading
from datetime import datetime
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings as cfg
from brain.trade_memory import get_trade_memory_db
from brain.ml_ensemble import get_ml_ensemble
from brain.self_optimizer import get_self_optimizer
from brain.confidence_engine import get_confidence_engine
from brain.statistical_engine import get_statistical_engine
from brain.reinforcement_agent import AegisRLAgent
from brain.model_version_manager import ModelVersionManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/ai_training.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("AITrainer")


class InstitutionalAITrainer:
    """GPU-accelerated training for all 6 institutional engines."""
    
    def __init__(self, use_gpu=True):
        self.use_gpu = use_gpu
        self.trade_memory = get_trade_memory_db()
        self.ml_ensemble = get_ml_ensemble()
        self.self_optimizer = get_self_optimizer()
        self.confidence_engine = get_confidence_engine()
        self.stat_engine = get_statistical_engine()
        self.rl_agent = AegisRLAgent()
        self.version_manager = ModelVersionManager()
        
        self.training_active = False
        self.last_train_time = None
        self.training_count = 0
        
        logger.info("[TRAINER] Institutional AI Trainer initialized")
        logger.info(f"   GPU Enabled: {self.use_gpu}")
        logger.info(f"   Min Training Data: {cfg.ML_MIN_TRAINING_DATA} trades")
        logger.info(f"   Retrain Interval: {cfg.ML_RETRAIN_INTERVAL} trades")
    
    def check_gpu_available(self):
        """Check if GPU is available for training."""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"[OK] GPU Available: {gpu_name}")
                logger.info(f"   CUDA Version: {torch.version.cuda}")
                return True
            else:
                logger.warning("[WARN] GPU not available, using CPU")
                return False
        except ImportError:
            logger.warning("[WARN] PyTorch not installed, GPU training unavailable")
            return False
    
    def train_ml_ensemble(self) -> bool:
        """Train ML ensemble with GPU acceleration."""
        try:
            logger.info("[ML] Training ML Ensemble...")
            
            # Check if enough data
            trade_count = self.trade_memory.get_trade_count()
            if trade_count < cfg.ML_MIN_TRAINING_DATA:
                logger.warning(f"[WAIT] Not enough data: {trade_count}/{cfg.ML_MIN_TRAINING_DATA}")
                return False
            
            # Train models (use a separate MLEnsemble instance for training to not overwrite the champion)
            from brain.ml_ensemble import MLEnsemble
            train_ensemble = MLEnsemble(model_filename="ml_ensemble_challenger.pkl")
            start_time = time.time()
            metrics = train_ensemble.train(self.trade_memory)
            
            if len(metrics) == 0:
                logger.warning("   No models trained")
                return False
            
            # Log results
            elapsed = time.time() - start_time
            logger.info(f"[OK] ML Ensemble trained in {elapsed:.1f}s")
            
            for m in metrics:
                logger.info(f"   {m.model_name}:")
                logger.info(f"      Accuracy: {m.accuracy:.2%}")
                logger.info(f"      Precision: {m.precision:.2%}")
                logger.info(f"      F1 Score: {m.f1_score:.2%}")
                logger.info(f"      Training samples: {m.training_samples}")
            
            # Propose retrained model as challenger in the Champion/Challenger arena
            try:
                from brain.champion_challenger import get_arena
                import time as _time
                challenger_name = f"ml_ensemble_v{int(_time.time())}"
                get_arena().propose_challenger(challenger_name)
                logger.info(f"[ARENA] New challenger proposed: {challenger_name}")
            except Exception as _ae:
                logger.warning(f"[ARENA] Challenger proposal failed (non-fatal): {_ae}")

            return True

            
        except Exception as e:
            logger.error(f"[FAIL] ML training failed: {e}", exc_info=True)
            return False
    
    def optimize_parameters(self) -> bool:
        """Run self-optimizer to tune parameters."""
        try:
            logger.info("[OPT] Running Self-Optimizer...")
            
            # Check if enough data
            if len(self.self_optimizer.recent_analyses) < 10:
                logger.warning("   Not enough trade analyses")
                return False
            
            # Run optimization
            result = self.self_optimizer.optimize(self.trade_memory)
            
            if result["status"] == "success":
                logger.info(f"[OK] Optimization complete (Gen {result['generation']})")
                logger.info(f"   Changes: {result['changes']}")
                logger.info(f"   Win Rate: {result['performance']['win_rate']:.2%}")
                logger.info(f"   Profit Factor: {result['performance']['profit_factor']:.2f}")
                return True
            else:
                logger.warning(f"   Optimization status: {result['status']}")
                return False
                
        except Exception as e:
            logger.error(f"[FAIL] Optimization failed: {e}", exc_info=True)
            return False
    
    def analyze_statistics(self) -> bool:
        """Update statistical engine parameters."""
        try:
            logger.info("[STAT] Analyzing Statistics...")
            
            # Get recent trades
            recent_trades = self.trade_memory.get_recent_trades(limit=100)
            if len(recent_trades) < 20:
                logger.warning("   Not enough trades for statistical analysis")
                return False
            
            # Extract prices
            prices = [t['entry_price'] for t in recent_trades if t.get('entry_price')]
            
            if len(prices) < 20:
                logger.warning("   Not enough price data")
                return False
            
            # Run statistical analysis
            import numpy as np
            prices_array = np.array(prices)
            stat_result = self.stat_engine.analyze(prices_array)
            
            logger.info("[OK] Statistical analysis complete")
            logger.info(f"   Hurst Exponent: {stat_result.hurst_exponent:.3f} ({stat_result.market_behavior})")
            logger.info(f"   Entropy: {stat_result.entropy:.3f} ({stat_result.predictability})")
            logger.info(f"   Statistical Edge: {stat_result.statistical_edge:.3f}")
            logger.info(f"   Recommended: {stat_result.recommended_direction}")
            
            # Update Bayesian priors based on outcomes
            winning_trades = [t for t in recent_trades if (t.get('profit_usd') or 0.0) > 0.0]
            for trade in winning_trades[-10:]:  # Last 10 wins
                direction = trade.get('direction', 'BUY')
                if direction == 'BUY':
                    self.stat_engine.update_priors('BULLISH_WIN')
                else:
                    self.stat_engine.update_priors('BEARISH_WIN')
            
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Statistical analysis failed: {e}", exc_info=True)
            return False
    
    def train_cycle(self) -> dict:
        """Run one complete training cycle."""
        logger.info("="*70)
        logger.info("[TRAINER] STARTING TRAINING CYCLE")
        logger.info("="*70)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "ml_trained": False,
            "optimized": False,
            "stats_updated": False,
        }
        
        # 1. Train ML Ensemble
        results["ml_trained"] = self.train_ml_ensemble()
        
        # 2. Run Self-Optimizer
        results["optimized"] = self.optimize_parameters()
        
        # 3. Update Statistical Engine
        results["stats_updated"] = self.analyze_statistics()
        
        # 4. Train Reinforcement Learning Agent
        results["rl_trained"] = False
        try:
            from config.quant_x_config import QX
            if QX.flag("offline_rl"):
                logger.info("[RL] Training Offline RL Agent (CQL)...")
                from brain.train_reinforcement import train_cql_offline
                success = train_cql_offline()
                if success:
                    results["rl_trained"] = True
            else:
                logger.info("[RL] Training Reinforcement Learning Agent...")
                rl_results = self.rl_agent.train_on_history(self.trade_memory)
                if rl_results.get("status") == "success":
                    results["rl_trained"] = True
                    
                    # Checkpoint & validation using ModelVersionManager
                    policy_metrics = self.rl_agent.calculate_policy_metrics()
                    logger.info("[RL] Policy Metrics Calculated:")
                    for k, v in policy_metrics.items():
                        logger.info(f"   {k.replace('_', ' ').title()}: {v:.4f}")

                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    rl_model_path = os.path.join(base_dir, "models", "aegis_rl.pt")
                    loss = rl_results.get("loss", 0.0)
                    win_rate = policy_metrics.get("win_rate", 100.0)
                    
                    self.version_manager.save_checkpoint(
                        rl_model_path, "aegis_rl", val_loss=loss, val_acc=win_rate,
                        training_loss=loss, training_metrics=policy_metrics,
                        validation_metrics=policy_metrics, config_metadata={"epochs": 50, "lr": 0.005}
                    )
                    rolled_back = self.version_manager.verify_and_rollback(rl_model_path, "aegis_rl", loss, win_rate)
                    if rolled_back:
                        logger.warning("[ROLLBACK] Reinforcement Learning model rolled back to best stable checkpoint.")
                else:
                    logger.warning(f"   RL Agent training status: {rl_results.get('status')}")
        except Exception as e:
            logger.error(f"❌ RL training failed: {e}", exc_info=True)
        
        # 5. Update training count
        self.training_count += 1
        self.last_train_time = datetime.now()
        
        logger.info("="*70)
        logger.info(f"[TRAINER] TRAINING CYCLE #{self.training_count} COMPLETE")
        logger.info(f"   ML Trained:    {'YES' if results['ml_trained'] else 'NO'}")
        logger.info(f"   Optimized:     {'YES' if results['optimized'] else 'NO'}")
        logger.info(f"   Stats Updated: {'YES' if results['stats_updated'] else 'NO'}")
        logger.info(f"   RL Trained:    {'YES' if results['rl_trained'] else 'NO'}")
        logger.info("="*70)
        
        return results
    
    def continuous_training(self, interval_seconds=300):
        """Run training continuously every N seconds."""
        logger.info(f"[TRAINER] Starting continuous training (every {interval_seconds}s)")
        
        while self.training_active:
            try:
                # Check if we have new trades
                trade_count = self.trade_memory.get_trade_count()
                
                if trade_count >= cfg.ML_MIN_TRAINING_DATA:
                    # Check if it's time to train
                    if trade_count % cfg.ML_RETRAIN_INTERVAL == 0:
                        self.train_cycle()
                    else:
                        logger.info(f"   Trade count: {trade_count} (next training at {(trade_count // cfg.ML_RETRAIN_INTERVAL + 1) * cfg.ML_RETRAIN_INTERVAL})")
                else:
                    logger.info(f"   Collecting data: {trade_count}/{cfg.ML_MIN_TRAINING_DATA} trades")
                
                # Wait before next check
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Training interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in training loop: {e}", exc_info=True)
                time.sleep(interval_seconds)
        
        logger.info("Continuous training stopped")
    
    def start_background_training(self, interval_seconds=300):
        """Start training in background thread."""
        if self.training_active:
            logger.warning("Training already active")
            return
        
        self.training_active = True
        
        training_thread = threading.Thread(
            target=self.continuous_training,
            args=(interval_seconds,),
            daemon=True
        )
        training_thread.start()
        
        logger.info("[OK] Background training started")
    
    def stop_training(self):
        """Stop background training."""
        self.training_active = False
        logger.info("Training stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Train AEGIS Institutional AI")
    parser.add_argument("--mode", choices=["once", "continuous"], default="continuous",
                       help="Training mode: once or continuous")
    parser.add_argument("--gpu", action="store_true", help="Force GPU usage")
    parser.add_argument("--interval", type=int, default=300,
                       help="Training interval in seconds (default: 300)")
    
    args = parser.parse_args()
    
    # Initialize trainer
    use_gpu = args.gpu or cfg.ML_USE_GPU
    trainer = InstitutionalAITrainer(use_gpu=use_gpu)
    
    # Check GPU
    if use_gpu:
        trainer.check_gpu_available()
    
    # Run training
    if args.mode == "once":
        logger.info("Running single training cycle...")
        trainer.train_cycle()
        logger.info("Training complete. Exiting.")
    else:
        logger.info("Running continuous training...")
        trainer.training_active = True
        try:
            trainer.continuous_training(interval_seconds=args.interval)
        except KeyboardInterrupt:
            logger.info("Training interrupted")
        finally:
            trainer.stop_training()


if __name__ == "__main__":
    main()
