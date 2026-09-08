import ast
import re
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

files_to_check = [
    "d:/Trading/Aegis_Gold/core/main.py",
    "d:/Trading/Aegis_Gold/brain/brain.py",
    "d:/Trading/Aegis_Gold/modules/mt5_gateway.py",
    "d:/Trading/Aegis_Gold/modules/risk_manager.py",
    "d:/Trading/Aegis_Gold/brain/risk_eval.py",
    "d:/Trading/Aegis_Gold/brain/smc_engine.py",
    "d:/Trading/Aegis_Gold/brain/confidence_engine.py",
    "d:/Trading/Aegis_Gold/brain/ml_ensemble.py"
]

print("==================================================")
print("     AUDIT OF DECISION -> EXECUTION PATH FOR SELL ")
print("==================================================")

for fpath in files_to_check:
    if not os.path.exists(fpath):
        print(f"File not found: {fpath}")
        continue
    print(f"\n--- FILE: {os.path.basename(fpath)} ---")
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    
    # 1. Search for truthy/falsy order type or direction checks (e.g., `if order_type:`, `if direction:`, `if action:`, `if type:`)
    truthy_patterns = [
        r'if\s+order_type\b',
        r'if\s+not\s+order_type\b',
        r'if\s+direction\b',
        r'if\s+not\s+direction\b',
        r'if\s+action\b',
        r'if\s+not\s+action\b',
        r'if\s+trade_type\b',
        r'if\s+not\s+trade_type\b',
        r'ORDER_TYPE_BUY\s*==\s*0',
        r'order_type\s*==\s*0',
        r'type\s*==\s*0',
        r'direction\s*==\s*0',
        r'direction\s*==\s*1'
    ]

    for idx, line in enumerate(lines, 1):
        for pat in truthy_patterns:
            if re.search(pat, line):
                print(f"  Line {idx:4d} [TRUTHY/FLAG]: {line.strip()}")
        
        # Also check SL / TP calculation for SELL
        if 'SELL' in line and ('sl' in line.lower() or 'tp' in line.lower() or 'price' in line.lower()):
            if ('+' in line or '-' in line or '>' in line or '<' in line) and not line.strip().startswith('#'):
                # Print lines doing SL/TP calculation for SELL
                print(f"  Line {idx:4d} [SELL SL/TP]: {line.strip()}")

