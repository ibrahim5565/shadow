"""
═══════════════════════════════════════════════════════════════════════════════
📊 CHECK PROFIT FACTOR 100% TRAINING STATUS
═══════════════════════════════════════════════════════════════════════════════

Quick status check for PF100 intensive GPU training.
Shows current profit factor, progress, and training stats.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brain.trade_memory import get_trade_memory_db
from brain.reinforcement_agent import AegisRLAgent


def check_status():
    """Check current PF100 training status."""
    print("\n" + "="*70)
    print("📊 PROFIT FACTOR 100% — TRAINING STATUS")
    print("="*70 + "\n")
    
    try:
        # Initialize components
        trade_memory = get_trade_memory_db()
        rl_agent = AegisRLAgent()
        
        # Get trade count
        trade_count = trade_memory.get_trade_count()
        print(f"📈 Total Trades in Memory: {trade_count}")
        
        if trade_count < 20:
            print(f"⏳ Waiting for more data... ({trade_count}/20 trades needed)")
            print("\n" + "="*70 + "\n")
            return
        
        # Get recent trades for PF calculation
        recent_trades = trade_memory.get_recent_trades(limit=2000)
        
        # Calculate actual profit factor from trades
        profits = [float(t.get('profit_usd', 0) or 0) for t in recent_trades]
        gross_profit = sum(p for p in profits if p > 0)
        gross_loss = abs(sum(p for p in profits if p < 0))
        actual_pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        wins = sum(1 for p in profits if p > 0)
        losses = sum(1 for p in profits if p < 0)
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        
        # Calculate RL agent policy metrics
        rl_agent.populate_replay_buffer(trade_memory)
        policy_metrics = rl_agent.calculate_policy_metrics()
        
        # Display status
        print(f"🎯 Target Profit Factor: 2.0 (100%)")
        print(f"📊 Current Profit Factor: {actual_pf:.3f}")
        print(f"   Progress: {(actual_pf / 2.0) * 100:.1f}%")
        print()
        
        # Status indicator
        if actual_pf >= 2.0:
            status = "✅ TARGET ACHIEVED!"
            status_color = "SUCCESS"
        elif actual_pf >= 1.5:
            status = "🟡 GOOD PROGRESS"
            status_color = "ON_TRACK"
        elif actual_pf >= 1.0:
            status = "🟠 IMPROVING"
            status_color = "POSITIVE"
        else:
            status = "🔴 TRAINING IN PROGRESS"
            status_color = "LEARNING"
        
        print(f"Status: {status}")
        print()
        
        # Detailed metrics
        print("📈 Performance Metrics:")
        print(f"   Win Rate: {win_rate * 100:.1f}%")
        print(f"   Winning Trades: {wins}")
        print(f"   Losing Trades: {losses}")
        print(f"   Gross Profit: ${gross_profit:.2f}")
        print(f"   Gross Loss: ${abs(gross_loss):.2f}")
        print()
        
        print("🤖 RL Agent Policy Metrics:")
        print(f"   Model Win Rate: {policy_metrics['win_rate']:.1f}%")
        print(f"   Model PF: {policy_metrics['profit_factor']:.3f}")
        print(f"   Max Drawdown: {policy_metrics['max_drawdown']:.4f}")
        print(f"   Reward/Risk: {policy_metrics['reward_to_risk']:.4f}")
        print(f"   Learning Stability: {policy_metrics['learning_stability']:.4f}")
        print()
        
        # Read last 10 lines of training log
        log_path = "logs/pf100_training.log"
        if os.path.exists(log_path):
            print("📝 Recent Training Log (last 10 lines):")
            print("-" * 70)
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        print(f"   {line.rstrip()}")
            except Exception as e:
                print(f"   (Could not read log: {e})")
            print("-" * 70)
        else:
            print("📝 Training log not found (training may not have started yet)")
        
        print()
        
        # Recommendations
        if actual_pf < 1.0:
            print("💡 Recommendations:")
            print("   - Training is learning from current performance")
            print("   - Continue trading to accumulate more data")
            print("   - Model will retrain every 20 trades")
            print("   - Expected improvement in next 50-100 trades")
        elif actual_pf < 1.5:
            print("💡 Recommendations:")
            print("   - Good progress! PF is positive")
            print("   - Continue current strategy")
            print("   - Target of 2.0 within reach")
        elif actual_pf < 2.0:
            print("💡 Recommendations:")
            print("   - Excellent! Close to 100% target")
            print("   - Maintain current trading approach")
            print("   - Fine-tuning in progress")
        else:
            print("💡 Status:")
            print("   - 🎉 100% PROFIT FACTOR ACHIEVED!")
            print("   - Training will continue to maintain performance")
            print("   - Consider increasing position sizes carefully")
        
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    check_status()
