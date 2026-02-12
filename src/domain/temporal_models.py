"""Temporal scoring domain models.

Defines decay rates, temporal windows, and scoring configurations
for the temporal scoring service.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, List
import math


class TemporalWindow(str, Enum):
    """Named temporal windows for query parsing."""

    IMMEDIATE = "immediate"      # Last few hours
    RECENT = "recent"            # Last 24 hours
    SHORT_TERM = "short_term"    # Last 7 days
    MEDIUM_TERM = "medium_term"  # Last 30 days
    LONG_TERM = "long_term"      # Last 90 days
    HISTORICAL = "historical"    # All time


@dataclass
class DecayConfig:
    """Configuration for exponential decay of an entity type.

    The decay formula is: score = exp(-lambda * hours_since_observation)

    Attributes:
        lambda_rate: Decay rate constant (higher = faster decay)
        half_life_hours: Time for relevance to drop to 50%
        min_score: Minimum score floor (entities never fully decay)
        description: Human-readable description
    """

    lambda_rate: float
    half_life_hours: float
    min_score: float = 0.1
    description: str = ""

    @classmethod
    def from_half_life(cls, half_life_hours: float, min_score: float = 0.1, description: str = "") -> "DecayConfig":
        """Create decay config from half-life in hours.

        Half-life is when score = 0.5, so:
        0.5 = exp(-lambda * half_life)
        ln(0.5) = -lambda * half_life
        lambda = -ln(0.5) / half_life = ln(2) / half_life
        """
        lambda_rate = math.log(2) / half_life_hours
        return cls(
            lambda_rate=lambda_rate,
            half_life_hours=half_life_hours,
            min_score=min_score,
            description=description,
        )


# Entity-type specific decay configurations
# Based on medical relevance patterns
ENTITY_DECAY_CONFIGS: Dict[str, DecayConfig] = {
    # Symptoms: Short half-life, symptoms are transient
    "Symptom": DecayConfig.from_half_life(
        half_life_hours=20,
        min_score=0.05,
        description="Symptoms decay quickly as they're often transient"
    ),

    # Vital signs: Very short half-life, need current values
    "VitalSign": DecayConfig.from_half_life(
        half_life_hours=33,
        min_score=0.05,
        description="Vital signs need to be current to be meaningful"
    ),

    # Lab results: Medium half-life
    "LabResult": DecayConfig.from_half_life(
        half_life_hours=72,
        min_score=0.1,
        description="Lab results stay relevant for a few days"
    ),

    # Medications: Longer half-life, current prescriptions matter
    "Medication": DecayConfig.from_half_life(
        half_life_hours=192,  # ~8 days
        min_score=0.15,
        description="Active medications remain highly relevant"
    ),

    # Diagnoses: Long half-life, chronic conditions persist
    "Diagnosis": DecayConfig.from_half_life(
        half_life_hours=1008,  # ~42 days
        min_score=0.2,
        description="Diagnoses are long-lasting medical facts"
    ),

    # Allergies: Near-permanent, critical safety info
    "Allergy": DecayConfig.from_half_life(
        half_life_hours=6930,  # ~289 days, but min_score keeps it high
        min_score=0.5,
        description="Allergies are permanent and safety-critical"
    ),

    # Procedures: Medium-long half-life
    "Procedure": DecayConfig.from_half_life(
        half_life_hours=720,  # ~30 days
        min_score=0.15,
        description="Recent procedures affect current care"
    ),

    # Preferences: Long half-life, stable over time
    "Preference": DecayConfig.from_half_life(
        half_life_hours=2160,  # ~90 days
        min_score=0.2,
        description="Patient preferences are relatively stable"
    ),

    # Demographics: Near-permanent
    "Demographics": DecayConfig.from_half_life(
        half_life_hours=8760,  # ~1 year
        min_score=0.8,
        description="Demographics rarely change"
    ),

    # Default for unknown types
    "default": DecayConfig.from_half_life(
        half_life_hours=168,  # ~7 days
        min_score=0.1,
        description="Default decay for unknown entity types"
    ),
}


@dataclass
class TemporalScore:
    """Result of temporal scoring for an entity.

    Attributes:
        entity_id: ID of the scored entity
        base_score: Raw exponential decay score [0, 1]
        frequency_boost: Bonus from observation frequency
        final_score: Combined score after all adjustments
        hours_since_observation: Time since last observation
        observation_count: Number of times entity was observed
        decay_config: The decay configuration used
    """

    entity_id: str
    base_score: float
    frequency_boost: float
    final_score: float
    hours_since_observation: float
    observation_count: int
    decay_config: DecayConfig
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_stale(self) -> bool:
        """Check if entity has decayed below minimum threshold."""
        return self.base_score <= self.decay_config.min_score

    @property
    def relevance_category(self) -> str:
        """Categorize relevance level."""
        if self.final_score >= 0.8:
            return "highly_relevant"
        elif self.final_score >= 0.5:
            return "relevant"
        elif self.final_score >= 0.3:
            return "somewhat_relevant"
        elif self.final_score >= 0.1:
            return "marginally_relevant"
        else:
            return "stale"


@dataclass
class TemporalQueryContext:
    """Parsed temporal context from a user query.

    Attributes:
        window: The identified temporal window
        start_time: Computed start of the time window
        end_time: Computed end of the time window (usually now)
        explicit_date: If user specified an explicit date
        confidence: Confidence in the temporal parsing
        original_text: The original temporal phrase
    """

    window: TemporalWindow
    start_time: datetime
    end_time: datetime
    explicit_date: Optional[datetime] = None
    confidence: float = 1.0
    original_text: str = ""

    @property
    def duration_hours(self) -> float:
        """Get duration of the temporal window in hours."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600


