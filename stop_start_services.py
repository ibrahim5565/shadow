import subprocess
import os
import sys

def run_batch(batch_path):
    try:
        result = subprocess.run([batch_path], shell=True, check=True, capture_output=True, text=True)
        print(f"Executed {batch_path}:\n{result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error executing {batch_path}: {e.stderr}")
        sys.exit(1)

def main():
    base_dir = r"d:\\Trading"
    # Stop Aegis services
    stop_batch = os.path.join(base_dir, "STOP_AEGIS.bat")
    run_batch(stop_batch)

    # Clear logs (using clear_logs.bat script)
    clear_logs_batch = os.path.join(base_dir, "clear_logs.bat")
    run_batch(clear_logs_batch)

    # (Optional) Telegram fix – placeholder call (future implementation)
    # telegram_fix_script = os.path.join(base_dir, "telegram_fix.py")
    # subprocess.run([sys.executable, telegram_fix_script], check=True)

    # Start Aegis services
    start_batch = os.path.join(base_dir, "START_AEGIS.bat")
    run_batch(start_batch)

    # Start MT5 RSI bot automatically
    mt5_script = os.path.join(base_dir, "mt5_rsi_bot.py")
    subprocess.Popen([sys.executable, mt5_script], cwd=base_dir)
    print("MT5 RSI bot launched in background.")

if __name__ == "__main__":
    main()
