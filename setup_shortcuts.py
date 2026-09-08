import os
import glob
import subprocess
import sys

def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='backslashreplace').decode('ascii'))

def main():
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    startup_path = os.path.join(os.path.expanduser("~"), r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup")
    
    safe_print(f"Desktop path: {desktop_path}")
    safe_print(f"Startup path: {startup_path}")

    # Patterns of old shortcuts to clean up from Desktop
    removed_count = 0
    if os.path.exists(desktop_path):
        for item in os.listdir(desktop_path):
            if item.lower().endswith(".lnk") and ("aegis" in item.lower() or "\U0001f680" in item or "start" in item.lower()):
                # Exclude our newly intended shortcut name if present
                if item == "Start Aegis Gold.lnk":
                    continue
                file_path = os.path.join(desktop_path, item)
                try:
                    os.remove(file_path)
                    safe_print(f"[REMOVED] Old shortcut: {file_path}")
                    removed_count += 1
                except Exception as e:
                    safe_print(f"[ERROR] Failed to remove {file_path}: {e}")

    # Create new clean shortcut via PowerShell / WScript.Shell
    target_bat = r"D:\Trading\run_aegis.bat"
    shortcut_name = "Start Aegis Gold.lnk"
    new_shortcut_path = os.path.join(desktop_path, shortcut_name)

    ps_script = f"""
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut('{new_shortcut_path}')
    $shortcut.TargetPath = '{target_bat}'
    $shortcut.WorkingDirectory = 'D:\\Trading'
    $shortcut.Description = 'Launch Aegis Gold Trading Bot, MT5, and Dashboard'
    $shortcut.Save()
    """

    try:
        res = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, check=True)
        safe_print(f"[CREATED] New clean shortcut: {new_shortcut_path}")
        safe_print(f"Target: {target_bat}")
    except subprocess.CalledProcessError as e:
        safe_print(f"[ERROR] PowerShell failed to create shortcut: {e.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    main()
