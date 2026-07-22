"""Final validation — run from repo root."""
import sys, random, subprocess, pathlib
sys.path.insert(0, '.')

PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    print(f"  [OK]  {msg}")
    PASS += 1

def fail(msg):
    global FAIL
    print(f"  [FAIL] {msg}")
    FAIL += 1

print("\n=== AEGIS-GOLD FINAL VALIDATION ===\n")

# ── 1. Package availability ──────────────────────────────────
print("[1] Package check...")
for pkg in ['torch','pandas','numpy','flask','flask_cors','requests',
            'dotenv','psutil','socks','MetaTrader5','xgboost']:
    try:
        __import__(pkg)
        ok(pkg)
    except ImportError as e:
        fail(f"{pkg} MISSING: {e}")

# ── 2. Module imports ────────────────────────────────────────
print("\n[2] Module import check...")
mods = [
    'config.settings','brain.indicators','brain.regime','brain.structure',
    'brain.entry','brain.risk_eval','brain.brain','brain.gpt_core','brain.gpt_brain',
    'brain.candle_ai','brain.trend_detector','brain.momentum_engine',
    'brain.volatility_engine','brain.spread_filter','brain.entry_engine',
    'brain.exit_engine','brain.adaptive_learning','brain.recovery_daemon',
    'brain.telegram_controller','brain.risk_manager','brain.mt5_connector',
    'brain.brain_logger','modules.feature_factory','modules.proxy_manager',
    'modules.risk_manager','modules.telegram_bot','brain.ai_supervisor',
    'modules.local_ai',
]
for m in mods:
    try:
        __import__(m)
        ok(m)
    except Exception as e:
        fail(f"{m}: {e}")

# ── 3. Claude/Anthropic removal ──────────────────────────────
print("\n[3] Claude/Anthropic removal check...")
import config.settings as cfg
if hasattr(cfg, 'ANTHROPIC_API_KEY'):
    fail("ANTHROPIC_API_KEY still in settings")
else:
    ok("No Claude/Anthropic keys in settings")

# anthropic package removed
r = subprocess.run([sys.executable, '-c', 'import anthropic'], capture_output=True)
if r.returncode != 0:
    ok("anthropic package uninstalled")
else:
    fail("anthropic package still installed — run: pip uninstall anthropic")

# ── 4. MT5 credentials from .env ────────────────────────────
print("\n[4] MT5 credentials from .env...")
if cfg.MT5_LOGIN > 0:
    ok(f"MT5_LOGIN loaded from env (value present)")
else:
    fail("MT5_LOGIN not loaded from .env")

# ── 5. Local AI engine ───────────────────────────────────────
print("\n[5] Local AI engine test...")
from modules.local_ai import full_analysis
random.seed(1)
base = 2000.0
cands = []
for i in range(120):
    o = base + random.uniform(-1, 1)
    h = o + random.uniform(0, 2)
    l = o - random.uniform(0, 2)
    c = random.uniform(l, h)
    cands.append({'open': o, 'high': h, 'low': l, 'close': c})
    base = c + 0.05
ticks = [
    {'bid': 2000+i*0.01, 'ask': 2000.01+i*0.01, 'time_msc': 1700000000000 + i*100}
    for i in range(50)
]
result = full_analysis(cands, cands[-30:], ticks, 2003.0, 0.01,
                       {'equity': 10000.0}, 'LONDON', 18.0)
if result['action'] in ('TRADE', 'WAIT'):
    ok(f"full_analysis: action={result['action']} conf={result['confidence']} grade={result['grade']}")
else:
    fail(f"Invalid action: {result['action']}")

# ── 6. Syntax check ─────────────────────────────────────────
print("\n[6] Syntax check all .py files...")
py_files = [f for f in pathlib.Path('.').glob('**/*.py')
            if '__pycache__' not in str(f) and 'scratch' not in str(f)]
syn_fail = []
for pf in py_files:
    r = subprocess.run([sys.executable, '-m', 'py_compile', str(pf)], capture_output=True)
    if r.returncode != 0:
        syn_fail.append(str(pf))

if syn_fail:
    for f in syn_fail:
        fail(f"Syntax error: {f}")
else:
    ok(f"{len(py_files)} files — all syntax clean")

# ── Summary ──────────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"RESULT: {PASS} passed, {FAIL} failed")
print('='*40)
sys.exit(0 if FAIL == 0 else 1)
