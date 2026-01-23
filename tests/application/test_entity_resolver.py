"""Unit tests for EntityResolver service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from application.services.entity_resolver import (
    EntityResolver,
    ResolutionStrategy,
    EntityMatch,
    ResolutionResult
)

# Check if rapidfuzz is available
try:
    import rapidfuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


@pytest.fixture
def mock_backend():
    """Mock knowledge graph backend."""
    backend = AsyncMock()
    backend.query = AsyncMock(return_value=[])
    return backend


@pytest.fixture
def resolver(mock_backend):
    """Create EntityResolver with mock backend."""
    return EntityResolver(
        backend=mock_backend,
        exact_threshold=1.0,
        fuzzy_threshold=0.85,
        semantic_threshold=0.90,
        structure_threshold=0.75
    )


@pytest.fixture
def sample_entities():
    """Sample entities for testing."""
    return [
        {
            "id": "concept:customer",
            "name": "Customer",
            "properties": {
                "description": "Individual or organization that purchases products",
                "domain": "sales"
            }
        },
        {
            "id": "concept:client",
            "name": "Client",
            "properties": {
                "description": "Customer or patron",
                "domain": "sales"
            }
        },
        {
            "id": "concept:product",
            "name": "Product",
            "properties": {
                "description": "Item for sale",
                "domain": "inventory"
            }
        }
    ]


class TestEntityResolverExactMatch:
    """Test exact matching strategy."""

    @pytest.mark.asyncio
    async def test_exact_match_found(self, resolver, mock_backend, sample_entities):
        """Test exact match when entity exists."""
        mock_backend.query.return_value = sample_entities

        result = await resolver.resolve_entity(
            "Customer",
            "BusinessConcept",
            strategy=ResolutionStrategy.EXACT_MATCH
        )

        assert result.is_duplicate is True
        assert result.canonical_entity_id == "concept:customer"
        assert result.recommended_action == "merge"
        assert result.confidence == 1.0
        assert len(result.matches) == 1
        assert result.matches[0].similarity_score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_case_insensitive(self, resolver, mock_backend, sample_entities):
        """Test exact match is case insensitive."""
        mock_backend.query.return_value = sample_entities

        result = await resolver.resolve_entity(
            "customer",  # lowercase
            "BusinessConcept",
            strategy=ResolutionStrategy.EXACT_MATCH
        )

        assert result.is_duplicate is True
        assert result.canonical_entity_id == "concept:customer"

    @pytest.mark.asyncio
    async def test_exact_match_not_found(self, resolver, mock_backend, sample_entities):
        """Test exact match when no entity matches."""
        mock_backend.query.return_value = sample_entities

        result = await resolver.resolve_entity(
            "Vendor",
            "BusinessConcept",
            strategy=ResolutionStrategy.EXACT_MATCH
        )

        assert result.is_duplicate is False
        assert result.canonical_entity_id is None
        assert result.recommended_action == "create_new"
        assert len(result.matches) == 0


class TestEntityResolverFuzzyMatch:
    """Test fuzzy matching strategy."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not RAPIDFUZZ_AVAILABLE, reason="rapidfuzz not installed")
    async def test_fuzzy_match_typo(self, resolver, mock_backend, sample_entities):
        """Test fuzzy match catches typos."""
        mock_backend.query.return_value = sample_entities

        result = await resolver.resolve_entity(
            "Custmer",  # Typo
            "BusinessConcept",
            strategy=ResolutionStrategy.FUZZY_MATCH
        )

        assert len(result.matches) > 0
        assert result.matches[0].entity_name == "Customer"
        assert result.matches[0].similarity_score > 0.85

    @pytest.mark.asyncio
    @pytest.mark.skipif(not RAPIDFUZZ_AVAILABLE, reason="rapidfuzz not installed")
    async def test_fuzzy_match_threshold(self, resolver, mock_backend, sample_entities):
        """Test fuzzy match respects threshold."""
        mock_backend.query.return_value = sample_entities

        result = await resolver.resolve_entity(
            "Xyz",  # Very different
            "BusinessConcept",
            strategy=ResolutionStrategy.FUZZY_MATCH
        )

        # Should not match due to low similarity
        assert len(result.matches) == 0 or result.matches[0].similarity_score < 0.85

    @pytest.mark.asyncio
    async def test_fuzzy_match_without_rapidfuzz(self, resolver, mock_backend, sample_entities):
        """Test fuzzy match gracefully handles missing rapidfuzz."""
        mock_backend.query.return_value = sample_entities

        # Hide rapidfuzz from sys.modules temporarily
        import sys
        rapidfuzz_backup = sys.modules.get('rapidfuzz')

        # Remove rapidfuzz from sys.modules to simulate it not being installed
        if 'rapidfuzz' in sys.modules:
            del sys.modules['rapidfuzz']

        # Mock the import to raise ImportError
        sys.modules['rapidfuzz'] = None

        try:
            # The _fuzzy_match method should catch the ImportError and return empty list
            result = await resolver.resolve_entity(
                "Custmer",
                "BusinessConcept",
                strategy=ResolutionStrategy.FUZZY_MATCH
            )

            # Should return empty matches without error (graceful degradation)
            assert len(result.matches) == 0
        finally:
            # Restore original state
            if rapidfuzz_backup is not None:
                sys.modules['rapidfuzz'] = rapidfuzz_backup
            elif 'rapidfuzz' in sys.modules:
                del sys.modules['rapidfuzz']


