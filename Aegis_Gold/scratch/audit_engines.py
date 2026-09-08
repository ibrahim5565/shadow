import numpy as np
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

results = {}

# 1. QuantFeatureEngine
try:
    from brain.quant_feature_engine import QuantFeatureEngine
    qfe = QuantFeatureEngine()
    prices = np.linspace(1900, 1950, 200).tolist()
    res = qfe.analyze(prices)
    assert 'hurst_100' in res
    vote = qfe.get_engine_vote(prices)
    assert 'direction' in vote and 'confidence' in vote
    regime = qfe.get_market_regime(prices)
    assert regime in ('TRENDING_UP','TRENDING_DOWN','MEAN_REVERTING','NOISE')
    eqs = qfe.quant_edge_score(prices, 'BUY')
    assert 0.0 <= eqs <= 1.0
    results['QuantFeatureEngine'] = f'OK regime={regime} eqs={eqs:.3f}'
except Exception as e:
    results['QuantFeatureEngine'] = f'FAIL: {type(e).__name__}: {e}'

# 2. KronosForecaster
try:
    from brain.kronos_forecaster import KronosForecaster
    kf = KronosForecaster()
    candles = [{'open':1900+i,'high':1910+i,'low':1890+i,'close':1905+i,'volume':100} for i in range(120)]
    vote = kf.get_engine_vote(candles)
    assert 'direction' in vote
    agr = kf.get_direction_agreement('BUY', candles)
    assert 0.0 <= agr <= 1.0
    results['KronosForecaster'] = f'OK dir={vote["direction"]} agr={agr}'
except Exception as e:
    results['KronosForecaster'] = f'FAIL: {type(e).__name__}: {e}'

# 3. MLEnsemble
try:
    from brain.ml_ensemble import get_engine_vote, get_ev_gate, compute_expected_value
    candles = [{'close':1900+i} for i in range(30)]
    vote = get_engine_vote(candles)
    assert 'direction' in vote
    ev = compute_expected_value(0.60, 300, 150, 0.01, 0.01, 100)
    assert isinstance(ev, float)
    results['MLEnsemble'] = f'OK dir={vote["direction"]} ev_test={ev:.4f}'
except Exception as e:
    results['MLEnsemble'] = f'FAIL: {type(e).__name__}: {e}'

# 4. AdaptiveLearning
try:
    from brain.adaptive_learning import AdaptiveLearning
    al = AdaptiveLearning()
    thresh = al.get_eqs_threshold()
    assert 0.0 <= thresh <= 1.0
    adapt = al.get_adaptations()
    assert 'eqs_threshold' in adapt
    results['AdaptiveLearning'] = f'OK thresh={thresh:.2f} pf={adapt.get("rolling_pf","N/A")}'
except Exception as e:
    results['AdaptiveLearning'] = f'FAIL: {type(e).__name__}: {e}'

# 5. ReinforcementAgent
try:
    from brain.reinforcement_agent import AegisRLAgent
    agent = AegisRLAgent()
    feat = [0.5]*9
    action, conf = agent.predict_action(feat)
    assert action in ('BUY','SELL','WAIT')
    weights = agent.get_engine_weights('scalp')
    assert isinstance(weights, dict)
    results['ReinforcementAgent'] = f'OK action={action} conf={conf}'
except Exception as e:
    results['ReinforcementAgent'] = f'FAIL: {type(e).__name__}: {e}'

# 6. StatisticalEngine
try:
    from brain.statistical_engine import StatisticalEngine
    se = StatisticalEngine()
    prices = np.linspace(1900, 1950, 100).tolist()
    res = se.analyze(prices, 'BUY')
    results['StatisticalEngine'] = f'OK type={type(res).__name__}'
except Exception as e:
    results['StatisticalEngine'] = f'FAIL: {type(e).__name__}: {e}'

# 7. ConfidenceEngine
try:
    from brain.confidence_engine import ConfidenceEngine
    ce = ConfidenceEngine()
    results['ConfidenceEngine'] = 'OK loaded'
except Exception as e:
    results['ConfidenceEngine'] = f'FAIL: {type(e).__name__}: {e}'

# 8. MetaDecisionEngine
try:
    from brain.meta_decision_engine import MetaDecisionEngine
    mde = MetaDecisionEngine()
    candles = [{'open':1900+i,'high':1910+i,'low':1890+i,'close':1905+i,'volume':100} for i in range(120)]
    m_res = mde.compute_mds(candles, 'BUY', 150, 300, 'XAUUSD', 0.01)
    results['MetaDecisionEngine'] = f'OK mds={m_res.mds:.3f} regime={m_res.market_regime}'
except Exception as e:
    results['MetaDecisionEngine'] = f'FAIL: {type(e).__name__}: {e}'

# 9. DecisionFusionV2
try:
    from brain.decision_fusion import DecisionFusionV2
    dfv2 = DecisionFusionV2()
    res = dfv2.fuse(
        smc_signal={'direction':'BUY','confidence':70},
        scalp_signal={'direction':'BUY','confidence':65},
        ml_prediction={'direction':'BUY','win_probability':0.65,'uncertainty':0.1},
        rl_action='BUY', rl_confidence=60,
        stat_analysis=None, macro_blackout=False,
        regime_type='TRENDING', regime_confidence=0.7,
        regime_ambiguous=False, calibration_penalty=0, drift_defensive=False
    )
    results['DecisionFusionV2'] = f'OK action={res.action} conf={res.confidence}'
except Exception as e:
    results['DecisionFusionV2'] = f'FAIL: {type(e).__name__}: {e}'

# 10. UnifiedQuantAIBrain
try:
    from brain.unified_brain import UnifiedQuantAIBrain
    ub = UnifiedQuantAIBrain()
    candles = [{'open':1900+i,'high':1910+i,'low':1890+i,'close':1905+i,'volume':100,'time':i} for i in range(50)]
    dec = ub.predict_unified(candles, None, 'XAUUSD', 'LONDON', 20.0, 0.01)
    results['UnifiedQuantAIBrain'] = f'OK action={dec.action} conf={dec.confidence}'
except Exception as e:
    results['UnifiedQuantAIBrain'] = f'FAIL: {type(e).__name__}: {e}'

print('='*60)
for k, v in results.items():
    status = 'PASS' if v.startswith('OK') else 'FAIL'
    print(f'[{status}] {k:30s}: {v}')
print('='*60)
ok_count = sum(1 for v in results.values() if v.startswith('OK'))
print(f'TOTAL: {ok_count}/{len(results)} engines operational')
