#!/usr/bin/env python3
"""
BROKER ACCOUNT ACTIVATION SCRIPT
Run this when you're ready to switch from DEMO to LIVE broker account with 0.09 pip spread.
"""

import json
import os
from pathlib import Path

# Paths
SETTINGS_PATH = Path(__file__).parent / "config" / "settings.py"
BRAIN_PATH = Path(__file__).parent / "brain" / "brain.py"

print("=" * 60)
print("BROKER ACCOUNT ACTIVATION SCRIPT")
print("=" * 60)
print("\n⚠️  WARNING: This will switch from DEMO to LIVE broker settings")
print("   - Lot size: 0.10 → 0.01 lot")
print("   - Pip value: Adjusted for 0.09 pip spread")
print("   - Spread limits: Tightened for real account")
print("   - Hard SL: Enabled for loss protection")
print()

confirmation = input("Are you ready to activate broker account? (yes/NO): ").lower().strip()

if confirmation != 'yes':
    print("❌ Activation cancelled. Settings remain in DEMO mode.")
    exit(0)

print("\n✅ ACTIVATING BROKER ACCOUNT SETTINGS...")

# 1. Update settings.py for EURUSD
with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Update EURUSD settings
eurusd_old = '''    "EURUSD": {
        "candidates": ["EURUSD", "EURUSD.a", "EURUSDm", "EURUSDpro", "EURUSD.cash"],
        "pip_value_per_lot": 10.0,      # $10 per pip per 1.0 lot (standard)
        # === BROKER-READY CONFIGURATION (ACTIVATE LATER) ===
        "broker_pip_value_0_01_lot": 0.10,     # YOUR BROKER: $0.10 per pip for 0.01 lot
        "broker_base_lot_live": 0.01,          # YOUR BROKER LOT: 0.01 lot (1 micro lot)
        "broker_spread_cost_per_trade": 0.09,  # YOUR BROKER: 0.09 pips for 0.001 lot
        "broker_lot_size_for_spread": 0.001,   # Reference lot for spread calculation
        "broker_min_tp_points": 6,             # MIN TP: 6 pips = $0.60 (above broker spread)
        # ====================================================
        "base_lot_demo": 0.10,          # DEMO: 0.10 lot (keep for testing)
        "base_lot_live": 0.10,          # LIVE: 0.10 lot (change to 0.01 when activating broker account)
        "max_lot": 0.20,
        "target_profit": 0.50,
        "min_tp_points": 5,
        "max_tp_points": 80,
        "min_sl_points": 0,
        "max_sl_points": 0,
        "spread_limits": {"ASIAN": 12, "LONDON": 8, "NY": 12, "OVERLAP": 15},
        "breakeven_trigger_pts": 2,
        "trail_trigger_pts": 3,
        "trail_distance_pts": 2,
        "time_stop_base_sec": 30,
        "mode": "MICRO_SCALP",
        "zone_threshold_pts": 5,
        "max_volatility_ratio": 2.0,
        "ema_range_threshold": 0.00010,
    },'''

