"""Tests for the HyperNetX adapter."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from infrastructure.hypernetx_adapter import HyperNetXAdapter


def _make_mock_backend(rows=None):
    """Create a mock Neo4j backend returning given rows."""
    backend = AsyncMock()
    backend.query_raw = AsyncMock(return_value=rows or [])
    return backend


def _sample_rows():
    """Sample Neo4j query results representing 2 FactUnits with 3 entities."""
    return [
        {
            "fact_id": "fact_001",
            "fact_type": "treatment",
            "confidence": 0.85,
            "validated": True,
            "validation_count": 3,
            "extraction_method": "co_occurrence",
            "source_document_id": "doc_001",
            "entity_id": "metformin",
            "entity_name": "Metformin",
            "entity_type": "Drug",
            "entity_layer": "SEMANTIC",
            "entity_confidence": 0.9,
            "participation_role": "treatment",
        },
        {
            "fact_id": "fact_001",
            "fact_type": "treatment",
            "confidence": 0.85,
            "validated": True,
            "validation_count": 3,
            "extraction_method": "co_occurrence",
            "source_document_id": "doc_001",
            "entity_id": "diabetes_t2",
            "entity_name": "Type 2 Diabetes",
            "entity_type": "Disease",
            "entity_layer": "SEMANTIC",
            "entity_confidence": 0.88,
            "participation_role": "condition",
        },
        {
            "fact_id": "fact_002",
            "fact_type": "association",
            "confidence": 0.72,
            "validated": False,
            "validation_count": 0,
            "extraction_method": "llm",
            "source_document_id": "doc_002",
            "entity_id": "diabetes_t2",
            "entity_name": "Type 2 Diabetes",
            "entity_type": "Disease",
            "entity_layer": "SEMANTIC",
            "entity_confidence": 0.88,
            "participation_role": "subject",
        },
        {
            "fact_id": "fact_002",
            "fact_type": "association",
            "confidence": 0.72,
            "validated": False,
            "validation_count": 0,
            "extraction_method": "llm",
            "source_document_id": "doc_002",
            "entity_id": "obesity",
            "entity_name": "Obesity",
            "entity_type": "Condition",
            "entity_layer": "PERCEPTION",
            "entity_confidence": 0.7,
            "participation_role": "related",
        },
    ]


class TestHyperNetXAdapterAvailability:
    def test_is_available_returns_true(self):
        adapter = HyperNetXAdapter(AsyncMock())
        assert adapter.is_available() is True

    @patch("infrastructure.hypernetx_adapter.HNX_AVAILABLE", False)
    def test_is_available_returns_false_when_not_installed(self):
        adapter = HyperNetXAdapter(AsyncMock())
        assert adapter.is_available() is False

    @patch("infrastructure.hypernetx_adapter.HNX_AVAILABLE", False)
    async def test_load_raises_when_not_installed(self):
        adapter = HyperNetXAdapter(AsyncMock())
        with pytest.raises(RuntimeError, match="HyperNetX is not installed"):
            await adapter.load_hypergraph()


class TestHyperNetXAdapterLoading:
    async def test_load_empty_graph(self):
        backend = _make_mock_backend(rows=[])
        adapter = HyperNetXAdapter(backend)
        H, node_props, edge_props = await adapter.load_hypergraph()
        assert len(H.edges) == 0
        assert len(H.nodes) == 0
        assert node_props == {}
        assert edge_props == {}

    async def test_load_with_data(self):
        backend = _make_mock_backend(rows=_sample_rows())
        adapter = HyperNetXAdapter(backend)
        H, node_props, edge_props = await adapter.load_hypergraph()

        assert len(H.edges) == 2
        assert len(H.nodes) == 3
        assert "metformin" in node_props
        assert "diabetes_t2" in node_props
        assert "obesity" in node_props
        assert "fact_001" in edge_props
        assert "fact_002" in edge_props

    async def test_node_properties(self):
        backend = _make_mock_backend(rows=_sample_rows())
        adapter = HyperNetXAdapter(backend)
        _, node_props, _ = await adapter.load_hypergraph()

        met = node_props["metformin"]
        assert met["name"] == "Metformin"
        assert met["entity_type"] == "Drug"
        assert met["layer"] == "SEMANTIC"
        assert met["confidence"] == 0.9

    async def test_edge_properties(self):
        backend = _make_mock_backend(rows=_sample_rows())
        adapter = HyperNetXAdapter(backend)
        _, _, edge_props = await adapter.load_hypergraph()

        f1 = edge_props["fact_001"]
        assert f1["fact_type"] == "treatment"
        assert f1["confidence"] == 0.85
        assert f1["validated"] is True

    async def test_hyperedge_membership(self):
        backend = _make_mock_backend(rows=_sample_rows())
        adapter = HyperNetXAdapter(backend)
        H, _, _ = await adapter.load_hypergraph()

        # fact_001 should connect metformin and diabetes_t2
        members_001 = set(H.edges["fact_001"])
        assert members_001 == {"metformin", "diabetes_t2"}

        # fact_002 should connect diabetes_t2 and obesity
        members_002 = set(H.edges["fact_002"])
        assert members_002 == {"diabetes_t2", "obesity"}


class TestHyperNetXAdapterFiltering:
    async def test_confidence_filter_in_query(self):
        backend = _make_mock_backend(rows=[])
        adapter = HyperNetXAdapter(backend)
        await adapter.load_hypergraph(min_confidence=0.8)

        call_args = backend.query_raw.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "min_confidence" in query
        assert params["min_confidence"] == 0.8

    async def test_document_filter_in_query(self):
        backend = _make_mock_backend(rows=[])
        adapter = HyperNetXAdapter(backend)
        await adapter.load_hypergraph(document_id="doc_001")

        call_args = backend.query_raw.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "document_id" in query
        assert params["document_id"] == "doc_001"

    async def test_layer_filter_in_query(self):
        backend = _make_mock_backend(rows=[])
        adapter = HyperNetXAdapter(backend)
        await adapter.load_hypergraph(layer="SEMANTIC")

        call_args = backend.query_raw.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "$layer" in query
        assert params["layer"] == "SEMANTIC"


class TestHyperNetXAdapterCache:
    async def test_cache_hit(self):
        backend = _make_mock_backend(rows=_sample_rows())
        adapter = HyperNetXAdapter(backend)

        # First call loads from Neo4j
        await adapter.load_hypergraph()
        assert backend.query_raw.call_count == 1

        # Second call hits cache
        await adapter.load_hypergraph()
        assert backend.query_raw.call_count == 1

    async def test_cache_miss_different_params(self):
        backend = _make_mock_backend(rows=_sample_rows())
        adapter = HyperNetXAdapter(backend)

        await adapter.load_hypergraph()
        await adapter.load_hypergraph(min_confidence=0.8)
        assert backend.query_raw.call_count == 2

    async def test_cache_invalidation(self):
        backend = _make_mock_backend(rows=_sample_rows())
        adapter = HyperNetXAdapter(backend)

        await adapter.load_hypergraph()
        adapter.invalidate_cache()
        await adapter.load_hypergraph()
        assert backend.query_raw.call_count == 2

    async def test_cache_expires_after_ttl(self):
        backend = _make_mock_backend(rows=_sample_rows())
        adapter = HyperNetXAdapter(backend)
        adapter.CACHE_TTL_SECONDS = 0  # Expire immediately

        await adapter.load_hypergraph()
        await adapter.load_hypergraph()
        assert backend.query_raw.call_count == 2
