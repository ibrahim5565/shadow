"""
===========================================================================
AEGIS GOLD — Pattern Memory System (Phase J)
===========================================================================

PURPOSE:
--------
Builds a comprehensive historical pattern outcome database with similarity 
matching to learn from past patterns and predict future outcomes.

CORE FEATURES:
--------------
1. Pattern Fingerprinting - Unique identifiers based on structure
2. Similarity Matching - Find historical patterns similar to current ones
3. Outcome Prediction - Use similar patterns to predict likely outcomes  
4. Memory Database - Persistent storage with efficient retrieval
5. Pattern Evolution - Track how patterns change over time
6. Confidence Scoring - Statistical confidence in predictions

INTEGRATION:
------------
- Builds on Phase G pattern outcome tracker
- Uses Phase F pattern scale classification  
- Integrates with Phase E multi-timeframe analysis
- Supports Phase I causality enforcement

===========================================================================
"""

import logging
import numpy as np
import json
import os
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict
from enum import Enum
import sqlite3
from pathlib import Path

logger = logging.getLogger("aegis.pattern_memory")

@dataclass
class PatternFingerprint:
    """
    Unique identifier for a pattern based on its structural characteristics.
    """
    # Core structure
    pattern_type: str              # "BOS_BULLISH", "CHOCH_BEARISH", etc.
    scale: str                     # "SMALL", "MEDIUM", "LARGE"  
    direction: str                 # "BUY", "SELL"
    
    # Price structure (normalized)
    structure_hash: str            # Hash of key price levels
    candle_pattern_hash: str       # Hash of candlestick sequence
    
    # Context fingerprint
    regime_type: str               # "TRENDING_UP", "RANGING", etc.
    mtf_alignment_bucket: str      # "LOW", "MED", "HIGH" (bucketed alignment)
    volatility_bucket: str         # "LOW", "NORMAL", "HIGH"
    
    # Timing characteristics
    formation_time_bucket: str     # "FAST", "NORMAL", "SLOW" formation
    timeframe_primary: str         # Primary detection timeframe
    
    # Technical context
    rr_bucket: str                 # "LOW", "MED", "HIGH" risk/reward
    structure_strength_bucket: str # "WEAK", "MODERATE", "STRONG"
    
    def to_key(self) -> str:
        """Generate unique key for this fingerprint."""
        components = [
            self.pattern_type, self.scale, self.direction,
            self.structure_hash[:8],  # First 8 chars of hash
            self.regime_type, self.mtf_alignment_bucket,
            self.volatility_bucket, self.formation_time_bucket,
            self.timeframe_primary, self.rr_bucket
        ]
        return "|".join(components)
