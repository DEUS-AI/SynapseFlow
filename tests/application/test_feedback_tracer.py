"""Unit tests for Feedback Tracer Service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from application.services.feedback_tracer import (
    FeedbackTracerService,
    FeedbackType,
    FeedbackSeverity,
    UserFeedback,
    FeedbackStatistics,
)


class TestFeedbackTypeEnum:
    """Test FeedbackType enumeration."""

    def test_feedback_type_values(self):
        """Test feedback type enum values."""
        assert FeedbackType.HELPFUL == "helpful"
        assert FeedbackType.UNHELPFUL == "unhelpful"
        assert FeedbackType.INCORRECT == "incorrect"
        assert FeedbackType.PARTIALLY_CORRECT == "partially_correct"
        assert FeedbackType.MISSING_INFO == "missing_info"


class TestFeedbackSeverityEnum:
    """Test FeedbackSeverity enumeration."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert FeedbackSeverity.CRITICAL == "critical"
        assert FeedbackSeverity.HIGH == "high"
        assert FeedbackSeverity.MEDIUM == "medium"
        assert FeedbackSeverity.LOW == "low"


class TestUserFeedback:
    """Test UserFeedback dataclass."""

    def test_feedback_creation(self):
        """Test creating user feedback."""
        feedback = UserFeedback(
            feedback_id="feedback-123",
            response_id="response-456",
            patient_id="patient-789",
            session_id="session-abc",
            query_text="What is diabetes?",
            response_text="Diabetes is a metabolic disease...",
            rating=4,
            feedback_type=FeedbackType.HELPFUL,
        )

        assert feedback.feedback_id == "feedback-123"
        assert feedback.rating == 4
        assert feedback.feedback_type == FeedbackType.HELPFUL
        assert feedback.severity is None
        assert feedback.correction_text is None
        assert feedback.entities_involved == []
        assert feedback.layers_traversed == []
        assert isinstance(feedback.timestamp, datetime)

    def test_feedback_with_all_fields(self):
        """Test feedback with all optional fields."""
        feedback = UserFeedback(
            feedback_id="feedback-123",
            response_id="response-456",
            patient_id="patient-789",
            session_id="session-abc",
            query_text="What is diabetes?",
            response_text="Incorrect response",
            rating=2,
            feedback_type=FeedbackType.INCORRECT,
            severity=FeedbackSeverity.HIGH,
            correction_text="The correct answer is...",
            entities_involved=["entity:1", "entity:2"],
            layers_traversed=["PERCEPTION", "SEMANTIC"],
            metadata={"source": "test"},
        )

        assert feedback.severity == FeedbackSeverity.HIGH
        assert feedback.correction_text == "The correct answer is..."
        assert len(feedback.entities_involved) == 2
        assert len(feedback.layers_traversed) == 2


class TestFeedbackStatistics:
    """Test FeedbackStatistics dataclass."""

    def test_statistics_creation(self):
        """Test creating feedback statistics."""
        stats = FeedbackStatistics(
            total_feedbacks=100,
            average_rating=3.5,
            rating_distribution={1: 10, 2: 15, 3: 25, 4: 30, 5: 20},
            feedback_type_distribution={"helpful": 60, "unhelpful": 40},
            layer_performance={
                "SEMANTIC": {"avg_rating": 4.0, "negative_rate": 0.1}
            },
            recent_trends={"trend": "improving"},
        )

        assert stats.total_feedbacks == 100
        assert stats.average_rating == 3.5
        assert stats.rating_distribution[4] == 30


