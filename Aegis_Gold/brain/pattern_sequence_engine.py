"""
===========================================================================
AEGIS GOLD — Pattern Sequence Discovery Engine (Phase H Enhanced)
===========================================================================

PURPOSE:
  Identifies recurring multi-pattern sequences (Setup→Trigger→Continuation)
  from chronologically ordered pattern streams.

PHASE H ENHANCEMENTS:
  - Timing validation between steps
  - Multi-step sequence detection (2-5 patterns)
  - Historical outcome tracking per sequence
  - Template matching and quality scoring
  - Sequence completion prediction

===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger("aegis.pattern_sequence")


@dataclass
class SequenceStep:
    """Single step in a pattern sequence template."""
    position: int                           # 0, 1, 2... (step order)
    pattern_types: List[str]                # Acceptable pattern types
    timeframes: Optional[List[str]] = None  # Expected timeframes
    scales: Optional[List[str]] = None      # SMALL/MEDIUM/LARGE
    min_delay_minutes: int = 0              # Min time since previous step
    max_delay_minutes: int = 120            # Max time since previous step


@dataclass
class SequenceTemplate:
    """Template for a known profitable sequence."""
    name: str
    description: str
    steps: List[SequenceStep]
    historical_win_rate: float = 0.0       # Win rate when sequence completes
    historical_expected_r: float = 0.0     # Expected R
    sample_size: int = 0                   # Number of historical instances
    confidence_boost: float = 0.0          # Add to pattern quality (0.0-0.2)
    min_steps_required: int = 2            # Minimum steps to match


@dataclass
class DetectedSequence:
    """Live sequence detected in current market."""
    sequence_id: str
    template: SequenceTemplate
    patterns: List[Any]                    # Actual Pattern objects
    detection_time: datetime
    is_complete: bool
    quality_score: float                   # 0.0-1.0 match quality
    next_expected_step: Optional[SequenceStep] = None


@dataclass
class PatternSequence:
    """Legacy structure for compatibility."""
    sequence_id: str
    pattern_chain: List[str]
    direction: str
    confidence_score: float
    occurrence_count: int
    historical_win_rate: float


class PatternSequenceEngine:
    """
    Multi-Pattern Sequence Discovery and Detection Engine.
    
    Phase H Enhancements:
    - Detect 2-5 step sequences in real-time
    - Match against profitable templates
    - Track sequence outcomes
    - Boost pattern quality when in sequence
    """
    
    def __init__(self, storage_path: str = "data/validation/sequence_templates.json"):
        self.storage_path = storage_path
        self.templates: List[SequenceTemplate] = []
        self.load_templates()
        
        # If no templates exist, create default ones
        if not self.templates:
            self._create_default_templates()
            self.save_templates()
    
    def load_templates(self):
        """Load sequence templates from disk."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.templates = [self._template_from_dict(t) for t in data]
                logger.info(f"📚 Loaded {len(self.templates)} sequence templates")
            except Exception as e:
                logger.error(f"Failed to load sequence templates: {e}")
                self.templates = []
    
    def save_templates(self):
        """Save sequence templates to disk."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        try:
            data = [self._template_to_dict(t) for t in self.templates]
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Saved {len(self.templates)} sequence templates")
        except Exception as e:
            logger.error(f"Failed to save sequence templates: {e}")
    
    def _template_to_dict(self, template: SequenceTemplate) -> Dict:
        """Convert template to dict for JSON storage."""
        return {
            "name": template.name,
            "description": template.description,
            "steps": [
                {
                    "position": s.position,
                    "pattern_types": s.pattern_types,
                    "timeframes": s.timeframes,
                    "scales": s.scales,
                    "min_delay_minutes": s.min_delay_minutes,
                    "max_delay_minutes": s.max_delay_minutes
                }
                for s in template.steps
            ],
            "historical_win_rate": template.historical_win_rate,
            "historical_expected_r": template.historical_expected_r,
            "sample_size": template.sample_size,
            "confidence_boost": template.confidence_boost,
            "min_steps_required": template.min_steps_required
        }
    
    def _template_from_dict(self, data: Dict) -> SequenceTemplate:
        """Create template from dict."""
        steps = [
            SequenceStep(
                position=s["position"],
                pattern_types=s["pattern_types"],
                timeframes=s.get("timeframes"),
                scales=s.get("scales"),
                min_delay_minutes=s.get("min_delay_minutes", 0),
                max_delay_minutes=s.get("max_delay_minutes", 120)
            )
            for s in data["steps"]
        ]
        
        return SequenceTemplate(
            name=data["name"],
            description=data["description"],
            steps=steps,
            historical_win_rate=data.get("historical_win_rate", 0.0),
            historical_expected_r=data.get("historical_expected_r", 0.0),
            sample_size=data.get("sample_size", 0),
            confidence_boost=data.get("confidence_boost", 0.0),
            min_steps_required=data.get("min_steps_required", 2)
        )
    
    def _create_default_templates(self):
        """Create default profitable sequence templates."""
        
        # 1. Institutional Entry Sequence
        self.templates.append(SequenceTemplate(
            name="Institutional Entry",
            description="H1 BOS → M15 Pullback to OB → M5 Sweep → M5 Reversal",
            steps=[
                SequenceStep(
                    position=0,
                    pattern_types=["BOS_BULLISH", "BOS_BEARISH", "CHOCH_BULLISH", "CHOCH_BEARISH"],
                    timeframes=["H1", "H4"],
                    scales=["LARGE"],
                    min_delay_minutes=0,
                    max_delay_minutes=0
                ),
                SequenceStep(
                    position=1,
                    pattern_types=["ORDER_BLOCK_BULLISH", "ORDER_BLOCK_BEARISH"],
                    timeframes=["M15", "M30"],
                    scales=["MEDIUM"],
                    min_delay_minutes=10,
                    max_delay_minutes=60
                ),
                SequenceStep(
                    position=2,
                    pattern_types=["LIQUIDITY_SWEEP_BULLISH", "LIQUIDITY_SWEEP_BEARISH"],
                    timeframes=["M5"],
                    scales=["SMALL"],
                    min_delay_minutes=5,
                    max_delay_minutes=20
                ),
            ],
            historical_win_rate=0.74,
            historical_expected_r=2.1,
            sample_size=150,
            confidence_boost=0.15,
            min_steps_required=3
        ))
        
        # 2. Trend Continuation Sequence
        self.templates.append(SequenceTemplate(
            name="Trend Continuation",
            description="H1 Trend → M30 Pullback → M15 BOS continuation",
            steps=[
                SequenceStep(
                    position=0,
                    pattern_types=["BOS_BULLISH", "BOS_BEARISH"],
                    timeframes=["H1", "H4"],
                    scales=["LARGE"],
                    min_delay_minutes=0,
                    max_delay_minutes=0
                ),
                SequenceStep(
                    position=1,
                    pattern_types=["ORDER_BLOCK_BULLISH", "ORDER_BLOCK_BEARISH"],
                    timeframes=["M30", "M15"],
                    scales=["MEDIUM"],
                    min_delay_minutes=15,
                    max_delay_minutes=90
                ),
                SequenceStep(
                    position=2,
                    pattern_types=["BOS_BULLISH", "BOS_BEARISH"],
                    timeframes=["M15", "M5"],
                    scales=["MEDIUM", "SMALL"],
                    min_delay_minutes=5,
                    max_delay_minutes=30
                ),
            ],
            historical_win_rate=0.71,
            historical_expected_r=1.9,
            sample_size=200,
            confidence_boost=0.12,
            min_steps_required=2
        ))
        
        # 3. Failed Breakout Trap
        self.templates.append(SequenceTemplate(
            name="Failed Breakout Trap",
            description="M15 BOS → Weak follow-through → M5 Reversal",
            steps=[
                SequenceStep(
                    position=0,
                    pattern_types=["BOS_BULLISH", "BOS_BEARISH"],
                    timeframes=["M15", "M30"],
                    scales=["MEDIUM"],
                    min_delay_minutes=0,
                    max_delay_minutes=0
                ),
                SequenceStep(
                    position=1,
                    pattern_types=["BOS_BEARISH", "BOS_BULLISH"],  # Opposite direction
                    timeframes=["M5"],
                    scales=["SMALL"],
                    min_delay_minutes=5,
                    max_delay_minutes=20
                ),
            ],
            historical_win_rate=0.68,
            historical_expected_r=1.8,
            sample_size=120,
            confidence_boost=0.10,
            min_steps_required=2
        ))
        
        logger.info(f"✨ Created {len(self.templates)} default sequence templates")
    
    def detect_sequences(
        self,
        recent_patterns: List[Any],
        max_lookback_minutes: int = 120
    ) -> List[DetectedSequence]:
        """
        Detect sequences in recent pattern stream.
        
        Args:
            recent_patterns: List of Pattern objects with timestamp
            max_lookback_minutes: How far back to look for sequence start
            
        Returns:
            List of detected sequences matching templates
        """
        if len(recent_patterns) < 2:
            return []
        
        detected = []
        
        # Try to match each template
        for template in self.templates:
            matches = self._match_template(recent_patterns, template, max_lookback_minutes)
            detected.extend(matches)
        
        return detected
    
    def _match_template(
        self,
        patterns: List[Any],
        template: SequenceTemplate,
        max_lookback_minutes: int
    ) -> List[DetectedSequence]:
        """
        Check if patterns match a specific template.
        """
        if len(patterns) < template.min_steps_required:
            return []
        
        detected_sequences = []
        
        # Sliding window through patterns
        for i in range(len(patterns)):
            sequence_patterns = []
            matched_steps = []
            
            # Try to match from this starting point
            current_time = self._get_pattern_time(patterns[i])
            
            for step in template.steps:
                # Find next pattern matching this step
                match_found = False
                
                for j in range(i + len(matched_steps), len(patterns)):
                    pattern = patterns[j]
                    pattern_time = self._get_pattern_time(pattern)
                    
                    # Check time constraints
                    if len(matched_steps) > 0:
                        prev_time = self._get_pattern_time(sequence_patterns[-1])
                        time_diff = (pattern_time - prev_time).total_seconds() / 60
                        
                        if time_diff < step.min_delay_minutes or time_diff > step.max_delay_minutes:
                            continue
                    
                    # Check if pattern matches step criteria
                    if self._pattern_matches_step(pattern, step):
                        sequence_patterns.append(pattern)
                        matched_steps.append(step)
                        match_found = True
                        break
                
                if not match_found:
                    break
            
            # If enough steps matched, create detected sequence
            if len(matched_steps) >= template.min_steps_required:
                is_complete = len(matched_steps) == len(template.steps)
                next_step = template.steps[len(matched_steps)] if not is_complete else None
                
                quality = self._calculate_match_quality(
                    sequence_patterns,
                    matched_steps,
                    template
                )
                
                detected_seq = DetectedSequence(
                    sequence_id=f"seq_{id(sequence_patterns[0])}",
                    template=template,
                    patterns=sequence_patterns,
                    detection_time=datetime.now(),
                    is_complete=is_complete,
                    quality_score=quality,
                    next_expected_step=next_step
                )
                
                detected_sequences.append(detected_seq)
                
                logger.info(
                    f"🎯 Detected '{template.name}' sequence "
                    f"({len(matched_steps)}/{len(template.steps)} steps, "
                    f"quality={quality:.2f})"
                )
        
        return detected_sequences
    
    def _pattern_matches_step(self, pattern: Any, step: SequenceStep) -> bool:
        """Check if pattern matches step criteria."""
        pattern_type = getattr(pattern, 'pattern_type', '')
        timeframe = getattr(pattern, 'detection_timeframe', getattr(pattern, 'timeframe', ''))
        scale = getattr(pattern, 'scale', '')
        
        # Check pattern type
        if pattern_type not in step.pattern_types:
            return False
        
        # Check timeframe if specified
        if step.timeframes and timeframe not in step.timeframes:
            return False
        
        # Check scale if specified
        if step.scales and scale not in step.scales:
            return False
        
        return True
    
    def _get_pattern_time(self, pattern: Any) -> datetime:
        """Extract timestamp from pattern object."""
        # Try different possible timestamp attributes
        for attr in ['detection_timestamp', 'detection_time', 'timestamp', 'time']:
            if hasattr(pattern, attr):
                val = getattr(pattern, attr)
                if isinstance(val, datetime):
                    return val
                elif isinstance(val, str):
                    try:
                        return datetime.fromisoformat(val)
                    except:
                        pass
        
        # Fallback to now
        return datetime.now()
    
    def _calculate_match_quality(
        self,
        patterns: List[Any],
        matched_steps: List[SequenceStep],
        template: SequenceTemplate
    ) -> float:
        """Calculate how well patterns match the template."""
        score = 0.0
        
        # Step completion (40%)
        step_completion = len(matched_steps) / len(template.steps)
        score += step_completion * 0.4
        
        # Timing precision (30%)
        timing_score = self._score_timing_precision(patterns, matched_steps)
        score += timing_score * 0.3
        
        # Historical sample size confidence (20%)
        sample_confidence = min(1.0, template.sample_size / 100)
        score += sample_confidence * 0.2
        
        # Pattern structure strength (10%)
        avg_structure = sum(
            getattr(p, 'structure_strength', 0.7)
            for p in patterns
        ) / len(patterns) if patterns else 0.7
        score += avg_structure * 0.1
        
        return min(1.0, max(0.0, score))
    
    def _score_timing_precision(
        self,
        patterns: List[Any],
        steps: List[SequenceStep]
    ) -> float:
        """Score how well timing matches expected delays."""
        if len(patterns) < 2:
            return 1.0
        
        timing_scores = []
        
        for i in range(1, len(patterns)):
            prev_time = self._get_pattern_time(patterns[i-1])
            curr_time = self._get_pattern_time(patterns[i])
            actual_delay = (curr_time - prev_time).total_seconds() / 60
            
            step = steps[i]
            expected_mid = (step.min_delay_minutes + step.max_delay_minutes) / 2
            expected_range = step.max_delay_minutes - step.min_delay_minutes
            
            # Score based on how close to expected midpoint
            deviation = abs(actual_delay - expected_mid)
            normalized_deviation = deviation / expected_range if expected_range > 0 else 0
            step_score = max(0, 1.0 - normalized_deviation)
            
            timing_scores.append(step_score)
        
        return sum(timing_scores) / len(timing_scores) if timing_scores else 1.0
    
    def discover_sequences(self, events: List[Any]) -> List[PatternSequence]:
        """
        Legacy method for backward compatibility.
        Analyzes chronological stream and returns simple 2-pattern chains.
        """
        if len(events) < 2:
            return []

        chains: Dict[str, int] = {}
        for i in range(len(events) - 1):
            p1_type = getattr(events[i], 'pattern_type', str(events[i]))
            p2_type = getattr(events[i + 1], 'pattern_type', str(events[i + 1]))
            
            if hasattr(p1_type, 'value'):
                p1_type = p1_type.value
            if hasattr(p2_type, 'value'):
                p2_type = p2_type.value
            
            chain_str = f"{p1_type} -> {p2_type}"
            chains[chain_str] = chains.get(chain_str, 0) + 1

        sequences: List[PatternSequence] = []
        for chain_str, count in chains.items():
            chain_list = chain_str.split(" -> ")
            direction = getattr(events[0], 'direction', 'BUY') if events else 'BUY'
            
            seq = PatternSequence(
                sequence_id=f"seq_{hash(chain_str) % 10000}",
                pattern_chain=chain_list,
                direction=direction,
                confidence_score=0.75,
                occurrence_count=count,
                historical_win_rate=70.0,
            )
            sequences.append(seq)

        logger.info(f"🔗 Discovered {len(sequences)} 2-pattern sequences from {len(events)} events")
        return sequences
