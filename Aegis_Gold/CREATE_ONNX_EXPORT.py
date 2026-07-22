#!/usr/bin/env python3
"""
Create ONNX exports of neural networks for visualization
"""

import torch
import torch.nn as nn
import os
import sys

class SimpleQNetwork(nn.Module):
    """Simple Q-Network for ONNX export"""
    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(50, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 3)
        )
    
    def forward(self, x):
        return self.layers(x)

class SimpleActorNetwork(nn.Module):
    """Simple Actor Network for ONNX export"""
    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(50, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 3),
            nn.Softmax(dim=-1)
        )
    
    def forward(self, x):
        return self.layers(x)

class SimpleCriticNetwork(nn.Module):
    """Simple Critic Network for ONNX export"""
    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(50, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )
    
    def forward(self, x):
        return self.layers(x)

def main():
    print("🔧 Creating ONNX exports...")
    
    # Create directory
    os.makedirs('onnx_exports', exist_ok=True)
    
    # Dummy input
    dummy_input = torch.randn(1, 50)
    
    try:
        # Export Q-Network
        q_model = SimpleQNetwork()
        torch.onnx.export(
            q_model,
            dummy_input,
            'onnx_exports/q_network.onnx',
            export_params=True,
            opset_version=11,
            do_constant_folding=True,
            input_names=['market_features'],
            output_names=['action_values']
        )
        print('✅ Q-Network ONNX exported')
        
        # Export Actor Network
        actor_model = SimpleActorNetwork()
        torch.onnx.export(
            actor_model,
            dummy_input,
            'onnx_exports/actor_network.onnx',
            export_params=True,
            opset_version=11,
            do_constant_folding=True,
            input_names=['state_features'],
            output_names=['action_probabilities']
        )
        print('✅ Actor Network ONNX exported')
        
        # Export Critic Network
        critic_model = SimpleCriticNetwork()
        torch.onnx.export(
            critic_model,
            dummy_input,
            'onnx_exports/critic_network.onnx',
            export_params=True,
            opset_version=11,
            do_constant_folding=True,
            input_names=['state_features'],
            output_names=['state_value']
        )
        print('✅ Critic Network ONNX exported')
        
        print("\n🎯 All ONNX files created successfully!")
        print("📁 Files created in onnx_exports/:")
        for file in os.listdir('onnx_exports'):
            if file.endswith('.onnx'):
                size = os.path.getsize(f'onnx_exports/{file}')
                print(f"   📄 {file} ({size:,} bytes)")
        
    except Exception as e:
        print(f"❌ Error creating ONNX files: {e}")

if __name__ == "__main__":
    main()