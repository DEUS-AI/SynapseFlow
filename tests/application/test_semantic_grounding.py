"""Unit tests for SemanticGroundingService."""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from application.services.semantic_grounding import (
    SemanticGroundingService,
    GroundedEntity,
    HybridSearchResult
)


# Check if sentence-transformers is available
try:
    import sentence_transformers
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


@pytest.fixture
def mock_backend():
    """Create mock knowledge graph backend."""
    backend = AsyncMock()
    backend.query = AsyncMock(return_value=[])
    return backend


@pytest.fixture
def grounding_service(mock_backend):
    """Create SemanticGroundingService with mock backend."""
    return SemanticGroundingService(
        backend=mock_backend,
        vector_weight=0.7,
        graph_weight=0.3
    )


@pytest.fixture
def sample_entity():
    """Sample entity data."""
    return {
        "id": "concept:customer",
        "name": "Customer",
        "type": "BusinessConcept",
        "description": "Individual or organization that purchases products",
        "domain": "sales"
    }


@pytest.fixture
def sample_entities():
    """Sample entities for candidate search."""
    return [
        {
            "id": "concept:customer",
            "name": "Customer",
            "type": "BusinessConcept"
        },
        {
            "id": "concept:product",
            "name": "Product",
            "type": "BusinessConcept"
        },
        {
            "id": "concept:order",
            "name": "Order",
            "type": "BusinessConcept"
        }
    ]


class TestGroundedEntity:
    """Test GroundedEntity dataclass."""

    def test_grounded_entity_creation(self):
        """Test creating a grounded entity."""
        entity = GroundedEntity(
            entity_id="concept:customer",
            entity_name="Customer",
            entity_type="BusinessConcept",
            embedding=np.array([0.1, 0.2, 0.3]),
            properties={"domain": "sales"},
            neighbors=["concept:order", "concept:product"]
        )

        assert entity.entity_id == "concept:customer"
        assert entity.entity_name == "Customer"
        assert entity.entity_type == "BusinessConcept"
        assert entity.embedding is not None
        assert entity.properties["domain"] == "sales"
        assert len(entity.neighbors) == 2

    def test_grounded_entity_defaults(self):
        """Test grounded entity with default values."""
        entity = GroundedEntity(
            entity_id="test",
            entity_name="Test",
            entity_type="TestType"
        )

        assert entity.embedding is None
        assert entity.properties == {}
        assert entity.neighbors == []


class TestHybridSearchResult:
    """Test HybridSearchResult dataclass."""

    def test_hybrid_search_result_creation(self):
        """Test creating a hybrid search result."""
        result = HybridSearchResult(
            entity_id="concept:customer",
            entity_name="Customer",
            vector_score=0.85,
            graph_score=0.60,
            combined_score=0.78,
            properties={"domain": "sales"},
            explanation="High semantic similarity"
        )

        assert result.entity_id == "concept:customer"
        assert result.vector_score == 0.85
        assert result.graph_score == 0.60
        assert result.combined_score == 0.78
        assert "semantic" in result.explanation.lower()


class TestServiceInitialization:
    """Test service initialization and configuration."""

    def test_default_initialization(self, mock_backend):
        """Test default service initialization."""
        service = SemanticGroundingService(backend=mock_backend)

        assert service.backend == mock_backend
        assert service.vector_weight == 0.7
        assert service.graph_weight == 0.3
        assert service._embedding_model_name == "all-MiniLM-L6-v2"
        assert service._embedding_model is None  # Lazy loaded

    def test_custom_weights(self, mock_backend):
        """Test custom weight configuration."""
        service = SemanticGroundingService(
            backend=mock_backend,
            vector_weight=0.8,
            graph_weight=0.2
        )

        assert service.vector_weight == 0.8
        assert service.graph_weight == 0.2

    def test_custom_embedding_model(self, mock_backend):
        """Test custom embedding model configuration."""
        service = SemanticGroundingService(
            backend=mock_backend,
            embedding_model="all-mpnet-base-v2"
        )

        assert service._embedding_model_name == "all-mpnet-base-v2"


