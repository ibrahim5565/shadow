#!/usr/bin/env python3
"""
🧠 AEGIS GOLD - NEURAL NETWORK VISUALIZER & ONNX EXPORTER
=====================================================
Complete neural network architecture visualization and ONNX export tool.
Shows real-time confidence scores, network topology, and data flow.
"""

import os
import sys
import torch
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import networkx as nx
from datetime import datetime
import json
import logging

# Setup paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from brain.reinforcement_agent import AegisQNetwork, AegisRLAgent
from brain.ml_ensemble import MLEnsemble
from config.settings import *

class NeuralNetworkVisualizer:
    def __init__(self):
        self.setup_logging()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [NN-VIZ] %(levelname)s %(message)s',
            handlers=[
                logging.FileHandler('logs/neural_viz.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_models(self):
        """Load all trained models"""
        self.logger.info("🧠 Loading neural network models...")
        
        # 1. Load RL Q-Network
        try:
            self.q_network = AegisQNetwork(input_size=50, hidden_size=256, output_size=3)
            if os.path.exists('models/aegis_rl.pt'):
                self.q_network.load_state_dict(torch.load('models/aegis_rl.pt', map_location=self.device))
                self.logger.info("✅ Q-Network loaded")
            else:
                self.logger.warning("⚠️  Q-Network weights not found, using random initialization")
        except Exception as e:
            self.logger.error(f"❌ Q-Network load error: {e}")
            
        # 2. Load Actor-Critic Networks
        try:
            from brain.train_reinforcement import ActorNetwork, CriticNetwork
            
            self.actor_network = ActorNetwork(input_size=50, hidden_size=128, output_size=3)
            if os.path.exists('models/aegis_rl_actor.pt'):
                self.actor_network.load_state_dict(torch.load('models/aegis_rl_actor.pt', map_location=self.device))
                self.logger.info("✅ Actor Network loaded")
                
            self.critic_network = CriticNetwork(input_size=50, hidden_size=128)
            if os.path.exists('models/aegis_rl_critic.pt'):
                self.critic_network.load_state_dict(torch.load('models/aegis_rl_critic.pt', map_location=self.device))
                self.logger.info("✅ Critic Network loaded")
        except Exception as e:
            self.logger.error(f"❌ Actor-Critic load error: {e}")
            
        # 3. Load ML Ensemble
        try:
            self.ml_ensemble = MLEnsemble()
            self.logger.info("✅ ML Ensemble initialized")
        except Exception as e:
            self.logger.error(f"❌ ML Ensemble error: {e}")
    
    def create_network_architecture_diagram(self):
        """Create comprehensive neural network architecture diagram"""
        self.logger.info("🎨 Creating network architecture diagram...")
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        fig.suptitle('AEGIS GOLD - NEURAL NETWORK ARCHITECTURE', fontsize=20, fontweight='bold')
        
        # 1. Q-Network Architecture
        self.draw_q_network(ax1)
        
        # 2. Actor-Critic Architecture  
        self.draw_actor_critic(ax2)
        
        # 3. ML Ensemble Architecture
        self.draw_ml_ensemble(ax3)
        
        # 4. Complete System Flow
        self.draw_system_flow(ax4)
        
        plt.tight_layout()
        plt.savefig('neural_network_architecture.png', dpi=300, bbox_inches='tight')
        plt.savefig('neural_network_architecture.pdf', bbox_inches='tight')
        self.logger.info("💾 Architecture diagram saved: neural_network_architecture.png/.pdf")
        return fig
        
    def draw_q_network(self, ax):
        """Draw Q-Network architecture"""
        ax.set_title('Deep Q-Network (DQN)\nState → Action-Value Estimation', fontsize=14, fontweight='bold')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)
        ax.axis('off')
        
        # Input layer
        input_box = FancyBboxPatch((0.5, 3), 1.5, 2, boxstyle="round,pad=0.1", 
                                  facecolor='lightblue', edgecolor='black', linewidth=2)
        ax.add_patch(input_box)
        ax.text(1.25, 4, 'INPUT\n50 Features\n(Indicators)', ha='center', va='center', fontweight='bold')
        
        # Hidden layers
        for i, (size, pos) in enumerate([(256, 3), (256, 4.5), (128, 6)]):
            box = FancyBboxPatch((pos, 2.5), 1.5, 3, boxstyle="round,pad=0.1",
                               facecolor='lightgreen', edgecolor='black', linewidth=2)
            ax.add_patch(box)
            ax.text(pos+0.75, 4, f'HIDDEN {i+1}\n{size} Neurons\nReLU + Dropout', 
                   ha='center', va='center', fontweight='bold')
            
        # Output layer
        output_box = FancyBboxPatch((7.5, 3), 1.5, 2, boxstyle="round,pad=0.1",
                                   facecolor='lightcoral', edgecolor='black', linewidth=2)
        ax.add_patch(output_box)
        ax.text(8.25, 4, 'OUTPUT\n3 Actions\n[BUY,SELL,HOLD]', ha='center', va='center', fontweight='bold')
        
        # Arrows
        for start, end in [(2, 3), (4.5, 6), (7.5, 7.5)]:
            ax.annotate('', xy=(end, 4), xytext=(start, 4),
                       arrowprops=dict(arrowstyle='->', lw=2, color='blue'))
    
    def draw_actor_critic(self, ax):
        """Draw Actor-Critic architecture"""
        ax.set_title('Actor-Critic Networks (PPO)\nPolicy & Value Estimation', fontsize=14, fontweight='bold')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)
        ax.axis('off')
        
        # Shared input
        input_box = FancyBboxPatch((1, 3.5), 1.5, 1, boxstyle="round,pad=0.1",
                                  facecolor='lightblue', edgecolor='black', linewidth=2)
        ax.add_patch(input_box)
        ax.text(1.75, 4, 'INPUT\n50 Features', ha='center', va='center', fontweight='bold')
        
        # Actor branch
        actor_box = FancyBboxPatch((4, 5.5), 2, 1.5, boxstyle="round,pad=0.1",
                                  facecolor='lightgreen', edgecolor='black', linewidth=2)
        ax.add_patch(actor_box)
        ax.text(5, 6.25, 'ACTOR\n128→64→3\nPolicy π(a|s)', ha='center', va='center', fontweight='bold')
        
        # Critic branch
        critic_box = FancyBboxPatch((4, 1.5), 2, 1.5, boxstyle="round,pad=0.1",
                                   facecolor='lightyellow', edgecolor='black', linewidth=2)
        ax.add_patch(critic_box)
        ax.text(5, 2.25, 'CRITIC\n128→64→1\nValue V(s)', ha='center', va='center', fontweight='bold')
        
        # Outputs
        policy_box = FancyBboxPatch((7.5, 5.5), 1.5, 1.5, boxstyle="round,pad=0.1",
                                   facecolor='lightcoral', edgecolor='black', linewidth=2)
        ax.add_patch(policy_box)
        ax.text(8.25, 6.25, 'ACTION\nProbabilities', ha='center', va='center', fontweight='bold')
        
        value_box = FancyBboxPatch((7.5, 1.5), 1.5, 1.5, boxstyle="round,pad=0.1",
                                  facecolor='lightcoral', edgecolor='black', linewidth=2)
        ax.add_patch(value_box)
        ax.text(8.25, 2.25, 'STATE\nValue', ha='center', va='center', fontweight='bold')
        
        # Arrows
        ax.annotate('', xy=(4, 6.25), xytext=(2.5, 4.25),
                   arrowprops=dict(arrowstyle='->', lw=2, color='green'))
        ax.annotate('', xy=(4, 2.25), xytext=(2.5, 3.75),
                   arrowprops=dict(arrowstyle='->', lw=2, color='orange'))
        ax.annotate('', xy=(7.5, 6.25), xytext=(6, 6.25),
                   arrowprops=dict(arrowstyle='->', lw=2, color='red'))
        ax.annotate('', xy=(7.5, 2.25), xytext=(6, 2.25),
                   arrowprops=dict(arrowstyle='->', lw=2, color='red'))
    
    def draw_ml_ensemble(self, ax):
        """Draw ML Ensemble architecture"""
        ax.set_title('ML Ensemble Models\nClassification & Regression', fontsize=14, fontweight='bold')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)
        ax.axis('off')
        
        # Input
        input_box = FancyBboxPatch((0.5, 3.5), 1.5, 1, boxstyle="round,pad=0.1",
                                  facecolor='lightblue', edgecolor='black', linewidth=2)
        ax.add_patch(input_box)
        ax.text(1.25, 4, 'FEATURES\n50 Indicators', ha='center', va='center', fontweight='bold')
        
        # Models
        models = [
            ('XGBoost', 6.5, 'lightgreen'),
            ('RandomForest', 5.5, 'lightyellow'), 
            ('GradientBoost', 4.5, 'lightpink'),
            ('MLP Neural', 3.5, 'lightcyan'),
            ('SVM', 2.5, 'lavender')
        ]
        
        for name, y, color in models:
            box = FancyBboxPatch((3, y-0.4), 2.5, 0.8, boxstyle="round,pad=0.05",
                               facecolor=color, edgecolor='black', linewidth=1)
            ax.add_patch(box)
            ax.text(4.25, y, name, ha='center', va='center', fontweight='bold')
            
            # Arrow from input
            ax.annotate('', xy=(3, y), xytext=(2, 4),
                       arrowprops=dict(arrowstyle='->', lw=1, color='gray'))
        
        # Ensemble output
        ensemble_box = FancyBboxPatch((7, 3), 2, 2, boxstyle="round,pad=0.1",
                                     facecolor='lightcoral', edgecolor='black', linewidth=2)
        ax.add_patch(ensemble_box)
        ax.text(8, 4, 'ENSEMBLE\nVOTING\nWeighted Average', ha='center', va='center', fontweight='bold')
        
        # Arrows to ensemble
        for _, y, _ in models:
            ax.annotate('', xy=(7, 4), xytext=(5.5, y),
                       arrowprops=dict(arrowstyle='->', lw=1, color='red'))
    
    def draw_system_flow(self, ax):
        """Draw complete system data flow"""
        ax.set_title('AEGIS GOLD - COMPLETE SYSTEM FLOW', fontsize=14, fontweight='bold')
        ax.set_xlim(0, 12)
        ax.set_ylim(0, 10)
        ax.axis('off')
        
        # Market data
        market_box = FancyBboxPatch((0.5, 8), 2, 1.5, boxstyle="round,pad=0.1",
                                   facecolor='lightblue', edgecolor='black', linewidth=2)
        ax.add_patch(market_box)
        ax.text(1.5, 8.75, 'MARKET DATA\nXAUUSD/EURUSD\nReal-time', ha='center', va='center', fontweight='bold')
        
        # Feature extraction
        feature_box = FancyBboxPatch((3.5, 8), 2, 1.5, boxstyle="round,pad=0.1",
                                    facecolor='lightyellow', edgecolor='black', linewidth=2)
        ax.add_patch(feature_box)
        ax.text(4.5, 8.75, 'INDICATORS\n50 Features\nTechnical Analysis', ha='center', va='center', fontweight='bold')
        
        # AI Models
        ai_box = FancyBboxPatch((6.5, 6), 2.5, 4, boxstyle="round,pad=0.1",
                               facecolor='lightgreen', edgecolor='black', linewidth=2)
        ax.add_patch(ai_box)
        ax.text(7.75, 8, 'AI MODELS\n• Q-Network\n• Actor-Critic\n• ML Ensemble\n• OMEGA AI', 
               ha='center', va='center', fontweight='bold')
        
        # OMEGA Supervisor
        omega_box = FancyBboxPatch((3.5, 4.5), 2, 2, boxstyle="round,pad=0.1",
                                  facecolor='lightcoral', edgecolor='black', linewidth=2)
        ax.add_patch(omega_box)
        ax.text(4.5, 5.5, 'OMEGA AI\nSUPERVISOR\nRisk Management', ha='center', va='center', fontweight='bold')
        
        # Final decision
        decision_box = FancyBboxPatch((9.5, 7), 2, 2, boxstyle="round,pad=0.1",
                                     facecolor='gold', edgecolor='black', linewidth=2)
        ax.add_patch(decision_box)
        ax.text(10.5, 8, 'TRADE\nDECISION\nBUY/SELL/HOLD', ha='center', va='center', fontweight='bold')
        
        # Arrows
        arrows = [
            ((2.5, 8.75), (3.5, 8.75)),  # Market → Features
            ((5.5, 8.75), (6.5, 8.75)),  # Features → AI
            ((6.5, 7), (5.5, 6)),        # AI → OMEGA
            ((9, 8), (9.5, 8)),          # AI → Decision
            ((5.5, 5.5), (9.5, 7.5))     # OMEGA → Decision
        ]
        
        for start, end in arrows:
            ax.annotate('', xy=end, xytext=start,
                       arrowprops=dict(arrowstyle='->', lw=2, color='blue'))
    
    def export_to_onnx(self):
        """Export models to ONNX format for visualization tools"""
        self.logger.info("📤 Exporting models to ONNX format...")
        
        os.makedirs('onnx_exports', exist_ok=True)
        
        # Create dummy input
        dummy_input = torch.randn(1, 50).to(self.device)
        
        try:
            # Export Q-Network
            torch.onnx.export(
                self.q_network,
                dummy_input,
                'onnx_exports/q_network.onnx',
                export_params=True,
                opset_version=11,
                do_constant_folding=True,
                input_names=['market_features'],
                output_names=['action_values'],
                dynamic_axes={'market_features': {0: 'batch_size'},
                            'action_values': {0: 'batch_size'}}
            )
            self.logger.info("✅ Q-Network exported to onnx_exports/q_network.onnx")
            
            # Export Actor Network
            if hasattr(self, 'actor_network'):
                torch.onnx.export(
                    self.actor_network,
                    dummy_input,
                    'onnx_exports/actor_network.onnx',
                    export_params=True,
                    opset_version=11,
                    do_constant_folding=True,
                    input_names=['state_features'],
                    output_names=['action_probabilities'],
                    dynamic_axes={'state_features': {0: 'batch_size'},
                                'action_probabilities': {0: 'batch_size'}}
                )
                self.logger.info("✅ Actor Network exported to onnx_exports/actor_network.onnx")
                
            # Export Critic Network
            if hasattr(self, 'critic_network'):
                torch.onnx.export(
                    self.critic_network,
                    dummy_input,
                    'onnx_exports/critic_network.onnx',
                    export_params=True,
                    opset_version=11,
                    do_constant_folding=True,
                    input_names=['state_features'],
                    output_names=['state_value'],
                    dynamic_axes={'state_features': {0: 'batch_size'},
                                'state_value': {0: 'batch_size'}}
                )
                self.logger.info("✅ Critic Network exported to onnx_exports/critic_network.onnx")
                
        except Exception as e:
            self.logger.error(f"❌ ONNX export error: {e}")
    
    def get_real_time_confidence(self):
        """Get real-time confidence scores from all models"""
        try:
            # Read latest market data (mock for now)
            dummy_features = torch.randn(1, 50).to(self.device)
            
            confidences = {}
            
            # Q-Network confidence
            if hasattr(self, 'q_network'):
                self.q_network.eval()
                with torch.no_grad():
                    q_values = self.q_network(dummy_features)
                    q_confidence = torch.max(torch.softmax(q_values, dim=1)).item() * 100
                    confidences['Q-Network'] = q_confidence
            
            # Actor-Critic confidence
            if hasattr(self, 'actor_network'):
                self.actor_network.eval()
                with torch.no_grad():
                    action_probs = self.actor_network(dummy_features)
                    actor_confidence = torch.max(action_probs).item() * 100
                    confidences['Actor'] = actor_confidence
                    
            if hasattr(self, 'critic_network'):
                self.critic_network.eval()
                with torch.no_grad():
                    state_value = self.critic_network(dummy_features)
                    critic_confidence = abs(state_value.item()) * 10  # Scale for display
                    confidences['Critic'] = critic_confidence
            
            return confidences
            
        except Exception as e:
            self.logger.error(f"❌ Confidence calculation error: {e}")
            return {}
    
    def create_confidence_dashboard(self):
        """Create real-time confidence dashboard"""
        self.logger.info("📊 Creating confidence dashboard...")
        
        confidences = self.get_real_time_confidence()
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle('AEGIS GOLD - REAL-TIME NEURAL NETWORK CONFIDENCE', fontsize=16, fontweight='bold')
        
        # Confidence bars
        if confidences:
            models = list(confidences.keys())
            values = list(confidences.values())
            colors = ['#4CAF50', '#2196F3', '#FF9800']
            
            bars = ax1.bar(models, values, color=colors[:len(models)])
            ax1.set_ylabel('Confidence %')
            ax1.set_title('Model Confidence Scores')
            ax1.set_ylim(0, 100)
            
            # Add value labels on bars
            for bar, value in zip(bars, values):
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
        
        # Confidence gauge for overall system
        overall_confidence = np.mean(list(confidences.values())) if confidences else 0
        
        # Create gauge
        theta = np.linspace(0, np.pi, 100)
        gauge_values = overall_confidence / 100 * np.pi
        
        ax2.fill_between(theta, 0, 1, color='lightgray', alpha=0.3)
        ax2.fill_between(theta[theta <= gauge_values], 0, 1, 
                        color='green' if overall_confidence >= 50 else 'red', alpha=0.7)
        
        ax2.text(np.pi/2, 0.5, f'{overall_confidence:.1f}%', 
                ha='center', va='center', fontsize=20, fontweight='bold')
        ax2.set_xlim(0, np.pi)
        ax2.set_ylim(0, 1)
        ax2.set_title('Overall System Confidence')
        ax2.axis('off')
        
        plt.tight_layout()
        plt.savefig('confidence_dashboard.png', dpi=300, bbox_inches='tight')
        self.logger.info("💾 Confidence dashboard saved: confidence_dashboard.png")
        return fig
    
    def generate_network_summary(self):
        """Generate comprehensive network summary"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'system': 'AEGIS GOLD Neural Networks',
            'networks': {
                'q_network': {
                    'type': 'Deep Q-Network (DQN)',
                    'input_size': 50,
                    'hidden_layers': [256, 256, 128],
                    'output_size': 3,
                    'activation': 'ReLU + Dropout',
                    'purpose': 'Action-Value Estimation'
                },
                'actor_critic': {
                    'type': 'Proximal Policy Optimization (PPO)',
                    'actor': {
                        'input_size': 50,
                        'hidden_layers': [128, 64],
                        'output_size': 3,
                        'purpose': 'Policy π(a|s)'
                    },
                    'critic': {
                        'input_size': 50,
                        'hidden_layers': [128, 64],
                        'output_size': 1,
                        'purpose': 'Value V(s)'
                    }
                },
                'ml_ensemble': {
                    'type': 'Multi-Model Ensemble',
                    'models': ['XGBoost', 'RandomForest', 'GradientBoosting', 'MLP', 'SVM'],
                    'voting': 'Weighted Average',
                    'purpose': 'Classification & Regression'
                }
            },
            'data_flow': {
                'input': 'Market Data (XAUUSD, EURUSD)',
                'preprocessing': '50 Technical Indicators',
                'ai_processing': 'Multi-Model Analysis',
                'supervision': 'OMEGA AI Risk Management',
                'output': 'Trade Decision (BUY/SELL/HOLD)'
            },
            'files_exported': [
                'neural_network_architecture.png',
                'neural_network_architecture.pdf', 
                'confidence_dashboard.png',
                'onnx_exports/q_network.onnx',
                'onnx_exports/actor_network.onnx',
                'onnx_exports/critic_network.onnx'
            ]
        }
        
        with open('neural_network_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary

def main():
    """Main execution function"""
    print("🧠 AEGIS GOLD - NEURAL NETWORK VISUALIZER")
    print("=" * 50)
    
    viz = NeuralNetworkVisualizer()
    
    # Load models
    viz.load_models()
    
    # Create visualizations
    viz.create_network_architecture_diagram()
    viz.create_confidence_dashboard() 
    
    # Export ONNX
    viz.export_to_onnx()
    
    # Generate summary
    summary = viz.generate_network_summary()
    
    print("\n✅ VISUALIZATION COMPLETE!")
    print("📁 Files created:")
    for file in summary['files_exported']:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ⚠️  {file} (creation failed)")
    
    print(f"\n🎯 Overall System Confidence: {viz.get_real_time_confidence()}")
    print("\n🌐 ONNX files can be viewed in:")
    print("   • Netron (https://netron.app)")
    print("   • TensorBoard")
    print("   • ONNX Runtime")

if __name__ == "__main__":
    main()