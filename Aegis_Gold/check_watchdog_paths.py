import os, re, ast

BASE = os.path.dirname(os.path.abspath(__file__))

# 1. Check unified_brain.py for class names
print("="*70)
print("CHECK unified_brain.py classes")
print("="*70)
ub = os.path.join(BASE, "brain", "unified_brain.py")
if os.path.isfile(ub):
    content = open(ub, "r", encoding="utf-8", errors="replace").read()
    # Find all class definitions
    for m in re.finditer(r"^class\s+(\w+)", content, re.MULTILINE):
        print("  class: %s" % m.group(1))
else:
    print("  NOT FOUND")

# 2. Check mt5_gateway location
print()
print("="*70)
print("CHECK mt5_gateway location")
print("="*70)
for candidate in ["modules/mt5_gateway.py", "core/mt5_gateway.py"]:
    fp = os.path.join(BASE, candidate)
    if os.path.isfile(fp):
        print("  FOUND: %s" % candidate)
        content = open(fp, "r", encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"^class\s+(\w+)", content, re.MULTILINE):
            print("    class: %s" % m.group(1))
    else:
        print("  NOT FOUND: %s" % candidate)

# 3. Check what test_watchdog_safe_mode.py imports
print()
print("="*70)
print("CHECK test_watchdog_safe_mode.py imports")
print("="*70)
tw = os.path.join(BASE, "test_watchdog_safe_mode.py")
if os.path.isfile(tw):
    content = open(tw, "r", encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"from\s+([\w.]+)\s+import\s+([\w, ]+)", content):
        print("  from %s import %s" % (m.group(1), m.group(2)))
    for m in re.finditer(r"import\s+([\w.]+)", content):
        print("  import %s" % m.group(1))
else:
    print("  NOT FOUND")

print()
print("="*70)
print("DONE")
print("="*70)