class TestFeedbackTracerServiceInit:
    """Test FeedbackTracerService initialization."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        return bus

    def test_initialization_defaults(self, mock_backend):
        """Test service initialization with defaults."""
        service = FeedbackTracerService(backend=mock_backend)

        assert service.backend == mock_backend
        assert service.event_bus is None
        assert service.confidence_decay == 0.05
        assert service.confidence_boost == 0.02

    def test_initialization_custom_settings(self, mock_backend, mock_event_bus):
        """Test service initialization with custom settings."""
        service = FeedbackTracerService(
            backend=mock_backend,
            event_bus=mock_event_bus,
            confidence_decay_on_negative=0.10,
            confidence_boost_on_positive=0.05,
        )

        assert service.event_bus == mock_event_bus
        assert service.confidence_decay == 0.10
        assert service.confidence_boost == 0.05

    def test_initial_statistics(self, mock_backend):
        """Test initial statistics."""
        service = FeedbackTracerService(backend=mock_backend)

        assert service.stats["total_collected"] == 0
        assert service.stats["positive_count"] == 0
        assert service.stats["negative_count"] == 0
        assert service.stats["corrections_count"] == 0


class TestSubmitFeedback:
    """Test feedback submission."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create feedback tracer service."""
        return FeedbackTracerService(backend=mock_backend)

    @pytest.mark.asyncio
    async def test_submit_feedback_basic(self, service):
        """Test basic feedback submission."""
        feedback = await service.submit_feedback(
            response_id="response-123",
            patient_id="patient-456",
            session_id="session-789",
            query_text="What is diabetes?",
            response_text="Diabetes is...",
            rating=4,
            feedback_type=FeedbackType.HELPFUL,
        )

        assert feedback.feedback_id is not None
        assert feedback.rating == 4
        assert feedback.feedback_type == FeedbackType.HELPFUL
        assert service.stats["total_collected"] == 1
        assert service.stats["positive_count"] == 1

    @pytest.mark.asyncio
    async def test_submit_feedback_negative(self, service):
        """Test negative feedback submission."""
        feedback = await service.submit_feedback(
            response_id="response-123",
            patient_id="patient-456",
            session_id="session-789",
            query_text="What is diabetes?",
            response_text="Incorrect response",
            rating=2,
            feedback_type=FeedbackType.INCORRECT,
        )

        assert service.stats["negative_count"] == 1

    @pytest.mark.asyncio
    async def test_submit_feedback_with_correction(self, service):
        """Test feedback with correction text."""
        feedback = await service.submit_feedback(
            response_id="response-123",
            patient_id="patient-456",
            session_id="session-789",
            query_text="What is diabetes?",
            response_text="Wrong answer",
            rating=1,
            feedback_type=FeedbackType.INCORRECT,
            correction_text="The correct answer is...",
        )

        assert feedback.correction_text == "The correct answer is..."
        assert service.stats["corrections_count"] == 1

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_rating(self, service):
        """Test feedback with invalid rating."""
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            await service.submit_feedback(
                response_id="response-123",
                patient_id="patient-456",
                session_id="session-789",
                query_text="Query",
                response_text="Response",
                rating=6,  # Invalid
                feedback_type=FeedbackType.HELPFUL,
            )

    @pytest.mark.asyncio
    async def test_submit_feedback_with_entities(self, service):
        """Test feedback with entity involvement."""
        feedback = await service.submit_feedback(
            response_id="response-123",
            patient_id="patient-456",
            session_id="session-789",
            query_text="Query",
            response_text="Response",
            rating=3,
            feedback_type=FeedbackType.PARTIALLY_CORRECT,
            entities_involved=["entity:1", "entity:2"],
            layers_traversed=["SEMANTIC", "REASONING"],
        )

        assert len(feedback.entities_involved) == 2
        assert len(feedback.layers_traversed) == 2