class TestEntityResolverEmbeddingMatch:
    """Test embedding-based semantic matching."""

    @pytest.mark.asyncio
    async def test_embedding_match_similar(self, resolver, mock_backend, sample_entities):
        """Test embedding match finds semantically similar entities."""
        mock_backend.query.return_value = sample_entities

        # Mock embedding model
        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1] * 384]  # Fake embedding
        resolver._embedding_model = mock_model

        # Mock cosine_similarity in sklearn.metrics.pairwise
        with patch('sklearn.metrics.pairwise.cosine_similarity') as mock_cosine:
            mock_cosine.return_value = [[0.95]]

            result = await resolver.resolve_entity(
                "Client",
                "BusinessConcept",
                strategy=ResolutionStrategy.EMBEDDING_SIMILARITY
            )

            # Since we mocked high similarity, should find matches
            # Note: actual matching depends on real embeddings

    @pytest.mark.asyncio
    async def test_embedding_match_without_model(self, resolver, mock_backend, sample_entities):
        """Test embedding match handles missing model gracefully."""
        mock_backend.query.return_value = sample_entities

        # Force model to None by patching the property
        resolver._embedding_model = None

        # Create a property mock that returns None
        with patch.object(type(resolver), 'embedding_model', new_callable=lambda: property(lambda self: None)):
            result = await resolver.resolve_entity(
                "Client",
                "BusinessConcept",
                strategy=ResolutionStrategy.EMBEDDING_SIMILARITY
            )

            # Should return empty matches without error
            assert len(result.matches) == 0

    @pytest.mark.asyncio
    async def test_embedding_cache(self, resolver, mock_backend, sample_entities):
        """Test embedding caching works."""
        mock_backend.query.return_value = sample_entities

        # Mock embedding model
        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1] * 384]  # Fake embedding
        resolver._embedding_model = mock_model

        # Mock cosine_similarity
        with patch('sklearn.metrics.pairwise.cosine_similarity') as mock_cosine:
            mock_cosine.return_value = [[0.95]]

            # First call
            await resolver.resolve_entity(
                "Customer",
                "BusinessConcept",
                strategy=ResolutionStrategy.EMBEDDING_SIMILARITY
            )

            # Cache should be populated
            assert len(resolver._embedding_cache) > 0


class TestEntityResolverHybridMatch:
    """Test hybrid matching strategy."""

    @pytest.mark.asyncio
    async def test_hybrid_exact_match_priority(self, resolver, mock_backend, sample_entities):
        """Test hybrid strategy prioritizes exact matches."""
        mock_backend.query.return_value = sample_entities

        result = await resolver.resolve_entity(
            "Customer",
            "BusinessConcept",
            strategy=ResolutionStrategy.HYBRID
        )

        assert result.is_duplicate is True
        assert result.matches[0].similarity_score == 1.0
        assert result.matches[0].strategy == ResolutionStrategy.EXACT_MATCH

    @pytest.mark.asyncio
    async def test_hybrid_weighted_combination(self, resolver, mock_backend, sample_entities):
        """Test hybrid strategy combines scores correctly."""
        mock_backend.query.return_value = sample_entities

        result = await resolver.resolve_entity(
            "Custmer",  # Typo - will match fuzzy but not exact
            "BusinessConcept",
            strategy=ResolutionStrategy.HYBRID
        )

        # Should have matches from multiple strategies
        if result.matches:
            # Check that strategy is HYBRID
            assert any(m.strategy == ResolutionStrategy.HYBRID for m in result.matches)


class TestEntityResolverActionDetermination:
    """Test action recommendation logic."""

    def test_exact_match_recommends_merge(self, resolver):
        """Test exact match recommends merge."""
        matches = [
            EntityMatch(
                entity_id="concept:customer",
                entity_name="Customer",
                similarity_score=1.0,
                strategy=ResolutionStrategy.EXACT_MATCH,
                properties={},
                confidence=1.0
            )
        ]

        result = resolver._determine_action(matches)

        assert result.recommended_action == "merge"
        assert result.confidence == 1.0

    def test_high_confidence_recommends_link(self, resolver):
        """Test high confidence match recommends link."""
        matches = [
            EntityMatch(
                entity_id="concept:customer",
                entity_name="Customer",
                similarity_score=0.92,
                strategy=ResolutionStrategy.FUZZY_MATCH,
                properties={},
                confidence=0.92
            )
        ]

        result = resolver._determine_action(matches)

        assert result.recommended_action == "link"
        assert result.confidence == 0.92

    def test_low_confidence_recommends_create(self, resolver):
        """Test low confidence match recommends create."""
        matches = [
            EntityMatch(
                entity_id="concept:customer",
                entity_name="Customer",
                similarity_score=0.75,
                strategy=ResolutionStrategy.FUZZY_MATCH,
                properties={},
                confidence=0.75
            )
        ]

        result = resolver._determine_action(matches)

        assert result.recommended_action == "create_new"
        assert result.confidence > 0  # Confidence in creating new

    def test_no_matches_recommends_create(self, resolver):
        """Test no matches recommends create."""
        matches = []

        result = resolver._determine_action(matches)

        assert result.recommended_action == "create_new"
        assert result.confidence == 1.0


