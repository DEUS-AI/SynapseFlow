"""Tests for the Hypergraph Analytics Service."""

from unittest.mock import AsyncMock

import hypernetx as hnx
import pytest

from application.services.hypergraph_analytics_service import (
    HypergraphAnalyticsService,
)


def _make_mock_adapter(edge_dict=None, node_props=None, edge_props=None):
    """Create a mock adapter that returns a pre-built hypergraph."""
    edge_dict = edge_dict or {}
    node_props = node_props or {}
    edge_props = edge_props or {}

    H = hnx.Hypergraph(edge_dict)

    adapter = AsyncMock()
    adapter.is_available.return_value = True
    adapter.load_hypergraph = AsyncMock(return_value=(H, node_props, edge_props))
    adapter.invalidate_cache = lambda: None
    return adapter


def _sample_adapter():
    """Adapter with a small medical hypergraph."""
    edge_dict = {
        "fact_001": {"metformin", "diabetes_t2", "kidney_function"},
        "fact_002": {"diabetes_t2", "obesity", "insulin_resistance"},
        "fact_003": {"obesity", "hypertension"},
        "fact_004": {"aspirin", "hypertension", "stroke_prevention"},
    }
    node_props = {
        "metformin": {"name": "Metformin", "entity_type": "Drug", "layer": "SEMANTIC", "confidence": 0.9},
        "diabetes_t2": {"name": "Type 2 Diabetes", "entity_type": "Disease", "layer": "SEMANTIC", "confidence": 0.88},
        "kidney_function": {"name": "Kidney Function", "entity_type": "Biomarker", "layer": "PERCEPTION", "confidence": 0.7},
        "obesity": {"name": "Obesity", "entity_type": "Condition", "layer": "SEMANTIC", "confidence": 0.85},
        "insulin_resistance": {"name": "Insulin Resistance", "entity_type": "Condition", "layer": "PERCEPTION", "confidence": 0.72},
        "hypertension": {"name": "Hypertension", "entity_type": "Disease", "layer": "SEMANTIC", "confidence": 0.9},
        "aspirin": {"name": "Aspirin", "entity_type": "Drug", "layer": "SEMANTIC", "confidence": 0.92},
        "stroke_prevention": {"name": "Stroke Prevention", "entity_type": "Treatment", "layer": "REASONING", "confidence": 0.8},
    }
    edge_props = {
        "fact_001": {"fact_type": "treatment", "confidence": 0.85, "validated": True},
        "fact_002": {"fact_type": "association", "confidence": 0.72, "validated": False},
        "fact_003": {"fact_type": "association", "confidence": 0.68, "validated": False},
        "fact_004": {"fact_type": "treatment", "confidence": 0.9, "validated": True},
    }
    return _make_mock_adapter(edge_dict, node_props, edge_props)


