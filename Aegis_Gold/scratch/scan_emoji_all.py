"""Scan all project Python files for non-ASCII logger calls that will crash cp1252."""
import os
from pathlib import Path

root = Path('.')
issues = []
for pyfile in sorted(root.rglob('*.py')):
    if any(p in str(pyfile) for p in ['.venv', '__pycache__', 'archive', 'scratch']):
        continue
    try:
        src = pyfile.read_text(encoding='utf-8', errors='ignore')
        for i, line in enumerate(src.split('\n'), 1):
            has_non_ascii = any(ord(c) > 127 for c in line)
            is_log_line = any(kw in line for kw in ['logger.', 'logging.', 'print('])
            if has_non_ascii and is_log_line:
                clean = ''.join(c if ord(c) < 128 else '[?]' for c in line.strip()[:100])
                issues.append(f'{pyfile}:{i}: {clean}')
    except Exception as e:
        issues.append(f'READ ERROR {pyfile}: {e}')

if issues:
    print(f'Found {len(issues)} non-ASCII logger lines:')
    for iss in issues:
        print(iss)
else:
    print('No non-ASCII logger issues found.')
