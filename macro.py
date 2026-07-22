import pyautogui
import time
import subprocess

print("WARNING: PLEASE TAKE YOUR HANDS OFF THE MOUSE AND KEYBOARD NOW.")
print("Automated deployment starting in 5 seconds...")
time.sleep(5)

print("Launching RDP...")
subprocess.Popen(["mstsc", "/v:13.127.149.130"])

print("Waiting 15 seconds for Windows Server to log in...")
time.sleep(15)

try:
    windows = pyautogui.getWindowsWithTitle("13.127.149.130")
    if windows:
        windows[0].activate()
except Exception as e:
    pass

time.sleep(2)

print("Pasting Aegis_Gold payload onto VPS desktop...")
pyautogui.hotkey('ctrl', 'v')

print("Waiting 25 seconds for the 30MB upload to complete over the internet...")
time.sleep(25)

print("Opening remote Start Menu...")
pyautogui.hotkey('ctrl', 'esc')
time.sleep(2)

print("Typing execution path to bot installer...")
pyautogui.write(r"C:\Users\Administrator\Desktop\Aegis_Gold\VPS_INSTALLER.bat")
time.sleep(2)

pyautogui.press('enter')
print("Automated Deployment Launched Successfully on Remote Server!")
