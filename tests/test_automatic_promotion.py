"""Tests for Automatic Layer Promotion Pipeline.

Tests the automatic promotion of entities between knowledge layers:
- PERCEPTION → SEMANTIC (confidence >= 0.85, validation >= 3, or ontology match)
- SEMANTIC → REASONING (confidence >= 0.90, reference >= 5, or inference rule)
- REASONING → APPLICATION (query freq >= 10/24h, cache hit rate >= 50%)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from application.services.automatic_layer_transition import (
    AutomaticLayerTransitionService,
    PromotionThresholds,
    QueryTracker,
)
from application.services.layer_transition import (
    Layer,
    TransitionStatus,
    LayerTransitionService,
)
from application.jobs.promotion_scanner import PromotionScannerJob
from application.event_bus import EventBus
from domain.event import KnowledgeEvent
from domain.roles import Role


class TestPromotionThresholds:
    """Test PromotionThresholds configuration."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = PromotionThresholds()

        assert thresholds.perception_confidence_threshold == 0.85
        assert thresholds.perception_validation_count == 3
        assert thresholds.semantic_confidence_threshold == 0.90
        assert thresholds.semantic_reference_count == 5
        assert thresholds.reasoning_query_frequency == 10
        assert thresholds.reasoning_time_window_hours == 24
        assert thresholds.reasoning_cache_hit_rate == 0.50

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = PromotionThresholds(
            perception_confidence_threshold=0.90,
            perception_validation_count=5,
            semantic_confidence_threshold=0.95,
        )

        assert thresholds.perception_confidence_threshold == 0.90
        assert thresholds.perception_validation_count == 5
        assert thresholds.semantic_confidence_threshold == 0.95


