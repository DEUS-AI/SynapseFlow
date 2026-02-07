"""Tests for the Temporal Scoring Service.

Tests the exponential decay functions, query temporal parsing,
and entity-type specific decay configurations.
"""

import pytest
from datetime import datetime, timedelta
import math

from domain.temporal_models import (
    DecayConfig,
    ENTITY_DECAY_CONFIGS,
    TemporalScore,
    TemporalQueryContext,
    TemporalWindow,
    TEMPORAL_KEYWORDS,
    WINDOW_DURATIONS,
)
from application.services.temporal_scoring import (
    TemporalScoringService,
    TemporalScoringConfig,
)


# ========================================
# DecayConfig Tests
# ========================================

class TestDecayConfig:
    """Tests for DecayConfig model."""

    def test_from_half_life_calculation(self):
        """Test that half-life correctly determines lambda rate."""
        # 20-hour half-life
        config = DecayConfig.from_half_life(20)

        # After 20 hours, score should be 0.5
        score_at_half_life = math.exp(-config.lambda_rate * 20)
        assert abs(score_at_half_life - 0.5) < 0.001

    def test_half_life_matches_decay(self):
        """Test that various half-lives produce correct decay."""
        for half_life in [10, 50, 100, 500]:
            config = DecayConfig.from_half_life(half_life)
            score = math.exp(-config.lambda_rate * half_life)
            assert abs(score - 0.5) < 0.001, f"Failed for half_life={half_life}"

    def test_min_score_parameter(self):
        """Test min_score is correctly set."""
        config = DecayConfig.from_half_life(20, min_score=0.2)
        assert config.min_score == 0.2


class TestEntityDecayConfigs:
    """Tests for entity-type specific decay configurations."""

    def test_symptom_decay_fast(self):
        """Symptoms should decay quickly (~20h half-life)."""
        config = ENTITY_DECAY_CONFIGS["Symptom"]
        assert 15 <= config.half_life_hours <= 25

    def test_allergy_decay_slow(self):
        """Allergies should decay very slowly."""
        config = ENTITY_DECAY_CONFIGS["Allergy"]
        assert config.half_life_hours > 1000
        assert config.min_score >= 0.5  # Always highly relevant

    def test_medication_decay_moderate(self):
        """Medications should have moderate decay (~8 days)."""
        config = ENTITY_DECAY_CONFIGS["Medication"]
        assert 150 <= config.half_life_hours <= 250

    def test_all_configs_have_required_fields(self):
        """All decay configs should have required fields."""
        for entity_type, config in ENTITY_DECAY_CONFIGS.items():
            assert config.lambda_rate > 0
            assert config.half_life_hours > 0
            assert 0 <= config.min_score <= 1
            assert isinstance(config.description, str)


# ========================================
# TemporalScoringService Tests
# ========================================

