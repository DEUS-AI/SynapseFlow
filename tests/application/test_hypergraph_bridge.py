"""Tests for Hypergraph Bridge Service.

Tests the neurosymbolic bridge layer between Document and Knowledge graphs.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from domain.hypergraph_models import (
    FactUnit,
    FactType,
    HyperEdge,
    EntityMention,
    ConfidenceScore,
    ConfidenceSource,
    CoOccurrenceContext,
    NeurosymbolicLink,
    BridgeStatistics,
)
from application.services.hypergraph_bridge_service import HypergraphBridgeService


class TestFactUnit:
    """Test FactUnit domain model."""

    def test_fact_unit_creation(self):
        """Test basic FactUnit creation."""
        fact = FactUnit(
            fact_type=FactType.TREATMENT,
            source_chunk_id="chunk_123",
            source_document_id="doc_456",
        )

        assert fact.id  # Should auto-generate
        assert fact.fact_type == FactType.TREATMENT
        assert fact.source_chunk_id == "chunk_123"
        assert len(fact.participants) == 0

    def test_add_participant(self):
        """Test adding participants to a fact."""
        fact = FactUnit(fact_type=FactType.ASSOCIATION)

        mention1 = EntityMention(
            entity_id="e1",
            entity_name="Metformin",
            entity_type="Drug",
            chunk_id="c1",
        )
        mention2 = EntityMention(
            entity_id="e2",
            entity_name="Diabetes",
            entity_type="Disease",
            chunk_id="c1",
        )

        fact.add_participant(mention1, role="treatment")
        fact.add_participant(mention2, role="condition")

        assert len(fact.participants) == 2
        assert fact.participant_roles["e1"] == "treatment"
        assert fact.participant_roles["e2"] == "condition"

    def test_confidence_aggregation(self):
        """Test multi-source confidence aggregation."""
        fact = FactUnit(fact_type=FactType.CAUSATION)

        # Add multiple confidence sources
        fact.add_confidence(ConfidenceScore(
            value=0.8,
            source=ConfidenceSource.EXTRACTION_MODEL,
        ))
        fact.add_confidence(ConfidenceScore(
            value=0.9,
            source=ConfidenceSource.ONTOLOGY_MATCH,
        ))
        fact.add_confidence(ConfidenceScore(
            value=0.7,
            source=ConfidenceSource.CO_OCCURRENCE,
        ))

        # Aggregate should be weighted average
        assert 0.7 < fact.aggregate_confidence < 0.9
        assert len(fact.confidence_scores) == 3

    def test_get_entity_pairs(self):
        """Test getting entity pairs for relationship extraction."""
        fact = FactUnit(fact_type=FactType.ASSOCIATION)

        for i in range(4):
            fact.add_participant(EntityMention(
                entity_id=f"e{i}",
                entity_name=f"Entity{i}",
                entity_type="Concept",
                chunk_id="c1",
            ))

        pairs = fact.get_entity_pairs()

        # 4 entities = 6 pairs (4 choose 2)
        assert len(pairs) == 6

    def test_to_neo4j_properties(self):
        """Test conversion to Neo4j properties."""
        fact = FactUnit(
            fact_type=FactType.TREATMENT,
            source_chunk_id="chunk_123",
            fact_text="Metformin treats diabetes effectively",
        )
        fact.add_confidence(ConfidenceScore(
            value=0.85,
            source=ConfidenceSource.EXTRACTION_MODEL,
        ))

        props = fact.to_neo4j_properties()

        assert props["fact_type"] == "treatment"
        assert props["source_chunk_id"] == "chunk_123"
        assert props["aggregate_confidence"] == 0.85
        assert "id" in props


class TestCoOccurrenceContext:
    """Test CoOccurrenceContext model."""

    def test_context_analysis(self):
        """Test co-occurrence context analysis."""
        context = CoOccurrenceContext(
            chunk_id="c1",
            document_id="d1",
            entities=[
                EntityMention(
                    entity_id="e1",
                    entity_name="Drug1",
                    entity_type="Drug",
                    chunk_id="c1",
                    extraction_confidence=0.8,
                ),
                EntityMention(
                    entity_id="e2",
                    entity_name="Disease1",
                    entity_type="Disease",
                    chunk_id="c1",
                    extraction_confidence=0.9,
                ),
            ],
            chunk_text="Drug1 is used to treat Disease1",
        )

        context.analyze()

        assert context.entity_count == 2
        assert context.type_diversity == 2
        assert context.avg_extraction_confidence == pytest.approx(0.85)
        assert context.is_fact_candidate is True

    def test_context_not_fact_candidate(self):
        """Test context with insufficient entities."""
        context = CoOccurrenceContext(
            chunk_id="c1",
            document_id="d1",
            entities=[
                EntityMention(
                    entity_id="e1",
                    entity_name="Entity1",
                    entity_type="Concept",
                    chunk_id="c1",
                    extraction_confidence=0.3,  # Low confidence
                ),
            ],
        )

        context.analyze()

        assert context.is_fact_candidate is False

    def test_context_to_fact_unit(self):
        """Test conversion from context to FactUnit."""
        context = CoOccurrenceContext(
            chunk_id="c1",
            document_id="d1",
            entities=[
                EntityMention(
                    entity_id="e1",
                    entity_name="Drug1",
                    entity_type="Drug",
                    chunk_id="c1",
                    extraction_confidence=0.8,
                ),
                EntityMention(
                    entity_id="e2",
                    entity_name="Disease1",
                    entity_type="Disease",
                    chunk_id="c1",
                    extraction_confidence=0.9,
                ),
            ],
            chunk_text="Drug1 treats Disease1",
        )

        context.analyze()
        fact = context.to_fact_unit()

        assert fact is not None
        assert len(fact.participants) == 2
        assert fact.source_chunk_id == "c1"
        assert len(fact.confidence_scores) == 1


class TestEntityMention:
    """Test EntityMention model."""

    def test_entity_mention_creation(self):
        """Test basic entity mention creation."""
        mention = EntityMention(
            entity_id="e123",
            entity_name="Aspirin",
            entity_type="Drug",
            chunk_id="c456",
            position_start=10,
            position_end=17,
            extraction_confidence=0.95,
        )

        assert mention.entity_id == "e123"
        assert mention.entity_name == "Aspirin"
        assert mention.entity_type == "Drug"
        assert mention.extraction_confidence == 0.95

    def test_entity_mention_to_dict(self):
        """Test serialization."""
        mention = EntityMention(
            entity_id="e1",
            entity_name="Test",
            entity_type="Concept",
            chunk_id="c1",
        )

        data = mention.to_dict()

        assert data["entity_id"] == "e1"
        assert data["entity_name"] == "Test"
        assert "embedding" not in data  # Should not include embedding


class TestNeurosymbolicLink:
    """Test NeurosymbolicLink model."""

    def test_link_creation(self):
        """Test neurosymbolic link creation."""
        link = NeurosymbolicLink(
            entity_id="e1",
            entity_name="Diabetes",
            ontology_class="Disease",
            ontology_domain="medical",
            dikw_layer="SEMANTIC",
            external_ids={"ICD10": "E11", "SNOMED": "73211009"},
            embedding_ontology_alignment=0.85,
        )

        assert link.ontology_class == "Disease"
        assert link.external_ids["ICD10"] == "E11"
        assert link.embedding_ontology_alignment == 0.85


class TestBridgeStatistics:
    """Test BridgeStatistics model."""

    def test_statistics_creation(self):
        """Test bridge statistics creation."""
        stats = BridgeStatistics(
            total_fact_units=100,
            total_hyperedges=250,
            entities_with_facts=80,
            avg_fact_confidence=0.75,
            facts_by_type={"treatment": 40, "association": 60},
        )

        data = stats.to_dict()

        assert data["total_fact_units"] == 100
        assert data["total_hyperedges"] == 250
        assert data["avg_fact_confidence"] == 0.75
        assert data["facts_by_type"]["treatment"] == 40


class TestHypergraphBridgeService:
    """Test HypergraphBridgeService."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock Neo4j backend."""
        backend = AsyncMock()
        backend.query_raw = AsyncMock()
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create service with mock backend."""
        return HypergraphBridgeService(mock_backend)

    @pytest.mark.asyncio
    async def test_build_bridge_layer(self, service, mock_backend):
        """Test building bridge layer from co-occurrences."""
        # Mock co-occurrence query
        mock_backend.query_raw.side_effect = [
            # get_co_occurrences
            [
                {
                    "chunk_id": "c1",
                    "document_id": "d1",
                    "chunk_text": "Metformin treats diabetes",
                    "entities": [
                        {"id": "e1", "name": "Metformin", "type": "Drug", "confidence": 0.9},
                        {"id": "e2", "name": "Diabetes", "type": "Disease", "confidence": 0.85},
                    ],
                },
                {
                    "chunk_id": "c2",
                    "document_id": "d1",
                    "chunk_text": "Aspirin reduces inflammation",
                    "entities": [
                        {"id": "e3", "name": "Aspirin", "type": "Drug", "confidence": 0.8},
                        {"id": "e4", "name": "Inflammation", "type": "Condition", "confidence": 0.75},
                    ],
                },
            ],
            # create_fact_unit (first)
            [{"f": {}}],
            # create_participation (first fact, participant 1)
            [{"r": {}}],
            # create_participation (first fact, participant 2)
            [{"r": {}}],
            # create_fact_unit (second)
            [{"f": {}}],
            # create_participation (second fact, participant 1)
            [{"r": {}}],
            # create_participation (second fact, participant 2)
            [{"r": {}}],
            # enrich_with_ontology
            [
                {"name": "Metformin", "labels": ["Drug"], "type": "Drug"},
                {"name": "Diabetes", "labels": ["Disease"], "type": "Disease"},
            ],
            # get_database_statistics
            [{"fact_count": 2, "edge_count": 4, "entities_with_facts": 4, "avg_confidence": 0.82}],
        ]

        stats = await service.build_bridge_layer(limit=100)

        assert stats.total_fact_units == 2
        assert stats.total_hyperedges == 4
        assert stats.entities_with_facts == 4

    @pytest.mark.asyncio
    async def test_get_facts_for_entity(self, service, mock_backend):
        """Test getting facts for an entity."""
        mock_backend.query_raw.return_value = [
            {
                "fact": {
                    "id": "f1",
                    "fact_type": "treatment",
                    "fact_text": "Metformin treats diabetes",
                    "aggregate_confidence": 0.85,
                    "source_chunk_id": "c1",
                },
                "co_participants": [
                    {"id": "e2", "name": "Diabetes", "type": "Disease"},
                ],
            },
        ]

        facts = await service.get_facts_for_entity("Metformin")

        assert len(facts) == 1
        assert facts[0]["fact_type"] == "treatment"
        assert facts[0]["confidence"] == 0.85
        assert len(facts[0]["co_participants"]) == 1

    @pytest.mark.asyncio
    async def test_propagate_to_knowledge_graph(self, service, mock_backend):
        """Test propagating facts to KG relationships."""
        mock_backend.query_raw.return_value = [{"created_relationships": 5}]

        created = await service.propagate_to_knowledge_graph(confidence_threshold=0.7)

        assert created == 5
        mock_backend.query_raw.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_fact_chains(self, service, mock_backend):
        """Test finding fact chains."""
        mock_backend.query_raw.return_value = [
            {
                "source": "DrugA",
                "bridge_entity": "Pathway1",
                "target": "DiseaseB",
                "fact1_type": "affects",
                "fact2_type": "causes",
                "chain_confidence": 0.75,
            },
        ]

        chains = await service.find_fact_chains("DrugA")

        assert len(chains) == 1
        assert chains[0]["bridge"] == "Pathway1"
        assert chains[0]["chain_confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_validate_fact(self, service, mock_backend):
        """Test fact validation."""
        mock_backend.query_raw.return_value = [{"f": {"id": "f1", "validated": True}}]

        result = await service.validate_fact("f1", validated=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_cleanup_low_confidence(self, service, mock_backend):
        """Test cleanup of low-confidence facts."""
        mock_backend.query_raw.return_value = [{"deleted": 10}]

        deleted = await service.cleanup_low_confidence_facts(threshold=0.3)

        assert deleted == 10

    @pytest.mark.asyncio
    async def test_get_bridge_report(self, service, mock_backend):
        """Test bridge report generation."""
        mock_backend.query_raw.side_effect = [
            # get_database_statistics
            [{"fact_count": 50, "edge_count": 120, "entities_with_facts": 40, "avg_confidence": 0.72}],
            # fact type distribution
            [
                {"type": "association", "count": 30},
                {"type": "treatment", "count": 20},
            ],
            # confidence distribution
            [
                {"confidence_level": "high", "count": 15},
                {"confidence_level": "medium", "count": 25},
                {"confidence_level": "low", "count": 10},
            ],
        ]

        report = await service.get_bridge_report()

        assert report["statistics"]["total_fact_units"] == 50
        assert report["statistics"]["total_hyperedges"] == 120
        assert report["facts_by_type"]["association"] == 30
        assert report["confidence_distribution"]["high"] == 15
        assert len(report["recommendations"]) >= 1


class TestIntegration:
    """Integration tests for hypergraph models."""

    def test_full_fact_creation_pipeline(self):
        """Test complete fact creation from co-occurrence."""
        # Create context
        context = CoOccurrenceContext(
            chunk_id="chunk_test",
            document_id="doc_test",
            entities=[
                EntityMention(
                    entity_id="drug_1",
                    entity_name="Metformin",
                    entity_type="Drug",
                    chunk_id="chunk_test",
                    extraction_confidence=0.9,
                ),
                EntityMention(
                    entity_id="disease_1",
                    entity_name="Type 2 Diabetes",
                    entity_type="Disease",
                    chunk_id="chunk_test",
                    extraction_confidence=0.85,
                ),
                EntityMention(
                    entity_id="condition_1",
                    entity_name="Obesity",
                    entity_type="Condition",
                    chunk_id="chunk_test",
                    extraction_confidence=0.8,
                ),
            ],
            chunk_text="Metformin is commonly prescribed for Type 2 Diabetes patients with Obesity",
        )

        # Analyze and convert
        context.analyze()
        fact = context.to_fact_unit()

        # Verify
        assert fact is not None
        assert len(fact.participants) == 3
        assert fact.aggregate_confidence > 0.5
        assert fact.fact_type in FactType

        # Test entity pairs
        pairs = fact.get_entity_pairs()
        assert len(pairs) == 3  # 3 choose 2

        # Test Neo4j conversion
        props = fact.to_neo4j_properties()
        assert "id" in props
        assert props["participant_count"] == 3

    def test_confidence_propagation(self):
        """Test confidence propagation through sources."""
        fact = FactUnit(fact_type=FactType.TREATMENT)

        # Add multiple evidence sources
        fact.add_confidence(ConfidenceScore(
            value=0.6,
            source=ConfidenceSource.CO_OCCURRENCE,
            evidence="Entities appear in same chunk",
        ))

        assert fact.aggregate_confidence == pytest.approx(0.6, rel=0.01)

        fact.add_confidence(ConfidenceScore(
            value=0.9,
            source=ConfidenceSource.ONTOLOGY_MATCH,
            evidence="Drug-Disease relationship in ontology",
        ))

        # With ontology match, confidence should increase
        assert fact.aggregate_confidence > 0.6

        fact.add_confidence(ConfidenceScore(
            value=1.0,
            source=ConfidenceSource.USER_VALIDATION,
            evidence="User confirmed relationship",
        ))

        # With user validation, confidence should be high
        assert fact.aggregate_confidence > 0.8