class TestEmbeddingGeneration:
    """Test embedding generation."""

    @pytest.mark.skipif(not SENTENCE_TRANSFORMERS_AVAILABLE, reason="sentence-transformers not installed")
    def test_generate_entity_embedding_with_model(self, grounding_service):
        """Test generating embedding when model is available."""
        # Mock the embedding model
        mock_model = MagicMock()
        mock_model.encode.return_value = [np.array([0.1, 0.2, 0.3])]
        grounding_service._embedding_model = mock_model

        embedding = grounding_service.generate_entity_embedding(
            "Customer",
            {"description": "A person who buys products"}
        )

        assert embedding is not None
        assert isinstance(embedding, np.ndarray)
        mock_model.encode.assert_called_once()

    def test_generate_entity_embedding_without_model(self, grounding_service):
        """Test generating embedding when model is not available."""
        grounding_service._embedding_model = None

        embedding = grounding_service.generate_entity_embedding("Customer")

        assert embedding is None

    @pytest.mark.skipif(not SENTENCE_TRANSFORMERS_AVAILABLE, reason="sentence-transformers not installed")
    def test_generate_embedding_combines_properties(self, grounding_service):
        """Test that embedding generation combines name and properties."""
        mock_model = MagicMock()
        mock_model.encode.return_value = [np.array([0.1, 0.2, 0.3])]
        grounding_service._embedding_model = mock_model

        properties = {
            "description": "A buyer",
            "domain": "sales",
            "id": "concept:customer",  # Should be excluded
            "custom_field": "value"
        }

        grounding_service.generate_entity_embedding("Customer", properties)

        # Verify the text includes name, description, and custom fields
        call_args = mock_model.encode.call_args[0][0][0]
        assert "Customer" in call_args
        assert "buyer" in call_args.lower()
        assert "sales" in call_args or "domain: sales" in call_args


class TestEntityGrounding:
    """Test entity grounding functionality."""

    @pytest.mark.asyncio
    async def test_ground_entity_found(self, grounding_service, mock_backend, sample_entity):
        """Test grounding an entity that exists."""
        mock_backend.query.return_value = [
            {"e": sample_entity, "neighbors": ["concept:order", "concept:product"]}
        ]

        # Mock embedding generation
        mock_model = MagicMock()
        mock_model.encode.return_value = [np.array([0.1, 0.2, 0.3])]
        grounding_service._embedding_model = mock_model

        grounded = await grounding_service.ground_entity("concept:customer")

        assert grounded is not None
        assert grounded.entity_id == "concept:customer"
        assert grounded.entity_name == "Customer"
        assert grounded.entity_type == "BusinessConcept"
        assert len(grounded.neighbors) == 2

    @pytest.mark.asyncio
    async def test_ground_entity_not_found(self, grounding_service, mock_backend):
        """Test grounding a non-existent entity."""
        mock_backend.query.return_value = []

        grounded = await grounding_service.ground_entity("concept:nonexistent")

        assert grounded is None

    @pytest.mark.asyncio
    async def test_ground_entity_uses_cache(self, grounding_service, mock_backend, sample_entity):
        """Test that grounding uses embedding cache."""
        mock_backend.query.return_value = [
            {"e": sample_entity, "neighbors": []}
        ]

        # Pre-populate cache
        fake_embedding = np.array([0.1, 0.2, 0.3])
        grounding_service._embedding_cache["concept:customer"] = fake_embedding

        grounded = await grounding_service.ground_entity("concept:customer")

        assert grounded is not None
        assert np.array_equal(grounded.embedding, fake_embedding)

    @pytest.mark.asyncio
    async def test_ground_entity_force_recompute(self, grounding_service, mock_backend, sample_entity):
        """Test force recomputing embedding."""
        mock_backend.query.return_value = [
            {"e": sample_entity, "neighbors": []}
        ]

        # Pre-populate cache
        old_embedding = np.array([0.1, 0.2, 0.3])
        grounding_service._embedding_cache["concept:customer"] = old_embedding

        # Mock new embedding
        mock_model = MagicMock()
        new_embedding = np.array([0.4, 0.5, 0.6])
        mock_model.encode.return_value = [new_embedding]
        grounding_service._embedding_model = mock_model

        grounded = await grounding_service.ground_entity(
            "concept:customer",
            force_recompute=True
        )

        assert grounded is not None
        assert np.array_equal(grounded.embedding, new_embedding)
        assert not np.array_equal(grounded.embedding, old_embedding)

    @pytest.mark.asyncio
    async def test_ground_entity_error_handling(self, grounding_service, mock_backend):
        """Test error handling during grounding."""
        mock_backend.query.side_effect = Exception("Database error")

        grounded = await grounding_service.ground_entity("concept:customer")

        assert grounded is None


