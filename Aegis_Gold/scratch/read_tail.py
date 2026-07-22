import os
import sys

# Ensure stdout encodes correctly
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def read_tail(filename, n=100):
    try:
        with open(filename, 'rb') as f:
            f.seek(0, os.SEEK_END)
            end_pos = f.tell()
            buffer = bytearray()
            pointer = end_pos
            lines_found = 0
            
            while pointer > 0 and lines_found < n:
                pointer -= 1
                f.seek(pointer)
                char = f.read(1)
                if char == b'\n':
                    lines_found += 1
                buffer.extend(char)
                
            buffer.reverse()
            # Decode using utf-8 and ignore errors
            text = buffer.decode('utf-8', errors='ignore')
            return text
    except Exception as e:
        return f"Error reading {filename}: {e}"

print("=== LAST 50 LINES OF AEGIS.LOG ===")
print(read_tail("data/aegis.log", 50))

print("\n=== LAST 50 LINES OF ERROR.LOG ===")
print(read_tail("data/error.log", 50))
