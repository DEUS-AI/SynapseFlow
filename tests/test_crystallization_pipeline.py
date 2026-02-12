"""Tests for the Crystallization Pipeline.

Tests the flow from Graphiti/FalkorDB episodic memory to Neo4j DIKW layers.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from application.services.entity_resolver import (
    EntityResolver,
    CrystallizationMatch,
    MergeResult,
)
from application.services.crystallization_service import (
    CrystallizationService,
    CrystallizationConfig,
    CrystallizationMode,
    CrystallizationResult,
)
from application.services.promotion_gate import (
    PromotionGate,
    PromotionGateConfig,
)
from domain.promotion_models import (
    PromotionDecision,
    PromotionStatus,
    RiskLevel,
    EntityCategory,
    CATEGORY_RISK_MAPPING,
)
from application.event_bus import EventBus
from domain.event import KnowledgeEvent
from domain.roles import Role


# ========================================
# EntityResolver Tests
# ========================================

class TestEntityResolver:
    """Tests for EntityResolver service."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock Neo4j backend."""
        backend = AsyncMock()
        backend.query = AsyncMock(return_value={"rows": [], "nodes": {}})
        backend.get_entity = AsyncMock(return_value=None)
        backend.update_entity_properties = AsyncMock(return_value=True)
        return backend

    @pytest.fixture
    def resolver(self, mock_backend):
        """Create an EntityResolver instance."""
        return EntityResolver(backend=mock_backend)

    def test_normalize_entity_name(self, resolver):
        """Test entity name normalization."""
        # Basic normalization
        assert resolver.normalize_entity_name("  Imurel  ") == "imurel"
        assert resolver.normalize_entity_name("HYPERTENSION") == "hypertension"

        # Medical abbreviation expansion
        assert resolver.normalize_entity_name("HTN") == "hypertension"
        assert resolver.normalize_entity_name("DM2") == "diabetes mellitus type 2"
        assert resolver.normalize_entity_name("COPD") == "chronic obstructive pulmonary disease"

    def test_normalize_entity_type(self, resolver):
        """Test entity type normalization."""
        # Graphiti → DIKW type mapping
        assert resolver.normalize_entity_type("medication") == "Medication"
        assert resolver.normalize_entity_type("drug") == "Medication"
        assert resolver.normalize_entity_type("diagnosis") == "Diagnosis"
        assert resolver.normalize_entity_type("condition") == "Diagnosis"
        assert resolver.normalize_entity_type("allergy") == "Allergy"

        # Unknown types get title case
        assert resolver.normalize_entity_type("unknown_type") == "Unknown_Type"

    @pytest.mark.asyncio
    async def test_find_existing_no_match(self, resolver, mock_backend):
        """Test finding entity when no match exists."""
        match = await resolver.find_existing_for_crystallization(
            name="Metformin",
            entity_type="Medication",
        )

        assert not match.found
        assert match.entity_id is None

    @pytest.mark.asyncio
    async def test_find_existing_exact_match(self, resolver, mock_backend):
        """Test finding entity with exact match."""
        mock_backend.query.return_value = {
            "rows": [{
                "id": "entity_123",
                "name": "Metformin",
                "properties": {"dikw_layer": "PERCEPTION"},
                "labels": ["Entity", "Medication"],
            }],
            "nodes": {},
        }

        match = await resolver.find_existing_for_crystallization(
            name="Metformin",
            entity_type="Medication",
        )

        assert match.found
        assert match.entity_id == "entity_123"
        assert match.match_type == "exact"
        assert match.similarity_score == 1.0

    @pytest.mark.asyncio
    async def test_merge_for_crystallization(self, resolver, mock_backend):
        """Test merging entity data during crystallization."""
        mock_backend.query.return_value = {
            "rows": [{
                "properties": {
                    "name": "Metformin",
                    "confidence": 0.8,
                    "observation_count": 2,
                }
            }],
        }

        result = await resolver.merge_for_crystallization(
            existing_id="entity_123",
            new_data={"confidence": 0.9, "new_field": "value"},
        )

        assert result.success
        assert result.entity_id == "entity_123"
        assert result.observation_count == 3  # 2 + 1


