"""Unit tests for Confidence models."""

import pytest
from datetime import datetime
from domain.confidence_models import (
    Confidence,
    ConfidenceSource,
    UncertaintyType,
    ConfidenceCombination,
    AggregationStrategy,
    ConfidenceTracker,
    ConfidencePropagation,
    create_confidence,
    neural_confidence,
    symbolic_confidence
)


class TestConfidence:
    """Test Confidence model."""

    def test_confidence_creation(self):
        """Test creating a confidence instance."""
        conf = Confidence(
            score=0.85,
            source=ConfidenceSource.NEURAL_MODEL,
            generated_by="llm_reasoner"
        )

        assert conf.score == 0.85
        assert conf.source == ConfidenceSource.NEURAL_MODEL
        assert conf.generated_by == "llm_reasoner"
        assert conf.uncertainty_type == UncertaintyType.EPISTEMIC

    def test_confidence_score_bounds(self):
        """Test confidence score is bounded [0, 1]."""
        # Valid scores
        Confidence(score=0.0, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")
        Confidence(score=1.0, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")
        Confidence(score=0.5, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        # Invalid scores should raise validation error
        with pytest.raises(Exception):
            Confidence(score=-0.1, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        with pytest.raises(Exception):
            Confidence(score=1.1, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

    def test_to_certainty(self):
        """Test conversion to certainty."""
        high_conf = Confidence(score=0.95, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")
        low_conf = Confidence(score=0.7, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        assert high_conf.to_certainty() == 1.0
        assert low_conf.to_certainty() == 0.0

    def test_is_high_confidence(self):
        """Test high confidence detection."""
        high = Confidence(score=0.9, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")
        medium = Confidence(score=0.75, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")
        low = Confidence(score=0.5, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        assert high.is_high_confidence(threshold=0.8) is True
        assert medium.is_high_confidence(threshold=0.8) is False
        assert low.is_high_confidence(threshold=0.8) is False

    def test_is_uncertain(self):
        """Test uncertainty detection."""
        certain = Confidence(score=0.9, source=ConfidenceSource.SYMBOLIC_RULE, generated_by="test")
        uncertain = Confidence(score=0.3, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        assert certain.is_uncertain(threshold=0.5) is False
        assert uncertain.is_uncertain(threshold=0.5) is True

    def test_decay(self):
        """Test confidence decay."""
        original = Confidence(score=0.9, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        decayed = original.decay(factor=0.9)

        assert decayed.score == pytest.approx(0.81, rel=1e-3)
        assert decayed.source == original.source
        assert "decayed" in decayed.generated_by.lower()

    def test_confidence_with_evidence(self):
        """Test confidence with evidence."""
        conf = Confidence(
            score=0.85,
            source=ConfidenceSource.NEURAL_MODEL,
            generated_by="test",
            evidence=["fact1", "fact2", "fact3"],
            reasoning="Based on pattern matching"
        )

        assert len(conf.evidence) == 3
        assert conf.reasoning == "Based on pattern matching"


class TestConfidenceCombination:
    """Test confidence combination."""

    def test_min_aggregation(self):
        """Test MIN aggregation strategy."""
        scores = [
            Confidence(score=0.9, source=ConfidenceSource.NEURAL_MODEL, generated_by="test1"),
            Confidence(score=0.7, source=ConfidenceSource.SYMBOLIC_RULE, generated_by="test2"),
            Confidence(score=0.85, source=ConfidenceSource.HYBRID, generated_by="test3")
        ]

        result = ConfidenceCombination.combine(scores, strategy=AggregationStrategy.MIN)

        assert result.combined_score == 0.7
        assert result.strategy == AggregationStrategy.MIN

    def test_max_aggregation(self):
        """Test MAX aggregation strategy."""
        scores = [
            Confidence(score=0.9, source=ConfidenceSource.NEURAL_MODEL, generated_by="test1"),
            Confidence(score=0.7, source=ConfidenceSource.SYMBOLIC_RULE, generated_by="test2")
        ]

        result = ConfidenceCombination.combine(scores, strategy=AggregationStrategy.MAX)

        assert result.combined_score == 0.9

    def test_average_aggregation(self):
        """Test AVERAGE aggregation strategy."""
        scores = [
            Confidence(score=0.8, source=ConfidenceSource.NEURAL_MODEL, generated_by="test1"),
            Confidence(score=0.6, source=ConfidenceSource.NEURAL_MODEL, generated_by="test2"),
            Confidence(score=1.0, source=ConfidenceSource.SYMBOLIC_RULE, generated_by="test3")
        ]

        result = ConfidenceCombination.combine(scores, strategy=AggregationStrategy.AVERAGE)

        expected = (0.8 + 0.6 + 1.0) / 3
        assert result.combined_score == pytest.approx(expected, rel=1e-3)

    def test_weighted_average_aggregation(self):
        """Test WEIGHTED_AVERAGE aggregation strategy."""
        scores = [
            Confidence(score=0.8, source=ConfidenceSource.NEURAL_MODEL, generated_by="test1"),
            Confidence(score=0.6, source=ConfidenceSource.NEURAL_MODEL, generated_by="test2")
        ]

        weights = [0.7, 0.3]
        result = ConfidenceCombination.combine(
            scores,
            strategy=AggregationStrategy.WEIGHTED_AVERAGE,
            weights=weights
        )

        expected = 0.8 * 0.7 + 0.6 * 0.3
        assert result.combined_score == pytest.approx(expected, rel=1e-3)

    def test_weighted_average_equal_weights(self):
        """Test weighted average with no weights (equal weights)."""
        scores = [
            Confidence(score=0.8, source=ConfidenceSource.NEURAL_MODEL, generated_by="test1"),
            Confidence(score=0.6, source=ConfidenceSource.NEURAL_MODEL, generated_by="test2")
        ]

        result = ConfidenceCombination.combine(
            scores,
            strategy=AggregationStrategy.WEIGHTED_AVERAGE
        )

        # Should default to equal weights
        expected = (0.8 + 0.6) / 2
        assert result.combined_score == pytest.approx(expected, rel=1e-3)

    def test_product_aggregation(self):
        """Test PRODUCT aggregation strategy."""
        scores = [
            Confidence(score=0.9, source=ConfidenceSource.NEURAL_MODEL, generated_by="test1"),
            Confidence(score=0.8, source=ConfidenceSource.SYMBOLIC_RULE, generated_by="test2")
        ]

        result = ConfidenceCombination.combine(scores, strategy=AggregationStrategy.PRODUCT)

        expected = 0.9 * 0.8
        assert result.combined_score == pytest.approx(expected, rel=1e-3)

    def test_noisy_or_aggregation(self):
        """Test NOISY_OR aggregation strategy."""
        scores = [
            Confidence(score=0.7, source=ConfidenceSource.NEURAL_MODEL, generated_by="test1"),
            Confidence(score=0.6, source=ConfidenceSource.NEURAL_MODEL, generated_by="test2")
        ]

        result = ConfidenceCombination.combine(scores, strategy=AggregationStrategy.NOISY_OR)

        # 1 - (1-0.7) * (1-0.6) = 1 - 0.3 * 0.4 = 1 - 0.12 = 0.88
        expected = 1.0 - (1.0 - 0.7) * (1.0 - 0.6)
        assert result.combined_score == pytest.approx(expected, rel=1e-3)

    def test_empty_scores_raises_error(self):
        """Test combining empty scores raises error."""
        with pytest.raises(ValueError):
            ConfidenceCombination.combine([], strategy=AggregationStrategy.AVERAGE)

    def test_mismatched_weights_raises_error(self):
        """Test mismatched weights raises error."""
        scores = [
            Confidence(score=0.8, source=ConfidenceSource.NEURAL_MODEL, generated_by="test1"),
            Confidence(score=0.6, source=ConfidenceSource.NEURAL_MODEL, generated_by="test2")
        ]

        with pytest.raises(ValueError):
            ConfidenceCombination.combine(
                scores,
                strategy=AggregationStrategy.WEIGHTED_AVERAGE,
                weights=[0.7]  # Only 1 weight for 2 scores
            )


class TestConfidenceTracker:
    """Test confidence tracking over time."""

    def test_record_confidence(self):
        """Test recording confidence scores."""
        tracker = ConfidenceTracker()

        tracker.record(0.7, "Initial")
        tracker.record(0.8, "After validation")
        tracker.record(0.9, "After feedback")

        assert len(tracker.history) == 3

    def test_get_latest(self):
        """Test getting latest confidence."""
        tracker = ConfidenceTracker()

        tracker.record(0.7, "Initial")
        tracker.record(0.9, "Final")

        assert tracker.get_latest() == 0.9

    def test_get_latest_empty(self):
        """Test getting latest from empty tracker."""
        tracker = ConfidenceTracker()
        assert tracker.get_latest() is None

    def test_get_average(self):
        """Test getting average confidence."""
        tracker = ConfidenceTracker()

        tracker.record(0.6, "Test1")
        tracker.record(0.8, "Test2")
        tracker.record(1.0, "Test3")

        expected = (0.6 + 0.8 + 1.0) / 3
        assert tracker.get_average() == pytest.approx(expected, rel=1e-3)

    def test_get_average_empty(self):
        """Test getting average from empty tracker."""
        tracker = ConfidenceTracker()
        assert tracker.get_average() == 0.0

    def test_get_trend_increasing(self):
        """Test detecting increasing trend."""
        tracker = ConfidenceTracker()

        tracker.record(0.5, "Start")
        tracker.record(0.6, "Middle")
        tracker.record(0.7, "End")

        assert tracker.get_trend() == "increasing"

    def test_get_trend_decreasing(self):
        """Test detecting decreasing trend."""
        tracker = ConfidenceTracker()

        tracker.record(0.9, "Start")
        tracker.record(0.7, "Middle")
        tracker.record(0.5, "End")

        assert tracker.get_trend() == "decreasing"

    def test_get_trend_stable(self):
        """Test detecting stable trend."""
        tracker = ConfidenceTracker()

        tracker.record(0.8, "Start")
        tracker.record(0.79, "Middle")
        tracker.record(0.81, "End")

        assert tracker.get_trend() == "stable"

    def test_get_trend_insufficient_data(self):
        """Test trend with insufficient data."""
        tracker = ConfidenceTracker()
        tracker.record(0.8, "Single")

        assert tracker.get_trend() == "insufficient_data"


class TestConfidencePropagation:
    """Test confidence propagation."""

    def test_propagation_decay(self):
        """Test confidence decay through propagation."""
        propagator = ConfidencePropagation(decay_factor=0.9, min_threshold=0.1)

        initial = Confidence(score=0.9, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        propagated = propagator.propagate(initial, num_steps=3)

        # 0.9 * 0.9^3 = 0.9 * 0.729 = 0.6561
        expected = 0.9 * (0.9 ** 3)
        assert propagated.score == pytest.approx(expected, rel=1e-3)

    def test_propagation_min_threshold(self):
        """Test propagation respects minimum threshold."""
        propagator = ConfidencePropagation(decay_factor=0.5, min_threshold=0.2)

        initial = Confidence(score=0.3, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        propagated = propagator.propagate(initial, num_steps=5)

        # Should not go below min_threshold
        assert propagated.score >= 0.2

    def test_combine_with_rule(self):
        """Test combining neural and symbolic confidence."""
        propagator = ConfidencePropagation()

        neural = Confidence(score=0.8, source=ConfidenceSource.NEURAL_MODEL, generated_by="llm")
        symbolic_certainty = 1.0

        combined = propagator.combine_with_rule(neural, symbolic_certainty, alpha=0.6)

        # 0.6 * 0.8 + 0.4 * 1.0 = 0.48 + 0.4 = 0.88
        expected = 0.6 * 0.8 + 0.4 * 1.0
        assert combined.score == pytest.approx(expected, rel=1e-3)
        assert combined.source == ConfidenceSource.HYBRID

    def test_combine_with_equal_weights(self):
        """Test combining with equal weights (alpha=0.5)."""
        propagator = ConfidencePropagation()

        neural = Confidence(score=0.7, source=ConfidenceSource.NEURAL_MODEL, generated_by="llm")
        symbolic = 1.0

        combined = propagator.combine_with_rule(neural, symbolic, alpha=0.5)

        expected = 0.5 * 0.7 + 0.5 * 1.0
        assert combined.score == pytest.approx(expected, rel=1e-3)


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_create_confidence(self):
        """Test create_confidence function."""
        conf = create_confidence(
            score=0.85,
            source=ConfidenceSource.NEURAL_MODEL,
            generated_by="test",
            reasoning="Test reasoning"
        )

        assert conf.score == 0.85
        assert conf.source == ConfidenceSource.NEURAL_MODEL
        assert conf.reasoning == "Test reasoning"

    def test_symbolic_confidence(self):
        """Test symbolic_confidence function."""
        conf = symbolic_confidence(score=1.0, generated_by="rule_engine")

        assert conf.score == 1.0
        assert conf.source == ConfidenceSource.SYMBOLIC_RULE
        assert conf.uncertainty_type == UncertaintyType.EPISTEMIC

    def test_neural_confidence(self):
        """Test neural_confidence function."""
        conf = neural_confidence(score=0.75, generated_by="llm_model")

        assert conf.score == 0.75
        assert conf.source == ConfidenceSource.NEURAL_MODEL
        assert conf.uncertainty_type == UncertaintyType.ALEATORIC


class TestConfidenceProperties:
    """Test confidence model properties and metadata."""

    def test_timestamp_auto_generated(self):
        """Test timestamp is auto-generated."""
        conf = Confidence(score=0.8, source=ConfidenceSource.NEURAL_MODEL, generated_by="test")

        assert isinstance(conf.timestamp, datetime)

    def test_custom_properties(self):
        """Test custom properties storage."""
        conf = Confidence(
            score=0.8,
            source=ConfidenceSource.NEURAL_MODEL,
            generated_by="test",
            properties={"model": "gpt-4", "temperature": 0.3}
        )

        assert conf.properties["model"] == "gpt-4"
        assert conf.properties["temperature"] == 0.3

    def test_evidence_list(self):
        """Test evidence is properly stored."""
        conf = Confidence(
            score=0.9,
            source=ConfidenceSource.HYBRID,
            generated_by="test",
            evidence=["Rule A matched", "Pattern B found", "Validation passed"]
        )

        assert len(conf.evidence) == 3
        assert "Rule A matched" in conf.evidence