class TestComputeEntityCentrality:
    async def test_returns_ranked_results(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        results = await service.compute_entity_centrality(s=1)

        assert len(results) > 0
        # Results should be sorted descending by score
        scores = [r.centrality_score for r in results]
        assert scores == sorted(scores, reverse=True)

    async def test_result_fields(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        results = await service.compute_entity_centrality(s=1)

        for r in results:
            assert r.entity_id
            assert r.entity_name
            assert r.entity_type
            assert isinstance(r.centrality_score, float)
            assert isinstance(r.participating_fact_count, int)

    async def test_limit(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        results = await service.compute_entity_centrality(s=1, limit=3)
        assert len(results) <= 3

    async def test_empty_graph(self):
        service = HypergraphAnalyticsService(_make_mock_adapter())
        results = await service.compute_entity_centrality()
        assert results == []


class TestDetectKnowledgeCommunities:
    async def test_returns_communities(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        result = await service.detect_knowledge_communities()

        assert result.total_communities > 0
        assert isinstance(result.overall_modularity, float)
        assert len(result.communities) == result.total_communities

    async def test_community_fields(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        result = await service.detect_knowledge_communities()

        for c in result.communities:
            assert isinstance(c.community_id, int)
            assert c.member_count == len(c.member_entity_ids)
            assert len(c.dominant_types) > 0

    async def test_empty_graph(self):
        service = HypergraphAnalyticsService(_make_mock_adapter())
        result = await service.detect_knowledge_communities()
        assert result.total_communities == 0
        assert result.overall_modularity == 0.0


class TestAnalyzeConnectivity:
    async def test_returns_results_for_each_s(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        results = await service.analyze_connectivity(s_values=[1, 2])

        assert len(results) == 2
        assert results[0].s_value == 1
        assert results[1].s_value == 2

    async def test_components_have_entity_ids(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        results = await service.analyze_connectivity(s_values=[1])

        for comp in results[0].components:
            assert len(comp.entity_ids) > 0
            assert comp.size == len(comp.entity_ids)

    async def test_knowledge_islands_flagged(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        results = await service.analyze_connectivity(s_values=[1, 2, 3])

        # At higher s values, some components should be flagged as islands
        for result in results:
            for comp in result.components:
                if comp.size < 3:
                    assert comp.is_knowledge_island is True

    async def test_empty_graph(self):
        service = HypergraphAnalyticsService(_make_mock_adapter())
        results = await service.analyze_connectivity()
        assert len(results) == 3  # default [1, 2, 3]
        for r in results:
            assert r.component_count == 0


class TestComputeEntityDistances:
    async def test_returns_distances(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        results = await service.compute_entity_distances("diabetes_t2", s=1)

        assert len(results) > 0
        # Should be sorted by distance (reachable first)
        reachable = [r for r in results if r.reachable]
        if len(reachable) > 1:
            distances = [r.distance for r in reachable]
            assert distances == sorted(distances)

    async def test_entity_not_found(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        with pytest.raises(KeyError, match="not found"):
            await service.compute_entity_distances("nonexistent_entity")

    async def test_result_fields(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        results = await service.compute_entity_distances("metformin", s=1)

        for r in results:
            assert r.entity_id
            assert r.entity_name
            assert isinstance(r.distance, float)
            assert isinstance(r.reachable, bool)


class TestTopologicalSummary:
    async def test_returns_summary(self):
        service = HypergraphAnalyticsService(_sample_adapter())
        summary = await service.get_topological_summary()

        assert summary.node_count == 8
        assert summary.edge_count == 4
        assert summary.density > 0
        assert summary.avg_edge_size > 0
        assert summary.max_edge_size >= 2
        assert summary.avg_node_degree > 0

    async def test_empty_graph(self):
        service = HypergraphAnalyticsService(_make_mock_adapter())
        summary = await service.get_topological_summary()

        assert summary.node_count == 0
        assert summary.edge_count == 0
        assert summary.density == 0.0
        assert summary.avg_edge_size == 0.0
        assert summary.diameter is None


class TestHypergraphDiff:
    async def test_diff_detects_changes(self):
        # Use two different adapters to simulate before/after
        before_dict = {"fact_001": {"a", "b"}, "fact_002": {"b", "c"}}
        after_dict = {"fact_002": {"b", "c"}, "fact_003": {"c", "d"}}

        adapter = AsyncMock()
        adapter.is_available.return_value = True
        adapter.invalidate_cache = lambda: None

        call_count = 0

        async def mock_load(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return hnx.Hypergraph(before_dict), {}, {"fact_001": {"confidence": 0.8}, "fact_002": {"confidence": 0.7}}
            else:
                return hnx.Hypergraph(after_dict), {}, {"fact_002": {"confidence": 0.9}, "fact_003": {"confidence": 0.85}}

        adapter.load_hypergraph = mock_load

        service = HypergraphAnalyticsService(adapter)
        diff = await service.compute_hypergraph_diff()

        assert "fact_003" in diff.added_edges
        assert "fact_001" in diff.removed_edges
        assert "fact_002" in diff.modified_edges  # confidence changed
        assert "d" in diff.added_nodes
        assert "a" in diff.removed_nodes
