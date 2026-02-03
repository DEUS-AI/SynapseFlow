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
from typing import List, Dict, Any, Optional, Tuple
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


class KnowledgeLayer(str, Enum):
    """Knowledge graph layers in the DIKW hierarchy."""
    PERCEPTION = "PERCEPTION"
    SEMANTIC = "SEMANTIC"
    REASONING = "REASONING"
    APPLICATION = "APPLICATION"


class CrossLayerConfidencePropagation:
    """
    Propagates confidence across knowledge graph layers.

    Implements layer-aware confidence aggregation following the 4-layer
    architecture: PERCEPTION → SEMANTIC → REASONING → APPLICATION.

    Higher layers are considered more trustworthy as they represent
    validated, enriched, and frequently-used knowledge.
    """

    # Default layer weights (higher = more trusted)
    LAYER_WEIGHTS: Dict[KnowledgeLayer, float] = {
        KnowledgeLayer.APPLICATION: 1.0,   # Most trusted (validated by usage)
        KnowledgeLayer.REASONING: 0.9,      # Inferred with rules
        KnowledgeLayer.SEMANTIC: 0.8,       # Validated against ontologies
        KnowledgeLayer.PERCEPTION: 0.6,     # Raw extraction, needs validation
    }

    # Decay factors when crossing layer boundaries
    CROSS_LAYER_DECAY: Dict[Tuple[KnowledgeLayer, KnowledgeLayer], float] = {
        # Downward traversal (using lower-layer data) - higher decay
        (KnowledgeLayer.APPLICATION, KnowledgeLayer.REASONING): 0.95,
        (KnowledgeLayer.REASONING, KnowledgeLayer.SEMANTIC): 0.90,
        (KnowledgeLayer.SEMANTIC, KnowledgeLayer.PERCEPTION): 0.85,
        # Upward traversal (promoting data) - lower decay
        (KnowledgeLayer.PERCEPTION, KnowledgeLayer.SEMANTIC): 0.98,
        (KnowledgeLayer.SEMANTIC, KnowledgeLayer.REASONING): 0.95,
        (KnowledgeLayer.REASONING, KnowledgeLayer.APPLICATION): 0.92,
    }

    def __init__(
        self,
        layer_weights: Optional[Dict[KnowledgeLayer, float]] = None,
        min_confidence: float = 0.1,
        conflict_threshold: float = 0.3
    ):
        """
        Initialize cross-layer confidence propagation.

        Args:
            layer_weights: Custom layer weights (higher = more trusted)
            min_confidence: Minimum confidence to maintain
            conflict_threshold: Gap above which conflicts are flagged
        """
        self.layer_weights = layer_weights or self.LAYER_WEIGHTS.copy()
        self.min_confidence = min_confidence
        self.conflict_threshold = conflict_threshold

    def get_layer_weight(self, layer: KnowledgeLayer) -> float:
        """Get trust weight for a layer."""
        return self.layer_weights.get(layer, 0.5)

    def adjust_for_layer(
        self,
        confidence: Confidence,
        layer: KnowledgeLayer
    ) -> Confidence:
        """
        Adjust confidence based on its source layer.

        Args:
            confidence: Original confidence
            layer: Layer the confidence comes from

        Returns:
            Adjusted confidence
        """
        layer_weight = self.get_layer_weight(layer)
        adjusted_score = confidence.score * layer_weight

        return Confidence(
            score=max(adjusted_score, self.min_confidence),
            source=confidence.source,
            uncertainty_type=confidence.uncertainty_type,
            generated_by=f"{confidence.generated_by}_layer_adjusted",
            evidence=confidence.evidence + [f"Layer: {layer.value}", f"Weight: {layer_weight}"],
            reasoning=f"Adjusted for {layer.value} layer (weight={layer_weight})",
            properties={**confidence.properties, "source_layer": layer.value}
        )

    def propagate_cross_layer(
        self,
        confidences: Dict[KnowledgeLayer, Confidence],
        strategy: AggregationStrategy = AggregationStrategy.WEIGHTED_AVERAGE
    ) -> Confidence:
        """
        Aggregate confidence scores from multiple layers.

        Args:
            confidences: Map of layer to confidence score
            strategy: Aggregation strategy

        Returns:
            Aggregated confidence
        """
        if not confidences:
            raise ValueError("No confidences to aggregate")

        # Adjust each confidence for its layer
        adjusted_confidences = []
        weights = []

        for layer, conf in confidences.items():
            adjusted = self.adjust_for_layer(conf, layer)
            adjusted_confidences.append(adjusted)
            weights.append(self.get_layer_weight(layer))

        # Combine using specified strategy
        combination = ConfidenceCombination.combine(
            scores=adjusted_confidences,
            strategy=strategy,
            weights=weights if strategy == AggregationStrategy.WEIGHTED_AVERAGE else None
        )

        # Create result confidence
        evidence = [
            f"{layer.value}: {conf.score:.3f} (adjusted: {conf.score * self.get_layer_weight(layer):.3f})"
            for layer, conf in confidences.items()
        ]

        return Confidence(
            score=combination.combined_score,
            source=ConfidenceSource.HYBRID,
            uncertainty_type=UncertaintyType.MIXED,
            generated_by="cross_layer_propagation",
            evidence=evidence,
            reasoning=f"Cross-layer aggregation using {strategy.value}",
            properties={
                "layers_involved": [l.value for l in confidences.keys()],
                "strategy": strategy.value,
                "individual_scores": {l.value: c.score for l, c in confidences.items()}
            }
        )

    def resolve_conflict(
        self,
        layer1: KnowledgeLayer,
        confidence1: Confidence,
        layer2: KnowledgeLayer,
        confidence2: Confidence
    ) -> Tuple[Confidence, str]:
        """
        Resolve conflicting confidence scores from different layers.

        Resolution rules:
        1. Higher layer wins (APPLICATION > REASONING > SEMANTIC > PERCEPTION)
        2. Unless confidence gap > threshold, then prefer higher confidence
        3. Flag for human review if unclear

        Args:
            layer1: First layer
            confidence1: First confidence
            layer2: Second layer
            confidence2: Second confidence

        Returns:
            Tuple of (resolved confidence, resolution reason)
        """
        weight1 = self.get_layer_weight(layer1)
        weight2 = self.get_layer_weight(layer2)

        adjusted1 = confidence1.score * weight1
        adjusted2 = confidence2.score * weight2

        gap = abs(adjusted1 - adjusted2)

        # If one layer is clearly higher
        if weight1 > weight2:
            higher_layer, higher_conf = layer1, confidence1
            lower_layer, lower_conf = layer2, confidence2
        else:
            higher_layer, higher_conf = layer2, confidence2
            lower_layer, lower_conf = layer1, confidence1

        # Check if confidence gap overrides layer priority
        if gap > self.conflict_threshold:
            # Go with higher confidence, regardless of layer
            if adjusted1 > adjusted2:
                winner = confidence1
                reason = (
                    f"Chose {layer1.value} due to confidence gap ({adjusted1:.3f} vs {adjusted2:.3f})"
                )
            else:
                winner = confidence2
                reason = (
                    f"Chose {layer2.value} due to confidence gap ({adjusted2:.3f} vs {adjusted1:.3f})"
                )
        else:
            # Higher layer wins
            winner = higher_conf
            reason = (
                f"Higher layer {higher_layer.value} preferred "
                f"(gap {gap:.3f} < threshold {self.conflict_threshold})"
            )

        # Create resolved confidence with conflict metadata
        resolved = Confidence(
            score=winner.score,
            source=winner.source,
            uncertainty_type=winner.uncertainty_type,
            generated_by="conflict_resolution",
            evidence=winner.evidence + [
                f"Conflict: {layer1.value}={confidence1.score:.3f} vs {layer2.value}={confidence2.score:.3f}",
                f"Resolution: {reason}"
            ],
            reasoning=reason,
            properties={
                "conflict_resolved": True,
                "layers_involved": [layer1.value, layer2.value],
                "original_scores": {
                    layer1.value: confidence1.score,
                    layer2.value: confidence2.score
                }
            }
        )

        return resolved, reason

    def propagate_through_layers(
        self,
        initial_confidence: Confidence,
        from_layer: KnowledgeLayer,
        to_layer: KnowledgeLayer
    ) -> Confidence:
        """
        Propagate confidence when traversing between layers.

        Args:
            initial_confidence: Starting confidence
            from_layer: Source layer
            to_layer: Target layer

        Returns:
            Propagated confidence
        """
        # Get decay factor for this traversal
        decay = self.CROSS_LAYER_DECAY.get(
            (from_layer, to_layer),
            0.95  # Default decay
        )

        # Apply decay
        propagated_score = initial_confidence.score * decay

        return Confidence(
            score=max(propagated_score, self.min_confidence),
            source=initial_confidence.source,
            uncertainty_type=initial_confidence.uncertainty_type,
            generated_by=f"{initial_confidence.generated_by}_cross_layer",
            evidence=initial_confidence.evidence + [
                f"Traversed: {from_layer.value} → {to_layer.value}",
                f"Decay: {decay}"
            ],
            reasoning=f"Cross-layer propagation from {from_layer.value} to {to_layer.value}",
            properties={
                **initial_confidence.properties,
                "from_layer": from_layer.value,
                "to_layer": to_layer.value,
                "decay_applied": decay
            }
        )

    def needs_human_review(
        self,
        confidences: Dict[KnowledgeLayer, Confidence]
    ) -> Tuple[bool, str]:
        """
        Determine if confidence conflicts need human review.

        Args:
            confidences: Map of layer to confidence

        Returns:
            Tuple of (needs_review, reason)
        """
        if len(confidences) < 2:
            return False, "Single source, no conflict"

        # Check for significant disagreements
        scores = [(l, c.score) for l, c in confidences.items()]
        scores.sort(key=lambda x: x[1], reverse=True)

        highest = scores[0]
        lowest = scores[-1]

        gap = highest[1] - lowest[1]

        if gap > 0.5:
            return True, (
                f"Large confidence gap: {highest[0].value}={highest[1]:.2f} "
                f"vs {lowest[0].value}={lowest[1]:.2f}"
            )

        # Check if higher layer has lower confidence (suspicious)
        layer_order = [KnowledgeLayer.PERCEPTION, KnowledgeLayer.SEMANTIC,
                       KnowledgeLayer.REASONING, KnowledgeLayer.APPLICATION]

        for i, layer1 in enumerate(layer_order[:-1]):
            for layer2 in layer_order[i+1:]:
                if layer1 in confidences and layer2 in confidences:
                    # Higher layer should generally have higher or equal confidence
                    if confidences[layer1].score > confidences[layer2].score + 0.2:
                        return True, (
                            f"Lower layer {layer1.value} has higher confidence than "
                            f"higher layer {layer2.value}"
                        )

        return False, "No significant conflicts detected"


# Convenience factory for cross-layer propagation
def create_cross_layer_propagator(
    min_confidence: float = 0.1,
    conflict_threshold: float = 0.3
) -> CrossLayerConfidencePropagation:
    """Create a cross-layer confidence propagator with custom settings."""
    return CrossLayerConfidencePropagation(
        min_confidence=min_confidence,
        conflict_threshold=conflict_threshold
    )
