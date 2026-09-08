import re
import glob
import sys

sys.stdout.reconfigure(encoding='utf-8')

py_files = glob.glob("d:/Trading/Aegis_Gold/brain/*.py") + glob.glob("d:/Trading/Aegis_Gold/modules/*.py")

print("==================================================")
print("  AUDIT OF 'direction' VALUES IN ENGINE DICTIONARIES ")
print("==================================================")

for fpath in py_files:
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # find lines with "direction":
    for idx, line in enumerate(content.split("\n"), 1):
        if '"direction":' in line or "'direction':" in line:
            if not line.strip().startswith("#"):
                print(f"{fpath}:{idx} -> {line.strip()}")