class TestPreferencePairs:
    """Test preference pair generation for RLHF."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create feedback tracer service."""
        return FeedbackTracerService(backend=mock_backend)

    @pytest.mark.asyncio
    async def test_create_preference_pair(self, service):
        """Test preference pair creation from feedback."""
        await service.submit_feedback(
            response_id="response-123",
            patient_id="patient-456",
            session_id="session-789",
            query_text="What is diabetes?",
            response_text="Wrong answer",
            rating=1,  # Low rating
            feedback_type=FeedbackType.INCORRECT,
            correction_text="Diabetes is a metabolic disease...",
        )

        pairs = await service.get_preference_pairs()

        assert len(pairs) == 1
        assert pairs[0]["query"] == "What is diabetes?"
        assert pairs[0]["chosen"] == "Diabetes is a metabolic disease..."
        assert pairs[0]["rejected"] == "Wrong answer"

    @pytest.mark.asyncio
    async def test_no_preference_pair_high_rating(self, service):
        """Test no preference pair for high-rated feedback."""
        await service.submit_feedback(
            response_id="response-123",
            patient_id="patient-456",
            session_id="session-789",
            query_text="What is diabetes?",
            response_text="Good answer",
            rating=4,  # High rating
            feedback_type=FeedbackType.HELPFUL,
            correction_text="Minor improvement...",  # Has correction but rating is good
        )

        pairs = await service.get_preference_pairs()

        assert len(pairs) == 0

    @pytest.mark.asyncio
    async def test_filter_pairs_by_rating_gap(self, service):
        """Test filtering preference pairs by rating gap."""
        # Low rating (gap = 4)
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="Q1",
            response_text="Bad",
            rating=1,
            feedback_type=FeedbackType.INCORRECT,
            correction_text="Good",
        )

        # Medium rating (gap = 2)
        await service.submit_feedback(
            response_id="r2",
            patient_id="p2",
            session_id="s2",
            query_text="Q2",
            response_text="OK",
            rating=3,
            feedback_type=FeedbackType.PARTIALLY_CORRECT,
            correction_text="Better",
        )

        pairs = await service.get_preference_pairs(min_rating_gap=3)

        assert len(pairs) == 1
        assert pairs[0]["query"] == "Q1"

    @pytest.mark.asyncio
    async def test_limit_preference_pairs(self, service):
        """Test limiting preference pairs returned."""
        for i in range(5):
            await service.submit_feedback(
                response_id=f"r{i}",
                patient_id=f"p{i}",
                session_id=f"s{i}",
                query_text=f"Q{i}",
                response_text="Bad",
                rating=1,
                feedback_type=FeedbackType.INCORRECT,
                correction_text="Good",
            )

        pairs = await service.get_preference_pairs(limit=3)

        assert len(pairs) == 3


class TestCorrectionExamples:
    """Test correction example extraction for SFT."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create feedback tracer service."""
        return FeedbackTracerService(backend=mock_backend)

    @pytest.mark.asyncio
    async def test_get_corrections(self, service):
        """Test getting correction examples."""
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="What is diabetes?",
            response_text="Wrong",
            rating=2,
            feedback_type=FeedbackType.INCORRECT,
            correction_text="Correct answer",
        )

        corrections = await service.get_correction_examples()

        assert len(corrections) == 1
        assert corrections[0]["query"] == "What is diabetes?"
        assert corrections[0]["corrected_response"] == "Correct answer"

    @pytest.mark.asyncio
    async def test_filter_corrections_by_type(self, service):
        """Test filtering corrections by feedback type."""
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="Q1",
            response_text="Response1",
            rating=2,
            feedback_type=FeedbackType.INCORRECT,
            correction_text="Correction1",
        )

        await service.submit_feedback(
            response_id="r2",
            patient_id="p2",
            session_id="s2",
            query_text="Q2",
            response_text="Response2",
            rating=3,
            feedback_type=FeedbackType.MISSING_INFO,
            correction_text="Correction2",
        )

        corrections = await service.get_correction_examples(
            feedback_type=FeedbackType.INCORRECT
        )

        assert len(corrections) == 1
        assert corrections[0]["query"] == "Q1"

    @pytest.mark.asyncio
    async def test_no_corrections_without_correction_text(self, service):
        """Test no corrections returned for feedback without correction text."""
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="Q1",
            response_text="Response1",
            rating=2,
            feedback_type=FeedbackType.UNHELPFUL,
            # No correction_text
        )

        corrections = await service.get_correction_examples()

        assert len(corrections) == 0


