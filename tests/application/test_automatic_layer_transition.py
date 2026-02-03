"""Unit tests for Automatic Layer Transition Service."""

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
    LayerTransitionRecord,
)
from domain.event import KnowledgeEvent
from domain.roles import Role


class TestPromotionThresholds:
    """Test PromotionThresholds dataclass."""

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
            perception_confidence_threshold=0.9,
            perception_validation_count=5,
            semantic_confidence_threshold=0.95,
        )

        assert thresholds.perception_confidence_threshold == 0.9
        assert thresholds.perception_validation_count == 5
        assert thresholds.semantic_confidence_threshold == 0.95


class TestQueryTracker:
    """Test QueryTracker dataclass."""

    def test_initial_state(self):
        """Test tracker initial state."""
        tracker = QueryTracker(entity_id="entity:123")

        assert tracker.entity_id == "entity:123"
        assert tracker.query_count == 0
        assert tracker.first_query_at is None
        assert tracker.last_query_at is None
        assert tracker.cache_hits == 0
        assert tracker.cache_misses == 0

    def test_cache_hit_rate_zero(self):
        """Test cache hit rate with no queries."""
        tracker = QueryTracker(entity_id="entity:123")
        assert tracker.cache_hit_rate == 0.0

    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate calculation."""
        tracker = QueryTracker(
            entity_id="entity:123",
            cache_hits=7,
            cache_misses=3,
        )

        assert tracker.cache_hit_rate == 0.7

    def test_cache_hit_rate_all_hits(self):
        """Test cache hit rate with all hits."""
        tracker = QueryTracker(
            entity_id="entity:123",
            cache_hits=10,
            cache_misses=0,
        )

        assert tracker.cache_hit_rate == 1.0


class TestAutomaticLayerTransitionServiceInit:
    """Test AutomaticLayerTransitionService initialization."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        return MagicMock()

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        bus = MagicMock()
        bus.subscribe = MagicMock()
        bus.publish = AsyncMock()
        return bus

    def test_initialization_defaults(self, mock_backend, mock_event_bus):
        """Test service initialization with defaults."""
        service = AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
        )

        assert service.backend == mock_backend
        assert service.event_bus == mock_event_bus
        assert service.enable_auto_promotion is True
        assert isinstance(service.thresholds, PromotionThresholds)

    def test_initialization_custom_thresholds(self, mock_backend, mock_event_bus):
        """Test service initialization with custom thresholds."""
        custom_thresholds = PromotionThresholds(
            perception_confidence_threshold=0.9,
        )

        service = AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
            thresholds=custom_thresholds,
        )

        assert service.thresholds.perception_confidence_threshold == 0.9

    def test_event_subscriptions(self, mock_backend, mock_event_bus):
        """Test that service subscribes to required events."""
        service = AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
        )

        # Verify subscriptions
        calls = mock_event_bus.subscribe.call_args_list
        event_types = [call[0][0] for call in calls]

        assert "entity_created" in event_types
        assert "entity_updated" in event_types
        assert "query_executed" in event_types

    def test_initial_statistics(self, mock_backend, mock_event_bus):
        """Test initial statistics state."""
        service = AutomaticLayerTransitionService(
            backend=mock_backend,
            event_bus=mock_event_bus,
        )

        assert service.stats["promotions_attempted"] == 0
        assert service.stats["promotions_completed"] == 0
        assert service.stats["promotions_rejected"] == 0


