"""Unit tests for Neurosymbolic Query Service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from application.services.neurosymbolic_query_service import (
    NeurosymbolicQueryService,
    QueryStrategy,
    QueryType,
    LayerResult,
    QueryTrace,
)
from domain.confidence_models import (
    Confidence,
    ConfidenceSource,
    KnowledgeLayer,
    CrossLayerConfidencePropagation,
    create_confidence,
)


class TestQueryStrategyEnum:
    """Test QueryStrategy enumeration."""

    def test_strategy_values(self):
        """Test strategy enum values."""
        assert QueryStrategy.SYMBOLIC_ONLY == "symbolic_only"
        assert QueryStrategy.SYMBOLIC_FIRST == "symbolic_first"
        assert QueryStrategy.NEURAL_FIRST == "neural_first"
        assert QueryStrategy.COLLABORATIVE == "collaborative"


class TestQueryTypeEnum:
    """Test QueryType enumeration."""

    def test_query_type_values(self):
        """Test query type enum values."""
        assert QueryType.DRUG_INTERACTION == "drug_interaction"
        assert QueryType.CONTRAINDICATION == "contraindication"
        assert QueryType.SYMPTOM_INTERPRETATION == "symptom_interpretation"
        assert QueryType.TREATMENT_RECOMMENDATION == "treatment_recommendation"
        assert QueryType.DISEASE_INFORMATION == "disease_information"
        assert QueryType.DATA_CATALOG == "data_catalog"
        assert QueryType.GENERAL == "general"


class TestLayerResult:
    """Test LayerResult dataclass."""

    def test_layer_result_creation(self):
        """Test creating a layer result."""
        confidence = create_confidence(0.8, ConfidenceSource.HYBRID, "test")
        result = LayerResult(
            layer=KnowledgeLayer.SEMANTIC,
            entities=[{"id": "entity:1", "name": "Test"}],
            relationships=[],
            confidence=confidence,
            query_time_ms=10.5,
        )

        assert result.layer == KnowledgeLayer.SEMANTIC
        assert len(result.entities) == 1
        assert result.query_time_ms == 10.5
        assert result.cache_hit is False

    def test_layer_result_with_cache_hit(self):
        """Test layer result with cache hit."""
        confidence = create_confidence(0.9, ConfidenceSource.SYMBOLIC_RULE, "cache")
        result = LayerResult(
            layer=KnowledgeLayer.APPLICATION,
            entities=[],
            relationships=[],
            confidence=confidence,
            query_time_ms=0.1,
            cache_hit=True,
        )

        assert result.cache_hit is True


class TestQueryTrace:
    """Test QueryTrace dataclass."""

    def test_query_trace_creation(self):
        """Test creating a query trace."""
        confidence = create_confidence(0.85, ConfidenceSource.HYBRID, "combined")
        trace = QueryTrace(
            query_id="query_000001",
            query_text="What treats headache?",
            strategy=QueryStrategy.COLLABORATIVE,
            layers_traversed=[KnowledgeLayer.REASONING, KnowledgeLayer.SEMANTIC],
            layer_results=[],
            final_confidence=confidence,
            conflicts_detected=[],
            total_time_ms=100.0,
        )

        assert trace.query_id == "query_000001"
        assert trace.strategy == QueryStrategy.COLLABORATIVE
        assert len(trace.layers_traversed) == 2
        assert isinstance(trace.timestamp, datetime)


class TestNeurosymbolicQueryServiceInit:
    """Test NeurosymbolicQueryService initialization."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.list_entities_by_layer = AsyncMock(return_value=[])
        backend.list_relationships = AsyncMock(return_value=[])
        return backend

    def test_initialization_defaults(self, mock_backend):
        """Test service initialization with defaults."""
        service = NeurosymbolicQueryService(backend=mock_backend)

        assert service.backend == mock_backend
        assert service.enable_caching is True
        assert service.cache_ttl == 300
        assert isinstance(service.confidence_propagator, CrossLayerConfidencePropagation)

    def test_initialization_custom_settings(self, mock_backend):
        """Test service initialization with custom settings."""
        propagator = CrossLayerConfidencePropagation(min_confidence=0.2)
        service = NeurosymbolicQueryService(
            backend=mock_backend,
            confidence_propagator=propagator,
            enable_caching=False,
            cache_ttl_seconds=600,
        )

        assert service.enable_caching is False
        assert service.cache_ttl == 600
        assert service.confidence_propagator.min_confidence == 0.2

    def test_initial_statistics(self, mock_backend):
        """Test initial statistics."""
        service = NeurosymbolicQueryService(backend=mock_backend)

        assert service.stats["total_queries"] == 0
        assert service.stats["cache_hits"] == 0
        assert "by_strategy" in service.stats
        assert "by_layer" in service.stats


