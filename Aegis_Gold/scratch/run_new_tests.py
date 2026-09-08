import sys
import os

sys.path.insert(0, os.path.abspath("."))

import unittest

import tests.test_pattern_confirmation_timing as t1
import tests.test_no_pattern_repainting as t2
import tests.test_engine_vote_schema as t3
import tests.test_consensus_threshold as t4
import tests.test_sl_tp_structural_derivation as t5
import tests.test_future_data_injection as t6
import tests.test_quant_feature_timestamp as t7
import tests.test_ev_decision_engine as t8
import tests.test_pattern_detection as t9
import tests.test_no_confidence_trade_gate as t10
import tests.test_no_forced_trades as t11
import tests.test_pattern_state_machine as t12
import tests.test_pattern_expiry as t13
import tests.test_pattern_chase as t14
import tests.test_pattern_causality as t15
import tests.test_pattern_outcome_labeling as t16
import tests.test_pattern_engine_consensus as t17
import tests.test_pattern_backtest as t18
import tests.test_backtest_live_parity as t19
import tests.test_future_move_forecast as t20
import tests.test_pattern_scale as t21
import tests.test_remaining_rr as t22
import tests.test_full_pattern_discovery as t23
import tests.test_every_trade_causality as t24
import tests.test_trade_reconstruction as t25
import tests.test_pattern_sequence_discovery as t26
import tests.test_full_causality as t27
import tests.test_opportunity_engine as t28
import tests.test_regime_engine as t29
import tests.test_exhaustive_scanner as t30
import tests.test_entry_zone_engine as t31
import tests.test_opportunity_ledger as t32

loader = unittest.TestLoader()
suite = unittest.TestSuite()

suite.addTests(loader.loadTestsFromModule(t1))
suite.addTests(loader.loadTestsFromModule(t2))
suite.addTests(loader.loadTestsFromModule(t3))
suite.addTests(loader.loadTestsFromModule(t4))
suite.addTests(loader.loadTestsFromModule(t5))
suite.addTests(loader.loadTestsFromModule(t6))
suite.addTests(loader.loadTestsFromModule(t7))
suite.addTests(loader.loadTestsFromModule(t8))
suite.addTests(loader.loadTestsFromModule(t9))
suite.addTests(loader.loadTestsFromModule(t10))
suite.addTests(loader.loadTestsFromModule(t11))
suite.addTests(loader.loadTestsFromModule(t12))
suite.addTests(loader.loadTestsFromModule(t13))
suite.addTests(loader.loadTestsFromModule(t14))
suite.addTests(loader.loadTestsFromModule(t15))
suite.addTests(loader.loadTestsFromModule(t16))
suite.addTests(loader.loadTestsFromModule(t17))
suite.addTests(loader.loadTestsFromModule(t18))
suite.addTests(loader.loadTestsFromModule(t19))
suite.addTests(loader.loadTestsFromModule(t20))
suite.addTests(loader.loadTestsFromModule(t21))
suite.addTests(loader.loadTestsFromModule(t22))
suite.addTests(loader.loadTestsFromModule(t23))
suite.addTests(loader.loadTestsFromModule(t24))
suite.addTests(loader.loadTestsFromModule(t25))
suite.addTests(loader.loadTestsFromModule(t26))
suite.addTests(loader.loadTestsFromModule(t27))
suite.addTests(loader.loadTestsFromModule(t28))
suite.addTests(loader.loadTestsFromModule(t29))
suite.addTests(loader.loadTestsFromModule(t30))
suite.addTests(loader.loadTestsFromModule(t31))
suite.addTests(loader.loadTestsFromModule(t32))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

print(f"\n==================================================")
print(f"TEST RUN SUMMARY:")
print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
print(f"Failed: {len(result.failures)}")
print(f"Errors: {len(result.errors)}")
print(f"Skipped: {len(result.skipped)}")
print(f"==================================================")