class TestQueryTracker:
    """Test QueryTracker for APPLICATION promotion."""

    def test_cache_hit_rate_empty(self):
        """Test cache hit rate with no queries."""
        tracker = QueryTracker(entity_id="test-entity")
        assert tracker.cache_hit_rate == 0.0

    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate calculation."""
        tracker = QueryTracker(entity_id="test-entity")
        tracker.cache_hits = 7
        tracker.cache_misses = 3

        assert tracker.cache_hit_rate == 0.7

    def test_cache_hit_rate_all_hits(self):
        """Test 100% cache hit rate."""
        tracker = QueryTracker(entity_id="test-entity")
        tracker.cache_hits = 10
        tracker.cache_misses = 0

        assert tracker.cache_hit_rate == 1.0


class TestAutomaticLayerTransitionService:
    """Test AutomaticLayerTransitionService."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.get_entity = AsyncMock(return_value=None)
        backend.get_promotion_candidates = AsyncMock(return_value=[])
        backend.promote_entity = AsyncMock(return_value={
            "transition_id": "test-transition",
            "status": "completed"
        })
        return backend

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        bus = MagicMock(spec=EventBus)
        bus.subscribe = MagicMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.fixture
    def service(self, mock_backend, mock_event_bus):
        """Create service with mocks."""
        return AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
            enable_auto_promotion=True
        )

    def test_initialization(self, service, mock_event_bus):
        """Test service initialization."""
        assert service.enable_auto_promotion is True
        assert service.thresholds is not None
        assert mock_event_bus.subscribe.call_count == 3  # 3 event subscriptions

    def test_initialization_disabled(self, mock_backend, mock_event_bus):
        """Test service with auto-promotion disabled."""
        service = AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
            enable_auto_promotion=False
        )
        assert service.enable_auto_promotion is False

    @pytest.mark.asyncio
    async def test_check_perception_promotion_high_confidence(self, service):
        """Test PERCEPTION promotion based on high confidence."""
        entity_data = {
            "id": "entity-1",
            "layer": "PERCEPTION",
            "extraction_confidence": 0.90  # Above 0.85 threshold
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_perception_promotion_low_confidence(self, service):
        """Test PERCEPTION entity with low confidence not promoted."""
        entity_data = {
            "id": "entity-1",
            "layer": "PERCEPTION",
            "extraction_confidence": 0.70  # Below 0.85 threshold
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_perception_promotion_validation_count(self, service):
        """Test PERCEPTION promotion based on validation count."""
        entity_data = {
            "id": "entity-1",
            "layer": "PERCEPTION",
            "extraction_confidence": 0.50,  # Low confidence
            "validation_count": 5  # Above 3 threshold
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_perception_promotion_ontology_match(self, service):
        """Test PERCEPTION promotion based on ontology match."""
        entity_data = {
            "id": "entity-1",
            "layer": "PERCEPTION",
            "extraction_confidence": 0.50,  # Low confidence
            "validation_count": 0,
            "snomed_code": "387517004"  # Has SNOMED code
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_semantic_promotion_high_confidence(self, service):
        """Test SEMANTIC promotion based on high confidence."""
        entity_data = {
            "id": "entity-1",
            "layer": "SEMANTIC",
            "confidence": 0.95  # Above 0.90 threshold
        }

        result = await service._check_semantic_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_semantic_promotion_inference_rules(self, service):
        """Test SEMANTIC promotion based on inference rules."""
        entity_data = {
            "id": "entity-1",
            "layer": "SEMANTIC",
            "confidence": 0.70,  # Low confidence
            "inference_rules_applied": ["drug_interaction_check"]
        }

        result = await service._check_semantic_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_semantic_promotion_reference_count(self, service):
        """Test SEMANTIC promotion based on reference count."""
        entity_data = {
            "id": "entity-1",
            "layer": "SEMANTIC",
            "confidence": 0.70,  # Low confidence
            "reference_count": 10  # Above 5 threshold
        }

        result = await service._check_semantic_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_reasoning_promotion_meets_criteria(self, service):
        """Test REASONING promotion when criteria met."""
        tracker = QueryTracker(entity_id="entity-1")
        tracker.query_count = 15  # Above 10 threshold
        tracker.first_query_at = datetime.now() - timedelta(hours=1)
        tracker.cache_hits = 10
        tracker.cache_misses = 5  # 66% cache hit rate, above 50%

        result = await service._check_reasoning_promotion("entity-1", tracker)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_reasoning_promotion_low_query_count(self, service):
        """Test REASONING promotion fails with low query count."""
        tracker = QueryTracker(entity_id="entity-1")
        tracker.query_count = 5  # Below 10 threshold
        tracker.first_query_at = datetime.now() - timedelta(hours=1)
        tracker.cache_hits = 5
        tracker.cache_misses = 0

        result = await service._check_reasoning_promotion("entity-1", tracker)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_reasoning_promotion_low_cache_rate(self, service):
        """Test REASONING promotion fails with low cache hit rate."""
        tracker = QueryTracker(entity_id="entity-1")
        tracker.query_count = 15  # Above 10 threshold
        tracker.first_query_at = datetime.now() - timedelta(hours=1)
        tracker.cache_hits = 2
        tracker.cache_misses = 10  # 16% cache hit rate, below 50%

        result = await service._check_reasoning_promotion("entity-1", tracker)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_reasoning_promotion_outside_window(self, service):
        """Test REASONING promotion resets if outside time window."""
        tracker = QueryTracker(entity_id="entity-1")
        tracker.query_count = 15
        tracker.first_query_at = datetime.now() - timedelta(hours=48)  # Outside 24h window
        tracker.cache_hits = 10
        tracker.cache_misses = 5

        result = await service._check_reasoning_promotion("entity-1", tracker)
        assert result is False
        # Tracker should be reset
        assert tracker.query_count == 1

    def test_enrich_for_semantic_layer(self, service):
        """Test entity enrichment for SEMANTIC layer."""
        entity_data = {
            "id": "entity-1",
            "name": "Diabetes",
            "layer": "PERCEPTION"
        }

        enriched = service._enrich_for_layer(entity_data, Layer.SEMANTIC)

        assert enriched["properties"]["layer"] == "SEMANTIC"
        assert enriched["properties"]["domain"] == "medical"
        assert enriched["properties"]["validated"] is True
        assert "validated_at" in enriched["properties"]

    def test_enrich_for_reasoning_layer(self, service):
        """Test entity enrichment for REASONING layer."""
        entity_data = {
            "id": "entity-1",
            "name": "Diabetes Treatment",
            "layer": "SEMANTIC"
        }

        enriched = service._enrich_for_layer(entity_data, Layer.REASONING)

        assert enriched["properties"]["layer"] == "REASONING"
        assert "confidence" in enriched["properties"]
        assert "reasoning" in enriched["properties"]
        assert enriched["properties"]["inference_rules_applied"] == []

    def test_enrich_for_application_layer(self, service):
        """Test entity enrichment for APPLICATION layer."""
        entity_data = {
            "id": "entity-1",
            "name": "Common Query Pattern",
            "layer": "REASONING"
        }

        enriched = service._enrich_for_layer(entity_data, Layer.APPLICATION)

        assert enriched["properties"]["layer"] == "APPLICATION"
        assert enriched["properties"]["usage_context"] == "query_pattern"
        assert enriched["properties"]["access_pattern"] == "frequent_query"

    def test_get_statistics(self, service):
        """Test statistics retrieval."""
        stats = service.get_statistics()

        assert "promotions_attempted" in stats
        assert "promotions_completed" in stats
        assert "promotions_rejected" in stats
        assert "by_layer" in stats
        assert "thresholds" in stats
        assert "auto_promotion_enabled" in stats


class TestPromotionScannerJob:
    """Test PromotionScannerJob background job."""

    @pytest.fixture
    def mock_transition_service(self):
        """Create mock transition service."""
        service = MagicMock()
        service.scan_for_promotion_candidates = AsyncMock(return_value=[])
        service._get_entity_data = AsyncMock(return_value=None)
        service._promote_entity = AsyncMock(return_value=MagicMock(
            status=TransitionStatus.COMPLETED
        ))
        return service

    @pytest.fixture
    def scanner(self, mock_transition_service):
        """Create scanner with mock service."""
        return PromotionScannerJob(
            transition_service=mock_transition_service,
            scan_interval_seconds=60,
        )

    def test_initialization(self, scanner):
        """Test scanner initialization."""
        assert scanner.scan_interval == 60
        assert scanner.enable_perception_scan is True
        assert scanner.enable_semantic_scan is True
        assert scanner._running is False

    @pytest.mark.asyncio
    async def test_run_once_no_candidates(self, scanner, mock_transition_service):
        """Test single scan with no candidates."""
        mock_transition_service.scan_for_promotion_candidates.return_value = []

        results = await scanner.run_once()

        assert results["perception_candidates"] == 0
        assert results["semantic_candidates"] == 0
        assert results["promotions"] == 0
        assert scanner.stats["total_scans"] == 1

    @pytest.mark.asyncio
    async def test_run_once_with_candidates(self, scanner, mock_transition_service):
        """Test single scan with promotion candidates."""
        # Return candidates for PERCEPTION layer
        mock_transition_service.scan_for_promotion_candidates.side_effect = [
            [{"id": "entity-1", "name": "Test Entity", "extraction_confidence": 0.90}],
            []  # No SEMANTIC candidates
        ]
        mock_transition_service._get_entity_data.return_value = {
            "id": "entity-1",
            "name": "Test Entity",
            "layer": "PERCEPTION"
        }

        results = await scanner.run_once()

        assert results["perception_candidates"] == 1
        assert results["promotions"] == 1
        assert scanner.stats["total_scans"] == 1
        assert scanner.stats["total_promotions"] == 1

    def test_get_statistics(self, scanner):
        """Test statistics retrieval."""
        stats = scanner.get_statistics()

        assert "total_scans" in stats
        assert "total_promotions" in stats
        assert "running" in stats
        assert "scan_interval_seconds" in stats


class TestPromotionIntegration:
    """Integration tests for the full promotion pipeline."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend with promotion support."""
        backend = MagicMock()
        backend.get_entity = AsyncMock(return_value={
            "id": "entity-1",
            "properties": {
                "name": "Crohn's Disease",
                "layer": "PERCEPTION",
                "extraction_confidence": 0.90
            }
        })
        backend.get_promotion_candidates = AsyncMock(return_value=[
            {
                "id": "entity-1",
                "name": "Crohn's Disease",
                "layer": "PERCEPTION",
                "extraction_confidence": 0.90
            }
        ])
        backend.promote_entity = AsyncMock(return_value={
            "transition_id": "test-transition-1",
            "entity_id": "entity-1",
            "from_layer": "PERCEPTION",
            "to_layer": "SEMANTIC",
            "status": "completed"
        })
        return backend

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        bus = MagicMock(spec=EventBus)
        bus.subscribe = MagicMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.mark.asyncio
    async def test_full_promotion_flow(self, mock_backend, mock_event_bus):
        """Test complete promotion flow from scan to promotion."""
        # Make get_promotion_candidates return different results for each layer
        mock_backend.get_promotion_candidates.side_effect = [
            [{"id": "entity-1", "name": "Crohn's Disease", "layer": "PERCEPTION", "extraction_confidence": 0.90}],
            []  # No SEMANTIC candidates
        ]

        # Create services
        auto_service = AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
            enable_auto_promotion=True
        )

        scanner = PromotionScannerJob(
            transition_service=auto_service,
            scan_interval_seconds=60
        )

        # Run scan
        results = await scanner.run_once()

        # Verify promotion occurred
        assert results["perception_candidates"] == 1
        assert results["semantic_candidates"] == 0
        assert results["promotions"] == 1

        # Verify backend was called
        mock_backend.get_promotion_candidates.assert_called()

    @pytest.mark.asyncio
    async def test_promotion_scan_results(self, mock_backend, mock_event_bus):
        """Test run_promotion_scan method."""
        service = AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
            enable_auto_promotion=True
        )

        results = await service.run_promotion_scan()

        assert "scanned_layers" in results
        assert "PERCEPTION" in results["scanned_layers"]
        assert "SEMANTIC" in results["scanned_layers"]
        assert "candidates_found" in results
        assert "promotions_executed" in results


class TestEventHandlers:
    """Test event handlers for automatic promotion."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.get_entity = AsyncMock(return_value=None)
        backend.promote_entity = AsyncMock()
        return backend

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        bus = MagicMock(spec=EventBus)
        bus.subscribe = MagicMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.fixture
    def service(self, mock_backend, mock_event_bus):
        """Create service with mocks."""
        return AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
            enable_auto_promotion=True
        )

    @pytest.mark.asyncio
    async def test_handle_entity_created_promotes(self, service, mock_backend):
        """Test entity_created event triggers promotion."""
        event = KnowledgeEvent(
            action="entity_created",
            data={
                "id": "entity-1",
                "name": "Test Entity",
                "layer": "PERCEPTION",
                "extraction_confidence": 0.90  # Above threshold
            },
            role=Role.DATA_ENGINEER
        )

        # Mock the transition service
        service._transition_service.request_transition = MagicMock(
            return_value=MagicMock(
                transition_id="test-1",
                status=TransitionStatus.PENDING
            )
        )
        service._transition_service.execute_transition = AsyncMock(
            return_value=MagicMock(
                transition_id="test-1",
                status=TransitionStatus.COMPLETED
            )
        )

        await service._handle_entity_created(event)

        # Verify promotion was attempted
        assert service.stats["promotions_attempted"] > 0

    @pytest.mark.asyncio
    async def test_handle_entity_created_skips_non_perception(self, service):
        """Test entity_created skips non-PERCEPTION entities."""
        event = KnowledgeEvent(
            action="entity_created",
            data={
                "id": "entity-1",
                "layer": "SEMANTIC",  # Not PERCEPTION
                "confidence": 0.90
            },
            role=Role.DATA_ENGINEER
        )

        initial_attempts = service.stats["promotions_attempted"]
        await service._handle_entity_created(event)

        # No promotion should be attempted
        assert service.stats["promotions_attempted"] == initial_attempts

    @pytest.mark.asyncio
    async def test_handle_entity_created_disabled(self, mock_backend, mock_event_bus):
        """Test entity_created does nothing when auto-promotion disabled."""
        service = AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
            enable_auto_promotion=False  # Disabled
        )

        event = KnowledgeEvent(
            action="entity_created",
            data={
                "id": "entity-1",
                "layer": "PERCEPTION",
                "extraction_confidence": 0.90
            },
            role=Role.DATA_ENGINEER
        )

        await service._handle_entity_created(event)

        # No promotion should be attempted
        assert service.stats["promotions_attempted"] == 0