class TestHybridSearch:
    """Test hybrid search functionality."""

    @pytest.mark.asyncio
    async def test_hybrid_search_with_embeddings(self, grounding_service, mock_backend, sample_entities):
        """Test hybrid search when embeddings are available."""
        # Mock get_candidate_entities
        mock_backend.query.return_value = sample_entities

        # Mock embedding model
        mock_model = MagicMock()
        mock_model.encode.return_value = [np.array([0.1, 0.2, 0.3])]
        grounding_service._embedding_model = mock_model

        # Mock grounding for each candidate
        with patch.object(grounding_service, 'ground_entity') as mock_ground:
            # Return grounded entities with embeddings
            mock_ground.side_effect = [
                GroundedEntity(
                    entity_id=e["id"],
                    entity_name=e["name"],
                    entity_type=e["type"],
                    embedding=np.array([0.15, 0.25, 0.35]),
                    neighbors=["other1", "other2"]
                )
                for e in sample_entities
            ]

            # Mock cosine similarity
            with patch('sklearn.metrics.pairwise.cosine_similarity') as mock_cosine:
                mock_cosine.return_value = [[0.85]]

                results = await grounding_service.hybrid_search(
                    "customer information",
                    entity_type="BusinessConcept",
                    top_k=5
                )

                assert len(results) <= 5
                for result in results:
                    assert isinstance(result, HybridSearchResult)
                    assert result.combined_score >= 0.3  # min threshold

    @pytest.mark.asyncio
    async def test_hybrid_search_fallback(self, grounding_service, mock_backend, sample_entities):
        """Test fallback to name-based search when embeddings unavailable."""
        grounding_service._embedding_model = None

        # Mock fallback search
        mock_backend.query.return_value = [
            {"id": "concept:customer", "name": "Customer", "properties": {"domain": "sales"}}
        ]

        results = await grounding_service.hybrid_search(
            "customer",
            entity_type="BusinessConcept"
        )

        assert len(results) > 0
        assert results[0].entity_name == "Customer"
        assert results[0].vector_score == 0.0  # Fallback doesn't use vectors
        assert results[0].graph_score > 0

    @pytest.mark.asyncio
    async def test_hybrid_search_no_candidates(self, grounding_service, mock_backend):
        """Test hybrid search with no candidate entities."""
        mock_backend.query.return_value = []

        mock_model = MagicMock()
        grounding_service._embedding_model = mock_model

        results = await grounding_service.hybrid_search("test query")

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_hybrid_search_respects_top_k(self, grounding_service, mock_backend):
        """Test hybrid search respects top_k parameter."""
        # Return many candidates
        candidates = [
            {"id": f"concept:{i}", "name": f"Concept{i}", "type": "BusinessConcept"}
            for i in range(20)
        ]
        mock_backend.query.return_value = candidates

        mock_model = MagicMock()
        mock_model.encode.return_value = [np.array([0.1, 0.2, 0.3])]
        grounding_service._embedding_model = mock_model

        with patch.object(grounding_service, 'ground_entity') as mock_ground:
            mock_ground.side_effect = [
                GroundedEntity(
                    entity_id=c["id"],
                    entity_name=c["name"],
                    entity_type=c["type"],
                    embedding=np.array([0.1, 0.2, 0.3]),
                    neighbors=[]
                )
                for c in candidates
            ]

            with patch('sklearn.metrics.pairwise.cosine_similarity') as mock_cosine:
                mock_cosine.return_value = [[0.9]]

                results = await grounding_service.hybrid_search(
                    "query",
                    top_k=3
                )

                assert len(results) == 3

    @pytest.mark.asyncio
    async def test_hybrid_search_min_score_threshold(self, grounding_service, mock_backend, sample_entities):
        """Test hybrid search filters by minimum combined score."""
        mock_backend.query.return_value = sample_entities

        mock_model = MagicMock()
        mock_model.encode.return_value = [np.array([0.1, 0.2, 0.3])]
        grounding_service._embedding_model = mock_model

        with patch.object(grounding_service, 'ground_entity') as mock_ground:
            mock_ground.side_effect = [
                GroundedEntity(
                    entity_id=e["id"],
                    entity_name=e["name"],
                    entity_type=e["type"],
                    embedding=np.array([0.1, 0.2, 0.3]),
                    neighbors=[]
                )
                for e in sample_entities
            ]

            with patch('sklearn.metrics.pairwise.cosine_similarity') as mock_cosine:
                # Return very low similarity
                mock_cosine.return_value = [[0.1]]

                results = await grounding_service.hybrid_search(
                    "query",
                    min_combined_score=0.5
                )

                # All results should be filtered out (combined score too low)
                assert len(results) == 0


