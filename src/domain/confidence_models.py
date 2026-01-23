"""Confidence Models.

This module defines models for managing confidence scores and uncertainty
in the neurosymbolic knowledge management system.

It supports:
- Unified confidence representation
- Confidence aggregation strategies
- Uncertainty types (epistemic vs aleatoric)
- Confidence provenance tracking
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import math


class UncertaintyType(str, Enum):
    """Types of uncertainty."""
    EPISTEMIC = "epistemic"  # Due to lack of knowledge
    ALEATORIC = "aleatoric"  # Due to inherent randomness
    MIXED = "mixed"


class ConfidenceSource(str, Enum):
    """Source of confidence score."""
    SYMBOLIC_RULE = "symbolic_rule"
    NEURAL_MODEL = "neural_model"
    HYBRID = "hybrid"
    USER_INPUT = "user_input"
    VALIDATION = "validation"
    HEURISTIC = "heuristic"


class AggregationStrategy(str, Enum):
    """Strategies for combining confidence scores."""
    MIN = "min"  # Conservative: take minimum
    MAX = "max"  # Optimistic: take maximum
    AVERAGE = "average"  # Mean of scores
    WEIGHTED_AVERAGE = "weighted_average"  # Weighted mean
    PRODUCT = "product"  # Multiply probabilities
    NOISY_OR = "noisy_or"  # 1 - product(1 - scores)


class Confidence(BaseModel):
    """
    Represents a confidence score with metadata.

    Confidence values are always in [0.0, 1.0] range.
    """

    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    source: ConfidenceSource = Field(..., description="Source of confidence")
    uncertainty_type: UncertaintyType = Field(
        default=UncertaintyType.EPISTEMIC,
        description="Type of uncertainty"
    )

    # Provenance
    generated_by: str = Field(..., description="Component that generated this score")
    timestamp: datetime = Field(default_factory=datetime.now, description="When score was generated")

    # Supporting evidence
    evidence: List[str] = Field(default_factory=list, description="Evidence supporting this confidence")
    reasoning: Optional[str] = Field(None, description="Explanation of confidence score")

    # Metadata
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")

    def to_certainty(self) -> float:
        """Convert to certainty (for symbolic reasoning)."""
        return 1.0 if self.score >= 0.9 else 0.0

    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if confidence is above threshold."""
        return self.score >= threshold

    def is_uncertain(self, threshold: float = 0.5) -> bool:
        """Check if confidence indicates uncertainty."""
        return self.score < threshold

    def decay(self, factor: float = 0.9) -> 'Confidence':
        """
        Apply confidence decay (for reasoning chains).

        Args:
            factor: Decay factor (0.0 to 1.0)

        Returns:
            New Confidence with decayed score
        """
        return Confidence(
            score=self.score * factor,
            source=self.source,
            uncertainty_type=self.uncertainty_type,
            generated_by=f"{self.generated_by}_decayed",
            evidence=self.evidence,
            reasoning=f"Decayed from {self.score:.3f} by factor {factor}"
        )


class ConfidenceCombination(BaseModel):
    """
    Represents a combination of multiple confidence scores.

    Used when aggregating evidence from multiple sources.
    """

    scores: List[Confidence] = Field(..., description="Individual confidence scores")
    strategy: AggregationStrategy = Field(..., description="Aggregation strategy used")
    combined_score: float = Field(..., ge=0.0, le=1.0, description="Aggregated score")
    weights: Optional[List[float]] = Field(None, description="Weights for weighted average")

    timestamp: datetime = Field(default_factory=datetime.now)
    properties: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def combine(
        cls,
        scores: List[Confidence],
        strategy: AggregationStrategy = AggregationStrategy.WEIGHTED_AVERAGE,
        weights: Optional[List[float]] = None
    ) -> 'ConfidenceCombination':
        """
        Combine multiple confidence scores using specified strategy.

        Args:
            scores: List of confidence objects
            strategy: Aggregation strategy
            weights: Optional weights for weighted average

        Returns:
            ConfidenceCombination object
        """
        if not scores:
            raise ValueError("Cannot combine empty list of scores")

        score_values = [s.score for s in scores]

        if strategy == AggregationStrategy.MIN:
            combined = min(score_values)

        elif strategy == AggregationStrategy.MAX:
            combined = max(score_values)

        elif strategy == AggregationStrategy.AVERAGE:
            combined = sum(score_values) / len(score_values)

        elif strategy == AggregationStrategy.WEIGHTED_AVERAGE:
            if not weights:
                # Equal weights
                weights = [1.0 / len(scores)] * len(scores)
            elif len(weights) != len(scores):
                raise ValueError("Weights must match number of scores")

            # Normalize weights
            weight_sum = sum(weights)
            normalized_weights = [w / weight_sum for w in weights]

            combined = sum(s * w for s, w in zip(score_values, normalized_weights))

        elif strategy == AggregationStrategy.PRODUCT:
            # Multiply probabilities (assuming independence)
            combined = math.prod(score_values)

        elif strategy == AggregationStrategy.NOISY_OR:
            # Noisy-OR: 1 - product(1 - p_i)
            combined = 1.0 - math.prod(1.0 - s for s in score_values)

        else:
            raise ValueError(f"Unknown aggregation strategy: {strategy}")

        return cls(
            scores=scores,
            strategy=strategy,
            combined_score=combined,
            weights=weights
        )


