"""Auto-fix all non-ASCII chars in logger/print calls in brain/ and modules/ directories."""
import re
from pathlib import Path

# Map common emoji to ASCII labels
EMOJI_MAP = {
    '\U0001f7e2': '[OK]',      # green circle
    '\u2705': '[OK]',           # check mark
    '\u274c': '[ERR]',          # cross mark
    '\u26a0\ufe0f': '[WARN]',   # warning
    '\u26a0': '[WARN]',
    '\U0001f9e0': '[BRAIN]',    # brain
    '\U0001f4ca': '[CHART]',    # bar chart
    '\U0001f525': '[FIRE]',     # fire
    '\u2764\ufe0f': '[HEART]',  # heart
    '\u2764': '[HEART]',
    '\U0001f4b0': '[MONEY]',    # money bag
    '\u23f3': '[WAIT]',         # hourglass
    '\U0001f6d1': '[STOP]',     # stop sign
    '\U0001f4e2': '[INFO]',     # megaphone
    '\U0001f916': '[BOT]',      # robot
    '\U0001f4c8': '[UP]',       # chart up
    '\U0001f4c9': '[DOWN]',     # chart down
    '\u2b06\ufe0f': '[UP]',
    '\u2b07\ufe0f': '[DOWN]',
    '\u25b6\ufe0f': '[>]',
    '\u2b50': '[*]',            # star
    '\U0001f31f': '[**]',
    '\U0001f4a1': '[TIP]',      # lightbulb
    '\U0001f504': '[CYCLE]',    # cycle
    '\U0001f9ea': '[TEST]',     # test tube
    '\U0001f4dd': '[NOTE]',     # memo
}

def replace_emoji(text: str) -> str:
    for emoji, label in EMOJI_MAP.items():
        text = text.replace(emoji, label)
    # Final catch: replace any remaining non-ASCII with '?'
    return ''.join(c if ord(c) < 128 else '?' for c in text)

target_dirs = ['brain', 'modules', 'config']
modified = []

for dir_name in target_dirs:
    p = Path(dir_name)
    if not p.exists():
        continue
    for pyfile in sorted(p.rglob('*.py')):
        if '__pycache__' in str(pyfile):
            continue
        src = pyfile.read_text(encoding='utf-8', errors='ignore')
        needs_fix = False
        new_lines = []
        for line in src.split('\n'):
            if any(ord(c) > 127 for c in line) and any(kw in line for kw in ['logger.', 'logging.', 'print(']):
                new_line = replace_emoji(line)
                new_lines.append(new_line)
                needs_fix = True
            else:
                new_lines.append(line)
        if needs_fix:
            pyfile.write_text('\n'.join(new_lines), encoding='utf-8')
            modified.append(str(pyfile))

if modified:
    print(f'Fixed {len(modified)} files:')
    for f in modified:
        print(f'  {f}')
else:
    print('No files needed fixing.')
