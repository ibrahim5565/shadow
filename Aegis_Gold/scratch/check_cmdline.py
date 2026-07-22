import psutil

print("=" * 60)
print("Active Python Processes:")
print("=" * 60)
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        name = proc.info['name']
        if 'python' in name.lower():
            pid = proc.info['pid']
            cmdline = proc.info['cmdline']
            print(f"PID: {pid} | Command: {cmdline}")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
print("=" * 60)
