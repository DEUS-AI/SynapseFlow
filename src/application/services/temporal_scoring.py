"""Temporal Scoring Service for DIKW Knowledge Graph.

Replaces binary time-based filtering with sophisticated exponential decay
functions tailored to each entity type. Entities decay in relevance over
time at rates appropriate to their medical significance.

Features:
- Exponential decay with entity-type specific rates
- Frequency boost for frequently observed entities
- Natural language temporal query parsing
- Configurable decay parameters
"""

import math
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from domain.temporal_models import (
    DecayConfig,
    ENTITY_DECAY_CONFIGS,
    TemporalScore,
    TemporalQueryContext,
    TemporalWindow,
    TEMPORAL_KEYWORDS,
    WINDOW_DURATIONS,
)


@dataclass
class TemporalScoringConfig:
    """Configuration for the temporal scoring service."""

    # Weight for frequency boost (0 = disabled, 1 = full weight)
    frequency_weight: float = 0.3

    # Maximum frequency boost multiplier
    max_frequency_boost: float = 2.0

    # Minimum score to include in results
    min_relevance_threshold: float = 0.05

    # Default window if no temporal context detected
    default_window: TemporalWindow = TemporalWindow.SHORT_TERM

    # Enable adaptive decay based on query context
    enable_adaptive_decay: bool = True