# Temporal keywords mapping (Spanish + English)
TEMPORAL_KEYWORDS: Dict[str, TemporalWindow] = {
    # Immediate (last few hours)
    "ahora": TemporalWindow.IMMEDIATE,
    "now": TemporalWindow.IMMEDIATE,
    "ahora mismo": TemporalWindow.IMMEDIATE,
    "right now": TemporalWindow.IMMEDIATE,
    "en este momento": TemporalWindow.IMMEDIATE,
    "at the moment": TemporalWindow.IMMEDIATE,
    "actualmente": TemporalWindow.IMMEDIATE,
    "currently": TemporalWindow.IMMEDIATE,

    # Recent (last 24 hours)
    "hoy": TemporalWindow.RECENT,
    "today": TemporalWindow.RECENT,
    "esta mañana": TemporalWindow.RECENT,
    "this morning": TemporalWindow.RECENT,
    "hace poco": TemporalWindow.RECENT,
    "recently": TemporalWindow.RECENT,
    "hace unas horas": TemporalWindow.RECENT,
    "a few hours ago": TemporalWindow.RECENT,

    # Short-term (last week)
    "esta semana": TemporalWindow.SHORT_TERM,
    "this week": TemporalWindow.SHORT_TERM,
    "últimos días": TemporalWindow.SHORT_TERM,
    "last few days": TemporalWindow.SHORT_TERM,
    "ayer": TemporalWindow.SHORT_TERM,
    "yesterday": TemporalWindow.SHORT_TERM,
    "últimamente": TemporalWindow.SHORT_TERM,
    "lately": TemporalWindow.SHORT_TERM,

    # Medium-term (last month)
    "este mes": TemporalWindow.MEDIUM_TERM,
    "this month": TemporalWindow.MEDIUM_TERM,
    "últimas semanas": TemporalWindow.MEDIUM_TERM,
    "last few weeks": TemporalWindow.MEDIUM_TERM,
    "el mes pasado": TemporalWindow.MEDIUM_TERM,
    "last month": TemporalWindow.MEDIUM_TERM,

    # Long-term (last 3 months)
    "últimos meses": TemporalWindow.LONG_TERM,
    "last few months": TemporalWindow.LONG_TERM,
    "este trimestre": TemporalWindow.LONG_TERM,
    "this quarter": TemporalWindow.LONG_TERM,
    "recientemente": TemporalWindow.LONG_TERM,

    # Historical (all time)
    "siempre": TemporalWindow.HISTORICAL,
    "always": TemporalWindow.HISTORICAL,
    "históricamente": TemporalWindow.HISTORICAL,
    "historically": TemporalWindow.HISTORICAL,
    "desde que empezó": TemporalWindow.HISTORICAL,
    "since the beginning": TemporalWindow.HISTORICAL,
    "alguna vez": TemporalWindow.HISTORICAL,
    "ever": TemporalWindow.HISTORICAL,
    "en el pasado": TemporalWindow.HISTORICAL,
    "in the past": TemporalWindow.HISTORICAL,
}


# Temporal window durations in hours
WINDOW_DURATIONS: Dict[TemporalWindow, float] = {
    TemporalWindow.IMMEDIATE: 6,
    TemporalWindow.RECENT: 24,
    TemporalWindow.SHORT_TERM: 168,      # 7 days
    TemporalWindow.MEDIUM_TERM: 720,     # 30 days
    TemporalWindow.LONG_TERM: 2160,      # 90 days
    TemporalWindow.HISTORICAL: 87600,    # ~10 years (effectively all time)
}
