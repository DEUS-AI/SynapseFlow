"""Integration tests for Hypergraph Analytics API endpoints.

Tests all endpoints with mock analytics service, 503 when unavailable,
and filter parameter passthrough.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.api.hypergraph_router import router, set_analytics_service, get_analytics
from domain.hypergraph_models import (
    TopologicalSummary,
    CentralityResult,
    CommunityDetectionResult,
    CommunityResult,
    ConnectivityResult,
    ConnectivityComponent,
    DistanceResult,
)


@pytest.fixture
def mock_analytics_service():
    """Mock HypergraphAnalyticsService."""
    service = AsyncMock()
    service.is_available = MagicMock(return_value=True)

    # Mock adapter for euler/HIF endpoints
    service.adapter = AsyncMock()

    return service


@pytest.fixture
def app_with_service(mock_analytics_service):
    """FastAPI app with analytics service wired up."""
    app = FastAPI()
    app.include_router(router)

    # Override the dependency to inject the mock
    app.dependency_overrides[get_analytics] = lambda: mock_analytics_service

    yield app, mock_analytics_service

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def client(app_with_service):
    """Test client with mocked analytics."""
    app, _ = app_with_service
    return TestClient(app)


@pytest.fixture
def app_unavailable():
    """FastAPI app with no analytics service (503 mode)."""
    app = FastAPI()
    app.include_router(router)
    # Don't override — let the real get_analytics() run with _analytics_service=None
    return app


class TestServiceUnavailable:
    """Test 503 responses when HyperNetX is unavailable."""

    def test_summary_returns_503(self, app_unavailable):
        # Reset global state to ensure None
        set_analytics_service(None)
        client = TestClient(app_unavailable)
        resp = client.get("/api/hypergraph/summary")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "HyperNetX analytics not available"

    def test_centrality_returns_503(self, app_unavailable):
        set_analytics_service(None)
        client = TestClient(app_unavailable)
        resp = client.get("/api/hypergraph/centrality")
        assert resp.status_code == 503

    def test_communities_returns_503(self, app_unavailable):
        set_analytics_service(None)
        client = TestClient(app_unavailable)
        resp = client.get("/api/hypergraph/communities")
        assert resp.status_code == 503

    def test_connectivity_returns_503(self, app_unavailable):
        set_analytics_service(None)
        client = TestClient(app_unavailable)
        resp = client.get("/api/hypergraph/connectivity")
        assert resp.status_code == 503

    def test_distances_returns_503(self, app_unavailable):
        set_analytics_service(None)
        client = TestClient(app_unavailable)
        resp = client.get("/api/hypergraph/entity/e1/distances")
        assert resp.status_code == 503

    def test_euler_returns_503(self, app_unavailable):
        set_analytics_service(None)
        client = TestClient(app_unavailable)
        resp = client.get("/api/hypergraph/visualization/euler")
        assert resp.status_code == 503

    def test_hif_returns_503(self, app_unavailable):
        set_analytics_service(None)
        client = TestClient(app_unavailable)
        resp = client.get("/api/hypergraph/export/hif")
        assert resp.status_code == 503


class TestSummaryEndpoint:
    """Test GET /api/hypergraph/summary."""

    def test_returns_topological_summary(self, client, app_with_service):
        _, service = app_with_service
        service.get_topological_summary.return_value = TopologicalSummary(
            node_count=50,
            edge_count=30,
            density=0.12,
            avg_edge_size=3.5,
            max_edge_size=8,
            avg_node_degree=2.1,
            diameter=4,
        )

        resp = client.get("/api/hypergraph/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_count"] == 50
        assert data["edge_count"] == 30
        assert data["density"] == 0.12
        assert data["diameter"] == 4

    def test_passes_filter_params(self, client, app_with_service):
        _, service = app_with_service
        service.get_topological_summary.return_value = TopologicalSummary(
            node_count=10, edge_count=5, density=0.5,
            avg_edge_size=2.0, max_edge_size=3, avg_node_degree=1.0,
        )

        client.get("/api/hypergraph/summary?min_confidence=0.8&layer=SEMANTIC&document_id=doc1")

        service.get_topological_summary.assert_called_once_with(
            min_confidence=0.8, layer="SEMANTIC", document_id="doc1"
        )


class TestCentralityEndpoint:
    """Test GET /api/hypergraph/centrality."""

    def test_returns_centrality_list(self, client, app_with_service):
        _, service = app_with_service
        service.compute_entity_centrality.return_value = [
            CentralityResult("e1", "Entity 1", "Condition", 0.95, 5),
            CentralityResult("e2", "Entity 2", "Medication", 0.80, 3),
        ]

        resp = client.get("/api/hypergraph/centrality")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["entity_id"] == "e1"
        assert data[0]["centrality_score"] == 0.95

    def test_passes_s_and_limit(self, client, app_with_service):
        _, service = app_with_service
        service.compute_entity_centrality.return_value = []

        client.get("/api/hypergraph/centrality?s=2&limit=10")

        service.compute_entity_centrality.assert_called_once_with(
            s=2, limit=10, min_confidence=None, layer=None, document_id=None
        )


class TestCommunitiesEndpoint:
    """Test GET /api/hypergraph/communities."""

    def test_returns_community_detection(self, client, app_with_service):
        _, service = app_with_service
        service.detect_knowledge_communities.return_value = CommunityDetectionResult(
            total_communities=2,
            overall_modularity=0.45,
            communities=[
                CommunityResult(0, ["e1", "e2"], 2, ["Condition"], 0.3),
                CommunityResult(1, ["e3", "e4"], 2, ["Medication"], 0.15),
            ],
        )

        resp = client.get("/api/hypergraph/communities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_communities"] == 2
        assert data["overall_modularity"] == 0.45
        assert len(data["communities"]) == 2


class TestConnectivityEndpoint:
    """Test GET /api/hypergraph/connectivity."""

    def test_returns_connectivity(self, client, app_with_service):
        _, service = app_with_service
        service.analyze_connectivity.return_value = [
            ConnectivityResult(
                s_value=1,
                component_count=2,
                components=[
                    ConnectivityComponent(0, 3, ["e1", "e2", "e3"]),
                    ConnectivityComponent(1, 1, ["e4"], is_knowledge_island=True),
                ],
            ),
        ]

        resp = client.get("/api/hypergraph/connectivity")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["s_value"] == 1
        assert data[0]["component_count"] == 2

    def test_parses_s_values(self, client, app_with_service):
        _, service = app_with_service
        service.analyze_connectivity.return_value = []

        client.get("/api/hypergraph/connectivity?s_values=1,2,3")

        service.analyze_connectivity.assert_called_once_with(
            s_values=[1, 2, 3], min_confidence=None, layer=None, document_id=None
        )


class TestEntityDistancesEndpoint:
    """Test GET /api/hypergraph/entity/{entity_id}/distances."""

    def test_returns_distances(self, client, app_with_service):
        _, service = app_with_service
        service.compute_entity_distances.return_value = [
            DistanceResult("e2", "Entity 2", 1.0, True),
            DistanceResult("e3", "Entity 3", 2.0, True),
            DistanceResult("e4", "Entity 4", -1.0, False),
        ]

        resp = client.get("/api/hypergraph/entity/e1/distances")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["distance"] == 1.0
        assert data[2]["reachable"] is False

    def test_entity_not_found_returns_404(self, client, app_with_service):
        _, service = app_with_service
        service.compute_entity_distances.side_effect = KeyError("e_unknown")

        resp = client.get("/api/hypergraph/entity/e_unknown/distances")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Entity not found in hypergraph"

    def test_passes_s_param(self, client, app_with_service):
        _, service = app_with_service
        service.compute_entity_distances.return_value = []

        client.get("/api/hypergraph/entity/e1/distances?s=3")

        service.compute_entity_distances.assert_called_once_with(
            entity_id="e1", s=3, min_confidence=None, layer=None, document_id=None
        )


class TestEulerVisualizationEndpoint:
    """Test GET /api/hypergraph/visualization/euler."""

    def test_returns_d3_json(self, client, app_with_service):
        _, service = app_with_service

        # Build a mock HyperNetX-like Hypergraph
        mock_H = MagicMock()
        mock_H.nodes = ["e1", "e2", "e3"]

        # Simulate edges: edge_id -> members mapping
        edge_data = {"f1": ["e1", "e2"], "f2": ["e2", "e3"]}
        mock_H.edges = MagicMock()
        mock_H.edges.__iter__ = MagicMock(return_value=iter(["f1", "f2"]))
        mock_H.edges.__getitem__ = MagicMock(side_effect=lambda k: edge_data[k])

        node_props = {
            "e1": {"name": "Hypertension", "entity_type": "Condition", "layer": "SEMANTIC"},
            "e2": {"name": "Lisinopril", "entity_type": "Medication", "layer": "SEMANTIC"},
            "e3": {"name": "Patient A", "entity_type": "Patient", "layer": "PERCEPTION"},
        }
        edge_props = {
            "f1": {"fact_type": "treats", "confidence": 0.9},
            "f2": {"fact_type": "prescribed_to", "confidence": 0.7},
        }

        service.adapter.load_hypergraph.return_value = (mock_H, node_props, edge_props)

        resp = client.get("/api/hypergraph/visualization/euler")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "sets" in data
        assert len(data["nodes"]) == 3
        assert len(data["sets"]) == 2
        # Sets sorted by confidence desc
        assert data["sets"][0]["confidence"] == 0.9

    def test_max_edges_limits_sets(self, client, app_with_service):
        _, service = app_with_service

        mock_H = MagicMock()
        mock_H.nodes = ["e1", "e2", "e3", "e4"]

        edge_data = {
            "f1": ["e1", "e2"],
            "f2": ["e2", "e3"],
            "f3": ["e3", "e4"],
        }
        mock_H.edges = MagicMock()
        mock_H.edges.__iter__ = MagicMock(return_value=iter(["f1", "f2", "f3"]))
        mock_H.edges.__getitem__ = MagicMock(side_effect=lambda k: edge_data[k])

        node_props = {f"e{i}": {"name": f"Entity {i}", "entity_type": "T", "layer": "P"} for i in range(1, 5)}
        edge_props = {
            "f1": {"fact_type": "a", "confidence": 0.9},
            "f2": {"fact_type": "b", "confidence": 0.5},
            "f3": {"fact_type": "c", "confidence": 0.7},
        }
        service.adapter.load_hypergraph.return_value = (mock_H, node_props, edge_props)

        resp = client.get("/api/hypergraph/visualization/euler?max_edges=2")
        assert resp.status_code == 200
        data = resp.json()
        # Only top 2 by confidence: f1(0.9) and f3(0.7)
        assert len(data["sets"]) == 2
        assert data["sets"][0]["confidence"] == 0.9
        assert data["sets"][1]["confidence"] == 0.7
        # Nodes filtered to visible edges only (e1,e2 from f1 + e3,e4 from f3)
        node_ids = {n["id"] for n in data["nodes"]}
        assert node_ids == {"e1", "e2", "e3", "e4"}


class TestHIFExportEndpoint:
    """Test GET /api/hypergraph/export/hif."""

    def test_returns_hif_format(self, client, app_with_service):
        _, service = app_with_service

        mock_H = MagicMock()
        mock_H.nodes = ["e1", "e2"]

        edge_data = {"f1": ["e1", "e2"]}
        mock_H.edges = MagicMock()
        # Return a fresh iterator each time (HIF iterates edges 3 times)
        mock_H.edges.__iter__ = MagicMock(side_effect=lambda: iter(["f1"]))
        mock_H.edges.__getitem__ = MagicMock(side_effect=lambda k: edge_data[k])

        node_props = {
            "e1": {"name": "A", "entity_type": "Condition"},
            "e2": {"name": "B", "entity_type": "Medication"},
        }
        edge_props = {"f1": {"fact_type": "treats", "confidence": 0.85}}
        service.adapter.load_hypergraph.return_value = (mock_H, node_props, edge_props)

        resp = client.get("/api/hypergraph/export/hif")
        assert resp.status_code == 200
        data = resp.json()

        assert data["network-type"] == "asc"
        assert data["metadata"]["format"] == "HIF"
        assert data["metadata"]["generator"] == "SynapseFlow"
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert len(data["incidences"]) == 2  # f1->e1, f1->e2

        # Verify node structure
        assert data["nodes"][0]["node"] == "e1"
        assert data["nodes"][0]["attrs"]["name"] == "A"

        # Verify edge structure
        assert data["edges"][0]["edge"] == "f1"
        assert set(data["edges"][0]["nodes"]) == {"e1", "e2"}

    def test_passes_filter_to_load(self, client, app_with_service):
        _, service = app_with_service

        mock_H = MagicMock()
        mock_H.nodes = []
        mock_H.edges = MagicMock()
        mock_H.edges.__iter__ = MagicMock(return_value=iter([]))
        service.adapter.load_hypergraph.return_value = (mock_H, {}, {})

        client.get("/api/hypergraph/export/hif?min_confidence=0.7&layer=REASONING")

        service.adapter.load_hypergraph.assert_called_once_with(
            min_confidence=0.7, layer="REASONING", document_id=None
        )
