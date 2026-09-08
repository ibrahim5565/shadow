"""Find and print non-ASCII logger lines."""
src = open('brain/ai_supervisor.py', encoding='utf-8').read()
lines = src.split('\n')
for i, line in enumerate(lines, 1):
    if any(ord(c) > 127 for c in line) and ('logger' in line.lower() or 'logging' in line.lower()):
        clean = ''.join(c if ord(c) < 128 else f'[U+{ord(c):04X}]' for c in line[:150])
        print(f'Line {i}: {clean}')
