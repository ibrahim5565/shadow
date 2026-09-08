import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

def inspect_file(path, lines_around):
    if not os.path.exists(path):
        return
    print(f"\n==========================================")
    print(f"FILE: {os.path.basename(path)}")
    print(f"==========================================")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    for l_num in lines_around:
        start = max(0, l_num - 15)
        end = min(len(lines), l_num + 10)
        print(f"--- Around Line {l_num} ---")
        for i in range(start, end):
            print(f"{i+1:4d}: {lines[i].rstrip()}")

inspect_file("d:/Trading/Aegis_Gold/brain/ai_supervisor.py", [346])
inspect_file("d:/Trading/Aegis_Gold/brain/kronos_forecaster.py", [456])
inspect_file("d:/Trading/Aegis_Gold/brain/ml_ensemble.py", [986])
inspect_file("d:/Trading/Aegis_Gold/brain/quant_feature_engine.py", [180])
