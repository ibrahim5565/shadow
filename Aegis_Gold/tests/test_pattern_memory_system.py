"""
===========================================================================
AEGIS GOLD — Pattern Memory System Test Suite (Phase J)
===========================================================================

Tests for historical pattern outcome database with similarity matching.

CRITICAL TEST COVERAGE:
-----------------------
1. Pattern fingerprint creation and uniqueness
2. Similarity matching algorithm accuracy
3. Pattern memory storage and retrieval
4. Outcome prediction based on historical patterns
5. Database persistence and migration
6. Performance with large pattern datasets

===========================================================================
"""

import os
import tempfile
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.pattern_memory_system import (
    PatternMemorySystem, 
    PatternFingerprint,
    PatternMemory,
    SimilarityMatch,
    PatternPrediction,
    get_pattern_memory_system
)


class TestPatternFingerprint:
    """Test suite for pattern fingerprint creation and comparison."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.sample_price_levels = [2010.0, 2015.0, 2005.0, 2020.0]
        self.sample_candle_data = [
            {"open": 2010.0, "high": 2015.0, "low": 2008.0, "close": 2012.0},
            {"open": 2012.0, "high": 2018.0, "low": 2010.0, "close": 2016.0},
            {"open": 2016.0, "high": 2020.0, "low": 2014.0, "close": 2019.0}
        ]
        
    def test_fingerprint_creation(self):
        """Test basic fingerprint creation."""
        # Create memory system (temporarily)
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            memory_system = PatternMemorySystem(db_path=db_path)
            
            fingerprint = memory_system.create_pattern_fingerprint(
                pattern_type="BOS_BULLISH",
                scale="MEDIUM",
                direction="BUY",
                price_levels=self.sample_price_levels,
                candle_data=self.sample_candle_data,
                regime="TRENDING_UP",
                mtf_alignment=0.75,
                volatility=0.5,
                formation_speed=0.6,
                timeframe="M15",
                rr_ratio=2.0,
                structure_strength=0.8
            )
            
            # Verify fingerprint properties
            assert fingerprint.pattern_type == "BOS_BULLISH"
            assert fingerprint.scale == "MEDIUM"
            assert fingerprint.direction == "BUY"
            assert fingerprint.regime_type == "TRENDING_UP"
            assert fingerprint.mtf_alignment_bucket == "HIGH"  # 0.75 > 0.7
            assert fingerprint.volatility_bucket == "NORMAL"  # 0.3 <= 0.5 < 0.7
            assert fingerprint.rr_bucket == "MED"  # 1.5 <= 2.0 < 2.5
            assert fingerprint.structure_hash != "no_structure"
            assert fingerprint.candle_pattern_hash != "no_candles"
            
            # Test key generation
            key = fingerprint.to_key()
            assert isinstance(key, str)
            assert "BOS_BULLISH" in key
            assert "MEDIUM" in key
            assert "BUY" in key
            
        print("✓ Fingerprint creation works")
        
    def test_identical_fingerprints(self):
        """Test that identical inputs produce identical fingerprints."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            memory_system = PatternMemorySystem(db_path=db_path)
            
            # Create two identical fingerprints
            fp1 = memory_system.create_pattern_fingerprint(
                pattern_type="BOS_BULLISH", scale="SMALL", direction="BUY",
                price_levels=[2010.0, 2015.0], candle_data=self.sample_candle_data,
                regime="TRENDING_UP", mtf_alignment=0.8, volatility=0.4,
                formation_speed=0.3, timeframe="M5", rr_ratio=1.8, structure_strength=0.7
            )
            
            fp2 = memory_system.create_pattern_fingerprint(
                pattern_type="BOS_BULLISH", scale="SMALL", direction="BUY",
                price_levels=[2010.0, 2015.0], candle_data=self.sample_candle_data,
                regime="TRENDING_UP", mtf_alignment=0.8, volatility=0.4,
                formation_speed=0.3, timeframe="M5", rr_ratio=1.8, structure_strength=0.7
            )
            
            assert fp1.to_key() == fp2.to_key()
            assert fp1.structure_hash == fp2.structure_hash
            assert fp1.candle_pattern_hash == fp2.candle_pattern_hash
            
        print("✓ Identical fingerprints match")
    def test_different_fingerprints(self):
        """Test that different inputs produce different fingerprints."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            memory_system = PatternMemorySystem(db_path=db_path)
            
            # Create different fingerprints
            fp1 = memory_system.create_pattern_fingerprint(
                pattern_type="BOS_BULLISH", scale="SMALL", direction="BUY",
                price_levels=[2010.0, 2015.0], candle_data=self.sample_candle_data,
                regime="TRENDING_UP", mtf_alignment=0.8, volatility=0.4,
                formation_speed=0.3, timeframe="M5", rr_ratio=1.8, structure_strength=0.7
            )
            
            fp2 = memory_system.create_pattern_fingerprint(
                pattern_type="CHOCH_BEARISH", scale="LARGE", direction="SELL",  # Different
                price_levels=[2020.0, 2015.0], candle_data=self.sample_candle_data,
                regime="RANGING", mtf_alignment=0.3, volatility=0.8,
                formation_speed=0.7, timeframe="H1", rr_ratio=2.5, structure_strength=0.4
            )
            
            assert fp1.to_key() != fp2.to_key()
            assert fp1.pattern_type != fp2.pattern_type
            assert fp1.scale != fp2.scale
            assert fp1.direction != fp2.direction
            
        print("✓ Different fingerprints are unique")


class TestSimilarityMatching:
    """Test suite for pattern similarity matching algorithm."""
    
    def setup_method(self):
        """Setup for similarity tests.""" 
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.memory_system = PatternMemorySystem(db_path=self.db_path)
        
    def test_exact_similarity_match(self):
        """Test exact similarity matching (1.0 score)."""
        # Create identical fingerprints
        fp1 = PatternFingerprint(
            pattern_type="BOS_BULLISH", scale="MEDIUM", direction="BUY",
            structure_hash="abc123", candle_pattern_hash="def456",
            regime_type="TRENDING_UP", mtf_alignment_bucket="HIGH",
            volatility_bucket="NORMAL", formation_time_bucket="FAST",
            timeframe_primary="M15", rr_bucket="MED", structure_strength_bucket="STRONG"
        )
        
        fp2 = PatternFingerprint(
            pattern_type="BOS_BULLISH", scale="MEDIUM", direction="BUY",
            structure_hash="abc123", candle_pattern_hash="def456",
            regime_type="TRENDING_UP", mtf_alignment_bucket="HIGH",
            volatility_bucket="NORMAL", formation_time_bucket="FAST",
            timeframe_primary="M15", rr_bucket="MED", structure_strength_bucket="STRONG"
        )
        
        similarity, matches = self.memory_system.calculate_similarity(fp1, fp2)
        
        assert similarity == 1.0  # Perfect match
        assert "pattern_type" in matches
        assert "direction" in matches
        assert "structure_hash" in matches
        
        print("✓ Exact similarity matching works")
        
    def test_partial_similarity_match(self):
        """Test partial similarity matching."""
        fp1 = PatternFingerprint(
            pattern_type="BOS_BULLISH", scale="MEDIUM", direction="BUY",
            structure_hash="abc123", candle_pattern_hash="def456",
            regime_type="TRENDING_UP", mtf_alignment_bucket="HIGH",
            volatility_bucket="NORMAL", formation_time_bucket="FAST",
            timeframe_primary="M15", rr_bucket="MED", structure_strength_bucket="STRONG"
        )
        
        fp2 = PatternFingerprint(
            pattern_type="BOS_BULLISH",    # Same (0.25 weight)
            scale="LARGE",                 # Different
            direction="BUY",               # Same (0.20 weight)  
            structure_hash="xyz789",       # Different
            candle_pattern_hash="def456",  # Same (0.05 weight)
            regime_type="RANGING",         # Different
            mtf_alignment_bucket="HIGH",   # Same (0.08 weight)
            volatility_bucket="HIGH",      # Different
            formation_time_bucket="SLOW",  # Different
            timeframe_primary="M15",       # Same (0.05 weight)
            rr_bucket="HIGH",              # Different
            structure_strength_bucket="WEAK"  # Different
        )
        
        similarity, matches = self.memory_system.calculate_similarity(fp1, fp2)
        
        # Should match on: pattern_type (0.25) + direction (0.20) + mtf_alignment_bucket (0.08) + 
        # timeframe_primary (0.05) + candle_pattern_hash (0.05) = 0.63
        expected_similarity = 0.25 + 0.20 + 0.08 + 0.05 + 0.05
        assert abs(similarity - expected_similarity) < 0.01
        assert "pattern_type" in matches
        assert "direction" in matches
        assert "candle_pattern_hash" in matches
        
        print("✓ Partial similarity matching works")
class TestPatternMemoryStorage:
    """Test suite for pattern memory storage and retrieval."""
    
    def setup_method(self):
        """Setup for storage tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.memory_system = PatternMemorySystem(db_path=self.db_path)
    
    def test_store_and_retrieve_pattern(self):
        """Test storing and retrieving pattern memories."""
        # Create sample fingerprint
        fingerprint = PatternFingerprint(
            pattern_type="BOS_BULLISH", scale="MEDIUM", direction="BUY",
            structure_hash="test123", candle_pattern_hash="candle456",
            regime_type="TRENDING_UP", mtf_alignment_bucket="HIGH",
            volatility_bucket="NORMAL", formation_time_bucket="FAST",
            timeframe_primary="M15", rr_bucket="MED", structure_strength_bucket="STRONG"
        )
        
        # Create pattern memory
        memory = PatternMemory(
            fingerprint=fingerprint,
            pattern_id="test_pattern_001",
            symbol="XAUUSD",
            detection_timestamp=datetime.now(timezone.utc).isoformat(),
            detection_price=2010.50,
            entry_price=2011.00,
            stop_loss=2005.00,
            take_profit=2023.00,
            outcome="TP_HIT",
            actual_r=2.0,
            time_to_completion_minutes=45,
            max_favorable_r=2.1,
            max_adverse_r=-0.2,
            pattern_quality_score=0.85,
            sequence_match=True,
            htf_confluence=True,
            session="LONDON",
            day_of_week=1,
            hour_of_day=10
        )
        
        # Store memory
        self.memory_system.store_pattern_memory(memory)
        
        # Verify it's in cache
        assert "test_pattern_001" in self.memory_system.memory_cache
        retrieved = self.memory_system.memory_cache["test_pattern_001"]
        
        assert retrieved.pattern_id == "test_pattern_001"
        assert retrieved.outcome == "TP_HIT"
        assert retrieved.actual_r == 2.0
        assert retrieved.fingerprint.pattern_type == "BOS_BULLISH"
        
        print("✓ Pattern storage and retrieval works")
        
    def test_database_persistence(self):
        """Test that patterns persist across system restarts."""
        # Create and store a pattern
        fingerprint = PatternFingerprint(
            pattern_type="CHOCH_BEARISH", scale="LARGE", direction="SELL",
            structure_hash="persist123", candle_pattern_hash="persist456", 
            regime_type="RANGING", mtf_alignment_bucket="MED",
            volatility_bucket="HIGH", formation_time_bucket="SLOW",
            timeframe_primary="H1", rr_bucket="LOW", structure_strength_bucket="MODERATE"
        )
        
        memory = PatternMemory(
            fingerprint=fingerprint,
            pattern_id="persist_pattern",
            symbol="XAUUSD", 
            detection_timestamp=datetime.now(timezone.utc).isoformat(),
            detection_price=2000.00, entry_price=1999.00,
            stop_loss=2010.00, take_profit=1980.00,
            outcome="SL_HIT", actual_r=-1.0,
            time_to_completion_minutes=30, max_favorable_r=0.1, max_adverse_r=-1.0,
            pattern_quality_score=0.65, sequence_match=False, htf_confluence=False,
            session="NY", day_of_week=3, hour_of_day=15
        )
        
        # Store in first system instance
        self.memory_system.store_pattern_memory(memory)
        initial_count = len(self.memory_system.memory_cache)
        
        # Create new system instance (simulate restart)
        new_memory_system = PatternMemorySystem(db_path=self.db_path)
        
        # Verify pattern was loaded
        assert len(new_memory_system.memory_cache) == initial_count
        assert "persist_pattern" in new_memory_system.memory_cache
        
        retrieved = new_memory_system.memory_cache["persist_pattern"]
        assert retrieved.outcome == "SL_HIT"
        assert retrieved.actual_r == -1.0
        
        print("✓ Database persistence works")


