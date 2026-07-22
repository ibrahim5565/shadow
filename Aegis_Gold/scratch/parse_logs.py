import re
import os

log_files = [
    r"d:\Trading\Aegis_Gold\logs\aegis.log",
    r"d:\Trading\Aegis_Gold\logs\aegis.log.1"
]

scans_count = 0
signals_count = 0
buy_signals = 0
sell_signals = 0
rejections = {}
mt5_rejections = []
duplicate_signals = 0

# For average metrics
confidences = []
spreads = []

# Raw sample of logging
unmatched = []

# Regex patterns
no_trade_pattern = re.compile(
    r"No trade signal: (.*?) \(Session: (\w+), Spread: ([\d\.]+) pts\)"
)
signal_found_pattern = re.compile(
    r"Signal Found – (BUY|SELL) @ (\w+) \(Confidence: (\d+)\)"
)
duplicate_signal_pattern = re.compile(r"Duplicate trade signal ignored\.")
mt5_error_pattern = re.compile(
    r"\[(exec_\w+|order_send)\] Failed: (.*)"
)
generic_no_trade_pattern = re.compile(
    r"No trade signal: (.*)"
)

for log_path in log_files:
    if not os.path.exists(log_path):
        continue
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "aegis.main" not in line:
                continue
                
            m_no_trade = no_trade_pattern.search(line)
            m_signal = signal_found_pattern.search(line)
            m_duplicate = duplicate_signal_pattern.search(line)
            
            if m_no_trade:
                scans_count += 1
                reason = m_no_trade.group(1)
                session = m_no_trade.group(2)
                spread = float(m_no_trade.group(3))
                
                rejections[reason] = rejections.get(reason, 0) + 1
                spreads.append(spread)
                
                score_match = re.search(r"\((\d+)\)", reason)
                if score_match:
                    confidences.append(int(score_match.group(1)))
                    
            elif m_signal:
                scans_count += 1
                signals_count += 1
                direction = m_signal.group(1)
                session = m_signal.group(2)
                conf = int(m_signal.group(3))
                
                if direction == "BUY":
                    buy_signals += 1
                elif direction == "SELL":
                    sell_signals += 1
                confidences.append(conf)
                
            elif m_duplicate:
                scans_count += 1
                duplicate_signals += 1
            else:
                m_gen = generic_no_trade_pattern.search(line)
                if m_gen:
                    scans_count += 1
                    rejections[m_gen.group(1)] = rejections.get(m_gen.group(1), 0) + 1
                else:
                    if "No Trade Found" in line:
                        scans_count += 1
                    elif len(unmatched) < 10 and ("INFO" in line or "WARNING" in line):
                        unmatched.append(line.strip())

# Check MT5 rejections from both aegis.log and errors.log
error_files = [
    r"d:\Trading\Aegis_Gold\logs\errors.log",
    r"d:\Trading\Aegis_Gold\logs\aegis.log",
    r"d:\Trading\Aegis_Gold\logs\aegis.log.1"
]
for log_path in error_files:
    if not os.path.exists(log_path):
        continue
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m_mt5 = mt5_error_pattern.search(line)
            if m_mt5:
                # parse timestamp
                timestamp = line.split(" [")[0] if " [" in line else ""
                reason = m_mt5.group(2)
                mt5_rejections.append({
                    "timestamp": timestamp,
                    "symbol": m_mt5.group(1).replace("exec_", ""),
                    "reason": reason,
                    "file": "modules/mt5_gateway.py",
                    "function": "execute_order",
                    "line": 302
                })

print(f"Total market scans (approx based on decisions): {scans_count}")
print(f"Total signals generated: {signals_count}")
print(f"Total BUY signals: {buy_signals}")
print(f"Total SELL signals: {sell_signals}")
print(f"Total duplicate signals ignored: {duplicate_signals}")
print(f"Total MT5 rejection events: {len(mt5_rejections)}")

print("\nRejection reasons count:")
for k, v in sorted(rejections.items(), key=lambda x: x[1], reverse=True):
    print(f"  {k}: {v}")

print("\nAverage Metrics:")
if confidences:
    print(f"  Average confidence score: {sum(confidences)/len(confidences):.2f}")
if spreads:
    print(f"  Average spread: {sum(spreads)/len(spreads):.2f} pts")

print("\nMT5 rejection details (first 10 unique/recent):")
seen = set()
count = 0
for r in mt5_rejections:
    key = (r['symbol'], r['reason'])
    if key not in seen:
        seen.add(key)
        print(f"  Timestamp: {r['timestamp']} | Symbol: {r['symbol']} | Reason: {r['reason']} | File: {r['file']} | Function: {r['function']} | Line: {r['line']}")
        count += 1
        if count >= 10:
            break

print("\nSample unmatched logs (to check for missing formats):")
for u in unmatched:
    print(f"  {u}")