eurusd_new = '''    "EURUSD": {
        "candidates": ["EURUSD", "EURUSD.a", "EURUSDm", "EURUSDpro", "EURUSD.cash"],
        "pip_value_per_lot": 10.0,
        "pip_value_0_01_lot": 0.10,     # YOUR BROKER: $0.10 per pip for 0.01 lot
        "base_lot_demo": 0.10,          # Keep demo for testing
        "base_lot_live": 0.01,          # ✅ ACTIVATED: 0.01 lot for live broker account
        "max_lot": 0.01,                # ✅ MAX: Only 0.01 lot (no increase)
        "target_profit": 0.50,          # $0.50 per trade (realistic for 0.01 lot)
        "min_tp_points": 6,             # ✅ MIN TP: 6 pips = $0.60 (above broker spread of 0.9 pips)
        "max_tp_points": 20,            # ✅ MAX TP: 20 pips = $2.00
        "min_sl_points": 8,             # ✅ MIN SL: 8 pips = $0.80 loss protection
        "max_sl_points": 15,            # ✅ MAX SL: 15 pips = $1.50 (hard limit)
        "spread_limits": {"ASIAN": 2, "LONDON": 1, "NY": 2, "OVERLAP": 3},  # ✅ TIGHT: 1-3 pips only
        "breakeven_trigger_pts": 3,     # Breakeven at 3 pips = $0.30
        "trail_trigger_pts": 6,         # Trail from 6 pips = $0.60
        "trail_distance_pts": 2,        # 2-pip trail
        "time_stop_base_sec": 180,      # 3 min time stop
        "mode": "BROKER_ADJUSTED",      # Custom for YOUR broker
        "zone_threshold_pts": 5,        # 5-pip zones
        "max_volatility_ratio": 1.2,    # Very low volatility tolerance
        "ema_range_threshold": 0.00008, # Tighter EMA range
        "spread_cost_per_trade": 0.09,  # YOUR BROKER: 0.09 pips for 0.001 lot
        "lot_size_for_spread": 0.001,   # Reference lot for spread calculation
    },'''

# Update XAUUSD settings
xauusd_old = '''    "XAUUSD": {
        "candidates": ["XAUUSD", "GOLD", "XAUUSD.a", "XAUUSDm", "GOLDm"],
        "pip_value_per_lot": 1.0,
        # === BROKER-READY CONFIGURATION (ACTIVATE LATER) ===
        "broker_pip_value_0_01_lot": 0.01,     # $0.01 per point for 0.01 lot
        "broker_base_lot_live": 0.01,          # YOUR BROKER LOT: 0.01 lot (1 micro lot)
        "broker_min_tp_points": 30,            # MIN TP: 30 points = $0.30
        # ====================================================
        "base_lot_demo": 0.10,
        "base_lot_live": 0.10,          # LIVE: 0.10 lot (change to 0.01 when activating broker account)
        "max_lot": 0.20,
        "target_profit": 0.50,
        "min_tp_points": 5,
        "max_tp_points": 300,
        "min_sl_points": 0,
        "max_sl_points": 0,
        "spread_limits": {"ASIAN": 25, "LONDON": 20, "NY": 25, "OVERLAP": 30},
        "breakeven_trigger_pts": 2,
        "trail_trigger_pts": 3,
        "trail_distance_pts": 2,
        "time_stop_base_sec": 30,
        "mode": "MICRO_SCALP",
        "zone_threshold_pts": 5,
        "max_volatility_ratio": 3.0,
        "ema_range_threshold": 0.50,
    },'''

xauusd_new = '''    "XAUUSD": {
        "candidates": ["XAUUSD", "GOLD", "XAUUSD.a", "XAUUSDm", "GOLDm"],
        "pip_value_per_lot": 1.0,
        "pip_value_0_01_lot": 0.01,     # $0.01 per point for 0.01 lot
        "base_lot_demo": 0.10,          # Keep demo for testing
        "base_lot_live": 0.01,          # ✅ ACTIVATED: 0.01 lot for live broker account
        "max_lot": 0.01,                # ✅ MAX: Only 0.01 lot (no increase)
        "target_profit": 0.50,          # $0.50 per trade
        "min_tp_points": 30,            # ✅ MIN TP: 30 points = $0.30 (XAUUSD moves more)
        "max_tp_points": 100,           # ✅ MAX TP: 100 points = $1.00
        "min_sl_points": 20,            # ✅ MIN SL: 20 points = $0.20 loss protection
        "max_sl_points": 50,            # ✅ MAX SL: 50 points = $0.50 (hard limit)
        "spread_limits": {"ASIAN": 10, "LONDON": 8, "NY": 10, "OVERLAP": 12},  # ✅ TIGHT: 8-12 points
        "breakeven_trigger_pts": 10,    # Breakeven at 10 points = $0.10
        "trail_trigger_pts": 20,        # Trail from 20 points = $0.20
        "trail_distance_pts": 5,        # 5-point trail
        "time_stop_base_sec": 300,      # 5 min time stop (XAUUSD slower)
        "mode": "BROKER_ADJUSTED",      # Custom for YOUR broker
        "zone_threshold_pts": 15,       # 15-point zones
        "max_volatility_ratio": 1.5,    # Low volatility tolerance
        "ema_range_threshold": 0.30,    # EMA range
    },'''

