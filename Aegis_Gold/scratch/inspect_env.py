import os
import sys

print("--- Python Executable ---")
print(sys.executable)

print("\n--- Environment Variables ---")
for key, val in os.environ.items():
    if any(k in key.upper() for k in ["API", "KEY", "GEMINI", "GOOGLE", "OPENAI", "MODEL"]):
        # Mask the value for security, showing only length and first/last chars if long
        masked_val = val
        if len(val) > 4:
            masked_val = val[:2] + "..." + val[-2:]
        print(f"  {key} = {masked_val}")

print("\n--- Testing Imports ---")
for lib in ["google.generativeai", "openai", "requests"]:
    try:
        __import__(lib)
        print(f"  {lib}: Available")
    except ImportError:
        print(f"  {lib}: NOT Available")
