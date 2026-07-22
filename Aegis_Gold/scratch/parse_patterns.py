import re
from collections import Counter

log_files = [
    r"d:\Trading\Aegis_Gold\logs\aegis.log",
    r"d:\Trading\Aegis_Gold\logs\aegis.log.1"
]

patterns = Counter()
claude_vetoes = 0
gpt_advisories = 0
no_trade_signals = 0
mt5_failures = 0
duplicate_signals = 0

for log_path in log_files:
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "aegis.main" in line:
                    if "Claude VETOED" in line:
                        claude_vetoes += 1
                    elif "GPT Brain advisory" in line:
                        gpt_advisories += 1
                    elif "No trade signal:" in line:
                        no_trade_signals += 1
                        # extract the part after No trade signal:
                        reason = line.split("No trade signal:")[1].split("(")[0].strip()
                        patterns[f"No trade signal: {reason}"] += 1
                    elif "Duplicate trade" in line:
                        duplicate_signals += 1
                    elif "Failed:" in line or "error" in line.lower() or "exception" in line.lower():
                        patterns[line.strip()] += 1
                elif "aegis.mt5" in line:
                    if "Failed:" in line:
                        mt5_failures += 1
                        reason = line.split("Failed:")[1].strip()
                        patterns[f"MT5 execution fail: {reason}"] += 1
    except Exception as e:
        print(f"Error reading {log_path}: {e}")

print(f"Claude vetoes: {claude_vetoes}")
print(f"GPT advisories: {gpt_advisories}")
print(f"No trade signals: {no_trade_signals}")
print(f"MT5 failures (from log lines): {mt5_failures}")
print(f"Duplicate signals: {duplicate_signals}")

print("\nMost common patterns:")
for k, v in patterns.most_common(20):
    print(f"  {k}: {v}")