class TestTemporalScoringService:
    """Tests for TemporalScoringService."""

    @pytest.fixture
    def service(self):
        """Create a TemporalScoringService instance."""
        return TemporalScoringService()

    def test_compute_score_recent_entity(self, service):
        """Test scoring for a recently observed entity."""
        now = datetime.utcnow()
        last_observed = now - timedelta(hours=1)

        score = service.compute_temporal_score(
            entity_id="test_123",
            entity_type="Symptom",
            last_observed=last_observed,
            observation_count=1,
            reference_time=now,
        )

        # Should be very high for recent observation
        assert score.base_score > 0.9
        assert score.final_score > 0.9
        assert score.hours_since_observation < 2
        assert score.relevance_category == "highly_relevant"

    def test_compute_score_stale_symptom(self, service):
        """Test scoring for an old symptom (should be low)."""
        now = datetime.utcnow()
        last_observed = now - timedelta(hours=100)  # ~4 days ago

        score = service.compute_temporal_score(
            entity_id="test_123",
            entity_type="Symptom",
            last_observed=last_observed,
            observation_count=1,
            reference_time=now,
        )

        # Symptom from 100 hours ago should have decayed significantly
        assert score.base_score < 0.3
        assert score.is_stale or score.base_score <= 0.1

    def test_compute_score_allergy_stays_relevant(self, service):
        """Test that allergies remain relevant even after long time."""
        now = datetime.utcnow()
        last_observed = now - timedelta(days=365)  # 1 year ago

        score = service.compute_temporal_score(
            entity_id="allergy_123",
            entity_type="Allergy",
            last_observed=last_observed,
            observation_count=1,
            reference_time=now,
        )

        # Allergy should still be relevant due to high min_score
        assert score.final_score >= 0.5
        assert score.relevance_category in ["highly_relevant", "relevant"]

    def test_frequency_boost(self, service):
        """Test that observation count boosts relevance."""
        now = datetime.utcnow()
        last_observed = now - timedelta(hours=24)

        # Score with 1 observation
        score_1 = service.compute_temporal_score(
            entity_id="test_123",
            entity_type="Symptom",
            last_observed=last_observed,
            observation_count=1,
            reference_time=now,
        )

        # Score with 10 observations
        score_10 = service.compute_temporal_score(
            entity_id="test_123",
            entity_type="Symptom",
            last_observed=last_observed,
            observation_count=10,
            reference_time=now,
        )

        # More observations should result in higher score
        assert score_10.final_score > score_1.final_score
        assert score_10.frequency_boost > score_1.frequency_boost

    def test_score_entities_batch(self, service):
        """Test batch scoring of multiple entities."""
        now = datetime.utcnow()

        entities = [
            {
                "id": "symptom_1",
                "entity_type": "Symptom",
                "last_observed": (now - timedelta(hours=1)).isoformat(),
                "observation_count": 3,
            },
            {
                "id": "symptom_2",
                "entity_type": "Symptom",
                "last_observed": (now - timedelta(hours=48)).isoformat(),
                "observation_count": 1,
            },
            {
                "id": "medication_1",
                "entity_type": "Medication",
                "last_observed": (now - timedelta(days=5)).isoformat(),
                "observation_count": 2,
            },
        ]

        scores = service.score_entities(entities, reference_time=now)

        # Should return scores for all entities
        assert len(scores) == 3

        # Should be sorted by final_score descending
        assert scores[0].final_score >= scores[1].final_score >= scores[2].final_score

        # Recent symptom should be first
        assert scores[0].entity_id == "symptom_1"

    def test_score_entities_filters_low_relevance(self, service):
        """Test that entities below threshold are filtered."""
        now = datetime.utcnow()

        entities = [
            {
                "id": "symptom_old",
                "entity_type": "Symptom",
                "last_observed": (now - timedelta(days=30)).isoformat(),  # Very old symptom
                "observation_count": 1,
            },
        ]

        # Configure very high threshold
        service.config.min_relevance_threshold = 0.8

        scores = service.score_entities(entities, reference_time=now)

        # Old symptom should be filtered out
        assert len(scores) == 0


# ========================================
# Temporal Query Parsing Tests
# ========================================

class TestTemporalQueryParsing:
    """Tests for natural language temporal query parsing."""

    @pytest.fixture
    def service(self):
        """Create a TemporalScoringService instance."""
        return TemporalScoringService()

    def test_parse_immediate_spanish(self, service):
        """Test parsing Spanish 'ahora' as immediate."""
        ctx = service.parse_temporal_query("¿Cómo me siento ahora?")

        assert ctx.window == TemporalWindow.IMMEDIATE
        assert ctx.confidence >= 0.8

    def test_parse_immediate_english(self, service):
        """Test parsing English 'right now' as immediate."""
        ctx = service.parse_temporal_query("How do I feel right now?")

        assert ctx.window == TemporalWindow.IMMEDIATE
        assert ctx.confidence >= 0.8

    def test_parse_recent_spanish(self, service):
        """Test parsing Spanish 'hoy' as recent."""
        ctx = service.parse_temporal_query("¿Qué síntomas tuve hoy?")

        assert ctx.window == TemporalWindow.RECENT
        assert ctx.duration_hours <= 24

    def test_parse_short_term_spanish(self, service):
        """Test parsing Spanish 'últimamente' as short-term."""
        ctx = service.parse_temporal_query("Últimamente me duele la cabeza")

        assert ctx.window == TemporalWindow.SHORT_TERM
        assert ctx.duration_hours <= 168  # 7 days

    def test_parse_historical_spanish(self, service):
        """Test parsing Spanish 'siempre' as historical."""
        ctx = service.parse_temporal_query("Siempre he tenido alergias")

        assert ctx.window == TemporalWindow.HISTORICAL

    def test_parse_explicit_days_ago_spanish(self, service):
        """Test parsing 'hace X días' pattern."""
        ctx = service.parse_temporal_query("Hace 3 días empecé a toser")

        assert ctx.explicit_date is not None
        assert ctx.confidence >= 0.9

        # Check the date is approximately 3 days ago
        expected_date = datetime.utcnow() - timedelta(days=3)
        delta = abs((ctx.explicit_date - expected_date).total_seconds())
        assert delta < 60  # Within 1 minute

    def test_parse_explicit_days_ago_english(self, service):
        """Test parsing 'X days ago' pattern."""
        ctx = service.parse_temporal_query("I started coughing 3 days ago")

        assert ctx.explicit_date is not None
        assert ctx.confidence >= 0.9

    def test_parse_no_temporal_context(self, service):
        """Test parsing query with no temporal context."""
        ctx = service.parse_temporal_query("¿Qué medicamentos tomo?")

        # Should default to short_term with lower confidence
        assert ctx.window == service.config.default_window
        assert ctx.confidence <= 0.6

    def test_parse_prefers_longer_matches(self, service):
        """Test that longer phrases are preferred."""
        ctx = service.parse_temporal_query("ahora mismo me siento mal")

        # "ahora mismo" is longer than just "ahora"
        assert ctx.original_text == "ahora mismo"


