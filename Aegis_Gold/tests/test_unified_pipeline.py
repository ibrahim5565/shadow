"""
===========================================================================
AEGIS GOLD — Unified Trading Pipeline Test Suite (Phase R)
===========================================================================

Tests for end-to-end integration of all 17 systems.

CRITICAL TEST COVERAGE:
-----------------------
1. Pipeline context creation and flow
2. Stage execution and error handling
3. Data flow through all stages
4. Integration of all 17 systems
5. Causality enforcement across pipeline
6. Performance metrics and health monitoring

===========================================================================
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.unified_trading_pipeline import (
    UnifiedTradingPipeline,
    PipelineContext,
    PipelineStage,
    PipelineStatus,
    PipelineMetrics,
    get_unified_trading_pipeline
)


class TestPipelineContextManagement:
    """Test suite for pipeline context creation and management."""
    
    def setup_method(self):
        """Setup for context tests."""
        self.pipeline = UnifiedTradingPipeline()
        
        self.market_snapshot = {
            'current_price': 2010.0,
            'volatility_level': 'NORMAL',
            'volume': 1000,
            'momentum_score': 0.7,
            'trend': 'UPTREND'
        }
    
    def test_create_pipeline_context(self):
        """Test creation of pipeline context."""
        context = self.pipeline.create_pipeline_context(
            symbol="XAUUSD",
            market_snapshot=self.market_snapshot
        )
        
        assert context is not None
        assert context.context_id is not None
        assert context.symbol == "XAUUSD"
        assert context.market_snapshot == self.market_snapshot
        assert context.current_stage == PipelineStage.DATA_INGESTION
        assert len(context.stages_completed) == 0
        
        print("✓ Pipeline context creation works")
    
    def test_context_stored_in_pipeline(self):
        """Test that context is stored in pipeline."""
        context = self.pipeline.create_pipeline_context(
            symbol="XAUUSD",
            market_snapshot=self.market_snapshot
        )
        
        assert context.context_id in self.pipeline.active_contexts
        retrieved = self.pipeline.get_pipeline_status(context.context_id)
        assert retrieved is not None
        assert retrieved.context_id == context.context_id
        
        print("✓ Context storage and retrieval works")
    
    def test_stage_completion_tracking(self):
        """Test tracking of completed stages."""
        context = self.pipeline.create_pipeline_context(
            symbol="XAUUSD",
            market_snapshot=self.market_snapshot
        )
        
        # Mark stages complete
        context.mark_stage_complete(PipelineStage.MTF_ANALYSIS)
        context.mark_stage_complete(PipelineStage.PATTERN_DETECTION)
        
        assert len(context.stages_completed) == 2
        assert PipelineStage.MTF_ANALYSIS in context.stages_completed
        assert PipelineStage.PATTERN_DETECTION in context.stages_completed
        
        print("✓ Stage completion tracking works")
    
    def test_stage_error_handling(self):
        """Test error handling in pipeline."""
        context = self.pipeline.create_pipeline_context(
            symbol="XAUUSD",
            market_snapshot=self.market_snapshot
        )
        
        # Add stage errors
        context.add_stage_error(PipelineStage.MTF_ANALYSIS, "Test error 1")
        context.add_stage_error(PipelineStage.PATTERN_DETECTION, "Test error 2")
        
        assert len(context.stage_errors) == 2
        assert context.stage_errors[0][0] == PipelineStage.MTF_ANALYSIS
        assert context.stage_errors[1][1] == "Test error 2"
        
        print("✓ Stage error handling works")


class TestPipelineExecution:
    """Test suite for pipeline execution flow."""
    
    def setup_method(self):
        """Setup for execution tests."""
        self.pipeline = UnifiedTradingPipeline()
        
        self.market_snapshot = {
            'current_price': 2010.0,
            'volatility_level': 'NORMAL',
            'volume': 1000,
            'momentum_score': 0.7,
            'trend': 'UPTREND'
        }
    
    def test_full_pipeline_execution(self):
        """Test full end-to-end pipeline execution."""
        context = self.pipeline.create_pipeline_context(
            symbol="XAUUSD",
            market_snapshot=self.market_snapshot
        )
        
        # Execute pipeline
        result = self.pipeline.execute_pipeline(context)
        
        assert result is not None
        assert result.context_id == context.context_id
        assert len(result.stages_completed) > 0
        assert result.processing_time_ms > 0
        
        # Check all stages completed
        expected_stages = [
            PipelineStage.MTF_ANALYSIS,
            PipelineStage.PATTERN_DETECTION,
            PipelineStage.QUALITY_VALIDATION,
            PipelineStage.OUTCOME_TRACKING,
            PipelineStage.CONSENSUS_EVALUATION,
            PipelineStage.OPPORTUNITY_ASSESSMENT,
            PipelineStage.ENTRY_SIGNAL,
            PipelineStage.RISK_SETUP,
            PipelineStage.EXECUTION,
            PipelineStage.POST_TRADE,
            PipelineStage.ANALYSIS
        ]
        
        for stage in expected_stages:
            assert stage in result.stages_completed, f"Stage {stage.value} not completed"
        
        print("✓ Full pipeline execution works")
    
    def test_pipeline_data_flow(self):
        """Test data flowing through pipeline stages."""
        context = self.pipeline.create_pipeline_context(
            symbol="XAUUSD",
            market_snapshot=self.market_snapshot
        )
        
        result = self.pipeline.execute_pipeline(context)
        
        # Check data at each stage
        assert result.mtf_analysis is not None
        assert result.detected_patterns is not None
        assert result.validated_patterns is not None
        assert result.pattern_outcomes is not None
        assert result.ai_consensus is not None
        assert result.opportunity_assessment is not None
        assert result.entry_signals is not None
        assert result.risk_parameters is not None
        assert result.trades_executed is not None
        
        print("✓ Pipeline data flow works")
    
    def test_skip_stages(self):
        """Test skipping specific pipeline stages."""
        context = self.pipeline.create_pipeline_context(
            symbol="XAUUSD",
            market_snapshot=self.market_snapshot
        )
        
        # Skip some stages
        skip_stages = [
            PipelineStage.OUTCOME_TRACKING,
            PipelineStage.ANALYSIS
        ]
        
        result = self.pipeline.execute_pipeline(context, skip_stages=skip_stages)
        
        # Check skipped stages not in completed
        for stage in skip_stages:
            assert stage not in result.stages_completed
        
        print("✓ Skip stages feature works")
    
    def test_stage_outputs(self):
        """Test specific stage outputs."""
        context = self.pipeline.create_pipeline_context(
            symbol="XAUUSD",
            market_snapshot=self.market_snapshot
        )
        
        result = self.pipeline.execute_pipeline(context)
        
        # Verify MTF Analysis output
        assert 'M1' in result.mtf_analysis
        assert 'D1' in result.mtf_analysis
        
        # Verify entry signals
        assert len(result.entry_signals) > 0
        assert result.entry_signals[0]['signal_id'] is not None
        
        # Verify risk parameters
        assert result.risk_parameters['stop_loss_price'] is not None
        assert result.risk_parameters['final_target'] is not None
        
        print("✓ Stage outputs are correct")


class TestPipelineMetricsAndHealth:
    """Test suite for pipeline metrics and health monitoring."""
    
    def setup_method(self):
        """Setup for metrics tests."""
        self.pipeline = UnifiedTradingPipeline()
        
        self.market_snapshot = {
            'current_price': 2010.0,
            'volatility_level': 'NORMAL',
            'volume': 1000,
            'momentum_score': 0.7
        }
    
    def test_generate_pipeline_metrics(self):
        """Test generation of pipeline metrics."""
        # Execute a few pipeline cycles
        for _ in range(3):
            context = self.pipeline.create_pipeline_context(
                symbol="XAUUSD",
                market_snapshot=self.market_snapshot
            )
            self.pipeline.execute_pipeline(context)
        
        metrics = self.pipeline.generate_pipeline_metrics()
        
        assert metrics is not None
        assert metrics.signals_generated > 0
        assert metrics.trades_executed > 0
        assert metrics.avg_processing_time_ms > 0
        assert metrics.error_rate >= 0
        
        print("✓ Pipeline metrics generation works")
    
    def test_system_health_assessment(self):
        """Test system health assessment."""
        # Execute some cycles
        for _ in range(5):
            context = self.pipeline.create_pipeline_context(
                symbol="XAUUSD",
                market_snapshot=self.market_snapshot
            )
            self.pipeline.execute_pipeline(context)
        
        health = self.pipeline.get_system_health()
        
        assert health is not None
        assert 'status' in health
        assert health['status'] in ['HEALTHY', 'DEGRADED', 'CRITICAL', 'INITIALIZING']
        assert 'error_rate' in health
        assert 'ready' in health
        assert isinstance(health['ready'], bool)
        
        print("✓ System health assessment works")
    
    def test_metrics_history(self):
        """Test metrics history tracking."""
        # Generate multiple metrics
        for i in range(3):
            for _ in range(2):
                context = self.pipeline.create_pipeline_context(
                    symbol="XAUUSD",
                    market_snapshot=self.market_snapshot
                )
                self.pipeline.execute_pipeline(context)
            
            self.pipeline.generate_pipeline_metrics()
        
        assert len(self.pipeline.metrics_history) >= 3
        
        # Check metrics progression
        for metrics in self.pipeline.metrics_history:
            assert isinstance(metrics, PipelineMetrics)
            assert metrics.timestamp is not None
        
        print("✓ Metrics history tracking works")


class TestPipelineIntegration:
    """Test suite for system integration."""
    
    def test_system_registration(self):
        """Test registering external systems with pipeline."""
        pipeline = UnifiedTradingPipeline()
        
        # Create mock systems
        mock_system1 = Mock(name="entry_logic_engine")
        mock_system2 = Mock(name="risk_manager")
        
        # Register systems
        pipeline.register_system("entry_logic", mock_system1)
        pipeline.register_system("risk_manager", mock_system2)
        
        assert len(pipeline.systems) == 2
        assert "entry_logic" in pipeline.systems
        assert "risk_manager" in pipeline.systems
        
        print("✓ System registration works")
    
    def test_pipeline_configuration(self):
        """Test pipeline configuration."""
        config = {
            'enforce_causality': True,
            'max_concurrent_contexts': 50,
            'timeout_seconds': 300
        }
        
        pipeline = UnifiedTradingPipeline(config)
        
        assert pipeline.enforce_causality == True
        assert pipeline.max_concurrent_contexts == 50
        assert pipeline.timeout_seconds == 300
        
        print("✓ Pipeline configuration works")


class TestUnifiedPipeline:
    """Test suite for overall unified pipeline."""
    
    def test_get_singleton_pipeline(self):
        """Test singleton pattern."""
        pipeline1 = get_unified_trading_pipeline()
        pipeline2 = get_unified_trading_pipeline()
        
        assert pipeline1 is pipeline2
        assert isinstance(pipeline1, UnifiedTradingPipeline)
        
        print("✓ Singleton pipeline pattern works")
    
    def test_concurrent_contexts(self):
        """Test handling multiple concurrent contexts."""
        pipeline = UnifiedTradingPipeline()
        
        market_snapshot = {
            'current_price': 2010.0,
            'volatility_level': 'NORMAL'
        }
        
        # Create multiple contexts
        contexts = []
        for i in range(5):
            context = pipeline.create_pipeline_context(
                symbol=f"XAUUSD_{i}",
                market_snapshot=market_snapshot
            )
            contexts.append(context)
        
        assert len(pipeline.active_contexts) == 5
        
        # Execute all
        for context in contexts:
            pipeline.execute_pipeline(context)
        
        assert len(pipeline.completed_contexts) == 5
        
        print("✓ Concurrent context handling works")


if __name__ == "__main__":
    try:
        # Run all tests
        test_context = TestPipelineContextManagement()
        test_context.setup_method()
        test_context.test_create_pipeline_context()
        test_context.test_context_stored_in_pipeline()
        test_context.test_stage_completion_tracking()
        test_context.test_stage_error_handling()
        
        test_exec = TestPipelineExecution()
        test_exec.setup_method()
        test_exec.test_full_pipeline_execution()
        test_exec.test_pipeline_data_flow()
        test_exec.test_skip_stages()
        test_exec.test_stage_outputs()
        
        test_metrics = TestPipelineMetricsAndHealth()
        test_metrics.setup_method()
        test_metrics.test_generate_pipeline_metrics()
        test_metrics.test_system_health_assessment()
        test_metrics.test_metrics_history()
        
        test_integration = TestPipelineIntegration()
        test_integration.test_system_registration()
        test_integration.test_pipeline_configuration()
        
        test_pipeline = TestUnifiedPipeline()
        test_pipeline.test_get_singleton_pipeline()
        test_pipeline.test_concurrent_contexts()
        
        print("\n🎉 All Unified Trading Pipeline tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)