class TestPerceptionPromotionCheck:
    """Test PERCEPTION → SEMANTIC promotion checks."""

    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        backend = MagicMock()
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()
        return AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
        )

    @pytest.mark.asyncio
    async def test_promotion_by_confidence(self, service):
        """Test promotion when confidence threshold met."""
        entity_data = {
            "id": "entity:123",
            "layer": "PERCEPTION",
            "properties": {
                "extraction_confidence": 0.90,
            }
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_promotion_low_confidence(self, service):
        """Test no promotion when confidence below threshold."""
        entity_data = {
            "id": "entity:123",
            "layer": "PERCEPTION",
            "properties": {
                "extraction_confidence": 0.70,
            }
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is False

    @pytest.mark.asyncio
    async def test_promotion_by_validation_count(self, service):
        """Test promotion when validation count met."""
        entity_data = {
            "id": "entity:123",
            "layer": "PERCEPTION",
            "properties": {
                "extraction_confidence": 0.50,
                "validation_count": 5,
            }
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_promotion_by_ontology_match(self, service):
        """Test promotion when ontology match exists."""
        entity_data = {
            "id": "entity:123",
            "layer": "PERCEPTION",
            "properties": {
                "extraction_confidence": 0.50,
                "snomed_code": "123456",
            }
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_promotion_by_umls_cui(self, service):
        """Test promotion when UMLS CUI exists."""
        entity_data = {
            "id": "entity:123",
            "properties": {
                "umls_cui": "C0001234",
            }
        }

        result = await service._check_perception_promotion(entity_data)
        assert result is True


class TestSemanticPromotionCheck:
    """Test SEMANTIC → REASONING promotion checks."""

    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        backend = MagicMock()
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        return AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
        )

    @pytest.mark.asyncio
    async def test_promotion_by_confidence(self, service):
        """Test promotion when semantic confidence threshold met."""
        entity_data = {
            "id": "entity:123",
            "layer": "SEMANTIC",
            "properties": {
                "confidence": 0.95,
            }
        }

        result = await service._check_semantic_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_promotion_low_confidence(self, service):
        """Test no promotion when confidence below threshold."""
        entity_data = {
            "id": "entity:123",
            "layer": "SEMANTIC",
            "properties": {
                "confidence": 0.80,
            }
        }

        result = await service._check_semantic_promotion(entity_data)
        assert result is False

    @pytest.mark.asyncio
    async def test_promotion_by_inference_rules(self, service):
        """Test promotion when inference rules have fired."""
        entity_data = {
            "id": "entity:123",
            "layer": "SEMANTIC",
            "properties": {
                "confidence": 0.70,
                "inference_rules_applied": ["transitive_closure", "contraindication_rule"],
            }
        }

        result = await service._check_semantic_promotion(entity_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_promotion_by_reference_count(self, service):
        """Test promotion when reference count met."""
        entity_data = {
            "id": "entity:123",
            "layer": "SEMANTIC",
            "properties": {
                "confidence": 0.70,
                "reference_count": 10,
            }
        }

        result = await service._check_semantic_promotion(entity_data)
        assert result is True


class TestReasoningPromotionCheck:
    """Test REASONING → APPLICATION promotion checks."""

    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        backend = MagicMock()
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        return AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
        )

    @pytest.mark.asyncio
    async def test_promotion_meets_criteria(self, service):
        """Test promotion when all criteria met."""
        tracker = QueryTracker(
            entity_id="entity:123",
            query_count=15,
            first_query_at=datetime.now() - timedelta(hours=12),
            last_query_at=datetime.now(),
            cache_hits=10,
            cache_misses=5,
        )

        result = await service._check_reasoning_promotion("entity:123", tracker)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_promotion_low_query_count(self, service):
        """Test no promotion when query count below threshold."""
        tracker = QueryTracker(
            entity_id="entity:123",
            query_count=5,  # Below threshold of 10
            first_query_at=datetime.now() - timedelta(hours=12),
            last_query_at=datetime.now(),
            cache_hits=5,
            cache_misses=0,
        )

        result = await service._check_reasoning_promotion("entity:123", tracker)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_promotion_low_cache_hit_rate(self, service):
        """Test no promotion when cache hit rate below threshold."""
        tracker = QueryTracker(
            entity_id="entity:123",
            query_count=15,
            first_query_at=datetime.now() - timedelta(hours=12),
            last_query_at=datetime.now(),
            cache_hits=3,
            cache_misses=12,  # 20% hit rate, below 50% threshold
        )

        result = await service._check_reasoning_promotion("entity:123", tracker)
        assert result is False

    @pytest.mark.asyncio
    async def test_tracker_reset_outside_window(self, service):
        """Test tracker is reset when outside time window."""
        tracker = QueryTracker(
            entity_id="entity:123",
            query_count=15,
            first_query_at=datetime.now() - timedelta(hours=48),  # Outside 24h window
            last_query_at=datetime.now(),
            cache_hits=10,
            cache_misses=5,
        )

        result = await service._check_reasoning_promotion("entity:123", tracker)

        # Tracker should be reset
        assert tracker.query_count == 1
        assert result is False


class TestEntityEnrichment:
    """Test entity data enrichment for layer promotion."""

    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        backend = MagicMock()
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        return AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
        )

    def test_enrich_for_semantic_layer(self, service):
        """Test enrichment for SEMANTIC layer promotion."""
        entity_data = {
            "id": "entity:123",
            "name": "Test Entity",
            "properties": {
                "source": "dda",
            }
        }

        enriched = service._enrich_for_layer(entity_data, Layer.SEMANTIC)

        assert enriched["properties"]["layer"] == "SEMANTIC"
        assert enriched["properties"]["domain"] == "medical"
        assert enriched["properties"]["validated"] is True
        assert "validated_at" in enriched["properties"]
        assert "promotion_timestamp" in enriched["properties"]

    def test_enrich_for_reasoning_layer(self, service):
        """Test enrichment for REASONING layer promotion."""
        entity_data = {
            "id": "entity:123",
            "name": "Test Entity",
            "layer": "SEMANTIC",
            "properties": {
                "extraction_confidence": 0.90,
            }
        }

        enriched = service._enrich_for_layer(entity_data, Layer.REASONING)

        assert enriched["properties"]["layer"] == "REASONING"
        assert "confidence" in enriched["properties"]
        assert "reasoning" in enriched["properties"]
        assert enriched["properties"]["promoted_from"] == "SEMANTIC"

    def test_enrich_for_application_layer(self, service):
        """Test enrichment for APPLICATION layer promotion."""
        entity_data = {
            "id": "entity:123",
            "name": "Test Entity",
            "layer": "REASONING",
            "properties": {}
        }

        enriched = service._enrich_for_layer(entity_data, Layer.APPLICATION)

        assert enriched["properties"]["layer"] == "APPLICATION"
        assert enriched["properties"]["usage_context"] == "query_pattern"
        assert enriched["properties"]["access_pattern"] == "frequent_query"
        assert "promoted_at" in enriched["properties"]


class TestEventHandling:
    """Test event handling for automatic promotion."""

    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        backend = MagicMock()
        backend.get_entity = AsyncMock(return_value=None)
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()
        return AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
        )

    @pytest.mark.asyncio
    async def test_handle_entity_created_disabled(self, service):
        """Test entity_created handler when auto-promotion disabled."""
        service.enable_auto_promotion = False

        event = KnowledgeEvent(
            action="entity_created",
            data={"id": "entity:123", "layer": "PERCEPTION"},
            role=Role.SYSTEM_ADMIN,
        )

        await service._handle_entity_created(event)
        # Should return early without any promotion checks

    @pytest.mark.asyncio
    async def test_handle_entity_created_non_perception(self, service):
        """Test entity_created handler for non-PERCEPTION entity."""
        event = KnowledgeEvent(
            action="entity_created",
            data={"id": "entity:123", "layer": "SEMANTIC"},
            role=Role.SYSTEM_ADMIN,
        )

        await service._handle_entity_created(event)
        # Should return early without promotion checks

    @pytest.mark.asyncio
    async def test_handle_entity_updated_disabled(self, service):
        """Test entity_updated handler when auto-promotion disabled."""
        service.enable_auto_promotion = False

        event = KnowledgeEvent(
            action="entity_updated",
            data={"id": "entity:123", "layer": "SEMANTIC"},
            role=Role.SYSTEM_ADMIN,
        )

        await service._handle_entity_updated(event)
        # Should return early without any promotion checks

    @pytest.mark.asyncio
    async def test_handle_query_executed_disabled(self, service):
        """Test query_executed handler when auto-promotion disabled."""
        service.enable_auto_promotion = False

        event = KnowledgeEvent(
            action="query_executed",
            data={"entities_involved": [{"id": "entity:123", "layer": "REASONING"}]},
            role=Role.SYSTEM_ADMIN,
        )

        await service._handle_query_executed(event)
        # Should return early without tracking


class TestQueryTrackerManagement:
    """Test query tracker management."""

    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        backend = MagicMock()
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        return AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
        )

    def test_get_or_create_tracker_new(self, service):
        """Test creating a new tracker."""
        tracker = service._get_or_create_tracker("entity:123")

        assert tracker.entity_id == "entity:123"
        assert tracker.query_count == 0
        assert "entity:123" in service._query_trackers

    def test_get_or_create_tracker_existing(self, service):
        """Test getting an existing tracker."""
        # Create first
        tracker1 = service._get_or_create_tracker("entity:123")
        tracker1.query_count = 5

        # Get existing
        tracker2 = service._get_or_create_tracker("entity:123")

        assert tracker2.query_count == 5
        assert tracker1 is tracker2