class TestFeedbackStatisticsCalculation:
    """Test feedback statistics calculation."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create feedback tracer service."""
        return FeedbackTracerService(backend=mock_backend)

    @pytest.mark.asyncio
    async def test_empty_statistics(self, service):
        """Test statistics with no feedback."""
        stats = await service.get_feedback_statistics()

        assert stats.total_feedbacks == 0
        assert stats.average_rating == 0.0
        assert stats.rating_distribution == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    @pytest.mark.asyncio
    async def test_rating_distribution(self, service):
        """Test rating distribution calculation."""
        for rating in [5, 5, 4, 4, 4, 3, 2, 1]:
            await service.submit_feedback(
                response_id=f"r{rating}",
                patient_id="p1",
                session_id="s1",
                query_text="Q",
                response_text="R",
                rating=rating,
                feedback_type=FeedbackType.HELPFUL,
            )

        stats = await service.get_feedback_statistics()

        assert stats.rating_distribution[5] == 2
        assert stats.rating_distribution[4] == 3
        assert stats.rating_distribution[3] == 1
        assert stats.rating_distribution[2] == 1
        assert stats.rating_distribution[1] == 1

    @pytest.mark.asyncio
    async def test_average_rating(self, service):
        """Test average rating calculation."""
        for rating in [5, 4, 3, 2, 1]:
            await service.submit_feedback(
                response_id=f"r{rating}",
                patient_id="p1",
                session_id="s1",
                query_text="Q",
                response_text="R",
                rating=rating,
                feedback_type=FeedbackType.HELPFUL,
            )

        stats = await service.get_feedback_statistics()

        assert stats.average_rating == 3.0  # (5+4+3+2+1)/5

    @pytest.mark.asyncio
    async def test_layer_performance(self, service):
        """Test layer performance calculation."""
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="Q1",
            response_text="R1",
            rating=5,
            feedback_type=FeedbackType.HELPFUL,
            layers_traversed=["SEMANTIC"],
        )

        await service.submit_feedback(
            response_id="r2",
            patient_id="p2",
            session_id="s2",
            query_text="Q2",
            response_text="R2",
            rating=1,
            feedback_type=FeedbackType.INCORRECT,
            layers_traversed=["SEMANTIC"],
        )

        stats = await service.get_feedback_statistics()

        assert "SEMANTIC" in stats.layer_performance
        assert stats.layer_performance["SEMANTIC"]["total"] == 2
        assert stats.layer_performance["SEMANTIC"]["avg_rating"] == 3.0
        assert stats.layer_performance["SEMANTIC"]["negative_rate"] == 0.5


class TestFeedbackTrends:
    """Test feedback trend calculation."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create feedback tracer service."""
        return FeedbackTracerService(backend=mock_backend)

    @pytest.mark.asyncio
    async def test_insufficient_data_trend(self, service):
        """Test trend with insufficient data."""
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="Q",
            response_text="R",
            rating=4,
            feedback_type=FeedbackType.HELPFUL,
        )

        stats = await service.get_feedback_statistics()

        assert stats.recent_trends["trend"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_improving_trend(self, service):
        """Test improving trend detection."""
        # Submit 20 feedbacks with improving ratings
        for i in range(20):
            # First 10: low ratings (2-3)
            # Last 10: high ratings (4-5)
            rating = 3 if i < 10 else 5
            await service.submit_feedback(
                response_id=f"r{i}",
                patient_id="p1",
                session_id="s1",
                query_text="Q",
                response_text="R",
                rating=rating,
                feedback_type=FeedbackType.HELPFUL,
            )

        stats = await service.get_feedback_statistics()

        assert stats.recent_trends["trend"] == "improving"


class TestTrainingDataExport:
    """Test training data export."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create feedback tracer service."""
        return FeedbackTracerService(backend=mock_backend)

    @pytest.mark.asyncio
    async def test_export_training_data(self, service):
        """Test exporting all training data."""
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="Q1",
            response_text="Bad",
            rating=1,
            feedback_type=FeedbackType.INCORRECT,
            correction_text="Good",
        )

        export = await service.export_training_data()

        assert "preference_pairs" in export
        assert "corrections" in export
        assert "statistics" in export
        assert "total_feedbacks" in export
        assert "exported_at" in export


