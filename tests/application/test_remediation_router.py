"""Tests for remediation API router endpoints.

Covers task 6.4:
- POST /api/ontology/remediation/dry-run
- POST /api/ontology/remediation/execute
- POST /api/ontology/remediation/rollback/{batch_id}
- GET /api/ontology/orphans
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from application.api.remediation_router import (
    router,
    set_remediation_service,
    set_deduplication_service,
    _remediation_service,
)
from fastapi import FastAPI

# Create a test app with just the remediation router
app = FastAPI()
app.include_router(router)


@pytest.fixture
def mock_service():
    """Create a mock remediation service and wire it up."""
    service = AsyncMock()
    set_remediation_service(service)
    yield service
    # Reset after test
    set_remediation_service(None)


@pytest.fixture
def client(mock_service):
    """Create a test client with the mocked service."""
    return TestClient(app)


class TestDryRunEndpoint:
    """Test POST /api/ontology/remediation/dry-run."""

    def test_dry_run_success(self, client, mock_service):
        mock_service.dry_run.return_value = {
            "pre_stats": {"total": 100, "knowledge_entities": 50},
            "unmapped_types": [{"type": "Disease", "count": 10}],
            "remediation_preview": [{"name": "disease_mapping", "would_update": 10}],
            "total_would_update": 10,
        }

        response = client.post("/api/ontology/remediation/dry-run")

        assert response.status_code == 200
        data = response.json()
        assert data["total_would_update"] == 10
        assert len(data["remediation_preview"]) == 1
        mock_service.dry_run.assert_called_once()

    def test_dry_run_service_unavailable(self):
        """Should return 503 when service is not initialized."""
        set_remediation_service(None)
        client = TestClient(app)

        response = client.post("/api/ontology/remediation/dry-run")

        assert response.status_code == 503


class TestExecuteEndpoint:
    """Test POST /api/ontology/remediation/execute."""

    def test_execute_success(self, client, mock_service):
        mock_service.execute.return_value = {
            "batch_id": "20260212_120000",
            "total_updated": 50,
            "steps": [],
            "coverage_before": 0.0,
            "coverage_after": 80.0,
        }

        response = client.post("/api/ontology/remediation/execute")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == "20260212_120000"
        assert data["total_updated"] == 50
        mock_service.execute.assert_called_once_with(
            mark_structural=True, mark_noise=True
        )

    def test_execute_with_options(self, client, mock_service):
        mock_service.execute.return_value = {
            "batch_id": "20260212_120000",
            "total_updated": 30,
            "steps": [],
        }

        response = client.post(
            "/api/ontology/remediation/execute",
            json={"mark_structural": False, "mark_noise": False},
        )

        assert response.status_code == 200
        mock_service.execute.assert_called_once_with(
            mark_structural=False, mark_noise=False
        )


class TestRollbackEndpoint:
    """Test POST /api/ontology/remediation/rollback/{batch_id}."""

    def test_rollback_success(self, client, mock_service):
        mock_service.rollback.return_value = {
            "batch_id": "20260212_120000",
            "rolled_back": 42,
        }

        response = client.post("/api/ontology/remediation/rollback/20260212_120000")

        assert response.status_code == 200
        data = response.json()
        assert data["rolled_back"] == 42
        mock_service.rollback.assert_called_once_with("20260212_120000")


class TestOrphansEndpoint:
    """Test GET /api/ontology/orphans."""

    def test_list_orphans_success(self, client, mock_service):
        mock_service.get_orphans.return_value = [
            {
                "id": "ent-1",
                "name": "Orphan A",
                "type": "Disease",
                "labels": ["Disease"],
                "canonical_type": "disease",
                "layer": "SEMANTIC",
            }
        ]

        response = client.get("/api/ontology/orphans")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["orphans"][0]["id"] == "ent-1"
        mock_service.get_orphans.assert_called_once_with(limit=100)

    def test_list_orphans_custom_limit(self, client, mock_service):
        mock_service.get_orphans.return_value = []

        response = client.get("/api/ontology/orphans?limit=10")

        assert response.status_code == 200
        mock_service.get_orphans.assert_called_once_with(limit=10)


class TestDeduplicationEndpointsReachable:
    """Test that deduplication endpoints return non-404 when service is available."""

    @pytest.fixture
    def mock_dedup_service(self):
        service = AsyncMock()
        # create_merge_plan is synchronous — use MagicMock so it returns
        # the value directly instead of a coroutine
        service.create_merge_plan = MagicMock(return_value=[])
        set_deduplication_service(service)
        yield service
        set_deduplication_service(None)

    @pytest.fixture
    def dedup_client(self, mock_dedup_service):
        return TestClient(app)

    def test_dry_run_endpoint_reachable(self, dedup_client, mock_dedup_service):
        mock_dedup_service.detect_duplicates.return_value = []
        mock_dedup_service.create_merge_plan.return_value = []
        mock_dedup_service.detect_cross_type_duplicates.return_value = []

        response = dedup_client.post("/api/ontology/deduplication/dry-run")
        assert response.status_code != 404

    def test_execute_endpoint_reachable(self, dedup_client, mock_dedup_service):
        mock_dedup_service.detect_duplicates.return_value = []
        mock_dedup_service.create_merge_plan.return_value = []
        mock_dedup_service.execute_merge.return_value = AsyncMock(
            total_merged=0, total_relationships_transferred=0, batch_id="test", details=[]
        )
        mock_dedup_service.detect_cross_type_duplicates.return_value = []

        response = dedup_client.post("/api/ontology/deduplication/execute")
        assert response.status_code != 404

    def test_dismiss_endpoint_reachable(self, dedup_client, mock_dedup_service):
        mock_dedup_service.dismiss_entities.return_value = 2

        response = dedup_client.post(
            "/api/ontology/deduplication/dismiss",
            json={"entity_ids": ["e1", "e2"]},
        )
        assert response.status_code != 404

    def test_dry_run_categorized_response(self, dedup_client, mock_dedup_service):
        """Dry-run returns categorized same_type + cross_type sections."""
        from application.services.deduplication_service import MergePlan, CrossTypeDuplicateGroup

        mock_dedup_service.detect_duplicates.return_value = []
        mock_dedup_service.create_merge_plan.return_value = [
            MergePlan(
                winner_id="w1", winner_name="Aspirin", loser_id="l1",
                loser_name="aspirin", entity_type="Drug", rationale="A wins",
            )
        ]
        mock_dedup_service.detect_cross_type_duplicates.return_value = [
            CrossTypeDuplicateGroup(
                canonical_form="corticosteroids",
                entities=[
                    {"id": "e1", "name": "corticosteroids", "type": "Drug", "relationship_count": 3},
                    {"id": "e2", "name": "Corticosteroids", "type": "Treatment", "relationship_count": 1},
                ],
                entity_count=2,
            )
        ]

        response = dedup_client.post("/api/ontology/deduplication/dry-run")
        assert response.status_code == 200
        data = response.json()
        assert data["total_same_type"] == 1
        assert data["total_cross_type"] == 1
        assert len(data["same_type_plan"]) == 1
        assert len(data["cross_type_groups"]) == 1
        assert data["cross_type_groups"][0]["canonical_form"] == "corticosteroids"

    def test_execute_includes_skipped_cross_type(self, dedup_client, mock_dedup_service):
        """Execute response includes skipped_cross_type count."""
        from application.services.deduplication_service import MergeSummary, CrossTypeDuplicateGroup

        mock_dedup_service.detect_duplicates.return_value = []
        mock_dedup_service.create_merge_plan.return_value = []
        mock_dedup_service.execute_merge.return_value = MergeSummary(
            total_merged=0, total_relationships_transferred=0, batch_id="test_batch"
        )
        mock_dedup_service.detect_cross_type_duplicates.return_value = [
            CrossTypeDuplicateGroup(canonical_form="x", entities=[], entity_count=2),
            CrossTypeDuplicateGroup(canonical_form="y", entities=[], entity_count=3),
        ]

        response = dedup_client.post("/api/ontology/deduplication/execute")
        assert response.status_code == 200
        data = response.json()
        assert data["skipped_cross_type"] == 2
        assert data["total_merged"] == 0
        assert "batch_id" in data