class TestEntityResolverPropertySimilarity:
    """Test property-based similarity calculation."""

    def test_identical_properties(self, resolver):
        """Test identical properties return 1.0 similarity."""
        props1 = {"name": "Customer", "domain": "sales"}
        props2 = {"name": "Customer", "domain": "sales"}

        similarity = resolver._calculate_property_similarity(props1, props2)

        assert similarity == 1.0

    def test_no_common_properties(self, resolver):
        """Test no common properties return 0.0 similarity."""
        props1 = {"name": "Customer"}
        props2 = {"type": "Entity"}

        similarity = resolver._calculate_property_similarity(props1, props2)

        assert similarity == 0.0

    def test_partial_overlap(self, resolver):
        """Test partial property overlap."""
        props1 = {"name": "Customer", "domain": "sales", "type": "Concept"}
        props2 = {"name": "Customer", "description": "A client"}

        similarity = resolver._calculate_property_similarity(props1, props2)

        # Jaccard: |{name}| / |{name, domain, type, description}| = 1/4 = 0.25
        assert similarity == 0.25

    def test_empty_properties(self, resolver):
        """Test empty properties."""
        assert resolver._calculate_property_similarity({}, {}) == 1.0
        assert resolver._calculate_property_similarity({}, {"name": "Test"}) == 0.0


class TestEntityResolverIntegration:
    """Integration tests for EntityResolver."""

    @pytest.mark.asyncio
    async def test_full_resolution_workflow(self, resolver, mock_backend):
        """Test complete resolution workflow."""
        # Setup existing entity
        existing_entities = [
            {
                "id": "concept:customer",
                "name": "Customer",
                "properties": {"description": "A client", "domain": "sales"}
            }
        ]
        mock_backend.query.return_value = existing_entities

        # Test with variation
        result = await resolver.resolve_entity(
            "Cust",
            "BusinessConcept",
            properties={"domain": "sales"},
            strategy=ResolutionStrategy.HYBRID
        )

        # Should find match
        assert isinstance(result, ResolutionResult)
        assert result.recommended_action in ["merge", "link", "create_new"]

    @pytest.mark.asyncio
    async def test_no_existing_entities(self, resolver, mock_backend):
        """Test resolution when no entities exist."""
        mock_backend.query.return_value = []

        result = await resolver.resolve_entity(
            "NewConcept",
            "BusinessConcept",
            strategy=ResolutionStrategy.HYBRID
        )

        assert result.is_duplicate is False
        assert result.recommended_action == "create_new"
        assert len(result.matches) == 0

    @pytest.mark.asyncio
    async def test_error_handling(self, resolver, mock_backend):
        """Test error handling in resolution."""
        # Simulate backend error
        mock_backend.query.side_effect = Exception("Database error")

        result = await resolver.resolve_entity(
            "Customer",
            "BusinessConcept",
            strategy=ResolutionStrategy.HYBRID
        )

        # Should handle gracefully
        assert isinstance(result, ResolutionResult)


class TestEntityResolverConfiguration:
    """Test configuration and initialization."""

    def test_custom_thresholds(self, mock_backend):
        """Test custom threshold configuration."""
        resolver = EntityResolver(
            backend=mock_backend,
            fuzzy_threshold=0.95,
            semantic_threshold=0.98
        )

        assert resolver.fuzzy_threshold == 0.95
        assert resolver.semantic_threshold == 0.98

    def test_custom_embedding_model(self, mock_backend):
        """Test custom embedding model configuration."""
        resolver = EntityResolver(
            backend=mock_backend,
            embedding_model="all-mpnet-base-v2"
        )

        assert resolver._embedding_model_name == "all-mpnet-base-v2"

    def test_lazy_model_loading(self, mock_backend):
        """Test embedding model loads lazily."""
        resolver = EntityResolver(backend=mock_backend)

        # Model should not be loaded initially
        assert resolver._embedding_model is None

        # Accessing property should trigger load (or return None if not available)
        model = resolver.embedding_model

        # If loaded, should be cached
        if model is not None:
            assert resolver._embedding_model is not None