class TestSimilarEntityFinding:
    """Test finding similar entities."""

    @pytest.mark.asyncio
    async def test_find_similar_entities(self, grounding_service, mock_backend, sample_entities):
        """Test finding entities similar to a reference entity."""
        # Mock grounding the reference entity
        reference_embedding = np.array([0.1, 0.2, 0.3])

        with patch.object(grounding_service, 'ground_entity') as mock_ground:
            # Reference entity
            mock_ground.return_value = GroundedEntity(
                entity_id="concept:customer",
                entity_name="Customer",
                entity_type="BusinessConcept",
                embedding=reference_embedding,
                neighbors=[]
            )

            # Mock candidate retrieval
            mock_backend.query.return_value = sample_entities

            # Mock grounding candidates
            async def ground_side_effect(entity_id, *args, **kwargs):
                if entity_id == "concept:customer":
                    return GroundedEntity(
                        entity_id="concept:customer",
                        entity_name="Customer",
                        entity_type="BusinessConcept",
                        embedding=reference_embedding,
                        neighbors=[]
                    )
                return GroundedEntity(
                    entity_id=entity_id,
                    entity_name=entity_id.split(":")[-1],
                    entity_type="BusinessConcept",
                    embedding=np.array([0.15, 0.25, 0.35]),
                    neighbors=[]
                )

            mock_ground.side_effect = ground_side_effect

            # Mock cosine similarity
            with patch.object(grounding_service, '_cosine_similarity') as mock_cosine:
                mock_cosine.return_value = 0.85

                similar = await grounding_service.find_similar_entities(
                    "concept:customer",
                    top_k=2,
                    similarity_threshold=0.7
                )

                assert len(similar) <= 2
                for entity_id, score in similar:
                    assert entity_id != "concept:customer"  # Excludes self
                    assert score >= 0.7

    @pytest.mark.asyncio
    async def test_find_similar_no_embedding(self, grounding_service, mock_backend):
        """Test finding similar entities when reference has no embedding."""
        with patch.object(grounding_service, 'ground_entity') as mock_ground:
            mock_ground.return_value = GroundedEntity(
                entity_id="concept:customer",
                entity_name="Customer",
                entity_type="BusinessConcept",
                embedding=None,  # No embedding
                neighbors=[]
            )

            similar = await grounding_service.find_similar_entities("concept:customer")

            assert len(similar) == 0

    @pytest.mark.asyncio
    async def test_find_similar_entity_not_found(self, grounding_service, mock_backend):
        """Test finding similar entities when reference doesn't exist."""
        with patch.object(grounding_service, 'ground_entity') as mock_ground:
            mock_ground.return_value = None

            similar = await grounding_service.find_similar_entities("concept:nonexistent")

            assert len(similar) == 0


