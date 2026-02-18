"""Tests for OntologyQualityService.

Comprehensive unit tests for ontology quality assessment.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, Set

from domain.ontology_quality_models import OntologyQualityLevel


# Mock the SemanticNormalizer to avoid import issues
class MockSemanticNormalizer:
    """Mock normalizer with required attributes."""

    def __init__(self):
        self._abbreviation_map = {"dm": "diabetes mellitus", "htn": "hypertension"}
        self._synonym_map = {"sugar": "glucose", "bp": "blood pressure"}

    def normalize(self, text: str) -> str:
        return text.lower().strip().replace(" ", "_")

    def expand_abbreviations(self, text: str) -> str:
        return text

    def detect_duplicates(self, names: List[str]) -> List[Dict[str, Any]]:
        return []


class TestOntologyQualityService:
    """Tests for OntologyQualityService."""

    @pytest.fixture
    def mock_kg_backend(self):
        """Mock knowledge graph backend."""
        backend = AsyncMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def sample_entities(self):
        """Sample entities for testing."""
        return [
            {
                "id": "e1",
                "name": "Diabetes Mellitus",
                "type": "Disease",
                "labels": ["Disease", "Entity"],
                "layer": "SEMANTIC",
                "confidence": 0.9,
                "properties": {"name": "Diabetes Mellitus", "description": "A chronic condition"},
            },
            {
                "id": "e2",
                "name": "Insulin",
                "type": "Medication",
                "labels": ["Medication", "Entity"],
                "layer": "SEMANTIC",
                "confidence": 0.85,
                "properties": {"name": "Insulin"},
            },
            {
                "id": "e3",
                "name": "Patient A",
                "type": "Person",
                "labels": ["Person", "Entity"],
                "layer": "PERCEPTION",
                "confidence": 0.7,
                "properties": {"name": "Patient A"},
            },
        ]

    @pytest.fixture
    def sample_relationships(self):
        """Sample relationships for testing."""
        return [
            {
                "source_id": "e1",
                "target_id": "e2",
                "relationship_type": "TREATED_WITH",
                "source_labels": ["Disease"],
                "target_labels": ["Medication"],
            },
            {
                "source_id": "e3",
                "target_id": "e1",
                "relationship_type": "HAS_CONDITION",
                "source_labels": ["Person"],
                "target_labels": ["Disease"],
            },
        ]

    @pytest.fixture
    def service(self, mock_kg_backend):
        """Create OntologyQualityService with mocked dependencies."""
        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            return OntologyQualityService(kg_backend=mock_kg_backend)

    # --- Assessment Method Tests ---

    @pytest.mark.asyncio
    async def test_assess_ontology_empty_graph(self, mock_kg_backend):
        """Test assessment with empty graph."""
        mock_kg_backend.query_raw = AsyncMock(return_value=[])

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            service = OntologyQualityService(kg_backend=mock_kg_backend)
            report = await service.assess_ontology_quality()

        assert report.entity_count == 0
        assert report.relationship_count == 0

    @pytest.mark.asyncio
    async def test_assess_ontology_with_entities(self, mock_kg_backend, sample_entities, sample_relationships):
        """Test full assessment with entities."""
        # First call returns entities, second returns relationships
        mock_kg_backend.query_raw = AsyncMock(
            side_effect=[sample_entities, sample_relationships]
        )

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            service = OntologyQualityService(kg_backend=mock_kg_backend)
            report = await service.assess_ontology_quality()

        assert report.entity_count == 3
        assert isinstance(report.quality_level, OntologyQualityLevel)

    @pytest.mark.asyncio
    async def test_assess_ontology_processing_time(self, mock_kg_backend, sample_entities, sample_relationships):
        """Test that processing time is tracked."""
        mock_kg_backend.query_raw = AsyncMock(
            side_effect=[sample_entities, sample_relationships]
        )

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            service = OntologyQualityService(kg_backend=mock_kg_backend)
            report = await service.assess_ontology_quality()

        assert report.processing_time_ms >= 0

    # --- Coverage Assessment Tests ---

    @pytest.mark.asyncio
    async def test_coverage_all_mapped(self, service, sample_entities):
        """Test coverage when all entities are mapped."""
        score = await service._assess_coverage(sample_entities)

        assert score.total_entities == 3
        assert score.coverage_ratio >= 0

    @pytest.mark.asyncio
    async def test_coverage_partially_mapped(self, service):
        """Test coverage with some unmapped entities."""
        entities = [
            {"id": "e1", "name": "Test", "type": "Disease", "labels": ["Disease"]},
            {"id": "e2", "name": "Unknown", "type": "Custom", "labels": []},  # No labels
        ]

        score = await service._assess_coverage(entities)

        assert score.unmapped_entities >= 0

    @pytest.mark.asyncio
    async def test_coverage_class_distribution(self, service, sample_entities):
        """Test class distribution tracking."""
        score = await service._assess_coverage(sample_entities)

        assert isinstance(score.class_distribution, dict)

    # --- Compliance Assessment Tests ---

    @pytest.mark.asyncio
    async def test_compliance_with_entities(self, service, sample_entities):
        """Test compliance assessment."""
        score = await service._assess_compliance(sample_entities)

        assert score.total_validated >= 0
        assert score.compliance_ratio >= 0

    @pytest.mark.asyncio
    async def test_compliance_empty_entities(self, service):
        """Test compliance with empty entity list."""
        score = await service._assess_compliance([])

        assert score.total_validated == 0
        assert score.compliance_ratio == 0.0  # No entities = no compliance

    # --- Taxonomy Assessment Tests ---

    @pytest.mark.asyncio
    async def test_taxonomy_valid_hierarchy(self, service, sample_entities, sample_relationships):
        """Test taxonomy coherence assessment."""
        score = await service._assess_taxonomy(sample_entities, sample_relationships)

        assert score.total_relationships >= 0
        assert score.coherence_ratio >= 0

    @pytest.mark.asyncio
    async def test_taxonomy_orphan_nodes(self, service):
        """Test detection of orphan nodes."""
        entities = [
            {"id": "e1", "name": "Orphan", "type": "Concept", "labels": []},
        ]
        relationships = []

        score = await service._assess_taxonomy(entities, relationships)

        # All entities without relationships are orphans
        assert score.orphan_nodes >= 0

    @pytest.mark.asyncio
    async def test_taxonomy_empty_relationships(self, service, sample_entities):
        """Test taxonomy with no relationships."""
        score = await service._assess_taxonomy(sample_entities, [])

        assert score.coherence_ratio == 0.0  # No relationships = default 0

    # --- Consistency Assessment Tests ---

    @pytest.mark.asyncio
    async def test_consistency_uniform_mapping(self, service, sample_entities):
        """Test consistency with uniform mappings."""
        score = await service._assess_consistency(sample_entities)

        assert score.consistency_ratio >= 0

    @pytest.mark.asyncio
    async def test_consistency_ambiguous_mapping(self, service):
        """Test detection of ambiguous mappings."""
        entities = [
            {"id": "e1", "name": "Test", "type": "Disease", "labels": ["Disease"]},
            {"id": "e2", "name": "Test2", "type": "Disease", "labels": ["Condition"]},  # Different class
        ]

        score = await service._assess_consistency(entities)

        assert score.total_types >= 0

    @pytest.mark.asyncio
    async def test_consistency_empty_entities(self, service):
        """Test consistency with no entities."""
        score = await service._assess_consistency([])

        assert score.consistency_ratio == 1.0  # No types = no inconsistency

    # --- Normalization Assessment Tests ---

    @pytest.mark.asyncio
    async def test_normalization_assessment(self, service, sample_entities):
        """Test normalization quality assessment."""
        score = await service._assess_normalization(sample_entities)

        assert score.total_names >= 0
        assert score.normalization_rate >= 0

    @pytest.mark.asyncio
    async def test_normalization_empty_entities(self, service):
        """Test normalization with no entities."""
        score = await service._assess_normalization([])

        assert score.total_names == 0
        assert score.normalization_rate == 0

    @pytest.mark.asyncio
    async def test_normalization_abbreviation_detection(self, service):
        """Test detection of abbreviations in entity names."""
        entities = [
            {"id": "e1", "name": "DM Type 2", "type": "Disease", "labels": []},  # dm = diabetes mellitus
            {"id": "e2", "name": "HTN Stage 1", "type": "Condition", "labels": []},  # htn = hypertension
        ]

        score = await service._assess_normalization(entities)

        assert score.abbreviations_expanded >= 0

    # --- Cross-Reference Assessment Tests ---

    @pytest.mark.asyncio
    async def test_cross_reference_valid(self, service, sample_entities, sample_relationships):
        """Test valid cross-reference detection."""
        score = await service._assess_cross_references(sample_relationships, sample_entities)

        assert score.total_references >= 0

    @pytest.mark.asyncio
    async def test_cross_reference_empty(self, service, sample_entities):
        """Test cross-reference with no relationships."""
        score = await service._assess_cross_references([], sample_entities)

        assert score.total_references == 0
        assert score.validity_ratio == 0.0  # No references = default 0

    # --- Interoperability Assessment Tests ---

    @pytest.mark.asyncio
    async def test_interoperability_assessment(self, service, sample_entities):
        """Test interoperability assessment."""
        score = await service._assess_interoperability(sample_entities)

        assert score.exchange_readiness >= 0

    @pytest.mark.asyncio
    async def test_interoperability_empty_entities(self, service):
        """Test interoperability with no entities."""
        score = await service._assess_interoperability([])

        # Should handle empty gracefully
        assert score.schema_org_types == 0

    # --- Helper Method Tests ---

    def test_get_unique_classes(self, service, sample_entities):
        """Test class extraction."""
        classes = service._get_unique_classes(sample_entities)

        assert isinstance(classes, set)

    def test_is_valid_hierarchy_same_labels(self, service):
        """Test same-label relationships are valid."""
        source_labels = {"Disease"}
        target_labels = {"Disease"}

        result = service._is_valid_hierarchy(source_labels, target_labels, "IS_A")

        # Same-type relationships should be valid
        assert result is True

    def test_is_valid_hierarchy_attribute_dataentity(self, service):
        """Test valid Attribute -> DataEntity hierarchy."""
        source_labels = {"Attribute"}
        target_labels = {"DataEntity"}

        result = service._is_valid_hierarchy(source_labels, target_labels, "BELONGS_TO")

        assert result is True

    def test_is_valid_hierarchy_invalid_combo(self, service):
        """Test invalid hierarchy combination."""
        source_labels = {"Disease"}
        target_labels = {"Medication"}

        result = service._is_valid_hierarchy(source_labels, target_labels, "IS_A")

        # No overlap, not a valid hierarchy combination
        assert result is False

    def test_detect_cycles_simple(self, service):
        """Test simple cycle detection with parents dict."""
        # parents dict: node -> set of parents
        parents = {
            "a": {"b"},
            "b": {"a"},  # Cycle: a -> b -> a
        }

        cycles = service._detect_cycles(parents)

        # Should detect the cycle
        assert isinstance(cycles, list)

    def test_detect_cycles_no_cycle(self, service):
        """Test acyclic graph detection."""
        # parents dict with no cycles
        parents = {
            "a": {"b"},
            "b": {"c"},
            "c": set(),  # Root
        }

        cycles = service._detect_cycles(parents)

        # Should be empty
        assert len(cycles) == 0

    def test_detect_cycles_complex(self, service):
        """Test complex multi-node cycle detection."""
        parents = {
            "a": {"b"},
            "b": {"c"},
            "c": {"a"},  # Cycle: a -> b -> c -> a
        }

        cycles = service._detect_cycles(parents)

        assert len(cycles) > 0

    def test_is_valid_relationship_unknown_type(self, service):
        """Test that unknown relationship types are allowed."""
        source_types = {"Disease"}
        target_types = {"Medication"}
        valid_combinations = {
            "hasAttribute": [("DataEntity", "Attribute")],
        }

        result = service._is_valid_relationship(
            "UNKNOWN_TYPE", source_types, target_types, valid_combinations
        )

        # Unknown types are allowed
        assert result is True

    def test_is_valid_relationship_wildcard(self, service):
        """Test wildcard relationship matching."""
        source_types = {"Disease"}
        target_types = {"Domain"}
        valid_combinations = {
            "belongsToDomain": [("*", "Domain")],  # Wildcard source
        }

        result = service._is_valid_relationship(
            "belongsToDomain", source_types, target_types, valid_combinations
        )

        assert result is True

    def test_is_valid_relationship_no_match(self, service):
        """Test relationship with no valid combination."""
        source_types = {"Disease"}
        target_types = {"Medication"}
        valid_combinations = {
            "hasAttribute": [("DataEntity", "Attribute")],
        }

        result = service._is_valid_relationship(
            "hasAttribute", source_types, target_types, valid_combinations
        )

        assert result is False


class TestQuickOntologyCheck:
    """Tests for quick_ontology_check function."""

    @pytest.mark.asyncio
    async def test_quick_ontology_check(self):
        """Test quick ontology check function."""
        mock_backend = AsyncMock()
        mock_backend.query_raw = AsyncMock(return_value=[])

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import quick_ontology_check
            result = await quick_ontology_check(mock_backend)

        assert "quality_level" in result
        assert "overall_score" in result

    @pytest.mark.asyncio
    async def test_quick_ontology_check_with_data(self):
        """Test quick check with actual entities."""
        entities = [
            {"id": "e1", "name": "Test", "type": "Disease", "labels": ["Disease"], "properties": {}},
        ]

        mock_backend = AsyncMock()
        mock_backend.query_raw = AsyncMock(side_effect=[entities, []])

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import quick_ontology_check
            result = await quick_ontology_check(mock_backend)

        assert result["entity_count"] == 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_backend_error_handling(self):
        """Test handling of backend errors."""
        mock_backend = AsyncMock()
        mock_backend.query_raw = AsyncMock(side_effect=Exception("Connection failed"))

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            service = OntologyQualityService(kg_backend=mock_backend)
            report = await service.assess_ontology_quality()

        # Should handle error gracefully
        assert report.entity_count == 0

    @pytest.mark.asyncio
    async def test_empty_relationships(self):
        """Test with entities but no relationships."""
        mock_backend = AsyncMock()
        mock_backend.query_raw = AsyncMock(
            side_effect=[
                [{"id": "e1", "name": "Test", "type": "Concept", "labels": [], "properties": {}}],
                [],
            ]
        )

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            service = OntologyQualityService(kg_backend=mock_backend)
            report = await service.assess_ontology_quality()

        assert report.entity_count == 1
        assert report.relationship_count == 0

    @pytest.mark.asyncio
    async def test_entities_with_missing_fields(self):
        """Test handling entities with missing optional fields."""
        mock_backend = AsyncMock()
        mock_backend.query_raw = AsyncMock(
            side_effect=[
                [
                    {"id": "e1"},  # Minimal entity
                    {"id": "e2", "name": None, "type": None, "labels": None},  # Null fields
                ],
                [],
            ]
        )

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            service = OntologyQualityService(kg_backend=mock_backend)
            report = await service.assess_ontology_quality()

        # Should handle gracefully without crashing
        assert report.entity_count == 2

    @pytest.mark.asyncio
    async def test_large_entity_list(self):
        """Test with a larger number of entities."""
        mock_backend = AsyncMock()

        # Generate 100 entities
        entities = [
            {
                "id": f"e{i}",
                "name": f"Entity {i}",
                "type": "Concept",
                "labels": ["Concept"],
                "properties": {"name": f"Entity {i}"},
            }
            for i in range(100)
        ]

        mock_backend.query_raw = AsyncMock(side_effect=[entities, []])

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            service = OntologyQualityService(kg_backend=mock_backend)
            report = await service.assess_ontology_quality()

        assert report.entity_count == 100

    @pytest.mark.asyncio
    async def test_complex_relationship_graph(self):
        """Test with complex relationship structure."""
        mock_backend = AsyncMock()

        entities = [
            {"id": f"e{i}", "name": f"Entity {i}", "type": "Concept", "labels": ["Concept"], "properties": {}}
            for i in range(5)
        ]

        # Create relationships forming a tree
        relationships = [
            {"source_id": "e1", "target_id": "e0", "relationship_type": "IS_A", "source_labels": ["Concept"], "target_labels": ["Concept"]},
            {"source_id": "e2", "target_id": "e0", "relationship_type": "IS_A", "source_labels": ["Concept"], "target_labels": ["Concept"]},
            {"source_id": "e3", "target_id": "e1", "relationship_type": "IS_A", "source_labels": ["Concept"], "target_labels": ["Concept"]},
            {"source_id": "e4", "target_id": "e1", "relationship_type": "IS_A", "source_labels": ["Concept"], "target_labels": ["Concept"]},
        ]

        mock_backend.query_raw = AsyncMock(side_effect=[entities, relationships])

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            service = OntologyQualityService(kg_backend=mock_backend)
            report = await service.assess_ontology_quality()

        assert report.entity_count == 5
        assert report.relationship_count == 4


class TestStructuralEntityLabels:
    """Tests for structural entity label detection."""

    @pytest.fixture
    def service(self, ):
        mock_backend = AsyncMock()
        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            return OntologyQualityService(kg_backend=mock_backend)

    def test_conversation_session_is_structural(self, service):
        """ConversationSession label is treated as structural."""
        entity = {"labels": ["ConversationSession"], "exclude_from_ontology": False, "is_structural": False}
        assert service._is_structural_entity(entity) is True

    def test_message_is_structural(self, service):
        """Message label is treated as structural."""
        entity = {"labels": ["Message"], "exclude_from_ontology": False, "is_structural": False}
        assert service._is_structural_entity(entity) is True

    def test_disease_is_not_structural(self, service):
        """Disease label is NOT structural."""
        entity = {"labels": ["Disease"], "exclude_from_ontology": False, "is_structural": False}
        assert service._is_structural_entity(entity) is False


class TestCoverageReviewPending:
    """Tests for coverage assessment excluding _needs_review entities."""

    @pytest.fixture
    def service(self):
        mock_backend = AsyncMock()
        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            return OntologyQualityService(kg_backend=mock_backend)

    @pytest.mark.asyncio
    async def test_needs_review_excluded_from_unmapped_types(self, service):
        """Entities with _needs_review=true should NOT appear in unmapped_types."""
        entities = [
            {
                "id": "e1", "name": "Unknown Entity", "type": "Unknown",
                "labels": [], "properties": {"_needs_review": True, "_review_reason": "unknown_type"},
                "exclude_from_ontology": False, "is_structural": False, "is_noise": False,
            },
        ]
        score = await service._assess_coverage(entities)
        assert "Unknown" not in score.unmapped_types

    @pytest.mark.asyncio
    async def test_truly_unmapped_type_in_unmapped_types(self, service):
        """Entities without _needs_review should appear in unmapped_types."""
        entities = [
            {
                "id": "e1", "name": "New Thing", "type": "NewType",
                "labels": [], "properties": {},
                "exclude_from_ontology": False, "is_structural": False, "is_noise": False,
            },
        ]
        score = await service._assess_coverage(entities)
        assert "NewType" in score.unmapped_types

    @pytest.mark.asyncio
    async def test_review_pending_still_counts_as_unmapped_in_ratio(self, service):
        """Review-pending entities should count as unmapped (not inflate mapped count)."""
        entities = [
            {
                "id": "e1", "name": "Aspirin", "type": "Drug", "labels": ["Drug"],
                "properties": {}, "exclude_from_ontology": False, "is_structural": False, "is_noise": False,
            },
            {
                "id": "e2", "name": "Unknown Entity", "type": "Unknown", "labels": [],
                "properties": {"_needs_review": True},
                "exclude_from_ontology": False, "is_structural": False, "is_noise": False,
            },
        ]
        score = await service._assess_coverage(entities)
        assert score.mapped_entities == 1
        assert score.unmapped_entities == 1
        assert score.coverage_ratio == 0.5


class TestConsistencyCanonicalTypes:
    """Tests for consistency assessment with _canonical_type."""

    @pytest.fixture
    def service(self):
        mock_backend = AsyncMock()
        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            return OntologyQualityService(kg_backend=mock_backend)

    @pytest.mark.asyncio
    async def test_remediation_mapped_entity_grouped_by_canonical_type(self, service):
        """Entity with _canonical_type and no ODIN label is grouped by canonical type."""
        entities = [
            {
                "id": "e1", "name": "IL-6", "type": "Cytokine",
                "labels": [],
                "properties": {"_ontology_mapped": True, "_canonical_type": "protein"},
            },
        ]
        score = await service._assess_consistency(entities)
        assert score.total_types == 1
        assert score.consistent_types == 1

    @pytest.mark.asyncio
    async def test_same_raw_type_same_canonical_is_consistent(self, service):
        """All entities of same raw type with same _canonical_type are consistent."""
        entities = [
            {
                "id": "e1", "name": "IL-6", "type": "Cytokine", "labels": [],
                "properties": {"_ontology_mapped": True, "_canonical_type": "protein"},
            },
            {
                "id": "e2", "name": "TNF-alpha", "type": "Cytokine", "labels": [],
                "properties": {"_ontology_mapped": True, "_canonical_type": "protein"},
            },
        ]
        score = await service._assess_consistency(entities)
        assert score.total_types == 1
        assert score.consistent_types == 1
        assert score.inconsistent_types == 0

    @pytest.mark.asyncio
    async def test_same_raw_type_conflicting_canonical_is_inconsistent(self, service):
        """Entities of same raw type with different _canonical_type are inconsistent."""
        entities = [
            {
                "id": "e1", "name": "Mercury Metal", "type": "Mercury", "labels": [],
                "properties": {"_ontology_mapped": True, "_canonical_type": "chemical"},
            },
            {
                "id": "e2", "name": "Planet Mercury", "type": "Mercury", "labels": [],
                "properties": {"_ontology_mapped": True, "_canonical_type": "planet"},
            },
        ]
        score = await service._assess_consistency(entities)
        assert score.total_types == 1
        assert score.inconsistent_types == 1


class TestOrphanBreakdown:
    """Tests for taxonomy orphan breakdown by source."""

    @pytest.fixture
    def service(self):
        mock_backend = AsyncMock()
        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            return OntologyQualityService(kg_backend=mock_backend)

    @pytest.mark.asyncio
    async def test_orphan_breakdown_from_remediation_metadata(self, service):
        """When _is_orphan/_orphan_source metadata exists, use it for breakdown."""
        entities = [
            {
                "id": "e1", "name": "Episodic Node", "type": "EntityNode", "labels": [],
                "properties": {"_is_orphan": True, "_orphan_source": "episodic"},
                "exclude_from_ontology": False, "is_structural": False,
            },
            {
                "id": "e2", "name": "Knowledge Orphan", "type": "Disease", "labels": ["Disease"],
                "properties": {"_is_orphan": True, "_orphan_source": "knowledge"},
                "exclude_from_ontology": False, "is_structural": False,
            },
            {
                "id": "e3", "name": "Connected Node", "type": "Drug", "labels": ["Drug"],
                "properties": {"_is_orphan": False},
                "exclude_from_ontology": False, "is_structural": False,
            },
        ]
        relationships = [
            {"source_id": "e3", "target_id": "e2", "relationship_type": "TREATS",
             "source_labels": ["Drug"], "target_labels": ["Disease"]},
        ]
        score = await service._assess_taxonomy(entities, relationships)
        assert score.orphan_breakdown == {"episodic": 1, "knowledge": 1, "unclassified": 0}
        assert score.orphan_nodes == 2

    @pytest.mark.asyncio
    async def test_orphan_breakdown_fallback_no_metadata(self, service):
        """When no _is_orphan metadata exists and no relationships, early return with empty breakdown."""
        entities = [
            {"id": "e1", "name": "Orphan", "type": "Concept", "labels": [], "properties": {},
             "exclude_from_ontology": False, "is_structural": False},
        ]
        score = await service._assess_taxonomy(entities, [])
        # Early return when no relationships — orphan_breakdown stays default empty dict
        assert score.orphan_breakdown == {}
        assert score.orphan_nodes == 0

    @pytest.mark.asyncio
    async def test_orphan_breakdown_fallback_with_relationships(self, service):
        """Fallback computes orphans when relationships exist but no orphan metadata."""
        entities = [
            {"id": "e1", "name": "Connected", "type": "Disease", "labels": ["Disease"], "properties": {},
             "exclude_from_ontology": False, "is_structural": False},
            {"id": "e2", "name": "Orphan", "type": "Drug", "labels": ["Drug"], "properties": {},
             "exclude_from_ontology": False, "is_structural": False},
        ]
        relationships = [
            {"source_id": "e1", "target_id": "e3", "relationship_type": "TREATS",
             "source_labels": ["Disease"], "target_labels": ["Drug"]},
        ]
        score = await service._assess_taxonomy(entities, relationships)
        # e2 is not connected in any relationship, so it's an orphan
        assert score.orphan_breakdown == {"unclassified": 1}
        assert score.orphan_nodes == 1

    @pytest.mark.asyncio
    async def test_orphan_nodes_equals_breakdown_sum(self, service):
        """orphan_nodes must equal sum of orphan_breakdown values."""
        entities = [
            {
                "id": "e1", "name": "Ep", "type": "X", "labels": [],
                "properties": {"_is_orphan": True, "_orphan_source": "episodic"},
                "exclude_from_ontology": False, "is_structural": False,
            },
            {
                "id": "e2", "name": "Kn", "type": "Y", "labels": [],
                "properties": {"_is_orphan": True, "_orphan_source": "knowledge"},
                "exclude_from_ontology": False, "is_structural": False,
            },
            {
                "id": "e3", "name": "Un", "type": "Z", "labels": [],
                "properties": {"_is_orphan": True, "_orphan_source": "unclassified"},
                "exclude_from_ontology": False, "is_structural": False,
            },
        ]
        relationships = [
            {"source_id": "e1", "target_id": "e2", "relationship_type": "X",
             "source_labels": [], "target_labels": []},
        ]
        score = await service._assess_taxonomy(entities, relationships)
        assert score.orphan_nodes == sum(score.orphan_breakdown.values())


class TestContextAwareRecommendations:
    """Tests for context-aware recommendation generation."""

    def test_orphan_recommendation_uses_knowledge_count(self):
        """Orphan recommendation should use knowledge orphan count, not total."""
        from domain.ontology_quality_models import OntologyQualityReport
        report = OntologyQualityReport(assessment_id="test", ontology_name="ODIN")
        report.taxonomy.orphan_nodes = 4400
        report.taxonomy.orphan_breakdown = {"episodic": 4388, "knowledge": 12, "unclassified": 0}
        report.compute_overall_score()
        report.generate_recommendations()

        orphan_recs = [r for r in report.recommendations if "orphan" in r.lower()]
        assert len(orphan_recs) == 1
        assert "12" in orphan_recs[0]
        assert "knowledge" in orphan_recs[0]

    def test_no_orphan_recommendation_when_only_episodic(self):
        """No orphan recommendation when only episodic orphans exist."""
        from domain.ontology_quality_models import OntologyQualityReport
        report = OntologyQualityReport(assessment_id="test", ontology_name="ODIN")
        report.taxonomy.orphan_nodes = 4388
        report.taxonomy.orphan_breakdown = {"episodic": 4388, "knowledge": 0, "unclassified": 0}
        report.compute_overall_score()
        report.generate_recommendations()

        orphan_recs = [r for r in report.recommendations if "orphan" in r.lower()]
        assert len(orphan_recs) == 0

    def test_no_unmapped_types_recommendation_when_empty(self):
        """No 'Add ontology mappings' recommendation when unmapped_types is empty."""
        from domain.ontology_quality_models import OntologyQualityReport
        report = OntologyQualityReport(assessment_id="test", ontology_name="ODIN")
        report.coverage.unmapped_types = []
        report.compute_overall_score()
        report.generate_recommendations()

        mapping_recs = [r for r in report.recommendations if "Add ontology mappings" in r]
        assert len(mapping_recs) == 0


class TestQuickOntologyCheckEnriched:
    """Tests for enriched quick_ontology_check response."""

    @pytest.mark.asyncio
    async def test_quick_check_includes_knowledge_coverage(self):
        """Quick check response should include knowledge_coverage."""
        mock_backend = AsyncMock()
        mock_backend.query_raw = AsyncMock(return_value=[])

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import quick_ontology_check
            result = await quick_ontology_check(mock_backend)

        assert "knowledge_coverage" in result
        assert isinstance(result["knowledge_coverage"], float)

    @pytest.mark.asyncio
    async def test_quick_check_includes_orphan_breakdown(self):
        """Quick check response should include orphan_breakdown."""
        mock_backend = AsyncMock()
        mock_backend.query_raw = AsyncMock(return_value=[])

        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import quick_ontology_check
            result = await quick_ontology_check(mock_backend)

        assert "orphan_breakdown" in result
        assert isinstance(result["orphan_breakdown"], dict)


class TestNormalizationExcludesDismissedAndMerged:
    """Test that _assess_normalization skips dismissed and merged entities."""

    @pytest.fixture
    def service(self):
        with patch('application.services.ontology_quality_service.SemanticNormalizer', MockSemanticNormalizer):
            from application.services.ontology_quality_service import OntologyQualityService
            mock_backend = AsyncMock()
            svc = OntologyQualityService(mock_backend)
        return svc

    @pytest.mark.asyncio
    async def test_dismissed_entities_excluded_from_duplicate_count(self, service):
        """Entities with _dedup_skip=true are not counted as duplicates."""
        entities = [
            {"id": "e1", "name": "Aspirin", "type": "Drug", "labels": [], "properties": {}},
            {"id": "e2", "name": "aspirin", "type": "Drug", "labels": [], "properties": {"_dedup_skip": True}},
            {"id": "e3", "name": "Metformin", "type": "Drug", "labels": [], "properties": {}},
            {"id": "e4", "name": "metformin", "type": "Drug", "labels": [], "properties": {}},
        ]
        score = await service._assess_normalization(entities)
        # Aspirin group: only e1 (e2 is dismissed), so not a duplicate pair
        # Metformin group: e3 + e4, so 1 duplicate group
        assert score.deduplication_candidates == 1

    @pytest.mark.asyncio
    async def test_merged_entities_excluded_from_duplicate_count(self, service):
        """Entities with _merged_into set are not counted as duplicates."""
        entities = [
            {"id": "e1", "name": "Aspirin", "type": "Drug", "labels": [], "properties": {}},
            {"id": "e2", "name": "aspirin", "type": "Drug", "labels": [], "properties": {"_merged_into": "e1"}},
        ]
        score = await service._assess_normalization(entities)
        # Only e1 is counted; e2 is merged, so no duplicate group
        assert score.deduplication_candidates == 0

    @pytest.mark.asyncio
    async def test_no_flags_counts_all_duplicates(self, service):
        """Without flags, all duplicates are counted."""
        entities = [
            {"id": "e1", "name": "Aspirin", "type": "Drug", "labels": [], "properties": {}},
            {"id": "e2", "name": "aspirin", "type": "Drug", "labels": [], "properties": {}},
        ]
        score = await service._assess_normalization(entities)
        assert score.deduplication_candidates == 1