class TestEventPublishing:
    """Test event publishing for feedback."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.fixture
    def service(self, mock_backend, mock_event_bus):
        """Create service with event bus."""
        return FeedbackTracerService(
            backend=mock_backend,
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_publishes_feedback_event(self, service):
        """Test that feedback submission publishes event."""
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="Q",
            response_text="R",
            rating=4,
            feedback_type=FeedbackType.HELPFUL,
        )

        service.event_bus.publish.assert_called_once()
        call_args = service.event_bus.publish.call_args
        event = call_args[0][0]
        assert event.action == "feedback_received"
        assert event.data["rating"] == 4


class TestServiceStatistics:
    """Test service-level statistics."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create feedback tracer service."""
        return FeedbackTracerService(backend=mock_backend)

    def test_get_service_statistics(self, service):
        """Test getting service statistics."""
        stats = service.get_statistics()

        assert "total_collected" in stats
        assert "positive_count" in stats
        assert "negative_count" in stats
        assert "corrections_count" in stats
        assert "preference_pairs_count" in stats
        assert "feedbacks_in_memory" in stats

    @pytest.mark.asyncio
    async def test_statistics_update(self, service):
        """Test statistics are updated after feedback."""
        await service.submit_feedback(
            response_id="r1",
            patient_id="p1",
            session_id="s1",
            query_text="Q",
            response_text="R",
            rating=5,
            feedback_type=FeedbackType.HELPFUL,
        )

        stats = service.get_statistics()

        assert stats["total_collected"] == 1
        assert stats["positive_count"] == 1
        assert stats["feedbacks_in_memory"] == 1