class TestGraphScoreComputation:
    """Test graph-based scoring."""

    def test_compute_graph_score_well_connected(self, grounding_service):
        """Test graph score for well-connected entity."""
        entity = GroundedEntity(
            entity_id="concept:customer",
            entity_name="Customer",
            entity_type="BusinessConcept",
            neighbors=["concept:" + str(i) for i in range(8)],  # 8 neighbors
            properties={"desc": "test", "domain": "sales", "category": "entity"}
        )

        score = grounding_service._compute_graph_score(entity)

        # High connectivity (0.8 * 0.4) + property richness (0.6 * 0.3) + type (1.0 * 0.3)
        # = 0.32 + 0.18 + 0.3 = 0.8
        assert score > 0.7

    def test_compute_graph_score_isolated(self, grounding_service):
        """Test graph score for isolated entity."""
        entity = GroundedEntity(
            entity_id="concept:isolated",
            entity_name="Isolated",
            entity_type="Column",  # Lower type score
            neighbors=[],  # No connections
            properties={}  # No properties
        )

        score = grounding_service._compute_graph_score(entity)

        # Only type score: 0.4 * 0.3 = 0.12
        assert score < 0.3

    def test_compute_graph_score_semantic_layer(self, grounding_service):
        """Test graph score prioritizes semantic layer entities."""
        business_concept = GroundedEntity(
            entity_id="concept:bc",
            entity_name="BusinessConcept",
            entity_type="BusinessConcept",
            neighbors=[],
            properties={}
        )

        column = GroundedEntity(
            entity_id="column:col",
            entity_name="Column",
            entity_type="Column",
            neighbors=[],
            properties={}
        )

        bc_score = grounding_service._compute_graph_score(business_concept)
        col_score = grounding_service._compute_graph_score(column)

        # BusinessConcept should have higher score due to type
        assert bc_score > col_score


class TestExplanationGeneration:
    """Test explanation generation."""

    def test_generate_explanation_high_vector(self, grounding_service):
        """Test explanation for high vector similarity."""
        entity = GroundedEntity(
            entity_id="test",
            entity_name="Test",
            entity_type="BusinessConcept",
            neighbors=[]
        )

        explanation = grounding_service._generate_explanation(0.85, 0.5, entity)

        assert "high semantic similarity" in explanation.lower()

    def test_generate_explanation_well_connected(self, grounding_service):
        """Test explanation for well-connected entity."""
        entity = GroundedEntity(
            entity_id="test",
            entity_name="Test",
            entity_type="BusinessConcept",
            neighbors=["n1", "n2", "n3", "n4", "n5"]
        )

        explanation = grounding_service._generate_explanation(0.6, 0.8, entity)

        assert "well-connected" in explanation.lower()
        assert "5 neighbors" in explanation.lower()

    def test_generate_explanation_low_confidence(self, grounding_service):
        """Test explanation for low confidence match."""
        entity = GroundedEntity(
            entity_id="test",
            entity_name="Test",
            entity_type="BusinessConcept",
            neighbors=[]
        )

        explanation = grounding_service._generate_explanation(0.3, 0.2, entity)

        assert "low confidence" in explanation.lower()


class TestCacheManagement:
    """Test embedding cache management."""

    def test_clear_cache(self, grounding_service):
        """Test clearing embedding cache."""
        # Populate cache
        grounding_service._embedding_cache["id1"] = np.array([0.1, 0.2])
        grounding_service._embedding_cache["id2"] = np.array([0.3, 0.4])

        assert len(grounding_service._embedding_cache) == 2

        grounding_service.clear_cache()

        assert len(grounding_service._embedding_cache) == 0

    def test_get_cache_size(self, grounding_service):
        """Test getting cache size."""
        assert grounding_service.get_cache_size() == 0

        grounding_service._embedding_cache["id1"] = np.array([0.1, 0.2])
        grounding_service._embedding_cache["id2"] = np.array([0.3, 0.4])

        assert grounding_service.get_cache_size() == 2


class TestCosineSimilarity:
    """Test cosine similarity computation."""

    def test_cosine_similarity_identical(self, grounding_service):
        """Test cosine similarity of identical vectors."""
        vec = np.array([0.5, 0.5, 0.5])

        similarity = grounding_service._cosine_similarity(vec, vec)

        assert abs(similarity - 1.0) < 0.01

    def test_cosine_similarity_orthogonal(self, grounding_service):
        """Test cosine similarity of orthogonal vectors."""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])

        similarity = grounding_service._cosine_similarity(vec1, vec2)

        assert abs(similarity - 0.0) < 0.01

    def test_cosine_similarity_opposite(self, grounding_service):
        """Test cosine similarity of opposite vectors."""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([-1.0, 0.0, 0.0])

        similarity = grounding_service._cosine_similarity(vec1, vec2)

        assert abs(similarity - (-1.0)) < 0.01
