import os

fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_watchdog_safe_mode.py")
content = open(fp, "r", encoding="utf-8").read()

# Find the logger.info with end/flush kwargs
old = 'logger.info(f"  Cycle {cycle}/10: ", end="", flush=True)'
new = 'logger.info(f"  Cycle {cycle}/10: ")'

if old in content:
    content = content.replace(old, new)
    print("Fixed logger.info end/flush bug")
else:
    print("Pattern not found, searching...")
    for i, l in enumerate(content.splitlines()):
        if "Cycle {cycle}/10" in l:
            print("  L%d| %s" % (i + 1, l))

open(fp, "w", encoding="utf-8").write(content)
print("File updated")