import os, re

BASE = os.path.dirname(os.path.abspath(__file__))
brain_py = os.path.join(BASE, "brain", "brain.py")

print("="*70)
print("VERIFY FUSION CALL IN brain.py")
print("="*70)

lines = open(brain_py, "r", encoding="utf-8", errors="replace").read().splitlines()
print("Total lines: %d" % len(lines))

# Find all fuse( calls
for i, l in enumerate(lines):
    if "fuse(" in l or "DecisionFusionV2" in l or "pattern_signal" in l or "w_scalp" in l:
        print("  L%d| %s" % (i+1, l[:200]))

print()
print("="*70)
print("DONE")
print("="*70)