class TestQueryTypeDetection:
    """Test query type detection."""

    @pytest.fixture
    def service(self):
        """Create service with mock backend."""
        backend = MagicMock()
        return NeurosymbolicQueryService(backend=backend)

    def test_detect_drug_interaction(self, service):
        """Test detection of drug interaction queries."""
        queries = [
            "Can I combine ibuprofen and aspirin safely?",
            "What is the interaction between warfarin and vitamin K?",
            "Do these drugs interact with each other?",
        ]

        for query in queries:
            result = service._detect_query_type(query)
            assert result == QueryType.DRUG_INTERACTION

    def test_detect_contraindication(self, service):
        """Test detection of contraindication queries."""
        queries = [
            "Is this medication contraindicated for kidney patients?",
            "Should I avoid taking aspirin with my condition?",
            "I'm allergic to penicillin, what alternatives are there?",
        ]

        for query in queries:
            result = service._detect_query_type(query)
            assert result == QueryType.CONTRAINDICATION

    def test_detect_symptom_interpretation(self, service):
        """Test detection of symptom interpretation queries."""
        queries = [
            "I'm feeling dizzy, what does it mean?",
            "Is it normal to feel tired after this medication?",
            "What symptom is this rash?",
        ]

        for query in queries:
            result = service._detect_query_type(query)
            assert result == QueryType.SYMPTOM_INTERPRETATION

    def test_detect_treatment_recommendation(self, service):
        """Test detection of treatment recommendation queries."""
        queries = [
            "What treatment options do I have?",
            "Should I take this therapy?",
            "Can you recommend a medication for headache?",
        ]

        for query in queries:
            result = service._detect_query_type(query)
            assert result == QueryType.TREATMENT_RECOMMENDATION

    def test_detect_disease_information(self, service):
        """Test detection of disease information queries."""
        queries = [
            "What is diabetes?",
            "Tell me about hypertension",
            "Explain how arthritis works",
        ]

        for query in queries:
            result = service._detect_query_type(query)
            assert result == QueryType.DISEASE_INFORMATION

    def test_detect_data_catalog(self, service):
        """Test detection of data catalog queries."""
        queries = [
            "What tables are in the database?",
            "Show me the schema for patients",
            "What columns does this DDA have?",
        ]

        for query in queries:
            result = service._detect_query_type(query)
            assert result == QueryType.DATA_CATALOG

    def test_detect_general(self, service):
        """Test detection of general queries."""
        queries = [
            "Hello, how are you?",
            "Random question without medical keywords",
        ]

        for query in queries:
            result = service._detect_query_type(query)
            assert result == QueryType.GENERAL


class TestSearchTermExtraction:
    """Test search term extraction."""

    @pytest.fixture
    def service(self):
        """Create service with mock backend."""
        backend = MagicMock()
        return NeurosymbolicQueryService(backend=backend)

    def test_extract_search_terms(self, service):
        """Test extracting search terms from query."""
        query = "What is the treatment for diabetes?"
        terms = service._extract_search_terms(query)

        assert "treatment" in terms
        assert "diabetes" in terms
        assert "what" not in terms
        assert "is" not in terms
        assert "the" not in terms

    def test_extract_search_terms_limit(self, service):
        """Test that search terms are limited to 10."""
        query = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
        terms = service._extract_search_terms(query)

        assert len(terms) <= 10

    def test_extract_search_terms_removes_punctuation(self, service):
        """Test that punctuation is removed from terms."""
        query = "What is diabetes? What treatments exist!"
        terms = service._extract_search_terms(query)

        assert "diabetes?" not in terms
        assert "diabetes" in terms
        assert "exist!" not in terms


