import os

ini_path = r"C:\Users\mohamed ibrahim d\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\config\terminal.ini"
if os.path.exists(ini_path):
    print(f"Reading terminal.ini from {ini_path}:")
    with open(ini_path, "r", encoding="utf-16-le", errors="ignore") as f:
        content = f.read()
    # Let's print sections that are relevant
    lines = content.splitlines()
    expert_section = False
    for line in lines:
        if line.strip().startswith("["):
            if "expert" in line.lower() or "inputs" in line.lower() or "common" in line.lower() or "safety" in line.lower():
                expert_section = True
                print(f"\n{line}")
            else:
                expert_section = False
        elif expert_section:
            print(f"  {line}")
else:
    print(f"terminal.ini not found at {ini_path}")