# ========================================
# Query Results Adjustment Tests
# ========================================

class TestQueryResultsAdjustment:
    """Tests for adjusting query results based on temporal context."""

    @pytest.fixture
    def service(self):
        """Create a TemporalScoringService instance."""
        return TemporalScoringService()

    def test_adjust_filters_by_temporal_window(self, service):
        """Test that entities outside window are filtered."""
        now = datetime.utcnow()

        entities = [
            {
                "id": "recent",
                "entity_type": "Symptom",
                "last_observed": (now - timedelta(hours=2)).isoformat(),
            },
            {
                "id": "old",
                "entity_type": "Symptom",
                "last_observed": (now - timedelta(days=10)).isoformat(),
            },
        ]

        # Create immediate temporal context
        ctx = TemporalQueryContext(
            window=TemporalWindow.IMMEDIATE,
            start_time=now - timedelta(hours=6),
            end_time=now,
        )

        adjusted = service.adjust_query_results(entities, ctx)

        # Only recent entity should remain
        assert len(adjusted) == 1
        assert adjusted[0]["id"] == "recent"

    def test_adjust_adds_temporal_scores(self, service):
        """Test that temporal scores are added to entities."""
        now = datetime.utcnow()

        entities = [
            {
                "id": "test",
                "entity_type": "Medication",
                "last_observed": (now - timedelta(hours=12)).isoformat(),
            },
        ]

        ctx = TemporalQueryContext(
            window=TemporalWindow.RECENT,
            start_time=now - timedelta(hours=24),
            end_time=now,
        )

        adjusted = service.adjust_query_results(entities, ctx)

        assert len(adjusted) == 1
        assert "temporal_score" in adjusted[0]
        assert "relevance_category" in adjusted[0]
        assert "hours_since_observation" in adjusted[0]

    def test_adjust_sorts_by_temporal_score(self, service):
        """Test that results are sorted by temporal score."""
        now = datetime.utcnow()

        entities = [
            {
                "id": "old",
                "entity_type": "Symptom",
                "last_observed": (now - timedelta(hours=20)).isoformat(),
            },
            {
                "id": "recent",
                "entity_type": "Symptom",
                "last_observed": (now - timedelta(hours=2)).isoformat(),
            },
        ]

        ctx = TemporalQueryContext(
            window=TemporalWindow.SHORT_TERM,
            start_time=now - timedelta(days=7),
            end_time=now,
        )

        adjusted = service.adjust_query_results(entities, ctx)

        # Recent entity should be first
        assert adjusted[0]["id"] == "recent"
        assert adjusted[0]["temporal_score"] > adjusted[1]["temporal_score"]


# ========================================
# Helper Method Tests
# ========================================