class TestQueryExecution:
    """Test query execution across layers."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.list_entities_by_layer = AsyncMock(return_value=[
            {"id": "entity:1", "name": "diabetes", "confidence": 0.9}
        ])
        backend.list_relationships = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create service with mock backend."""
        return NeurosymbolicQueryService(
            backend=mock_backend,
            enable_caching=False,
        )

    @pytest.mark.asyncio
    async def test_execute_query_basic(self, service):
        """Test basic query execution."""
        result, trace = await service.execute_query("What is diabetes?")

        assert "query_id" in result
        assert "strategy" in result
        assert "layers_traversed" in result
        assert "confidence" in result
        assert trace is not None
        assert isinstance(trace, QueryTrace)

    @pytest.mark.asyncio
    async def test_execute_query_force_strategy(self, service):
        """Test query execution with forced strategy."""
        result, trace = await service.execute_query(
            "General question",
            force_strategy=QueryStrategy.SYMBOLIC_ONLY
        )

        assert result["strategy"] == "symbolic_only"
        assert trace.strategy == QueryStrategy.SYMBOLIC_ONLY

    @pytest.mark.asyncio
    async def test_execute_query_no_trace(self, service):
        """Test query execution without trace."""
        result, trace = await service.execute_query(
            "What is diabetes?",
            trace_execution=False
        )

        assert trace is None
        assert "query_id" in result

    @pytest.mark.asyncio
    async def test_statistics_updated(self, service):
        """Test that statistics are updated after query."""
        initial_count = service.stats["total_queries"]

        await service.execute_query("What is diabetes?")

        assert service.stats["total_queries"] == initial_count + 1


class TestCaching:
    """Test query caching functionality."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.list_entities_by_layer = AsyncMock(return_value=[])
        backend.list_relationships = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create service with caching enabled."""
        return NeurosymbolicQueryService(
            backend=mock_backend,
            enable_caching=True,
            cache_ttl_seconds=300,
        )

    def test_cache_key_generation(self, service):
        """Test cache key is generated correctly."""
        key1 = service._get_cache_key("What is diabetes?")
        key2 = service._get_cache_key("What is diabetes?")
        key3 = service._get_cache_key("Different query")

        assert key1 == key2
        assert key1 != key3

    def test_cache_key_case_insensitive(self, service):
        """Test cache key is case insensitive."""
        key1 = service._get_cache_key("What is Diabetes?")
        key2 = service._get_cache_key("what is diabetes?")

        assert key1 == key2

    def test_add_to_cache(self, service):
        """Test adding result to cache."""
        result = {"entities": [], "relationships": []}
        cache_key = service._get_cache_key("Test query")

        service._add_to_cache(cache_key, result)

        cached = service._get_from_cache(cache_key)
        assert cached == result

    def test_cache_expiration(self, service):
        """Test cache entries expire after TTL."""
        service.cache_ttl = 0  # Immediate expiration

        result = {"entities": [], "relationships": []}
        cache_key = service._get_cache_key("Test query")

        service._add_to_cache(cache_key, result)

        # Should be expired immediately
        cached = service._get_from_cache(cache_key)
        assert cached is None

    def test_clear_cache(self, service):
        """Test cache clearing."""
        service._add_to_cache("key1", {"data": 1})
        service._add_to_cache("key2", {"data": 2})

        assert len(service._query_cache) == 2

        service.clear_cache()

        assert len(service._query_cache) == 0