# Replace in content
content = content.replace(eurusd_old, eurusd_new)
content = content.replace(xauusd_old, xauusd_new)

# Write back
with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Updated config/settings.py for broker account")

# 2. Update brain.py for hard SL
with open(BRAIN_PATH, 'r', encoding='utf-8') as f:
    brain_content = f.read()

# Replace lot size and SL
lot_old = '''    lot = 0.01  # Current: 0.01 lot for demo
    if getattr(risk_mgr, 'lot_override', 0.0) > 0.0:
        lot = risk_mgr.lot_override

    sl_points = 0  # No hard stop loss for demo'''

lot_new = '''    lot = 0.01  # ✅ BROKER: Always use 0.01 lot (1 micro lot)
    if getattr(risk_mgr, 'lot_override', 0.0) > 0.0:
        lot = 0.01  # ✅ BROKER: Force 0.01 lot regardless of override

    sl_points = int(sl_estimate)  # ✅ BROKER: Use hard SL for protection'''

brain_content = brain_content.replace(lot_old, lot_new)

# Write back
with open(BRAIN_PATH, 'w', encoding='utf-8') as f:
    f.write(brain_content)

print("✅ Updated brain/brain.py for broker account")

# 3. Create broker verification file
verification = {
    "broker_account_activated": True,
    "activation_date": "2026-06-17",
    "lot_size": "0.01 lot (1 micro lot)",
    "eurusd_pip_value": "$0.10 per pip",
    "xauusd_point_value": "$0.01 per point",
    "spread_cost": "0.09 pips for 0.001 lot",
    "min_tp_eurusd": "6 pips ($0.60)",
    "min_tp_xauusd": "30 points ($0.30)",
    "hard_sl_enabled": True,
    "notes": "Account optimized for broker's specific pip/spread values"
}

verification_path = Path(__file__).parent / "BROKER_ACTIVATED.json"
with open(verification_path, 'w') as f:
    json.dump(verification, f, indent=2)

print("\n" + "=" * 60)
print("✅ BROKER ACCOUNT SUCCESSFULLY ACTIVATED!")
print("=" * 60)

print("\n📋 ACTIVATED SETTINGS:")
print("1. LOT SIZE: 0.01 lot (1 micro lot) - FIXED")
print("2. EURUSD PIP VALUE: $0.10 per pip")
print("3. XAUUSD POINT VALUE: $0.01 per point")
print("4. SPREAD COST ACCOUNTED: 0.09 pips for 0.001 lot")
print("5. MIN TP EURUSD: 6 pips ($0.60)")
print("6. MIN TP XAUUSD: 30 points ($0.30)")
print("7. HARD SL: Enabled (8-15 pips EURUSD, 20-50 points XAUUSD)")
print("8. TIGHT SPREAD FILTERS: 1-3 pips EURUSD, 8-12 points XAUUSD")

print("\n⚠️  IMPORTANT NEXT STEPS:")
print("1. Restart the trading bot for changes to take effect")
print("2. Verify broker credentials in .env file")
print("3. Set DEMO_MODE = False in settings.py")
print("4. Test with small amount first")

print("\n📁 Verification file created: BROKER_ACTIVATED.json")
print("\n🎯 Your bot is now ready for LIVE trading with your broker!")