class TestHelperMethods:
    """Tests for helper methods."""

    @pytest.fixture
    def service(self):
        """Create a TemporalScoringService instance."""
        return TemporalScoringService()

    def test_get_decay_config_known_type(self, service):
        """Test getting config for known entity type."""
        config = service.get_decay_config("Symptom")
        assert config == ENTITY_DECAY_CONFIGS["Symptom"]

    def test_get_decay_config_unknown_type(self, service):
        """Test getting config for unknown entity type."""
        config = service.get_decay_config("UnknownType")
        assert config == ENTITY_DECAY_CONFIGS["default"]

    def test_estimate_relevance_at_time(self, service):
        """Test estimating future relevance."""
        # Symptom should decay to ~0.5 at half-life
        # The frequency boost adds ~0.2 for observation_count=1 (log(2) * weight)
        relevance = service.estimate_relevance_at_time(
            entity_type="Symptom",
            hours_in_future=20,  # ~half-life for symptoms
            current_observation_count=1,
        )

        # Base score ~0.5 + frequency boost ~0.1 = ~0.6
        assert 0.4 <= relevance <= 0.65

    def test_get_refresh_recommendation(self, service):
        """Test getting refresh recommendations."""
        hours = service.get_refresh_recommendation(
            entity_type="Symptom",
            target_relevance=0.5,
        )

        # Should be around 20 hours (symptom half-life)
        assert 15 <= hours <= 25

    def test_get_stats(self, service):
        """Test getting service statistics."""
        stats = service.get_stats()

        assert "config" in stats
        assert "decay_configs" in stats
        assert "frequency_weight" in stats["config"]
        assert "Symptom" in stats["decay_configs"]
        assert "half_life_hours" in stats["decay_configs"]["Symptom"]


# ========================================
# TemporalScore Model Tests
# ========================================

class TestTemporalScore:
    """Tests for TemporalScore model."""

    def test_is_stale_property(self):
        """Test is_stale property."""
        config = DecayConfig(lambda_rate=0.05, half_life_hours=20, min_score=0.1)

        stale_score = TemporalScore(
            entity_id="test",
            base_score=0.1,  # At min_score
            frequency_boost=0.0,
            final_score=0.1,
            hours_since_observation=100,
            observation_count=1,
            decay_config=config,
        )

        assert stale_score.is_stale

    def test_relevance_categories(self):
        """Test relevance category classification."""
        config = DecayConfig(lambda_rate=0.05, half_life_hours=20, min_score=0.1)

        # Highly relevant
        high_score = TemporalScore(
            entity_id="test",
            base_score=0.9,
            frequency_boost=0.0,
            final_score=0.9,
            hours_since_observation=1,
            observation_count=1,
            decay_config=config,
        )
        assert high_score.relevance_category == "highly_relevant"

        # Relevant
        mid_score = TemporalScore(
            entity_id="test",
            base_score=0.6,
            frequency_boost=0.0,
            final_score=0.6,
            hours_since_observation=10,
            observation_count=1,
            decay_config=config,
        )
        assert mid_score.relevance_category == "relevant"

        # Stale
        low_score = TemporalScore(
            entity_id="test",
            base_score=0.05,
            frequency_boost=0.0,
            final_score=0.05,
            hours_since_observation=100,
            observation_count=1,
            decay_config=config,
        )
        assert low_score.relevance_category == "stale"


# ========================================
# Custom Config Tests
# ========================================

class TestCustomConfig:
    """Tests for custom configuration."""

    def test_custom_frequency_weight(self):
        """Test custom frequency weight."""
        config = TemporalScoringConfig(frequency_weight=0.5)
        service = TemporalScoringService(config=config)

        now = datetime.utcnow()
        score = service.compute_temporal_score(
            entity_id="test",
            entity_type="Symptom",
            last_observed=now,
            observation_count=10,
            reference_time=now,
        )

        # Higher frequency weight should increase boost
        assert score.frequency_boost > 0.5

    def test_custom_decay_config(self):
        """Test custom decay configuration."""
        custom_config = DecayConfig.from_half_life(
            half_life_hours=10,
            min_score=0.3,
            description="Custom fast decay"
        )

        service = TemporalScoringService(
            custom_decay_configs={"CustomType": custom_config}
        )

        now = datetime.utcnow()
        score = service.compute_temporal_score(
            entity_id="test",
            entity_type="CustomType",
            last_observed=now - timedelta(hours=10),
            observation_count=1,
            reference_time=now,
        )

        # Should use custom config (0.5 at half-life)
        assert 0.45 <= score.base_score <= 0.55

    def test_default_window_config(self):
        """Test default temporal window configuration."""
        config = TemporalScoringConfig(default_window=TemporalWindow.HISTORICAL)
        service = TemporalScoringService(config=config)

        ctx = service.parse_temporal_query("generic query without time")
        assert ctx.window == TemporalWindow.HISTORICAL