class TestConflictDetection:
    """Test conflict detection between layers."""

    @pytest.fixture
    def service(self):
        """Create service with mock backend."""
        backend = MagicMock()
        return NeurosymbolicQueryService(backend=backend)

    def test_detect_conflicts_confidence_gap(self, service):
        """Test conflict detection based on confidence gap."""
        inferences = [
            {"type": "treatment_suggestion", "confidence": 0.9}
        ]
        validation_entities = [
            {"name": "contraindicated", "confidence": 0.3}
        ]

        conflicts = service._detect_conflicts(inferences, validation_entities)

        assert len(conflicts) > 0
        assert conflicts[0]["type"] == "confidence_gap"

    def test_detect_conflicts_no_gap(self, service):
        """Test no conflicts when confidence is similar."""
        inferences = [
            {"type": "treatment_suggestion", "confidence": 0.8}
        ]
        validation_entities = [
            {"name": "validated", "confidence": 0.75}
        ]

        conflicts = service._detect_conflicts(inferences, validation_entities)

        assert len(conflicts) == 0

    def test_detect_layer_conflicts(self, service):
        """Test conflict detection between layer results."""
        result1 = LayerResult(
            layer=KnowledgeLayer.PERCEPTION,
            entities=[],
            relationships=[],
            confidence=create_confidence(0.9, ConfidenceSource.NEURAL_MODEL, "test"),
            query_time_ms=10.0,
        )
        result2 = LayerResult(
            layer=KnowledgeLayer.SEMANTIC,
            entities=[],
            relationships=[],
            confidence=create_confidence(0.4, ConfidenceSource.SYMBOLIC_RULE, "test"),
            query_time_ms=10.0,
        )

        conflicts = service._detect_layer_conflicts([result1, result2])

        assert len(conflicts) > 0
        assert conflicts[0]["gap"] > 0.3


class TestStrategyExecution:
    """Test different query strategies."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        backend = MagicMock()
        backend.list_entities_by_layer = AsyncMock(return_value=[])
        backend.list_relationships = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create service with mock backend."""
        return NeurosymbolicQueryService(
            backend=mock_backend,
            enable_caching=False,
        )

    @pytest.mark.asyncio
    async def test_symbolic_only_strategy(self, service):
        """Test symbolic-only strategy execution."""
        trace = QueryTrace(
            query_id="test",
            query_text="Drug interaction query",
            strategy=QueryStrategy.SYMBOLIC_ONLY,
            layers_traversed=[],
            layer_results=[],
            final_confidence=create_confidence(0.0, ConfidenceSource.HEURISTIC, "init"),
            conflicts_detected=[],
            total_time_ms=0.0,
        )

        result = await service._execute_symbolic_only(
            "Drug interaction query",
            None,
            trace
        )

        assert "disclaimer" in result
        assert KnowledgeLayer.SEMANTIC in trace.layers_traversed
        assert KnowledgeLayer.REASONING in trace.layers_traversed

    @pytest.mark.asyncio
    async def test_symbolic_first_strategy(self, service):
        """Test symbolic-first strategy execution."""
        trace = QueryTrace(
            query_id="test",
            query_text="Data catalog query",
            strategy=QueryStrategy.SYMBOLIC_FIRST,
            layers_traversed=[],
            layer_results=[],
            final_confidence=create_confidence(0.0, ConfidenceSource.HEURISTIC, "init"),
            conflicts_detected=[],
            total_time_ms=0.0,
        )

        result = await service._execute_symbolic_first(
            "What tables exist?",
            None,
            trace
        )

        assert "entities" in result
        assert len(trace.layers_traversed) > 0

    @pytest.mark.asyncio
    async def test_neural_first_strategy(self, service):
        """Test neural-first strategy execution."""
        trace = QueryTrace(
            query_id="test",
            query_text="Symptom interpretation",
            strategy=QueryStrategy.NEURAL_FIRST,
            layers_traversed=[],
            layer_results=[],
            final_confidence=create_confidence(0.0, ConfidenceSource.HEURISTIC, "init"),
            conflicts_detected=[],
            total_time_ms=0.0,
        )

        result = await service._execute_neural_first(
            "I'm feeling dizzy",
            None,
            trace
        )

        assert "entities" in result
        assert KnowledgeLayer.PERCEPTION in trace.layers_traversed
        assert KnowledgeLayer.SEMANTIC in trace.layers_traversed

    @pytest.mark.asyncio
    async def test_collaborative_strategy(self, service):
        """Test collaborative strategy execution."""
        trace = QueryTrace(
            query_id="test",
            query_text="Treatment recommendation",
            strategy=QueryStrategy.COLLABORATIVE,
            layers_traversed=[],
            layer_results=[],
            final_confidence=create_confidence(0.0, ConfidenceSource.HEURISTIC, "init"),
            conflicts_detected=[],
            total_time_ms=0.0,
        )

        result = await service._execute_collaborative(
            "What treatment is best?",
            None,
            trace
        )

        assert "entities" in result
        assert len(trace.layers_traversed) >= 2


