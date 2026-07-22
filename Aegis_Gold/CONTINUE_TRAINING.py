#!/usr/bin/env python3
"""
CONTINUE TRAINING - Ensures all systems keep running
This script monitors and maintains all training processes
"""
import os
import sys
import time
import json
import subprocess
import threading
from datetime import datetime

class TrainingContinuator:
    def __init__(self):
        self.base_path = os.getcwd()
        self.processes = []
        self.running = True
        
    def log_status(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def check_never_pause_file(self):
        """Ensure ABSOLUTE_NEVER_PAUSE file exists"""
        file_path = "data/ABSOLUTE_NEVER_PAUSE.json"
        if not os.path.exists(file_path):
            never_pause_config = {
                "ABSOLUTE_NEVER_PAUSE": True,
                "FORCE_CONTINUOUS_TRADING": True,
                "OVERRIDE_ALL_STOPS": True,
                "IGNORE_ALL_PAUSE_CONDITIONS": True,
                "BLOCK_ALL_INTERRUPTS": True,
                "MAXIMUM_TRADING_MODE": True,
                "EMERGENCY_OVERRIDE_ACTIVE": True,
                "NEVER_STOP_TRADING": True,
                "INFINITE_TRADING_MODE": True,
                "UNSTOPPABLE_MODE": True,
                "ENABLE_TRADING_PAUSE": False,
                "PAUSE_ON_LOSS": False,
                "PAUSE_ON_DRAWDOWN": False,
                "MAX_CONSECUTIVE_LOSSES": 999999999,
                "DAILY_LOSS_LIMIT_USD": 999999999999,
                "DRAWDOWN_PROTECTION_ENABLED": False,
                "timestamp": datetime.now().isoformat(),
                "enforcer": "ABSOLUTE_NEVER_PAUSE"
            }
            
            os.makedirs("data", exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(never_pause_config, f, indent=2)
            self.log_status("🚫 ABSOLUTE_NEVER_PAUSE file created/restored")
            
    def start_training_process(self, command, description):
        """Start a training process"""
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=self.base_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.processes.append({
                'process': process,
                'command': command,
                'description': description,
                'start_time': datetime.now()
            })
            self.log_status(f"✅ Started: {description}")
            return process
        except Exception as e:
            self.log_status(f"❌ Failed to start {description}: {e}")
            return None
            
    def monitor_processes(self):
        """Monitor all processes and restart if needed"""
        while self.running:
            for proc_info in self.processes[:]:  # Copy list to modify safely
                process = proc_info['process']
                
                if process.poll() is not None:  # Process has terminated
                    self.log_status(f"🔄 Process terminated: {proc_info['description']}")
                    self.log_status(f"🚀 Restarting: {proc_info['command']}")
                    
                    # Remove old process
                    self.processes.remove(proc_info)
                    
                    # Start new process
                    self.start_training_process(
                        proc_info['command'],
                        proc_info['description']
                    )
                    
            time.sleep(10)  # Check every 10 seconds
            
    def ensure_force_resume_files(self):
        """Create force resume files continuously"""
        while self.running:
            try:
                os.makedirs("data", exist_ok=True)
                
                # Force resume file
                with open("data/FORCE_RESUME_NOW.json", 'w') as f:
                    json.dump({
                        "FORCE_RESUME": True,
                        "timestamp": datetime.now().isoformat(),
                        "action": "CONTINUE_TRADING"
                    }, f)
                    
                # Continue trading file
                with open("data/CONTINUE_TRADING.json", 'w') as f:
                    json.dump({
                        "CONTINUE_TRADING": True,
                        "NEVER_PAUSE": True,
                        "timestamp": datetime.now().isoformat()
                    }, f)
                    
                time.sleep(5)  # Create every 5 seconds
            except Exception as e:
                self.log_status(f"⚠️ Error creating resume files: {e}")
                time.sleep(1)
                
    def run(self):
        """Main execution loop"""
        self.log_status("🚀 Starting CONTINUE TRAINING system")
        
        # Ensure never pause configuration
        self.check_never_pause_file()
        
        # Start monitoring threads
        monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        resume_thread = threading.Thread(target=self.ensure_force_resume_files, daemon=True)
        
        monitor_thread.start()
        resume_thread.start()
        
        # Start training processes
        training_commands = [
            ("python brain/train_reinforcement.py", "🧠 Reinforcement Learning Training"),
            ("python brain/train_gpt.py", "🤖 GPT Model Training"),  
            ("python brain/ml_ensemble.py", "📊 ML Ensemble Training"),
        ]
        
        for command, description in training_commands:
            if os.path.exists(command.split()[1]):  # Check if file exists
                self.start_training_process(command, description)
            else:
                self.log_status(f"⚠️ Skipping {description} - file not found")
        
        # Main loop - keep system alive
        try:
            self.log_status("✅ CONTINUE TRAINING system active")
            self.log_status("🚫 ABSOLUTE NEVER PAUSE mode enforced")
            self.log_status("💪 Bot will NEVER pause for any reason")
            
            while self.running:
                # Status update every 30 seconds
                self.log_status(f"💪 Training continues - {len(self.processes)} processes active")
                
                # Update never pause file
                self.check_never_pause_file()
                
                time.sleep(30)
                
        except KeyboardInterrupt:
            self.log_status("🚫 Keyboard interrupt BLOCKED - NEVER PAUSE mode active")
            # Don't actually stop - continue running
            self.run()  # Restart the main loop
            
        except Exception as e:
            self.log_status(f"⚠️ Exception occurred: {e}")
            self.log_status("🔄 Restarting system - NEVER PAUSE mode")
            time.sleep(5)
            self.run()  # Restart on any error

if __name__ == "__main__":
    print("🚀 AEGIS GOLD - CONTINUE TRAINING SYSTEM")
    print("🚫 ABSOLUTE NEVER PAUSE MODE")
    print("💪 This system will NEVER stop for any reason")
    print("=" * 60)
    
    continuator = TrainingContinuator()
    continuator.run()