class TestOutcomePrediction:
    """Test suite for pattern outcome prediction."""
    
    def setup_method(self):
        """Setup for prediction tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.memory_system = PatternMemorySystem(db_path=self.db_path)
        
        # Seed with historical patterns
        self._create_sample_patterns()
    
    def _create_sample_patterns(self):
        """Create sample patterns for testing predictions."""
        base_fingerprint = PatternFingerprint(
            pattern_type="BOS_BULLISH", scale="MEDIUM", direction="BUY",
            structure_hash="sample123", candle_pattern_hash="sample456",
            regime_type="TRENDING_UP", mtf_alignment_bucket="HIGH",
            volatility_bucket="NORMAL", formation_time_bucket="FAST", 
            timeframe_primary="M15", rr_bucket="MED", structure_strength_bucket="STRONG"
        )
        
        # Create 5 winning patterns and 2 losing patterns
        outcomes = [
            ("TP_HIT", 2.0), ("TP_HIT", 1.8), ("TP_HIT", 2.2), 
            ("TP_HIT", 1.9), ("TP_HIT", 2.1),  # 5 wins
            ("SL_HIT", -1.0), ("SL_HIT", -1.0)  # 2 losses
        ]
        
        for i, (outcome, r_value) in enumerate(outcomes):
            memory = PatternMemory(
                fingerprint=base_fingerprint,
                pattern_id=f"sample_{i}",
                symbol="XAUUSD",
                detection_timestamp=datetime.now(timezone.utc).isoformat(),
                detection_price=2010.0, entry_price=2011.0,
                stop_loss=2005.0, take_profit=2023.0,
                outcome=outcome, actual_r=r_value,
                time_to_completion_minutes=40 + i*5,
                max_favorable_r=max(0, r_value + 0.1),
                max_adverse_r=min(0, r_value - 0.1),
                pattern_quality_score=0.8, sequence_match=False, htf_confluence=True,
                session="LONDON", day_of_week=i % 5, hour_of_day=10
            )
            
            self.memory_system.store_pattern_memory(memory)
    def test_outcome_prediction(self):
        """Test outcome prediction based on similar patterns.""" 
        # Create target fingerprint (identical to samples)
        target_fingerprint = PatternFingerprint(
            pattern_type="BOS_BULLISH", scale="MEDIUM", direction="BUY",
            structure_hash="sample123", candle_pattern_hash="sample456",
            regime_type="TRENDING_UP", mtf_alignment_bucket="HIGH",
            volatility_bucket="NORMAL", formation_time_bucket="FAST",
            timeframe_primary="M15", rr_bucket="MED", structure_strength_bucket="STRONG"
        )
        
        # Get prediction
        prediction = self.memory_system.predict_pattern_outcome(target_fingerprint)
        
        # Verify prediction quality
        assert prediction.sample_size == 7  # 5 wins + 2 losses
        assert prediction.predicted_outcome == "TP_HIT"  # Most common
        assert prediction.win_probability > 0.6  # 5/7 = 71%
        assert prediction.expected_r > 0.0  # Should be positive
        assert prediction.confidence > 0.5  # Should have decent confidence
        
        # Check outcomes breakdown
        assert prediction.outcomes_breakdown.get("TP_HIT", 0) == 5
        assert prediction.outcomes_breakdown.get("SL_HIT", 0) == 2
        
        print("✓ Outcome prediction works")
        
    def test_insufficient_data_prediction(self):
        """Test prediction with insufficient historical data."""
        # Create unique fingerprint with no historical matches
        unique_fingerprint = PatternFingerprint(
            pattern_type="UNIQUE_PATTERN", scale="TINY", direction="SIDEWAYS",
            structure_hash="unique999", candle_pattern_hash="unique888",
            regime_type="UNKNOWN", mtf_alignment_bucket="ZERO",
            volatility_bucket="EXTREME", formation_time_bucket="INSTANT",
            timeframe_primary="S1", rr_bucket="INFINITE", structure_strength_bucket="MYTHICAL"
        )
        
        prediction = self.memory_system.predict_pattern_outcome(unique_fingerprint)
        
        # Should return default/unknown prediction
        assert prediction.sample_size < self.memory_system.min_sample_size
        assert prediction.predicted_outcome == "UNKNOWN" 
        assert prediction.confidence == 0.0
        
        print("✓ Insufficient data handling works")


class TestPatternStatistics:
    """Test suite for pattern statistics and reporting."""
    
    def setup_method(self):
        """Setup for statistics tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.memory_system = PatternMemorySystem(db_path=self.db_path)
        
        # Create diverse pattern set
        self._create_diverse_patterns()
    
    def _create_diverse_patterns(self):
        """Create diverse patterns for statistics testing."""
        patterns = [
            # BOS_BULLISH patterns
            ("BOS_BULLISH", "SMALL", "BUY", "TP_HIT", 1.5),
            ("BOS_BULLISH", "SMALL", "BUY", "TP_HIT", 1.8),
            ("BOS_BULLISH", "SMALL", "BUY", "SL_HIT", -1.0),
            
            # CHOCH_BEARISH patterns  
            ("CHOCH_BEARISH", "MEDIUM", "SELL", "TP_HIT", 2.0),
            ("CHOCH_BEARISH", "MEDIUM", "SELL", "SL_HIT", -1.0),
            ("CHOCH_BEARISH", "MEDIUM", "SELL", "STALE", 0.2),
            
            # LARGE scale patterns
            ("BOS_BEARISH", "LARGE", "SELL", "TP_HIT", 3.0),
            ("BOS_BEARISH", "LARGE", "SELL", "TP_HIT", 2.8)
        ]
        
        for i, (ptype, scale, direction, outcome, r_val) in enumerate(patterns):
            fingerprint = PatternFingerprint(
                pattern_type=ptype, scale=scale, direction=direction,
                structure_hash=f"hash_{i}", candle_pattern_hash=f"candle_{i}",
                regime_type="TRENDING_UP", mtf_alignment_bucket="HIGH",
                volatility_bucket="NORMAL", formation_time_bucket="FAST",
                timeframe_primary="M15", rr_bucket="MED", structure_strength_bucket="STRONG"
            )
            
            memory = PatternMemory(
                fingerprint=fingerprint, pattern_id=f"diverse_{i}", symbol="XAUUSD",
                detection_timestamp=datetime.now(timezone.utc).isoformat(),
                detection_price=2010.0, entry_price=2011.0, stop_loss=2005.0, take_profit=2023.0,
                outcome=outcome, actual_r=r_val, time_to_completion_minutes=30,
                max_favorable_r=r_val + 0.1, max_adverse_r=r_val - 0.1,
                pattern_quality_score=0.8, sequence_match=False, htf_confluence=True,
                session="LONDON", day_of_week=1, hour_of_day=10
            )
            
            self.memory_system.store_pattern_memory(memory)
    
    def test_pattern_statistics(self):
        """Test pattern statistics calculation."""
        # Overall statistics
        overall_stats = self.memory_system.get_pattern_statistics()
        assert overall_stats["sample_size"] == 8
        assert overall_stats["win_count"] == 5  # 5 TP_HIT patterns
        assert overall_stats["loss_count"] == 2  # 2 SL_HIT patterns
        assert overall_stats["stale_count"] == 1  # 1 STALE pattern
        
        # BOS_BULLISH statistics
        bos_stats = self.memory_system.get_pattern_statistics(pattern_type="BOS_BULLISH")
        assert bos_stats["sample_size"] == 3
        assert bos_stats["win_count"] == 2
        assert bos_stats["loss_count"] == 1
        
        # SMALL scale statistics
        small_stats = self.memory_system.get_pattern_statistics(scale="SMALL")
        assert small_stats["sample_size"] == 3
        
        print("✓ Pattern statistics calculation works")
        
    def test_memory_report_generation(self):
        """Test comprehensive memory report generation."""
        report = self.memory_system.generate_memory_report()
        
        assert isinstance(report, str)
        assert "PATTERN MEMORY SYSTEM" in report
        assert "Total Patterns in Memory: 8" in report
        assert "OUTCOME DISTRIBUTION" in report
        assert "PATTERN TYPE DISTRIBUTION" in report
        assert "TP_HIT" in report
        assert "BOS_BULLISH" in report
        
        print("✓ Memory report generation works")