# ========================================
# CrystallizationService Tests
# ========================================

class TestCrystallizationService:
    """Tests for CrystallizationService."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock Neo4j backend."""
        backend = AsyncMock()
        backend.add_entity = AsyncMock()
        backend.query = AsyncMock(return_value={"rows": []})
        backend.get_entity = AsyncMock(return_value=None)
        return backend

    @pytest.fixture
    def mock_resolver(self):
        """Create a mock EntityResolver."""
        resolver = AsyncMock()
        resolver.find_existing_for_crystallization = AsyncMock(
            return_value=CrystallizationMatch(found=False)
        )
        resolver.merge_for_crystallization = AsyncMock(
            return_value=MergeResult(success=True, entity_id="merged_123", observation_count=2)
        )
        resolver.normalize_entity_type = MagicMock(side_effect=lambda x: x.title())
        return resolver

    @pytest.fixture
    def event_bus(self):
        """Create an EventBus."""
        return EventBus()

    @pytest.fixture
    def service(self, mock_backend, mock_resolver, event_bus):
        """Create a CrystallizationService instance."""
        config = CrystallizationConfig(mode=CrystallizationMode.BATCH)
        return CrystallizationService(
            neo4j_backend=mock_backend,
            entity_resolver=mock_resolver,
            event_bus=event_bus,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_crystallize_new_entity(self, service, mock_resolver):
        """Test crystallizing a new entity."""
        result = await service.crystallize_entities(
            entities=["Metformin"],
            source="test",
        )

        assert result.entities_processed == 1
        assert result.entities_created == 1
        assert result.entities_merged == 0

    @pytest.mark.asyncio
    async def test_crystallize_existing_entity(self, service, mock_resolver):
        """Test crystallizing an entity that already exists (merge)."""
        mock_resolver.find_existing_for_crystallization.return_value = CrystallizationMatch(
            found=True,
            entity_id="existing_123",
            entity_data={"name": "Metformin", "layer": "PERCEPTION"},
            match_type="exact",
            similarity_score=1.0,
        )

        result = await service.crystallize_entities(
            entities=["Metformin"],
            source="test",
        )

        assert result.entities_processed == 1
        assert result.entities_created == 0
        assert result.entities_merged == 1

    @pytest.mark.asyncio
    async def test_crystallize_batch(self, service):
        """Test batch crystallization with multiple entities."""
        entities = [
            {"name": "Metformin", "entity_type": "Medication"},
            {"name": "Diabetes", "entity_type": "Diagnosis"},
            {"name": "Headache", "entity_type": "Symptom"},
        ]

        result = await service.crystallize_entities(
            entities=entities,
            source="batch_test",
        )

        assert result.entities_processed == 3
        assert result.batch_id.startswith("batch_")

    @pytest.mark.asyncio
    async def test_crystallization_stats(self, service):
        """Test getting crystallization statistics."""
        stats = await service.get_crystallization_stats()

        assert "mode" in stats
        assert "running" in stats
        assert "pending_entities" in stats
        assert stats["mode"] == "batch"


# ========================================
# PromotionGate Tests
# ========================================

class TestPromotionGate:
    """Tests for PromotionGate service."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock Neo4j backend."""
        backend = AsyncMock()
        backend.get_entity = AsyncMock(return_value={
            "properties": {
                "name": "Metformin",
                "entity_type": "Medication",
                "dikw_layer": "PERCEPTION",
                "confidence": 0.9,
                "observation_count": 3,
                "first_observed": datetime.utcnow().isoformat(),
                "last_observed": datetime.utcnow().isoformat(),
            }
        })
        return backend

    @pytest.fixture
    def gate(self, mock_backend):
        """Create a PromotionGate instance."""
        return PromotionGate(neo4j_backend=mock_backend)

    def test_risk_level_mapping(self):
        """Test entity category to risk level mapping."""
        # HIGH risk categories
        assert CATEGORY_RISK_MAPPING[EntityCategory.DIAGNOSIS] == RiskLevel.HIGH
        assert CATEGORY_RISK_MAPPING[EntityCategory.MEDICATION] == RiskLevel.HIGH
        assert CATEGORY_RISK_MAPPING[EntityCategory.ALLERGY] == RiskLevel.HIGH

        # MEDIUM risk categories
        assert CATEGORY_RISK_MAPPING[EntityCategory.SYMPTOM] == RiskLevel.MEDIUM
        assert CATEGORY_RISK_MAPPING[EntityCategory.VITAL_SIGN] == RiskLevel.MEDIUM

        # LOW risk categories
        assert CATEGORY_RISK_MAPPING[EntityCategory.DEMOGRAPHICS] == RiskLevel.LOW
        assert CATEGORY_RISK_MAPPING[EntityCategory.PREFERENCE] == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_evaluate_promotion_approved(self, gate, mock_backend):
        """Test promotion evaluation that passes all criteria."""
        mock_backend.get_entity.return_value = {
            "properties": {
                "id": "entity_123",
                "name": "Metformin",
                "entity_type": "Medication",
                "dikw_layer": "PERCEPTION",
                "confidence": 0.9,
                "observation_count": 3,
                "first_observed": "2024-01-01T00:00:00",
                "last_observed": "2024-01-02T00:00:00",
            }
        }

        decision = await gate.evaluate_promotion(
            entity_id="entity_123",
            target_layer="SEMANTIC",
        )

        assert decision.entity_id == "entity_123"
        assert decision.from_layer == "PERCEPTION"
        assert decision.to_layer == "SEMANTIC"
        # Note: Approval depends on criteria which include ontology match

    @pytest.mark.asyncio
    async def test_evaluate_promotion_rejected_low_confidence(self, gate, mock_backend):
        """Test promotion rejection due to low confidence."""
        mock_backend.get_entity.return_value = {
            "properties": {
                "id": "entity_123",
                "name": "Unknown Entity",
                "entity_type": "Entity",
                "dikw_layer": "PERCEPTION",
                "confidence": 0.5,  # Below threshold
                "observation_count": 1,  # Below threshold
            }
        }

        decision = await gate.evaluate_promotion(
            entity_id="entity_123",
            target_layer="SEMANTIC",
        )

        assert decision.entity_id == "entity_123"
        assert decision.status == PromotionStatus.REJECTED
        assert not decision.approved
        assert not decision.all_criteria_met

    @pytest.mark.asyncio
    async def test_pending_reviews_queue(self, gate):
        """Test adding and retrieving pending reviews."""
        # Initially empty
        reviews = await gate.get_pending_reviews()
        assert len(reviews) == 0

    @pytest.mark.asyncio
    async def test_promotion_stats(self, gate):
        """Test getting promotion statistics."""
        stats = await gate.get_stats()

        assert stats.total_evaluated == 0
        assert stats.total_approved == 0
        assert stats.total_pending_review == 0
        assert stats.total_rejected == 0


# ========================================
# Integration Tests
# ========================================

class TestCrystallizationPipelineIntegration:
    """Integration tests for the full crystallization pipeline."""

    @pytest.fixture
    def event_bus(self):
        """Create an EventBus."""
        return EventBus()

    @pytest.mark.asyncio
    async def test_episode_added_event_triggers_crystallization(self, event_bus):
        """Test that episode_added events trigger crystallization."""
        events_received = []

        async def capture_event(event: KnowledgeEvent):
            events_received.append(event)

        event_bus.subscribe("episode_added", capture_event)

        # Simulate episode_added event
        event = KnowledgeEvent(
            action="episode_added",
            data={
                "episode_id": "ep_123",
                "patient_id": "patient:demo",
                "session_id": "session_456",
                "entities_extracted": ["Metformin", "Diabetes"],
                "timestamp": datetime.utcnow().isoformat(),
            },
            role=Role.KNOWLEDGE_MANAGER,
        )

        await event_bus.publish(event)

        assert len(events_received) == 1
        assert events_received[0].data["entities_extracted"] == ["Metformin", "Diabetes"]


class TestRoleEnum:
    """Test Role enum values."""

    def test_role_values(self):
        """Verify Role enum has expected values."""
        assert Role.KNOWLEDGE_MANAGER == "knowledge_manager"
        assert Role.DATA_ARCHITECT == "data_architect"
        assert Role.MEDICAL_ASSISTANT == "medical_assistant"