@dataclass
class PatternMemory:
    """
    Stored memory of a pattern with its outcome and characteristics.
    """
    fingerprint: PatternFingerprint
    pattern_id: str
    symbol: str
    
    # Detection info
    detection_timestamp: str
    detection_price: float
    entry_price: float
    stop_loss: float
    take_profit: float
    
    # Outcome
    outcome: str                   # "TP_HIT", "SL_HIT", "STALE", etc.
    actual_r: float               # Actual R achieved
    time_to_completion_minutes: int
    max_favorable_r: float
    max_adverse_r: float
    
    # Quality metrics at detection
    pattern_quality_score: float   # 0.0-1.0 from 10-gate system
    sequence_match: bool           # Was part of profitable sequence
    htf_confluence: bool          # Had HTF confluence
    
    # Market context
    session: str                   # "LONDON", "NY", "ASIA", "OVERLAP"
    day_of_week: int              # 0-6 (Monday=0)
    hour_of_day: int              # 0-23
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage.""" 
        result = asdict(self)
        result['fingerprint'] = asdict(self.fingerprint)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PatternMemory':
        """Create from dictionary."""
        fingerprint_data = data.pop('fingerprint')
        fingerprint = PatternFingerprint(**fingerprint_data)
        return cls(fingerprint=fingerprint, **data)
@dataclass
class SimilarityMatch:
    """
    Result of pattern similarity matching.
    """
    memory: PatternMemory
    similarity_score: float        # 0.0-1.0
    matching_features: List[str]   # Which features matched
    confidence: float             # Statistical confidence in match
    
class PatternPrediction:
    """
    Prediction based on similar historical patterns.
    """
    def __init__(self):
        self.predicted_outcome: str = "UNKNOWN"
        self.win_probability: float = 0.5
        self.expected_r: float = 0.0
        self.confidence: float = 0.0
        self.sample_size: int = 0
        self.similar_patterns: List[SimilarityMatch] = []
        self.avg_time_to_completion: int = 0
        self.max_expected_drawdown: float = 0.0
        
        # Statistical breakdown
        self.outcomes_breakdown: Dict[str, int] = {}
        self.r_distribution: Dict[str, float] = {}
        
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "predicted_outcome": self.predicted_outcome,
            "win_probability": self.win_probability,
            "expected_r": self.expected_r,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "avg_time_to_completion": self.avg_time_to_completion,
            "max_expected_drawdown": self.max_expected_drawdown,
            "outcomes_breakdown": self.outcomes_breakdown,
            "r_distribution": self.r_distribution
        }
class PatternMemorySystem:
    """
    Core pattern memory engine for similarity matching and outcome prediction.
    """
    
    def __init__(self, db_path: str = "data/pattern_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for fast lookups
        self.memory_cache: Dict[str, PatternMemory] = {}
        self.fingerprint_index: Dict[str, List[str]] = defaultdict(list)
        
        # Similarity thresholds
        self.min_similarity_threshold = 0.70
        self.min_sample_size = 3
        self.confidence_threshold = 0.60
        
        self._initialize_database()
        self._load_memory_cache()
        
        logger.info(f"[MEMORY] Pattern Memory System initialized with {len(self.memory_cache)} patterns")
    
    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection that is properly closed after use."""
        return sqlite3.connect(self.db_path)
    
    def _initialize_database(self):
        """Initialize SQLite database for pattern storage."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            
            # Create patterns table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pattern_memories (
                    pattern_id TEXT PRIMARY KEY,
                    fingerprint_key TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    scale TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    detection_timestamp TEXT NOT NULL,
                    detection_price REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    outcome TEXT NOT NULL,
                    actual_r REAL NOT NULL,
                    time_to_completion_minutes INTEGER NOT NULL,
                    max_favorable_r REAL NOT NULL,
                    max_adverse_r REAL NOT NULL,
                    pattern_quality_score REAL NOT NULL,
                    sequence_match INTEGER NOT NULL,
                    htf_confluence INTEGER NOT NULL,
                    session TEXT NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    hour_of_day INTEGER NOT NULL,
                    full_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for fast lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_fingerprint_key ON pattern_memories(fingerprint_key)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pattern_type ON pattern_memories(pattern_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scale_direction ON pattern_memories(scale, direction)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_outcome ON pattern_memories(outcome)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_detection_time ON pattern_memories(detection_timestamp)')
            
            conn.commit()
            logger.info("[MEMORY] Database initialized successfully")
        finally:
            conn.close()
    
    def _load_memory_cache(self):
        """Load pattern memories from database into cache."""
        try:
            conn = self._connect()
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT pattern_id, fingerprint_key, full_data FROM pattern_memories')
                
                for row in cursor.fetchall():
                    pattern_id, fingerprint_key, full_data = row
                    try:
                        data = json.loads(full_data)
                        memory = PatternMemory.from_dict(data)
                        self.memory_cache[pattern_id] = memory
                        self.fingerprint_index[fingerprint_key].append(pattern_id)
                    except Exception as e:
                        logger.warning(f"[MEMORY] Failed to load pattern {pattern_id}: {e}")
            finally:
                conn.close()
                        
        except Exception as e:
            logger.error(f"[MEMORY] Failed to load cache: {e}")
    
    def create_pattern_fingerprint(
        self,
        pattern_type: str,
        scale: str,
        direction: str,
        price_levels: List[float],
        candle_data: List[Dict],
        regime: str,
        mtf_alignment: float,
        volatility: float,
        formation_speed: float,
        timeframe: str,
        rr_ratio: float,
        structure_strength: float
    ) -> PatternFingerprint:
        """
        Create a unique fingerprint for a pattern based on its characteristics.
        """
        # Create structure hash from normalized price levels
        if price_levels:
            # Normalize prices relative to first price
            base_price = price_levels[0]
            normalized = [(p / base_price - 1.0) * 1000 for p in price_levels]  # Scale for hashing
            structure_data = "|".join([f"{n:.1f}" for n in normalized])
            structure_hash = hashlib.md5(structure_data.encode()).hexdigest()
        else:
            structure_hash = "no_structure"
        
        # Create candle pattern hash
        if candle_data:
            candle_pattern = []
            for candle in candle_data[-10:]:  # Last 10 candles
                o, h, l, c = candle.get('open', 0), candle.get('high', 0), candle.get('low', 0), candle.get('close', 0)
                if o > 0:
                    body = abs(c - o) / o * 100  # Body size %
                    upper_shadow = (h - max(o, c)) / o * 100  # Upper shadow %
                    lower_shadow = (min(o, c) - l) / o * 100  # Lower shadow %
                    candle_pattern.append(f"{body:.0f},{upper_shadow:.0f},{lower_shadow:.0f}")
            
            candle_hash = hashlib.md5("|".join(candle_pattern).encode()).hexdigest()
        else:
            candle_hash = "no_candles"
        
        # Bucket continuous values for similarity matching
        mtf_bucket = "LOW" if mtf_alignment < 0.4 else ("MED" if mtf_alignment < 0.7 else "HIGH")
        vol_bucket = "LOW" if volatility < 0.3 else ("NORMAL" if volatility < 0.7 else "HIGH") 
        formation_bucket = "FAST" if formation_speed < 0.3 else ("NORMAL" if formation_speed < 0.7 else "SLOW")
        rr_bucket = "LOW" if rr_ratio < 1.5 else ("MED" if rr_ratio < 2.5 else "HIGH")
        strength_bucket = "WEAK" if structure_strength < 0.4 else ("MODERATE" if structure_strength < 0.7 else "STRONG")
        
        return PatternFingerprint(
            pattern_type=pattern_type,
            scale=scale,
            direction=direction,
            structure_hash=structure_hash,
            candle_pattern_hash=candle_hash,
            regime_type=regime,
            mtf_alignment_bucket=mtf_bucket,
            volatility_bucket=vol_bucket,
            formation_time_bucket=formation_bucket,
            timeframe_primary=timeframe,
            rr_bucket=rr_bucket,
            structure_strength_bucket=strength_bucket
        )
    def store_pattern_memory(self, memory: PatternMemory):
        """
        Store a completed pattern in the memory system.
        """
        try:
            fingerprint_key = memory.fingerprint.to_key()
            
            # Store in database (properly close SQLite connection for Windows)
            conn = self._connect()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO pattern_memories 
                    (pattern_id, fingerprint_key, symbol, pattern_type, scale, direction,
                     detection_timestamp, detection_price, entry_price, stop_loss, take_profit,
                     outcome, actual_r, time_to_completion_minutes, max_favorable_r, max_adverse_r,
                     pattern_quality_score, sequence_match, htf_confluence, session, day_of_week,
                     hour_of_day, full_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    memory.pattern_id, fingerprint_key, memory.symbol, memory.fingerprint.pattern_type,
                    memory.fingerprint.scale, memory.fingerprint.direction, memory.detection_timestamp,
                    memory.detection_price, memory.entry_price, memory.stop_loss, memory.take_profit,
                    memory.outcome, memory.actual_r, memory.time_to_completion_minutes,
                    memory.max_favorable_r, memory.max_adverse_r, memory.pattern_quality_score,
                    int(memory.sequence_match), int(memory.htf_confluence), memory.session,
                    memory.day_of_week, memory.hour_of_day, json.dumps(memory.to_dict())
                ))
                conn.commit()
            finally:
                conn.close()
            
            # Update cache
            self.memory_cache[memory.pattern_id] = memory
            self.fingerprint_index[fingerprint_key].append(memory.pattern_id)
            
            logger.info(f"[MEMORY] Stored pattern {memory.pattern_id} with outcome {memory.outcome}")
            
        except Exception as e:
            logger.error(f"[MEMORY] Failed to store pattern {memory.pattern_id}: {e}")
    
    def calculate_similarity(self, fp1: PatternFingerprint, fp2: PatternFingerprint) -> Tuple[float, List[str]]:
        """
        Calculate similarity score between two pattern fingerprints.
        Returns (similarity_score, matching_features)
        """
        matches = []
        weights = {
            'pattern_type': 0.25,        # Most important
            'direction': 0.20,           # Very important 
            'scale': 0.15,               # Important
            'regime_type': 0.10,         # Moderately important
            'mtf_alignment_bucket': 0.08,
            'rr_bucket': 0.07,
            'structure_strength_bucket': 0.05,
            'timeframe_primary': 0.05,
            'volatility_bucket': 0.03,
            'formation_time_bucket': 0.02
        }
        
        total_score = 0.0
        
        for feature, weight in weights.items():
            val1 = getattr(fp1, feature, None)
            val2 = getattr(fp2, feature, None)
            
            if val1 == val2 and val1 is not None:
                total_score += weight
                matches.append(feature)
        
        # Bonus for structure similarity (hash comparison)
        if fp1.structure_hash == fp2.structure_hash:
            total_score += 0.1
            matches.append('structure_hash')
        
        # Partial bonus for candle pattern similarity
        if fp1.candle_pattern_hash == fp2.candle_pattern_hash:
            total_score += 0.05
            matches.append('candle_pattern_hash')
        
        return min(1.0, total_score), matches
    def find_similar_patterns(
        self,
        target_fingerprint: PatternFingerprint,
        min_similarity: float = None,
        max_results: int = 50
    ) -> List[SimilarityMatch]:
        """
        Find historical patterns similar to the target fingerprint.
        """
        if min_similarity is None:
            min_similarity = self.min_similarity_threshold
        
        matches = []
        target_key = target_fingerprint.to_key()
        
        # Start with exact fingerprint matches (fastest)
        if target_key in self.fingerprint_index:
            for pattern_id in self.fingerprint_index[target_key]:
                if pattern_id in self.memory_cache:
                    memory = self.memory_cache[pattern_id]
                    matches.append(SimilarityMatch(
                        memory=memory,
                        similarity_score=1.0,
                        matching_features=['exact_match'],
                        confidence=1.0
                    ))
        
        # If we need more matches, do similarity search
        if len(matches) < max_results:
            for memory in self.memory_cache.values():
                # Skip if already have exact match
                if any(m.memory.pattern_id == memory.pattern_id for m in matches):
                    continue
                
                similarity, matching_features = self.calculate_similarity(
                    target_fingerprint, memory.fingerprint
                )
                
                if similarity >= min_similarity:
                    # Calculate confidence based on sample quality
                    confidence = min(1.0, similarity * 0.8 + 0.2)  # Baseline confidence
                    
                    matches.append(SimilarityMatch(
                        memory=memory,
                        similarity_score=similarity,
                        matching_features=matching_features,
                        confidence=confidence
                    ))
        
        # Sort by similarity and limit results
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return matches[:max_results]
    
    def predict_pattern_outcome(self, target_fingerprint: PatternFingerprint) -> PatternPrediction:
        """
        Predict likely outcome for a pattern based on similar historical patterns.
        """
        prediction = PatternPrediction()
        
        # Find similar patterns
        similar_matches = self.find_similar_patterns(target_fingerprint)
        
        if len(similar_matches) < self.min_sample_size:
            logger.warning(f"[MEMORY] Insufficient similar patterns: {len(similar_matches)} < {self.min_sample_size}")
            return prediction  # Return default (unknown) prediction
        
        # Extract outcomes from similar patterns
        outcomes = []
        r_values = []
        completion_times = []
        drawdowns = []
        
        for match in similar_matches:
            memory = match.memory
            # Weight by similarity score
            weight = match.similarity_score
            
            outcomes.append((memory.outcome, weight))
            r_values.append(memory.actual_r * weight)
            completion_times.append(memory.time_to_completion_minutes * weight)
            drawdowns.append(abs(memory.max_adverse_r) * weight)
        
        # Calculate weighted statistics
        total_weight = sum(weight for _, weight in outcomes)
        
        if total_weight == 0:
            return prediction
        
        # Outcome probabilities
        outcome_weights = defaultdict(float)
        for outcome, weight in outcomes:
            outcome_weights[outcome] += weight
        
        # Normalize to probabilities
        for outcome in outcome_weights:
            outcome_weights[outcome] /= total_weight
        
        # Most likely outcome
        prediction.predicted_outcome = max(outcome_weights.items(), key=lambda x: x[1])[0]
        prediction.win_probability = outcome_weights.get('TP_HIT', 0.0)
        
        # Expected R and other metrics
        prediction.expected_r = sum(r_values) / total_weight
        prediction.avg_time_to_completion = int(sum(completion_times) / total_weight)
        prediction.max_expected_drawdown = sum(drawdowns) / total_weight
        
        # Sample size and confidence
        prediction.sample_size = len(similar_matches)
        prediction.similar_patterns = similar_matches[:10]  # Top 10 for reference
        
        # Calculate confidence based on sample size, similarity, and consistency
        sample_confidence = min(1.0, len(similar_matches) / 20.0)  # 20+ samples = full confidence
        avg_similarity = sum(m.similarity_score for m in similar_matches) / len(similar_matches)
        outcome_consistency = max(outcome_weights.values())  # How concentrated outcomes are
        
        prediction.confidence = (sample_confidence * 0.4 + avg_similarity * 0.3 + outcome_consistency * 0.3)
        
        # Breakdowns for analysis
        prediction.outcomes_breakdown = {k: int(v * len(similar_matches)) for k, v in outcome_weights.items()}
        prediction.r_distribution = {
            "min": min(m.memory.actual_r for m in similar_matches),
            "max": max(m.memory.actual_r for m in similar_matches),
            "mean": prediction.expected_r,
            "p25": sorted([m.memory.actual_r for m in similar_matches])[len(similar_matches)//4],
            "p75": sorted([m.memory.actual_r for m in similar_matches])[3*len(similar_matches)//4]
        }
        
        logger.info(
            f"[MEMORY] Predicted {prediction.predicted_outcome} "
            f"(P={prediction.win_probability:.2f}, R={prediction.expected_r:.2f}, "
            f"Conf={prediction.confidence:.2f}, N={prediction.sample_size})"
        )
        
        return prediction
    def get_pattern_statistics(
        self, 
        pattern_type: Optional[str] = None,
        scale: Optional[str] = None,
        direction: Optional[str] = None,
        regime: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for patterns matching filters.
        """
        # Filter memories
        filtered_memories = []
        for memory in self.memory_cache.values():
            if (pattern_type is None or memory.fingerprint.pattern_type == pattern_type) and \
               (scale is None or memory.fingerprint.scale == scale) and \
               (direction is None or memory.fingerprint.direction == direction) and \
               (regime is None or memory.fingerprint.regime_type == regime):
                filtered_memories.append(memory)
        
        if not filtered_memories:
            return {"sample_size": 0, "message": "No patterns match criteria"}
        
        # Calculate statistics
        total = len(filtered_memories)
        outcomes = defaultdict(int)
        r_values = []
        completion_times = []
        
        for memory in filtered_memories:
            outcomes[memory.outcome] += 1
            r_values.append(memory.actual_r)
            completion_times.append(memory.time_to_completion_minutes)
        
        win_count = outcomes.get('TP_HIT', 0)
        win_rate = win_count / total if total > 0 else 0.0
        
        return {
            "sample_size": total,
            "win_count": win_count,
            "loss_count": outcomes.get('SL_HIT', 0),
            "stale_count": outcomes.get('STALE', 0),
            "win_rate": round(win_rate * 100, 1),
            "avg_r": round(sum(r_values) / len(r_values), 2) if r_values else 0.0,
            "expected_r": round(sum(r for r in r_values if r > 0) * win_rate + 
                               sum(r for r in r_values if r < 0) * (1-win_rate), 2),
            "avg_completion_time": int(sum(completion_times) / len(completion_times)) if completion_times else 0,
            "outcomes_breakdown": dict(outcomes),
            "tradeable": win_rate > 0.6 and sum(r_values) / len(r_values) > 0.0
        }
    
    def migrate_from_outcome_tracker(self, outcome_tracker):
        """
        Migrate existing pattern data from PatternOutcomeTracker to memory system.
        """
        from brain.pattern_outcome_tracker import PatternOutcomeTracker, PatternOutcome
        
        migrated_count = 0
        
        for pattern_id, tracked_pattern in outcome_tracker.tracked_patterns.items():
            # Skip pending patterns
            if tracked_pattern.outcome == PatternOutcome.PENDING.value:
                continue
            
            try:
                # Create fingerprint (with some defaults for missing data)
                fingerprint = self.create_pattern_fingerprint(
                    pattern_type=tracked_pattern.pattern_type,
                    scale=tracked_pattern.scale,
                    direction=tracked_pattern.direction,
                    price_levels=[tracked_pattern.entry_price, tracked_pattern.stop_loss, tracked_pattern.take_profit],
                    candle_data=[],  # Not available in tracker
                    regime=tracked_pattern.regime,
                    mtf_alignment=tracked_pattern.mtf_alignment,
                    volatility=0.5,  # Default
                    formation_speed=0.5,  # Default
                    timeframe=tracked_pattern.detection_timeframe,
                    rr_ratio=tracked_pattern.rr_ratio,
                    structure_strength=tracked_pattern.structure_strength
                )
                
                # Extract session info from timestamp
                detection_time = datetime.fromisoformat(tracked_pattern.detection_timestamp)
                session = self._determine_session(detection_time.hour)
                
                # Create memory record
                memory = PatternMemory(
                    fingerprint=fingerprint,
                    pattern_id=pattern_id,
                    symbol=tracked_pattern.symbol,
                    detection_timestamp=tracked_pattern.detection_timestamp,
                    detection_price=tracked_pattern.detection_price,
                    entry_price=tracked_pattern.entry_price,
                    stop_loss=tracked_pattern.stop_loss,
                    take_profit=tracked_pattern.take_profit,
                    outcome=tracked_pattern.outcome,
                    actual_r=tracked_pattern.actual_r,
                    time_to_completion_minutes=tracked_pattern.time_to_completion_minutes,
                    max_favorable_r=tracked_pattern.max_favorable_r,
                    max_adverse_r=tracked_pattern.max_adverse_r,
                    pattern_quality_score=0.8,  # Default high quality
                    sequence_match=False,  # Unknown
                    htf_confluence=tracked_pattern.htf_bias != "NEUTRAL",
                    session=session,
                    day_of_week=detection_time.weekday(),
                    hour_of_day=detection_time.hour
                )
                
                self.store_pattern_memory(memory)
                migrated_count += 1
                
            except Exception as e:
                logger.warning(f"[MEMORY] Failed to migrate pattern {pattern_id}: {e}")
        
        logger.info(f"[MEMORY] Migrated {migrated_count} patterns from outcome tracker")
        return migrated_count
    
    def _determine_session(self, hour: int) -> str:
        """Determine trading session from hour (UTC)."""
        if 8 <= hour < 17:
            return "LONDON"
        elif 13 <= hour < 22:
            return "NY" if hour >= 17 else "OVERLAP"  
        elif 22 <= hour or hour < 8:
            return "ASIA"
        else:
            return "OVERLAP"
    def generate_memory_report(self) -> str:
        """Generate comprehensive memory system report."""
        total_patterns = len(self.memory_cache)
        
        if total_patterns == 0:
            return "No patterns in memory system yet."
        
        # Outcome distribution
        outcomes = defaultdict(int)
        for memory in self.memory_cache.values():
            outcomes[memory.outcome] += 1
        
        # Pattern type distribution  
        pattern_types = defaultdict(int)
        for memory in self.memory_cache.values():
            pattern_types[memory.fingerprint.pattern_type] += 1
        
        # Scale distribution
        scales = defaultdict(int)
        for memory in self.memory_cache.values():
            scales[memory.fingerprint.scale] += 1
        
        # Generate report
        report = [
            "="*70,
            "PATTERN MEMORY SYSTEM — COMPREHENSIVE REPORT",
            "="*70,
            f"Total Patterns in Memory: {total_patterns}",
            f"Unique Fingerprints: {len(self.fingerprint_index)}",
            "",
            "OUTCOME DISTRIBUTION:",
            "-"*40
        ]
        
        for outcome, count in sorted(outcomes.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_patterns) * 100
            report.append(f"  {outcome}: {count} ({pct:.1f}%)")
        
        report.extend([
            "",
            "PATTERN TYPE DISTRIBUTION:",
            "-"*40
        ])
        
        for ptype, count in sorted(pattern_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            pct = (count / total_patterns) * 100
            report.append(f"  {ptype}: {count} ({pct:.1f}%)")
        
        report.extend([
            "",
            "SCALE DISTRIBUTION:",
            "-"*40
        ])
        
        for scale, count in sorted(scales.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_patterns) * 100
            report.append(f"  {scale}: {count} ({pct:.1f}%)")
        
        # Sample predictions for common patterns
        report.extend([
            "",
            "SAMPLE PREDICTIONS:",
            "-"*40
        ])
        
        common_patterns = list(pattern_types.keys())[:3]
        for ptype in common_patterns:
            # Create sample fingerprint
            sample_memories = [m for m in self.memory_cache.values() 
                             if m.fingerprint.pattern_type == ptype]
            if sample_memories:
                sample = sample_memories[0]
                prediction = self.predict_pattern_outcome(sample.fingerprint)
                report.append(
                    f"  {ptype}: P(Win)={prediction.win_probability:.2f}, "
                    f"E(R)={prediction.expected_r:.2f}, N={prediction.sample_size}"
                )
        
        report.append("="*70)
        return "\n".join(report)


# Global singleton instance
_pattern_memory_system = None

def get_pattern_memory_system() -> PatternMemorySystem:
    """Get or create singleton pattern memory system instance."""
    global _pattern_memory_system
    if _pattern_memory_system is None:
        _pattern_memory_system = PatternMemorySystem()
    return _pattern_memory_system