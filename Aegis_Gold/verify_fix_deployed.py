import os, re, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
print("="*70)
print("VERIFY FIX DEPLOYED - Source Code Audit")
print("="*70)

# 1. Grep all .py files for problematic patterns
patterns = {
    "w_scalp": re.compile(r"w_scalp"),
    "SCALP_STANDARD": re.compile(r"SCALP_STANDARD"),
    "decidewrapper": re.compile(r"decidewrapper"),
    "Regime switcher error": re.compile(r"Regime switcher error"),
    "Fast confidence update error": re.compile(r"Fast confidence update error"),
}

print("\n[1] Scanning all .py files for problematic patterns...")
found_any = False
for root, dirs, files in os.walk(BASE):
    # Skip venv, node_modules, __pycache__, archive
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", ".venv_cuda", "node_modules", "archive", ".kiro")]
    for f in files:
        if not f.endswith(".py"):
            continue
        fp = os.path.join(root, f)
        try:
            content = open(fp, "r", encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for name, pat in patterns.items():
            matches = pat.findall(content)
            if matches:
                found_any = True
                print("  FOUND %s: %d matches in %s" % (name, len(matches), os.path.relpath(fp, BASE)))

if not found_any:
    print("  CLEAN: No w_scalp, SCALP_STANDARD, decidewrapper, or Regime switcher error in any .py file.")

# 2. Verify pattern_signal exists in decision_fusion.py
print("\n[2] Verifying pattern_signal in decision_fusion.py...")
df = os.path.join(BASE, "brain", "decision_fusion.py")
if os.path.isfile(df):
    content = open(df, "r", encoding="utf-8", errors="replace").read()
    if "pattern_signal" in content:
        print("  OK: pattern_signal found in decision_fusion.py")
        # Count occurrences
        print("  pattern_signal occurrences: %d" % content.count("pattern_signal"))
    else:
        print("  ERROR: pattern_signal NOT found in decision_fusion.py!")
else:
    print("  ERROR: decision_fusion.py not found at %s" % df)

# 3. Verify pattern_signal_normalizer.py exists
print("\n[3] Verifying pattern_signal_normalizer.py...")
psn = os.path.join(BASE, "brain", "pattern_signal_normalizer.py")
if os.path.isfile(psn):
    content = open(psn, "r", encoding="utf-8", errors="replace").read()
    print("  OK: pattern_signal_normalizer.py exists (%d bytes)" % len(content))
    if "normalize_pattern_signal" in content:
        print("  OK: normalize_pattern_signal() function present")
    else:
        print("  WARNING: normalize_pattern_signal() not found in file")
else:
    print("  ERROR: pattern_signal_normalizer.py not found!")

# 4. Check for running python processes
print("\n[4] Checking for running python processes...")
try:
    if sys.platform == "win32":
        result = subprocess.run(
            ["powershell", "-Command", "Get-Process python* -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime | Format-Table -AutoSize"],
            capture_output=True, text=True, timeout=15
        )
        print(result.stdout if result.stdout else "  No python processes found.")
        if result.stderr:
            print("  stderr: %s" % result.stderr[:200])
    else:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=15)
        for line in result.stdout.splitlines():
            if "python" in line.lower() and "grep" not in line:
                print("  %s" % line[:200])
except Exception as e:
    print("  Error checking processes: %s" % e)

print("\n" + "="*70)
print("VERIFICATION COMPLETE")
print("="*70)