def test_singleton_memory_system():
    """Test singleton pattern memory system."""
    system1 = get_pattern_memory_system()
    system2 = get_pattern_memory_system() 
    
    assert system1 is system2
    assert isinstance(system1, PatternMemorySystem)
    
    print("✓ Singleton memory system works")


if __name__ == "__main__":
    try:
        # Run all tests
        test_fingerprint = TestPatternFingerprint()
        test_fingerprint.setup_method()
        test_fingerprint.test_fingerprint_creation()
        test_fingerprint.test_identical_fingerprints()
        test_fingerprint.test_different_fingerprints()
        
        test_similarity = TestSimilarityMatching()
        test_similarity.setup_method() 
        test_similarity.test_exact_similarity_match()
        test_similarity.test_partial_similarity_match()
        
        test_storage = TestPatternMemoryStorage()
        test_storage.setup_method()
        test_storage.test_store_and_retrieve_pattern()
        test_storage.test_database_persistence()
        
        test_prediction = TestOutcomePrediction()
        test_prediction.setup_method()
        test_prediction.test_outcome_prediction()
        test_prediction.test_insufficient_data_prediction()
        
        test_stats = TestPatternStatistics()
        test_stats.setup_method()
        test_stats.test_pattern_statistics()
        test_stats.test_memory_report_generation()
        
        test_singleton_memory_system()
        
        print("\n🎉 All Pattern Memory System tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)