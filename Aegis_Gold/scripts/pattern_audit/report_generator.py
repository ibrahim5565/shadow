"""
Report Generator

Generates funnel tables and detection reports from audit results.
"""

from typing import List
import pandas as pd
from collections import Counter, defaultdict


def generate_funnel_table(funnel_records: List, output_path: str = None) -> pd.DataFrame:
    """
    Generate funnel table showing gate-by-gate pass rates.
    
    Args:
        funnel_records: List of FunnelRecord objects
        output_path: Optional path to save CSV
    
    Returns:
        DataFrame with funnel analysis
    """
    if not funnel_records:
        print("[WARN] No funnel records to analyze")
        return pd.DataFrame()
    
    # Group by pattern_type and direction
    groups = defaultdict(lambda: {
        'detected': 0,
        'risk_eval_pass': 0,
        'can_trade_pass': 0,
        'spread_pass': 0,
        'session_pass': 0,
        'integrity_pass': 0,
        'traded': 0
    })
    
    for record in funnel_records:
        key = (record.pattern_type, record.direction)
        groups[key]['detected'] += 1
        
        # Track cumulative pass rates through gates
        for gate in record.gates:
            if gate.gate_name == "RISK_EVALUATION" and gate.passed:
                groups[key]['risk_eval_pass'] += 1
            elif gate.gate_name == "RISK_MANAGER_CAN_TRADE" and gate.passed:
                groups[key]['can_trade_pass'] += 1
            elif gate.gate_name == "SPREAD_CHECK" and gate.passed:
                groups[key]['spread_pass'] += 1
            elif gate.gate_name == "SESSION_CHECK" and gate.passed:
                groups[key]['session_pass'] += 1
            elif gate.gate_name == "DIRECTION_INTEGRITY" and gate.passed:
                groups[key]['integrity_pass'] += 1
        
        if record.final_outcome == "TRADED":
            groups[key]['traded'] += 1
    
    # Convert to DataFrame
    rows = []
    for (pattern_type, direction), counts in groups.items():
        rows.append({
            'pattern_type': pattern_type,
            'direction': direction,
            **counts
        })
    
    df = pd.DataFrame(rows)
    
    if output_path:
        df.to_csv(output_path, index=False)
        print(f"[AUDIT] Funnel table saved to {output_path}")
    
    return df


def generate_detection_report(funnel_records: List, history_months: float) -> dict:
    """
    Generate detection count report.
    
    Args:
        funnel_records: List of FunnelRecord objects
        history_months: Number of months of historical data
    
    Returns:
        Dictionary with detection statistics
    """
    if not funnel_records:
        return {}
    
    total_patterns = len(funnel_records)
    
    # Count by direction
    buy_count = sum(1 for r in funnel_records if r.direction == "BUY")
    sell_count = sum(1 for r in funnel_records if r.direction == "SELL")
    
    # Count by timeframe
    tf_counts = Counter(r.timeframe for r in funnel_records)
    
    # Count by pattern type
    type_counts = Counter(r.pattern_type for r in funnel_records)
    
    # Count traded
    traded_count = sum(1 for r in funnel_records if r.final_outcome == "TRADED")
    
    # Rejection reasons
    rejection_counts = Counter(
        r.rejection_gate for r in funnel_records if r.rejection_gate
    )
    
    # Spread data
    estimated_spread_count = sum(
        1 for r in funnel_records if r.spread_source == "ESTIMATED"
    )
    actual_spread_count = sum(
        1 for r in funnel_records if r.spread_source == "ACTUAL_HISTORY"
    )
    
    # Session confirmation
    unconfirmed_session_count = sum(
        1 for r in funnel_records if not r.session_confirmed
    )
    
    # Calculate detection rate
    if history_months > 0:
        days_approx = history_months * 30
        detection_rate_per_day = total_patterns / days_approx if days_approx > 0 else 0
    else:
        detection_rate_per_day = 0
    
    return {
        'total_patterns': total_patterns,
        'buy_count': buy_count,
        'sell_count': sell_count,
        'timeframe_counts': dict(tf_counts),
        'pattern_type_counts': dict(type_counts),
        'traded_count': traded_count,
        'rejection_counts': dict(rejection_counts),
        'actual_spread_bars': actual_spread_count,
        'estimated_spread_bars': estimated_spread_count,
        'unconfirmed_sessions': unconfirmed_session_count,
        'detection_rate_per_day': detection_rate_per_day,
        'history_months': history_months
    }


def print_detection_report(report: dict):
    """Print formatted detection report to console."""
    print("\n" + "="*60)
    print("PATTERN DETECTION AUDIT REPORT")
    print("="*60)
    
    print(f"\nHistory: {report['history_months']:.1f} months")
    print(f"Total Patterns Detected: {report['total_patterns']}")
    print(f"  - BUY: {report['buy_count']} ({report['buy_count']/report['total_patterns']*100:.1f}%)")
    print(f"  - SELL: {report['sell_count']} ({report['sell_count']/report['total_patterns']*100:.1f}%)")
    print(f"Detection Rate: {report['detection_rate_per_day']:.2f} patterns/day")
    
    print(f"\nBy Timeframe:")
    for tf, count in sorted(report['timeframe_counts'].items()):
        print(f"  - {tf}: {count}")
    
    print(f"\nBy Pattern Type:")
    for ptype, count in sorted(report['pattern_type_counts'].items()):
        print(f"  - {ptype}: {count}")
    
    print(f"\nFunnel Conversion:")
    print(f"  - Detected: {report['total_patterns']}")
    print(f"  - Traded: {report['traded_count']} ({report['traded_count']/report['total_patterns']*100:.1f}%)")
    
    print(f"\nTop Rejection Gates:")
    for gate, count in sorted(report['rejection_counts'].items(), key=lambda x: x[1], reverse=True)[:5]:
        pct = count / report['total_patterns'] * 100
        print(f"  - {gate}: {count} ({pct:.1f}%)")
    
    print(f"\nSpread Data:")
    total_bars = report['actual_spread_bars'] + report['estimated_spread_bars']
    if total_bars > 0:
        print(f"  - Actual spread: {report['actual_spread_bars']} bars ({report['actual_spread_bars']/total_bars*100:.1f}%)")
        print(f"  - Estimated (95th percentile): {report['estimated_spread_bars']} bars ({report['estimated_spread_bars']/total_bars*100:.1f}%)")
    
    if report['unconfirmed_sessions'] > 0:
        print(f"\n⚠️  SESSION LABELS: UNCONFIRMED")
        print(f"   {report['unconfirmed_sessions']} patterns have unconfirmed session labels")
        print(f"   (Awaiting user-provided broker offset)")
    
    print("\n" + "="*60)