class ConfidenceTracker:
    """
    Tracks confidence evolution over time.

    Used for monitoring confidence changes in response to validation feedback.
    """

    def __init__(self):
        self.history: List[Tuple[datetime, float, str]] = []

    def record(self, score: float, reason: str = ""):
        """Record a confidence score."""
        self.history.append((datetime.now(), score, reason))

    def get_trend(self) -> str:
        """Get confidence trend (increasing, decreasing, stable)."""
        if len(self.history) < 2:
            return "insufficient_data"

        recent_scores = [s for _, s, _ in self.history[-5:]]

        # Simple linear trend
        if recent_scores[-1] > recent_scores[0] * 1.1:
            return "increasing"
        elif recent_scores[-1] < recent_scores[0] * 0.9:
            return "decreasing"
        else:
            return "stable"

    def get_average(self) -> float:
        """Get average confidence over all history."""
        if not self.history:
            return 0.0

        return sum(s for _, s, _ in self.history) / len(self.history)

    def get_latest(self) -> Optional[float]:
        """Get latest confidence score."""
        if not self.history:
            return None

        return self.history[-1][1]


class ConfidencePropagation:
    """
    Utilities for propagating confidence through reasoning chains.

    Supports:
    - Decay over reasoning steps
    - Minimum threshold enforcement
    - Provenance tracking
    """

    def __init__(self, decay_factor: float = 0.95, min_threshold: float = 0.1):
        """
        Initialize confidence propagation.

        Args:
            decay_factor: Multiplicative decay per reasoning step (0.0-1.0)
            min_threshold: Minimum confidence to keep propagating
        """
        self.decay_factor = decay_factor
        self.min_threshold = min_threshold

    def propagate(
        self,
        initial_confidence: Confidence,
        num_steps: int
    ) -> Confidence:
        """
        Propagate confidence through reasoning chain.

        Args:
            initial_confidence: Starting confidence
            num_steps: Number of reasoning steps

        Returns:
            Propagated confidence
        """
        decayed_score = initial_confidence.score * (self.decay_factor ** num_steps)

        if decayed_score < self.min_threshold:
            decayed_score = self.min_threshold

        return Confidence(
            score=decayed_score,
            source=initial_confidence.source,
            uncertainty_type=initial_confidence.uncertainty_type,
            generated_by=f"{initial_confidence.generated_by}_propagated",
            evidence=initial_confidence.evidence,
            reasoning=f"Propagated {num_steps} steps with decay factor {self.decay_factor}"
        )

    def combine_with_rule(
        self,
        neural_confidence: Confidence,
        symbolic_certainty: float,
        alpha: float = 0.5
    ) -> Confidence:
        """
        Combine neural confidence with symbolic certainty.

        Formula: combined = α × neural + (1-α) × symbolic

        Args:
            neural_confidence: Confidence from neural model
            symbolic_certainty: Certainty from symbolic rule (0.0 or 1.0)
            alpha: Weight for neural component (0.0-1.0)

        Returns:
            Combined confidence
        """
        combined_score = alpha * neural_confidence.score + (1 - alpha) * symbolic_certainty

        return Confidence(
            score=combined_score,
            source=ConfidenceSource.HYBRID,
            uncertainty_type=UncertaintyType.MIXED,
            generated_by="neurosymbolic_combination",
            evidence=[
                f"Neural: {neural_confidence.score:.3f}",
                f"Symbolic: {symbolic_certainty:.3f}",
                f"α={alpha}"
            ],
            reasoning=f"Neurosymbolic combination with α={alpha}"
        )


# Convenience functions
def create_confidence(
    score: float,
    source: ConfidenceSource,
    generated_by: str,
    reasoning: Optional[str] = None
) -> Confidence:
    """Create a confidence object."""
    return Confidence(
        score=score,
        source=source,
        generated_by=generated_by,
        reasoning=reasoning
    )


def symbolic_confidence(score: float = 1.0, generated_by: str = "symbolic_rule") -> Confidence:
    """Create a symbolic confidence (certain)."""
    return Confidence(
        score=score,
        source=ConfidenceSource.SYMBOLIC_RULE,
        generated_by=generated_by,
        uncertainty_type=UncertaintyType.EPISTEMIC,
        reasoning="Symbolic rule applied"
    )


def neural_confidence(score: float, generated_by: str = "neural_model") -> Confidence:
    """Create a neural confidence (uncertain)."""
    return Confidence(
        score=score,
        source=ConfidenceSource.NEURAL_MODEL,
        generated_by=generated_by,
        uncertainty_type=UncertaintyType.ALEATORIC,
        reasoning="Neural model prediction"
    )