class TemporalScoringService:
    """Service for computing temporal relevance scores.

    Uses exponential decay to model how entity relevance decreases over time,
    with entity-type specific decay rates. Symptoms decay quickly (hours),
    while allergies remain relevant almost indefinitely.

    The scoring formula is:
        base_score = max(min_score, exp(-lambda * hours_since_observation))
        frequency_boost = weight * log(observation_count + 1)
        final_score = base_score * (1 + frequency_boost)

    Example:
        >>> service = TemporalScoringService()
        >>> score = service.compute_temporal_score(
        ...     entity_type="Symptom",
        ...     last_observed=datetime.utcnow() - timedelta(hours=40),
        ...     observation_count=3
        ... )
        >>> print(f"Score: {score.final_score:.2f}")  # ~0.25 (decayed)
    """

    def __init__(
        self,
        config: Optional[TemporalScoringConfig] = None,
        custom_decay_configs: Optional[Dict[str, DecayConfig]] = None,
    ):
        """Initialize the temporal scoring service.

        Args:
            config: Service configuration
            custom_decay_configs: Override default decay configs
        """
        self.config = config or TemporalScoringConfig()
        self.decay_configs = {**ENTITY_DECAY_CONFIGS}
        if custom_decay_configs:
            self.decay_configs.update(custom_decay_configs)

    def compute_temporal_score(
        self,
        entity_id: str,
        entity_type: str,
        last_observed: datetime,
        observation_count: int = 1,
        reference_time: Optional[datetime] = None,
    ) -> TemporalScore:
        """Compute the temporal relevance score for an entity.

        Args:
            entity_id: Unique identifier of the entity
            entity_type: Type of entity (Symptom, Medication, etc.)
            last_observed: Timestamp of last observation
            observation_count: Number of times entity was observed
            reference_time: Reference time (defaults to now)

        Returns:
            TemporalScore with computed relevance
        """
        reference_time = reference_time or datetime.utcnow()

        # Get decay config for entity type
        decay_config = self.decay_configs.get(
            entity_type,
            self.decay_configs["default"]
        )

        # Compute hours since observation
        time_delta = reference_time - last_observed
        hours_since = max(0, time_delta.total_seconds() / 3600)

        # Compute base exponential decay score
        raw_score = math.exp(-decay_config.lambda_rate * hours_since)
        base_score = max(decay_config.min_score, raw_score)

        # Compute frequency boost: log(count + 1) scaled by weight
        frequency_boost = self.config.frequency_weight * math.log(observation_count + 1)
        frequency_boost = min(frequency_boost, self.config.max_frequency_boost - 1)

        # Combine scores
        final_score = min(1.0, base_score * (1 + frequency_boost))

        return TemporalScore(
            entity_id=entity_id,
            base_score=base_score,
            frequency_boost=frequency_boost,
            final_score=final_score,
            hours_since_observation=hours_since,
            observation_count=observation_count,
            decay_config=decay_config,
            timestamp=reference_time,
        )

    def score_entities(
        self,
        entities: List[Dict[str, Any]],
        reference_time: Optional[datetime] = None,
    ) -> List[TemporalScore]:
        """Score a batch of entities for temporal relevance.

        Args:
            entities: List of entity dicts with keys:
                - id: Entity ID
                - entity_type: Type of entity
                - last_observed: Timestamp (str or datetime)
                - observation_count: Optional count
            reference_time: Reference time for scoring

        Returns:
            List of TemporalScores, sorted by final_score descending
        """
        scores = []

        for entity in entities:
            entity_id = entity.get("id", entity.get("entity_id", ""))
            entity_type = entity.get("entity_type", "default")

            # Parse last_observed timestamp
            last_observed = entity.get("last_observed")
            if isinstance(last_observed, str):
                try:
                    last_observed = datetime.fromisoformat(last_observed.replace("Z", "+00:00"))
                except ValueError:
                    last_observed = datetime.utcnow()
            elif last_observed is None:
                last_observed = datetime.utcnow()

            observation_count = entity.get("observation_count", 1)

            score = self.compute_temporal_score(
                entity_id=entity_id,
                entity_type=entity_type,
                last_observed=last_observed,
                observation_count=observation_count,
                reference_time=reference_time,
            )

            # Filter out entities below threshold
            if score.final_score >= self.config.min_relevance_threshold:
                scores.append(score)

        # Sort by final score descending
        scores.sort(key=lambda s: s.final_score, reverse=True)
        return scores

    def parse_temporal_query(
        self,
        query: str,
        reference_time: Optional[datetime] = None,
    ) -> TemporalQueryContext:
        """Parse temporal context from a natural language query.

        Supports both Spanish and English temporal expressions.

        Args:
            query: User query text
            reference_time: Reference time (defaults to now)

        Returns:
            TemporalQueryContext with parsed temporal window

        Example:
            >>> ctx = service.parse_temporal_query("¿Cómo me sentí ayer?")
            >>> print(ctx.window)  # TemporalWindow.SHORT_TERM
        """
        reference_time = reference_time or datetime.utcnow()
        query_lower = query.lower()

        # Try to match known temporal keywords
        matched_window = None
        matched_phrase = ""
        confidence = 0.0

        for phrase, window in TEMPORAL_KEYWORDS.items():
            if phrase in query_lower:
                # Prefer longer matches (more specific)
                if len(phrase) > len(matched_phrase):
                    matched_window = window
                    matched_phrase = phrase
                    confidence = 0.9

        # Try to extract explicit time references
        explicit_date = self._extract_explicit_date(query, reference_time)
        if explicit_date:
            matched_window = self._classify_date_window(explicit_date, reference_time)
            confidence = 0.95

        # Default to short-term if no temporal context found
        if matched_window is None:
            matched_window = self.config.default_window
            confidence = 0.5

        # Compute time window
        duration_hours = WINDOW_DURATIONS[matched_window]
        start_time = reference_time - timedelta(hours=duration_hours)

        return TemporalQueryContext(
            window=matched_window,
            start_time=start_time,
            end_time=reference_time,
            explicit_date=explicit_date,
            confidence=confidence,
            original_text=matched_phrase or "",
        )

    def _extract_explicit_date(
        self,
        query: str,
        reference_time: datetime,
    ) -> Optional[datetime]:
        """Extract explicit date references from query.

        Handles patterns like:
        - "el 15 de enero"
        - "January 15"
        - "hace 3 días"
        - "3 days ago"
        """
        query_lower = query.lower()

        # Pattern: "hace X días/horas/semanas"
        spanish_ago = re.search(r"hace\s+(\d+)\s+(día|días|hora|horas|semana|semanas|mes|meses)", query_lower)
        if spanish_ago:
            amount = int(spanish_ago.group(1))
            unit = spanish_ago.group(2)

            if "hora" in unit:
                return reference_time - timedelta(hours=amount)
            elif "día" in unit:
                return reference_time - timedelta(days=amount)
            elif "semana" in unit:
                return reference_time - timedelta(weeks=amount)
            elif "mes" in unit:
                return reference_time - timedelta(days=amount * 30)

        # Pattern: "X days/hours/weeks ago"
        english_ago = re.search(r"(\d+)\s+(day|days|hour|hours|week|weeks|month|months)\s+ago", query_lower)
        if english_ago:
            amount = int(english_ago.group(1))
            unit = english_ago.group(2)

            if "hour" in unit:
                return reference_time - timedelta(hours=amount)
            elif "day" in unit:
                return reference_time - timedelta(days=amount)
            elif "week" in unit:
                return reference_time - timedelta(weeks=amount)
            elif "month" in unit:
                return reference_time - timedelta(days=amount * 30)

        return None

    def _classify_date_window(
        self,
        date: datetime,
        reference_time: datetime,
    ) -> TemporalWindow:
        """Classify an explicit date into a temporal window."""
        hours_ago = (reference_time - date).total_seconds() / 3600

        if hours_ago <= 6:
            return TemporalWindow.IMMEDIATE
        elif hours_ago <= 24:
            return TemporalWindow.RECENT
        elif hours_ago <= 168:  # 7 days
            return TemporalWindow.SHORT_TERM
        elif hours_ago <= 720:  # 30 days
            return TemporalWindow.MEDIUM_TERM
        elif hours_ago <= 2160:  # 90 days
            return TemporalWindow.LONG_TERM
        else:
            return TemporalWindow.HISTORICAL

    def get_decay_config(self, entity_type: str) -> DecayConfig:
        """Get the decay configuration for an entity type."""
        return self.decay_configs.get(entity_type, self.decay_configs["default"])

    def estimate_relevance_at_time(
        self,
        entity_type: str,
        hours_in_future: float,
        current_observation_count: int = 1,
    ) -> float:
        """Estimate entity relevance at a future time.

        Useful for planning when to refresh or crystallize data.

        Args:
            entity_type: Type of entity
            hours_in_future: Hours from now
            current_observation_count: Current observation count

        Returns:
            Estimated final score at that time
        """
        decay_config = self.get_decay_config(entity_type)

        # Compute future decay
        base_score = max(
            decay_config.min_score,
            math.exp(-decay_config.lambda_rate * hours_in_future)
        )

        # Frequency boost (unchanged over time)
        frequency_boost = self.config.frequency_weight * math.log(current_observation_count + 1)
        frequency_boost = min(frequency_boost, self.config.max_frequency_boost - 1)

        return min(1.0, base_score * (1 + frequency_boost))

    def get_refresh_recommendation(
        self,
        entity_type: str,
        target_relevance: float = 0.5,
    ) -> float:
        """Get recommended hours until entity should be refreshed.

        Computes when the entity will decay to target_relevance level.

        Args:
            entity_type: Type of entity
            target_relevance: Target relevance threshold

        Returns:
            Hours until entity reaches target relevance
        """
        decay_config = self.get_decay_config(entity_type)

        # Solve: target = exp(-lambda * hours)
        # hours = -ln(target) / lambda
        if target_relevance <= decay_config.min_score:
            # Entity won't decay below min_score
            return float("inf")

        return -math.log(target_relevance) / decay_config.lambda_rate

    def adjust_query_results(
        self,
        entities: List[Dict[str, Any]],
        temporal_context: TemporalQueryContext,
    ) -> List[Dict[str, Any]]:
        """Adjust entity results based on temporal context.

        Filters and re-scores entities based on the detected temporal window.

        Args:
            entities: Raw entity results
            temporal_context: Parsed temporal context from query

        Returns:
            Filtered and re-scored entities with temporal_score added
        """
        # Score all entities
        scores = self.score_entities(entities, reference_time=temporal_context.end_time)

        # Create a score lookup
        score_map = {s.entity_id: s for s in scores}

        # Filter by temporal window
        adjusted = []
        for entity in entities:
            entity_id = entity.get("id", entity.get("entity_id", ""))
            score = score_map.get(entity_id)

            if score is None:
                continue

            # Check if entity falls within temporal window
            last_observed = entity.get("last_observed")
            if isinstance(last_observed, str):
                try:
                    last_observed = datetime.fromisoformat(last_observed.replace("Z", "+00:00"))
                except ValueError:
                    last_observed = None

            if last_observed:
                if last_observed < temporal_context.start_time:
                    # Entity is outside temporal window, reduce score
                    if temporal_context.window != TemporalWindow.HISTORICAL:
                        continue

            # Add temporal score to entity
            entity_copy = entity.copy()
            entity_copy["temporal_score"] = score.final_score
            entity_copy["relevance_category"] = score.relevance_category
            entity_copy["hours_since_observation"] = score.hours_since_observation
            adjusted.append(entity_copy)

        # Sort by temporal score
        adjusted.sort(key=lambda e: e.get("temporal_score", 0), reverse=True)
        return adjusted

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about configured decay rates."""
        stats = {
            "config": {
                "frequency_weight": self.config.frequency_weight,
                "max_frequency_boost": self.config.max_frequency_boost,
                "min_relevance_threshold": self.config.min_relevance_threshold,
                "default_window": self.config.default_window.value,
            },
            "decay_configs": {},
        }

        for entity_type, config in self.decay_configs.items():
            stats["decay_configs"][entity_type] = {
                "half_life_hours": config.half_life_hours,
                "lambda_rate": round(config.lambda_rate, 6),
                "min_score": config.min_score,
                "description": config.description,
                "refresh_to_50pct_hours": round(
                    -math.log(0.5) / config.lambda_rate, 1
                ),
            }

        return stats
