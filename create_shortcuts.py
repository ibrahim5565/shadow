import os
import sys
import subprocess

def create_shortcut(target_path, shortcut_path, description, icon_path="", icon_index=0, working_dir=""):
    """Creates a Windows shortcut (.lnk) using PowerShell and WScript.Shell."""
    if not working_dir:
        working_dir = os.path.dirname(target_path)
    
    ps_cmd = f"""
    $wsh = New-Object -ComObject WScript.Shell
    $s = $wsh.CreateShortcut('{shortcut_path}')
    $s.TargetPath = '{target_path}'
    $s.WorkingDirectory = '{working_dir}'
    $s.Description = '{description}'
    """
    if icon_path:
        ps_cmd += f"\n    $s.IconLocation = '{icon_path},{icon_index}'"
    ps_cmd += "\n    $s.Save()"

    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[CREATED] {shortcut_path}")
    else:
        print(f"[ERROR] Failed to create shortcut {shortcut_path}: {res.stderr}")

def setup_autostart_and_shortcuts():
    base_dir = r"D:\Trading"
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    startup = os.path.join(os.path.expanduser("~"), r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup")
    
    start_vbs = os.path.join(base_dir, "START_BOT_SILENT.vbs")
    start_bat = os.path.join(base_dir, "run_aegis.bat")
    stop_bat = os.path.join(base_dir, "STOP_BOT_GRACEFUL.bat")
    manager_bat = os.path.join(base_dir, "BOT_MANAGER.bat")

    # 1. Start Bot Desktop Shortcut (Green Icon)
    start_lnk = os.path.join(desktop, "Start Trading Bot.lnk")
    create_shortcut(
        target_path=start_vbs if os.path.exists(start_vbs) else start_bat,
        shortcut_path=start_lnk,
        description="Launch Trading Bot silently in background",
        icon_path=r"%SystemRoot%\System32\shell32.dll",
        icon_index=137, # Green play icon
        working_dir=base_dir
    )

    # 2. Stop Bot Desktop Shortcut (Red Icon)
    stop_lnk = os.path.join(desktop, "Stop Trading Bot.lnk")
    create_shortcut(
        target_path=stop_bat,
        shortcut_path=stop_lnk,
        description="Stop all trading bot processes safely",
        icon_path=r"%SystemRoot%\System32\shell32.dll",
        icon_index=27, # Red X icon
        working_dir=base_dir
    )

    # 3. Bot Manager Control Panel (Gear / Computer Icon)
    manager_lnk = os.path.join(desktop, "Bot Control Panel.lnk")
    create_shortcut(
        target_path=manager_bat,
        shortcut_path=manager_lnk,
        description="Interactive Bot Manager for Windows Home",
        icon_path=r"%SystemRoot%\System32\shell32.dll",
        icon_index=21, # Computer / Settings icon
        working_dir=base_dir
    )

    # 4. Windows Startup Folder Shortcut (Autostart on boot)
    autostart_lnk = os.path.join(startup, "TradingBot_Autostart.lnk")
    create_shortcut(
        target_path=start_vbs,
        shortcut_path=autostart_lnk,
        description="Automatic Windows Startup for Trading Bot",
        icon_path=r"%SystemRoot%\System32\shell32.dll",
        icon_index=137,
        working_dir=base_dir
    )

if __name__ == "__main__":
    setup_autostart_and_shortcuts()