class TestStatistics:
    """Test statistics reporting."""

    @pytest.fixture
    def service(self):
        """Create service with mock backend."""
        backend = MagicMock()
        backend.list_entities_by_layer = AsyncMock(return_value=[])
        return NeurosymbolicQueryService(backend=backend)

    def test_get_statistics(self, service):
        """Test getting statistics."""
        stats = service.get_statistics()

        assert "total_queries" in stats
        assert "cache_hits" in stats
        assert "by_strategy" in stats
        assert "by_layer" in stats
        assert "cache_size" in stats
        assert "cache_hit_rate" in stats

    @pytest.mark.asyncio
    async def test_statistics_after_queries(self, service):
        """Test statistics after running queries."""
        service.backend.list_entities_by_layer = AsyncMock(return_value=[])
        service.backend.list_relationships = AsyncMock(return_value=[])

        await service.execute_query("What is diabetes?")
        await service.execute_query("What is hypertension?")

        stats = service.get_statistics()

        assert stats["total_queries"] == 2

    def test_cache_hit_rate_calculation(self, service):
        """Test cache hit rate calculation."""
        service.stats["total_queries"] = 10
        service.stats["cache_hits"] = 3

        stats = service.get_statistics()

        assert stats["cache_hit_rate"] == 0.3

    def test_cache_hit_rate_zero_queries(self, service):
        """Test cache hit rate with zero queries."""
        stats = service.get_statistics()

        assert stats["cache_hit_rate"] == 0


class TestQueryTypeStrategyMapping:
    """Test query type to strategy mapping."""

    def test_drug_interaction_uses_symbolic_only(self):
        """Test drug interactions use symbolic-only strategy."""
        assert NeurosymbolicQueryService.QUERY_TYPE_STRATEGIES[
            QueryType.DRUG_INTERACTION
        ] == QueryStrategy.SYMBOLIC_ONLY

    def test_contraindication_uses_symbolic_only(self):
        """Test contraindications use symbolic-only strategy."""
        assert NeurosymbolicQueryService.QUERY_TYPE_STRATEGIES[
            QueryType.CONTRAINDICATION
        ] == QueryStrategy.SYMBOLIC_ONLY

    def test_symptom_interpretation_uses_neural_first(self):
        """Test symptom interpretation uses neural-first strategy."""
        assert NeurosymbolicQueryService.QUERY_TYPE_STRATEGIES[
            QueryType.SYMPTOM_INTERPRETATION
        ] == QueryStrategy.NEURAL_FIRST

    def test_treatment_recommendation_uses_collaborative(self):
        """Test treatment recommendation uses collaborative strategy."""
        assert NeurosymbolicQueryService.QUERY_TYPE_STRATEGIES[
            QueryType.TREATMENT_RECOMMENDATION
        ] == QueryStrategy.COLLABORATIVE

    def test_data_catalog_uses_symbolic_first(self):
        """Test data catalog uses symbolic-first strategy."""
        assert NeurosymbolicQueryService.QUERY_TYPE_STRATEGIES[
            QueryType.DATA_CATALOG
        ] == QueryStrategy.SYMBOLIC_FIRST
