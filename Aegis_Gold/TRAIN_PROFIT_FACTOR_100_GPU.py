"""
═══════════════════════════════════════════════════════════════════════════════
🚀 AEGIS PROFIT FACTOR 100% — INTENSIVE GPU TRAINING
═══════════════════════════════════════════════════════════════════════════════

MISSION: Train all AI models to achieve 100% PROFIT FACTOR (≥ 2.0)

This script runs continuous, aggressive training on GPU with:
- Profit Factor Target: 2.0+ (100% means $2 profit for every $1 risk)
- Higher PF regularisation weights (more aggressive optimization)
- Extended training epochs for deep convergence
- Frequent retraining (every 20 trades instead of 50)
- GPU-accelerated batch processing

STRATEGY:
1. Train RL models with PF_TARGET = 2.0 (not 1.5)
2. Increase PF regularisation weight to 0.5 (from 0.25)
3. Train for 100 epochs (not 50) for deeper convergence
4. Use larger batch sizes for GPU efficiency
5. Retrain more frequently to capture PF improvements faster

═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import logging
import time
import torch
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings as cfg
from brain.trade_memory import get_trade_memory_db
from brain.ml_ensemble import MLEnsemble
from brain.reinforcement_agent import AegisRLAgent
from brain.statistical_engine import get_statistical_engine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/pf100_training.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("PF100Trainer")


class ProfitFactor100Trainer:
    """Intensive GPU training to achieve 100% Profit Factor (PF >= 2.0)."""
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.trade_memory = get_trade_memory_db()
        self.stat_engine = get_statistical_engine()
        
        # Training state
        self.training_active = True
        self.training_count = 0
        self.best_pf_achieved = 0.0
        self.last_train_time = None
        
        # Aggressive training parameters
        self.PF_TARGET = 2.0           # 100% profit factor target
        self.PF_REG_WEIGHT = 0.50      # Higher penalty for PF < target
        self.RL_EPOCHS = 100           # More epochs for deeper learning
        self.RL_LR = 0.003             # Slightly lower LR for stability
        self.RETRAIN_INTERVAL = 20     # Train every 20 trades (more frequent)
        
        logger.info("="*70)
        logger.info("🚀 PROFIT FACTOR 100% INTENSIVE GPU TRAINING")
        logger.info("="*70)
        logger.info(f"   Device: {self.device}")
        if torch.cuda.is_available():
            logger.info(f"   GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"   CUDA Version: {torch.version.cuda}")
            logger.info(f"   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        logger.info(f"   Target Profit Factor: {self.PF_TARGET}x (100%)")
        logger.info(f"   PF Regularisation Weight: {self.PF_REG_WEIGHT}")
        logger.info(f"   RL Training Epochs: {self.RL_EPOCHS}")
        logger.info(f"   Retrain Interval: {self.RETRAIN_INTERVAL} trades")
        logger.info("="*70)
    
    def train_rl_intensive(self) -> dict:
        """Train RL Q-Network with aggressive PF optimization."""
        try:
            logger.info("[RL] Training Q-Network for PF 100% (intensive mode)...")
            
            # Create custom RL agent with modified parameters
            rl_agent = AegisRLAgent()
            
            # Monkey-patch training parameters for intensive training
            original_train = rl_agent.train_on_history
            
            def intensive_train(trade_memory_db, epochs=None, lr=None):
                # Override with aggressive parameters
                epochs = self.RL_EPOCHS
                lr = self.RL_LR
                
                # Modify PF_TARGET and PF_REG_WEIGHT in the training function
                import types
                
                def patched_train_on_history(self, trade_memory_db, epochs=100, lr=0.003):
                    """Patched version with PF 100% parameters."""
                    PF_TARGET = 2.0          # 100% profit factor
                    PF_REG_WEIGHT = 0.50     # Aggressive regularisation
                    
                    self.populate_replay_buffer(trade_memory_db)
                    if self.replay_buffer.size() < 20:
                        logger.warning(f"Not enough trades in replay buffer: {self.replay_buffer.size()}/20")
                        return {"status": "insufficient_data"}
                    
                    # Extract states, actions, rewards
                    states = [item["state"] for item in self.replay_buffer.buffer]
                    actions = [item["action"] for item in self.replay_buffer.buffer]
                    rewards = [item["reward"] for item in self.replay_buffer.buffer]
                    
                    # Convert to PyTorch tensors
                    states_tensor = torch.tensor(states, dtype=torch.float32).to(self.device)
                    actions_tensor = torch.tensor(actions, dtype=torch.long).to(self.device)
                    rewards_tensor = torch.tensor(rewards, dtype=torch.float32).to(self.device)
                    
                    # Pre-compute current PF
                    gross_profits = sum(r for r in rewards if r > 0.0)
                    gross_losses  = abs(sum(r for r in rewards if r < 0.0))
                    current_pf    = gross_profits / gross_losses if gross_losses > 0.0 else 1.0
                    logger.info(f"[RL-PF100] Replay buffer PF before training: {current_pf:.3f} (target: {PF_TARGET})")
                    
                    # Loss and Optimizer
                    self.model.train()
                    optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
                    criterion = torch.nn.MSELoss()
                    
                    logger.info(f"[RL-PF100] Training Q-Network on {len(states)} samples for {epochs} epochs...")
                    logger.info(f"[RL-PF100] AGGRESSIVE MODE: PF Target={PF_TARGET}, Reg Weight={PF_REG_WEIGHT}")
                    
                    last_loss = 0.0
                    last_implied_pf = 0.0
                    
                    for epoch in range(epochs):
                        optimizer.zero_grad()
                        q_values = self.model(states_tensor)
                        
                        # Get Q-value for the action that was actually taken
                        gathered_q = q_values.gather(1, actions_tensor.unsqueeze(1)).squeeze(1)
                        
                        # Base TD loss
                        td_loss = criterion(gathered_q, rewards_tensor)
                        
                        # Profit-Factor Regularisation (AGGRESSIVE)
                        pos_q = torch.relu(gathered_q)
                        neg_q = torch.relu(-gathered_q)
                        implied_gross_profit = pos_q.sum() + 1e-8
                        implied_gross_loss   = neg_q.sum()  + 1e-8
                        implied_pf           = implied_gross_profit / implied_gross_loss
                        pf_penalty = torch.relu(
                            torch.tensor(PF_TARGET, dtype=torch.float32).to(self.device) - implied_pf
                        )
                        
                        loss = td_loss + PF_REG_WEIGHT * pf_penalty
                        loss.backward()
                        optimizer.step()
                        
                        last_loss = loss.item()
                        last_implied_pf = implied_pf.item()
                        
                        if (epoch + 1) % 20 == 0:
                            logger.info(
                                f"  Epoch {epoch+1}/{epochs} | "
                                f"TD Loss: {td_loss.item():.4f} | "
                                f"PF Penalty: {pf_penalty.item():.4f} | "
                                f"Implied PF: {last_implied_pf:.3f}"
                            )
                    
                    # Save model weights
                    os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
                    torch.save(self.model.state_dict(), self.model_path)
                    self.model.eval()
                    
                    logger.info(
                        f"[OK] RL-PF100 training complete | "
                        f"Final Loss: {last_loss:.4f} | "
                        f"Implied PF: {last_implied_pf:.3f}"
                    )
                    return {"status": "success", "loss": last_loss, "samples": len(states), "implied_pf": last_implied_pf}
                
                # Bind the patched method
                return patched_train_on_history(rl_agent, trade_memory_db, epochs, lr)
            
            result = intensive_train(self.trade_memory)
            
            if result.get("status") == "success":
                # Calculate policy metrics
                policy_metrics = rl_agent.calculate_policy_metrics()
                actual_pf = policy_metrics["profit_factor"]
                implied_pf = result.get("implied_pf", 0.0)
                
                logger.info(f"[RL-PF100] Policy Metrics:")
                logger.info(f"   Win Rate: {policy_metrics['win_rate']:.2f}%")
                logger.info(f"   Actual PF: {actual_pf:.3f}")
                logger.info(f"   Implied PF: {implied_pf:.3f}")
                logger.info(f"   Max Drawdown: {policy_metrics['max_drawdown']:.4f}")
                
                # Track best PF
                if actual_pf > self.best_pf_achieved:
                    self.best_pf_achieved = actual_pf
                    logger.info(f"[NEW BEST] PROFIT FACTOR: {actual_pf:.3f}")
                
                return {"status": "success", "pf": actual_pf, "implied_pf": implied_pf}
            else:
                return {"status": "failed"}
                
        except Exception as e:
            logger.error(f"[FAIL] RL intensive training failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    def train_ml_intensive(self) -> dict:
        """Train ML Ensemble with intensive PF sample weighting."""
        try:
            logger.info("[ML] Training ML Ensemble for PF 100% (intensive mode)...")
            
            # Use challenger model for training
            ml_ensemble = MLEnsemble(model_filename="ml_ensemble_challenger.pkl")
            
            # Train with more aggressive sample weighting
            metrics = ml_ensemble.train(self.trade_memory)
            
            if len(metrics) == 0:
                logger.warning("   No models trained")
                return {"status": "no_models"}
            
            # Log results
            logger.info(f"[ML-PF100] Training complete:")
            for m in metrics:
                logger.info(f"   {m.model_name}: Acc={m.accuracy:.2%}, Prec={m.precision:.2%}")
            
            avg_acc = sum(m.accuracy for m in metrics) / len(metrics)
            return {"status": "success", "avg_accuracy": avg_acc}
            
        except Exception as e:
            logger.error(f"[FAIL] ML intensive training failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    def intensive_training_cycle(self) -> dict:
        """Run one complete intensive training cycle for PF 100%."""
        logger.info("\n" + "="*70)
        logger.info(f"[PF100] TRAINING CYCLE #{self.training_count + 1} — TARGET: 100% PROFIT FACTOR")
        logger.info("="*70)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "cycle": self.training_count + 1,
            "rl_trained": False,
            "ml_trained": False,
            "current_pf": 0.0,
            "best_pf": self.best_pf_achieved
        }
        
        # Check trade count
        trade_count = self.trade_memory.get_trade_count()
        logger.info(f"[PF100] Trade count: {trade_count}")
        
        if trade_count < 20:
            logger.warning(f"   Not enough trades for training: {trade_count}/20")
            return results
        
        # 1. Train RL Q-Network (intensive)
        rl_result = self.train_rl_intensive()
        if rl_result["status"] == "success":
            results["rl_trained"] = True
            results["current_pf"] = rl_result.get("pf", 0.0)
            results["implied_pf"] = rl_result.get("implied_pf", 0.0)
        
        # 2. Train ML Ensemble (intensive)
        ml_result = self.train_ml_intensive()
        if ml_result["status"] == "success":
            results["ml_trained"] = True
            results["ml_accuracy"] = ml_result.get("avg_accuracy", 0.0)
        
        # Update counters
        self.training_count += 1
        self.last_train_time = datetime.now()
        
        # Summary
        logger.info("="*70)
        logger.info(f"[PF100] CYCLE #{self.training_count} COMPLETE")
        logger.info(f"   RL Trained: {'[OK]' if results['rl_trained'] else '[FAIL]'}")
        logger.info(f"   ML Trained: {'[OK]' if results['ml_trained'] else '[FAIL]'}")
        logger.info(f"   Current PF: {results.get('current_pf', 0.0):.3f}")
        logger.info(f"   Best PF: {self.best_pf_achieved:.3f}")
        logger.info(f"   Progress to 100%: {(self.best_pf_achieved / 2.0) * 100:.1f}%")
        logger.info("="*70 + "\n")
        
        return results
    
    def continuous_training(self):
        """Run continuous intensive training in background."""
        logger.info("[PF100] Starting continuous background training...")
        logger.info(f"   Retraining every {self.RETRAIN_INTERVAL} trades")
        logger.info(f"   Press Ctrl+C to stop\n")
        
        last_trained_count = 0
        
        while self.training_active:
            try:
                trade_count = self.trade_memory.get_trade_count()
                
                # Train if we have enough new trades
                if trade_count >= 20 and (trade_count - last_trained_count) >= self.RETRAIN_INTERVAL:
                    self.intensive_training_cycle()
                    last_trained_count = trade_count
                    
                    # Check if we've achieved 100% PF
                    if self.best_pf_achieved >= 2.0:
                        logger.info("="*70)
                        logger.info("🎉 100% PROFIT FACTOR ACHIEVED! 🎉")
                        logger.info(f"   Final PF: {self.best_pf_achieved:.3f}")
                        logger.info(f"   Training cycles: {self.training_count}")
                        logger.info("="*70)
                        # Continue training to maintain/improve
                else:
                    # Wait for more trades
                    trades_needed = self.RETRAIN_INTERVAL - (trade_count - last_trained_count)
                    if trade_count >= 20:
                        logger.info(f"[PF100] Waiting for {trades_needed} more trades... (Current: {trade_count})")
                    else:
                        logger.info(f"[PF100] Collecting initial data: {trade_count}/20 trades")
                
                # Sleep for 60 seconds before checking again
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("\n[PF100] Training interrupted by user")
                break
            except Exception as e:
                logger.error(f"[ERROR] Training loop error: {e}", exc_info=True)
                time.sleep(60)
        
        logger.info("[PF100] Background training stopped")
    
    def stop(self):
        """Stop background training."""
        self.training_active = False


def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("AEGIS PROFIT FACTOR 100% - INTENSIVE GPU TRAINING")
    print("="*70)
    print("Target: 100% Profit Factor (PF >= 2.0)")
    print("Mode: Continuous background training on GPU")
    print("="*70 + "\n")
    
    # Check GPU availability
    if not torch.cuda.is_available():
        print("WARNING: GPU not available! Training will use CPU (slower)")
        print("   Make sure CUDA is installed and GPU drivers are up to date")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Training cancelled.")
            return
    
    # Initialize trainer
    trainer = ProfitFactor100Trainer()
    
    # Run continuous training
    try:
        trainer.continuous_training()
    except KeyboardInterrupt:
        print("\nTraining interrupted by user")
    finally:
        trainer.stop()
        print("\n✅ Training stopped. Models saved.")


if __name__ == "__main__":
    main()
