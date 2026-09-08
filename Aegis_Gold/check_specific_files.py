import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

# 1. Check core/main.py for Fast confidence update error and w_scalp
print("="*70)
print("CHECK core/main.py")
print("="*70)
main_py = os.path.join(BASE, "core", "main.py")
if os.path.isfile(main_py):
    lines = open(main_py, "r", encoding="utf-8", errors="replace").read().splitlines()
    print("Total lines: %d" % len(lines))
    for i, l in enumerate(lines):
        if "Fast confidence update error" in l or "w_scalp" in l or "confidence update" in l.lower():
            print("  L%d| %s" % (i+1, l[:200]))
else:
    print("  NOT FOUND: %s" % main_py)

# 2. Check brain/regime_switcher.py for SCALP_STANDARD
print()
print("="*70)
print("CHECK brain/regime_switcher.py")
print("="*70)
rs = os.path.join(BASE, "brain", "regime_switcher.py")
if os.path.isfile(rs):
    lines = open(rs, "r", encoding="utf-8", errors="replace").read().splitlines()
    print("Total lines: %d" % len(lines))
    for i, l in enumerate(lines):
        if "SCALP_STANDARD" in l or "scalp" in l.lower():
            print("  L%d| %s" % (i+1, l[:200]))
else:
    print("  NOT FOUND: %s" % rs)

# 3. Check brain/brain.py for decidewrapper and Regime switcher error
print()
print("="*70)
print("CHECK brain/brain.py")
print("="*70)
brain_py = os.path.join(BASE, "brain", "brain.py")
if os.path.isfile(brain_py):
    lines = open(brain_py, "r", encoding="utf-8", errors="replace").read().splitlines()
    print("Total lines: %d" % len(lines))
    for i, l in enumerate(lines):
        if "decidewrapper" in l or "Regime switcher error" in l or "regime_switcher" in l:
            print("  L%d| %s" % (i+1, l[:200]))
else:
    print("  NOT FOUND: %s" % brain_py)

print()
print("="*70)
print("DONE")
print("="*70)