class TestStatistics:
    """Test statistics reporting."""

    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        backend = MagicMock()
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        return AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
        )

    def test_get_statistics_initial(self, service):
        """Test getting initial statistics."""
        stats = service.get_statistics()

        assert stats["promotions_attempted"] == 0
        assert stats["promotions_completed"] == 0
        assert stats["promotions_rejected"] == 0
        assert "thresholds" in stats
        assert stats["auto_promotion_enabled"] is True
        assert stats["active_trackers"] == 0

    def test_get_statistics_with_trackers(self, service):
        """Test statistics with active trackers."""
        service._get_or_create_tracker("entity:1")
        service._get_or_create_tracker("entity:2")

        stats = service.get_statistics()
        assert stats["active_trackers"] == 2

    def test_statistics_thresholds_included(self, service):
        """Test that thresholds are included in statistics."""
        stats = service.get_statistics()

        assert "perception_confidence" in stats["thresholds"]
        assert "semantic_confidence" in stats["thresholds"]
        assert "reasoning_query_frequency" in stats["thresholds"]


class TestPromotionScan:
    """Test batch promotion scanning."""

    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        backend = MagicMock()
        backend.get_promotion_candidates = AsyncMock(return_value=[])
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()
        return AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
        )

    @pytest.mark.asyncio
    async def test_scan_for_perception_candidates(self, service):
        """Test scanning for PERCEPTION promotion candidates."""
        service.backend.get_promotion_candidates = AsyncMock(
            return_value=["entity:1", "entity:2"]
        )

        candidates = await service.scan_for_promotion_candidates("PERCEPTION")

        assert len(candidates) == 2
        service.backend.get_promotion_candidates.assert_called_once_with(
            from_layer="PERCEPTION",
            confidence_threshold=0.85
        )

    @pytest.mark.asyncio
    async def test_scan_no_backend_support(self, service):
        """Test scan when backend doesn't support method."""
        del service.backend.get_promotion_candidates

        candidates = await service.scan_for_promotion_candidates("PERCEPTION")

        assert candidates == []

    @pytest.mark.asyncio
    async def test_run_promotion_scan(self, service):
        """Test running a full promotion scan."""
        service.backend.get_promotion_candidates = AsyncMock(return_value=[])

        results = await service.run_promotion_scan()

        assert "scanned_layers" in results
        assert "candidates_found" in results
        assert "promotions_executed" in results
        assert "PERCEPTION" in results["scanned_layers"]
        assert "SEMANTIC" in results["scanned_layers"]