class TestEntityDemotion:
    """Test entity demotion based on negative feedback."""

    @pytest.fixture
    def mock_backend_with_demotion(self):
        """Create mock backend that supports demotion queries."""
        backend = MagicMock()

        # Mock query_raw to return entity with high negative feedback
        async def mock_query_raw(query, params):
            if "feedback_count" in query:
                # Return entity ready for demotion
                return [{
                    "current_layer": "SEMANTIC",
                    "confidence": 0.5,
                    "feedback_count": 6,
                    "negative_count": 4,
                }]
            elif "demoted_id" in query:
                # Return success for demotion
                return [{"demoted_id": params.get("entity_id")}]
            return []

        backend.query_raw = AsyncMock(side_effect=mock_query_raw)
        return backend

    @pytest.fixture
    def service(self, mock_backend_with_demotion):
        """Create feedback tracer service."""
        return FeedbackTracerService(backend=mock_backend_with_demotion)

    @pytest.mark.asyncio
    async def test_check_demotion_triggers(self, service):
        """Test that entities are demoted after enough negative feedback."""
        demoted = await service.check_demotion(
            entity_ids=["entity-123"],
            demotion_threshold=3,
            min_feedback_count=5,
        )

        assert len(demoted) == 1
        assert "entity-123" in demoted

    @pytest.mark.asyncio
    async def test_check_demotion_no_trigger_insufficient_feedback(self):
        """Test no demotion when feedback count is too low."""
        backend = MagicMock()

        async def mock_query_raw(query, params):
            if "feedback_count" in query:
                return [{
                    "current_layer": "SEMANTIC",
                    "confidence": 0.5,
                    "feedback_count": 2,  # Too low
                    "negative_count": 2,
                }]
            return []

        backend.query_raw = AsyncMock(side_effect=mock_query_raw)
        service = FeedbackTracerService(backend=backend)

        demoted = await service.check_demotion(
            entity_ids=["entity-123"],
            demotion_threshold=3,
            min_feedback_count=5,
        )

        assert len(demoted) == 0

    @pytest.mark.asyncio
    async def test_check_demotion_no_trigger_low_negative_count(self):
        """Test no demotion when negative count is below threshold."""
        backend = MagicMock()

        async def mock_query_raw(query, params):
            if "feedback_count" in query:
                return [{
                    "current_layer": "REASONING",
                    "confidence": 0.7,
                    "feedback_count": 10,
                    "negative_count": 1,  # Too low
                }]
            return []

        backend.query_raw = AsyncMock(side_effect=mock_query_raw)
        service = FeedbackTracerService(backend=backend)

        demoted = await service.check_demotion(
            entity_ids=["entity-123"],
            demotion_threshold=3,
            min_feedback_count=5,
        )

        assert len(demoted) == 0

    @pytest.mark.asyncio
    async def test_demotion_path_semantic_to_perception(self):
        """Test demotion from SEMANTIC goes to PERCEPTION."""
        backend = MagicMock()
        demote_calls = []
        call_count = [0]

        async def mock_query_raw(query, params):
            call_count[0] += 1
            # First call is the check query, second is the demotion query
            if call_count[0] == 1:
                return [{
                    "current_layer": "SEMANTIC",
                    "confidence": 0.4,
                    "feedback_count": 10,
                    "negative_count": 5,
                }]
            else:
                demote_calls.append(params)
                return [{"demoted_id": params.get("entity_id")}]

        backend.query_raw = AsyncMock(side_effect=mock_query_raw)
        service = FeedbackTracerService(backend=backend)

        demoted = await service.check_demotion(["entity-123"])

        assert len(demoted) == 1
        assert demote_calls[0]["target_layer"] == "PERCEPTION"

    @pytest.mark.asyncio
    async def test_demotion_path_reasoning_to_semantic(self):
        """Test demotion from REASONING goes to SEMANTIC."""
        backend = MagicMock()
        demote_calls = []
        call_count = [0]

        async def mock_query_raw(query, params):
            call_count[0] += 1
            # First call is the check query, second is the demotion query
            if call_count[0] == 1:
                return [{
                    "current_layer": "REASONING",
                    "confidence": 0.4,
                    "feedback_count": 10,
                    "negative_count": 5,
                }]
            else:
                demote_calls.append(params)
                return [{"demoted_id": params.get("entity_id")}]

        backend.query_raw = AsyncMock(side_effect=mock_query_raw)
        service = FeedbackTracerService(backend=backend)

        demoted = await service.check_demotion(["entity-123"])

        assert len(demoted) == 1
        assert demote_calls[0]["target_layer"] == "SEMANTIC"

    @pytest.mark.asyncio
    async def test_no_demotion_below_perception(self):
        """Test entities at PERCEPTION cannot be demoted further."""
        backend = MagicMock()

        async def mock_query_raw(query, params):
            if "feedback_count" in query:
                return [{
                    "current_layer": "PERCEPTION",  # Already at lowest
                    "confidence": 0.2,
                    "feedback_count": 10,
                    "negative_count": 8,
                }]
            return []

        backend.query_raw = AsyncMock(side_effect=mock_query_raw)
        service = FeedbackTracerService(backend=backend)

        demoted = await service.check_demotion(["entity-123"])

        assert len(demoted) == 0  # Cannot demote PERCEPTION

    @pytest.mark.asyncio
    async def test_demotion_without_backend_support(self):
        """Test demotion gracefully handles missing backend methods."""
        backend = MagicMock(spec=[])  # No query_raw method
        service = FeedbackTracerService(backend=backend)

        demoted = await service.check_demotion(["entity-123"])

        assert len(demoted) == 0
