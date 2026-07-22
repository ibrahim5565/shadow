import shutil
import subprocess

nssm_path = shutil.which("nssm")
if nssm_path:
    print(f"NSSM found in PATH: {nssm_path}")
else:
    print("NSSM NOT found in PATH.")
    # Check common locations
    import os
    possible_paths = [
        r"C:\nssm\nssm.exe",
        r"C:\nssm-2.24\win64\nssm.exe",
        r"D:\nssm\nssm.exe"
    ]
    found = False
    for p in possible_paths:
        if os.path.exists(p):
            print(f"NSSM found at: {p}")
            found = True
            break
    if not found:
        print("NSSM not found in common locations either.")
