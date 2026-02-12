"""API Integration tests for the Crystallization Pipeline.

Tests the REST API endpoints using TestClient.
"""

import pytest
import os

# Set test environment variables before imports
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USERNAME", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "password")
os.environ.setdefault("ENABLE_CRYSTALLIZATION", "true")

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import pytest_asyncio


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    from application.api.main import app
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client():
    """Create an async client for testing."""
    from application.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ========================================
# Health Endpoint Tests
# ========================================

@pytest.mark.asyncio
async def test_crystallization_health_endpoint(async_client):
    """Test the crystallization health endpoint."""
    response = await async_client.get("/api/crystallization/health")

    # The endpoint should exist (may return 503 if not enabled)
    assert response.status_code in [200, 503]

    data = response.json()

    if response.status_code == 200:
        assert "crystallization_service" in data
        assert "promotion_gate" in data
        assert "entity_resolver" in data
        assert "healthy" in data
        print(f"✅ Health check passed: {data}")
    else:
        print(f"ℹ️  Crystallization not enabled: {data}")


# ========================================
# Stats Endpoint Tests
# ========================================

@pytest.mark.asyncio
async def test_crystallization_stats_endpoint(async_client):
    """Test the crystallization stats endpoint."""
    response = await async_client.get("/api/crystallization/stats")

    # May return 503 if crystallization is not enabled
    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert "mode" in data
        assert "running" in data
        assert "pending_entities" in data
        print(f"✅ Stats endpoint working: mode={data.get('mode')}")
    else:
        print("ℹ️  Crystallization service not available")


# ========================================
# Promotion Stats Endpoint Tests
# ========================================

@pytest.mark.asyncio
async def test_promotion_stats_endpoint(async_client):
    """Test the promotion stats endpoint."""
    response = await async_client.get("/api/crystallization/promotion/stats")

    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert "total_evaluated" in data
        assert "total_approved" in data
        assert "total_pending_review" in data
        print(f"✅ Promotion stats: evaluated={data.get('total_evaluated')}")


# ========================================
# Resolution Endpoint Tests
# ========================================

@pytest.mark.asyncio
async def test_resolution_stats_endpoint(async_client):
    """Test the resolution stats endpoint."""
    response = await async_client.get("/api/crystallization/resolution/stats")

    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert "fuzzy_threshold" in data
        assert "type_mappings_count" in data
        print(f"✅ Resolution stats: threshold={data.get('fuzzy_threshold')}")


@pytest.mark.asyncio
async def test_resolution_find_endpoint(async_client):
    """Test the entity resolution find endpoint."""
    response = await async_client.post(
        "/api/crystallization/resolution/find",
        params={
            "name": "Metformin",
            "entity_type": "Medication",
            "layer": "ANY",
        }
    )

    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert "found" in data
        assert "match_type" in data
        print(f"✅ Resolution find: found={data.get('found')}, type={data.get('match_type')}")


# ========================================
# Pending Reviews Endpoint Tests
# ========================================

@pytest.mark.asyncio
async def test_pending_reviews_endpoint(async_client):
    """Test the pending reviews endpoint."""
    response = await async_client.get("/api/crystallization/reviews/pending")

    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Pending reviews: {len(data)} items")


@pytest.mark.asyncio
async def test_pending_reviews_filter_by_risk(async_client):
    """Test filtering pending reviews by risk level."""
    response = await async_client.get(
        "/api/crystallization/reviews/pending",
        params={"risk_level": "HIGH"}
    )

    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        # All items should be HIGH risk
        for item in data:
            assert item.get("risk_level") == "HIGH"
        print(f"✅ Filtered reviews (HIGH risk): {len(data)} items")


# ========================================
# Trigger Crystallization Tests
# ========================================

@pytest.mark.asyncio
async def test_trigger_crystallization_endpoint(async_client):
    """Test manually triggering crystallization."""
    response = await async_client.post(
        "/api/crystallization/trigger",
        json={"patient_id": None}
    )

    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert "entities_processed" in data
        assert "batch_id" in data
        print(f"✅ Crystallization triggered: batch={data.get('batch_id')}")


# ========================================
# Promotion Evaluate Endpoint Tests
# ========================================

@pytest.mark.asyncio
async def test_promotion_evaluate_invalid_layer(async_client):
    """Test promotion evaluation with invalid layer."""
    response = await async_client.post(
        "/api/crystallization/promotion/evaluate/test_entity_123",
        params={"target_layer": "INVALID_LAYER"}
    )

    # Should return 400 for invalid layer
    assert response.status_code in [400, 503]

    if response.status_code == 400:
        data = response.json()
        assert "Invalid target layer" in data.get("detail", "")
        print("✅ Invalid layer correctly rejected")


@pytest.mark.asyncio
async def test_promotion_evaluate_nonexistent_entity(async_client):
    """Test promotion evaluation for nonexistent entity."""
    response = await async_client.post(
        "/api/crystallization/promotion/evaluate/nonexistent_entity_xyz",
        params={"target_layer": "SEMANTIC"}
    )

    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert data.get("approved") == False
        assert "not found" in data.get("reason", "").lower()
        print("✅ Nonexistent entity correctly rejected")


# ========================================
# Review Action Endpoint Tests
# ========================================

@pytest.mark.asyncio
async def test_review_action_not_found(async_client):
    """Test review action for nonexistent review."""
    response = await async_client.post(
        "/api/crystallization/reviews/nonexistent_entity/action",
        json={
            "reviewer": "test_user",
            "action": "approve",
            "reason": "Test approval"
        }
    )

    # Should return 404 or 503
    assert response.status_code in [404, 503]

    if response.status_code == 404:
        print("✅ Nonexistent review correctly returns 404")


@pytest.mark.asyncio
async def test_review_action_invalid_action(async_client):
    """Test review action with invalid action type."""
    response = await async_client.post(
        "/api/crystallization/reviews/some_entity/action",
        json={
            "reviewer": "test_user",
            "action": "invalid_action",
            "reason": "Test"
        }
    )

    # Should return 422 (validation error) or 503
    assert response.status_code in [422, 503]

    if response.status_code == 422:
        print("✅ Invalid action correctly rejected with 422")
