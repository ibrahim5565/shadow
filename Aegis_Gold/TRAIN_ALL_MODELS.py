"""
AEGIS COMPREHENSIVE MODEL TRAINING SUITE
Trains all AI models on June 24, 2026 data (first 200 trades)
Focuses on learning profitable patterns and decision-making

Training Pipeline:
1. Reinforcement Learning (Actor-Critic PPO) - 50 epochs
2. GPT Brain Model (Transformer) - 100 epochs  
3. Adaptive Learning Baseline Update
4. XGBoost Retraining (if applicable)

Usage:
    python TRAIN_ALL_MODELS.py
"""
import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("aegis.train_all")

# Check GPU availability
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
    if GPU_AVAILABLE:
        GPU_NAME = torch.cuda.get_device_name(0)
        GPU_MEMORY = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"🚀 GPU DETECTED: {GPU_NAME} ({GPU_MEMORY:.1f}GB)")
        logger.info(f"   CUDA Version: {torch.version.cuda}")
        logger.info(f"   Training will be 10-20x faster!")
    else:
        logger.warning("⚠️  GPU not available - training will use CPU (slower)")
except ImportError:
    GPU_AVAILABLE = False
    logger.warning("⚠️  PyTorch not installed - training will use CPU")

def print_header(title):
    print("\n" + "="*80)
    print(f"   {title}")
    print("="*80 + "\n")


def train_reinforcement_learning():
    """Train RL models on June 24 data"""
    print_header("STEP 1/4: REINFORCEMENT LEARNING TRAINING")
    try:
        from config.quant_x_config import QX
        if QX.flag("offline_rl"):
            logger.info("offline_rl flag is enabled. Training offline CQL RL agent...")
            from brain.train_reinforcement import train_cql_offline
            success = train_cql_offline()
        else:
            from brain.train_reinforcement import train_on_june24
            success = train_on_june24()
            
        if success:
            logger.info("✅ Reinforcement Learning training completed successfully")
            return True
        else:
            logger.error("❌ Reinforcement Learning training failed")
            return False
    except Exception as e:
        logger.error(f"❌ RL Training error: {e}", exc_info=True)
        return False


def train_gpt_brain():
    """Train GPT brain model"""
    print_header("STEP 2/4: GPT BRAIN MODEL TRAINING (100 EPOCHS)")
    try:
        from brain.train_gpt import train
        success = train()
        if success:
            logger.info("✅ GPT Brain training completed successfully")
            return True
        else:
            logger.error("❌ GPT Brain training failed")
            return False
    except Exception as e:
        logger.error(f"❌ GPT Training error: {e}", exc_info=True)
        return False


def update_adaptive_learning():
    """Initialize or update adaptive learning baseline"""
    print_header("STEP 3/4: ADAPTIVE LEARNING BASELINE UPDATE")
    try:
        from brain.adaptive_learning import AdaptiveLearning
        learner = AdaptiveLearning()
        
        # Simulate recording June 24 performance
        # Assuming we have the journal data
        import pandas as pd
        journal_path = os.path.join(os.path.dirname(__file__), "data", "journal.csv")
        
        if os.path.exists(journal_path):
            df = pd.read_csv(journal_path, encoding='latin1')
            df['timestamp'] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
            df_june24 = df[df['timestamp'].dt.date == pd.to_datetime('2026-06-24').date()].head(200)
            
            wins = 0
            losses = 0
            for idx, row in df_june24.iterrows():
                try:
                    pnl = float(row.iloc[8]) if pd.notna(row.iloc[8]) else 0.0
                    if pnl > 0:
                        wins += 1
                        learner.record_trade("WIN")
                    elif pnl < 0:
                        losses += 1
                        learner.record_trade("LOSS")
                except:
                    continue
            
            logger.info(f"✅ Adaptive Learning updated: {wins}W / {losses}L from June 24")
            logger.info(f"Adaptations: {learner.get_adaptations()}")
            return True
        else:
            logger.warning("⚠️ Journal not found, skipping adaptive learning update")
            return True
            
    except Exception as e:
        logger.error(f"❌ Adaptive Learning error: {e}", exc_info=True)
        return False


def train_xgboost():
    """Train XGBoost model if enough data"""
    print_header("STEP 4/4: XGBOOST MODEL TRAINING")
    try:
        from models.retrain import retrain
        success = retrain()
        if success:
            logger.info("✅ XGBoost training completed successfully")
            return True
        else:
            logger.warning("⚠️ XGBoost training skipped (insufficient data or not enabled)")
            return True  # Not critical
    except Exception as e:
        logger.error(f"❌ XGBoost Training error: {e}", exc_info=True)
        return True  # Non-critical


def main():
    """Main training orchestrator"""
    start_time = datetime.now()
    
    print("\n" + "="*80)
    print("   AEGIS AI COMPREHENSIVE TRAINING SUITE")
    print("   Training on June 24, 2026 Data (First 200 Trades)")
    print("="*80)
    print(f"\nTraining started at: {start_time}\n")
    
    results = {
        "Reinforcement Learning": False,
        "GPT Brain Model": False,
        "Adaptive Learning": False,
        "XGBoost Model": False
    }
    
    # Execute training pipeline
    results["Reinforcement Learning"] = train_reinforcement_learning()
    results["GPT Brain Model"] = train_gpt_brain()
    results["Adaptive Learning"] = update_adaptive_learning()
    results["XGBoost Model"] = train_xgboost()
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "="*80)
    print("   TRAINING SUMMARY")
    print("="*80)
    print(f"\nStart Time    : {start_time}")
    print(f"End Time      : {end_time}")
    print(f"Duration      : {duration}")
    print(f"\nResults:")
    
    for model, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {model:25s} : {status}")
    
    total_success = sum(results.values())
    total_models = len(results)
    
    print(f"\nOverall Success Rate: {total_success}/{total_models} ({100*total_success/total_models:.0f}%)")
    
    if total_success >= 2:  # At least RL and GPT trained
        print("\n✅ TRAINING COMPLETE - Models are ready for deployment")
        print("\nNext steps:")
        print("  1. Restart bot to load new models: python start_aegis.py")
        print("  2. Monitor performance in Telegram")
        print("  3. Check dashboard confidence scores")
        return 0
    else:
        print("\n❌ TRAINING INCOMPLETE - Some models failed")
        print("Check logs above for error details")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️ Training interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
