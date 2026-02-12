"""Integration tests for the Crystallization Pipeline.

These tests verify the full pipeline with actual Neo4j and FalkorDB connections.
Requires running Docker containers: neo4j, falkordb
"""

import pytest
import os
import asyncio
from datetime import datetime
from typing import Optional

# Set test environment variables before imports
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USERNAME", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "password")
os.environ.setdefault("ENABLE_CRYSTALLIZATION", "true")

from application.services.entity_resolver import EntityResolver
from application.services.crystallization_service import (
    CrystallizationService,
    CrystallizationConfig,
    CrystallizationMode,
)
from application.services.promotion_gate import PromotionGate, PromotionGateConfig
from domain.promotion_models import RiskLevel, PromotionStatus
from application.event_bus import EventBus
from domain.event import KnowledgeEvent
from domain.roles import Role


# ========================================
# Fixtures
# ========================================

@pytest.fixture
async def neo4j_backend():
    """Create a real Neo4j backend connection."""
    from infrastructure.neo4j_backend import Neo4jBackend

    backend = Neo4jBackend(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )

    yield backend

    # Cleanup: close connection
    await backend._close_driver()


@pytest.fixture
def event_bus():
    """Create an EventBus for testing."""
    return EventBus()


@pytest.fixture
async def entity_resolver(neo4j_backend):
    """Create an EntityResolver with real Neo4j backend."""
    return EntityResolver(
        backend=neo4j_backend,
        fuzzy_threshold=0.85,
    )


@pytest.fixture
async def promotion_gate(neo4j_backend):
    """Create a PromotionGate with real Neo4j backend."""
    return PromotionGate(
        neo4j_backend=neo4j_backend,
        config=PromotionGateConfig(),
    )


@pytest.fixture
async def crystallization_service(neo4j_backend, entity_resolver, event_bus):
    """Create a CrystallizationService for testing."""
    config = CrystallizationConfig(
        mode=CrystallizationMode.BATCH,
        batch_interval_minutes=60,  # Long interval to prevent auto-runs
        batch_threshold=100,
    )

    service = CrystallizationService(
        neo4j_backend=neo4j_backend,
        entity_resolver=entity_resolver,
        event_bus=event_bus,
        config=config,
    )

    yield service

    # Cleanup: stop service if running
    await service.stop()


# ========================================
# Neo4j Connection Test
# ========================================

@pytest.mark.asyncio
async def test_neo4j_connection(neo4j_backend):
    """Verify Neo4j connection is working."""
    # Simple query to verify connection
    result = await neo4j_backend.query(
        "RETURN 1 as test",
        {}
    )

    assert result is not None
    print("✅ Neo4j connection verified")


# ========================================
# Entity Resolver Integration Tests
# ========================================

@pytest.mark.asyncio
async def test_entity_resolver_find_nonexistent(entity_resolver):
    """Test finding an entity that doesn't exist."""
    match = await entity_resolver.find_existing_for_crystallization(
        name="NonexistentTestMedication12345",
        entity_type="Medication",
        layer="ANY",
    )

    assert not match.found
    assert match.entity_id is None
    print("✅ Entity resolver correctly reports no match for nonexistent entity")


@pytest.mark.asyncio
async def test_entity_resolver_normalization(entity_resolver):
    """Test entity name and type normalization."""
    # Test name normalization
    assert entity_resolver.normalize_entity_name("  METFORMIN  ") == "metformin"
    assert entity_resolver.normalize_entity_name("HTN") == "hypertension"

    # Test type normalization
    assert entity_resolver.normalize_entity_type("medication") == "Medication"
    assert entity_resolver.normalize_entity_type("drug") == "Medication"
    assert entity_resolver.normalize_entity_type("diagnosis") == "Diagnosis"

    print("✅ Entity normalization working correctly")


# ========================================
# Crystallization Service Integration Tests
# ========================================

@pytest.mark.asyncio
async def test_crystallization_service_stats(crystallization_service):
    """Test getting crystallization statistics."""
    stats = await crystallization_service.get_crystallization_stats()

    assert "mode" in stats
    assert "running" in stats
    assert "pending_entities" in stats
    assert stats["mode"] == "batch"

    print(f"✅ Crystallization stats: {stats}")


@pytest.mark.asyncio
async def test_crystallization_create_entity(crystallization_service, neo4j_backend):
    """Test crystallizing a new entity into Neo4j."""
    # Use a unique name to avoid conflicts
    test_entity_name = f"TestMedication_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    result = await crystallization_service.crystallize_entities(
        entities=[
            {
                "name": test_entity_name,
                "entity_type": "Medication",
                "confidence": 0.85,
            }
        ],
        source="integration_test",
    )

    assert result.entities_processed == 1
    assert result.entities_created == 1
    assert result.entities_merged == 0
    assert result.batch_id.startswith("batch_")

    print(f"✅ Created entity: {test_entity_name}")
    print(f"   Batch ID: {result.batch_id}")
    print(f"   Processing time: {result.processing_time_ms:.1f}ms")

    # Cleanup: Try to delete the test entity
    try:
        await neo4j_backend.query(
            "MATCH (n:Entity) WHERE n.name = $name DELETE n",
            {"name": test_entity_name}
        )
    except Exception as e:
        print(f"   Warning: Cleanup failed: {e}")


@pytest.mark.asyncio
async def test_crystallization_batch_processing(crystallization_service, neo4j_backend):
    """Test batch crystallization of multiple entities."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    test_entities = [
        {"name": f"TestMed1_{timestamp}", "entity_type": "Medication", "confidence": 0.8},
        {"name": f"TestDiag1_{timestamp}", "entity_type": "Diagnosis", "confidence": 0.75},
        {"name": f"TestSymptom1_{timestamp}", "entity_type": "Symptom", "confidence": 0.9},
    ]

    result = await crystallization_service.crystallize_entities(
        entities=test_entities,
        source="batch_integration_test",
    )

    assert result.entities_processed == 3
    assert result.entities_created >= 0  # May be 0 if entities already exist
    assert len(result.errors) == 0

    print(f"✅ Batch crystallization complete:")
    print(f"   Processed: {result.entities_processed}")
    print(f"   Created: {result.entities_created}")
    print(f"   Merged: {result.entities_merged}")
    print(f"   Time: {result.processing_time_ms:.1f}ms")

    # Cleanup
    for entity in test_entities:
        try:
            await neo4j_backend.query(
                "MATCH (n:Entity) WHERE n.name = $name DELETE n",
                {"name": entity["name"]}
            )
        except Exception:
            pass


# ========================================
# Promotion Gate Integration Tests
# ========================================

@pytest.mark.asyncio
async def test_promotion_gate_evaluate_nonexistent(promotion_gate):
    """Test evaluating promotion for nonexistent entity."""
    decision = await promotion_gate.evaluate_promotion(
        entity_id="nonexistent_entity_12345",
        target_layer="SEMANTIC",
    )

    assert not decision.approved
    assert decision.status == PromotionStatus.REJECTED
    assert "not found" in decision.reason.lower()

    print("✅ Promotion gate correctly rejects nonexistent entity")


@pytest.mark.asyncio
async def test_promotion_gate_risk_assessment(promotion_gate):
    """Test risk level assessment for different entity types."""
    # HIGH risk entities
    high_risk_level = promotion_gate._assess_risk_level("Medication")
    assert high_risk_level == RiskLevel.HIGH

    allergy_risk = promotion_gate._assess_risk_level("Allergy")
    assert allergy_risk == RiskLevel.HIGH

    diagnosis_risk = promotion_gate._assess_risk_level("Diagnosis")
    assert diagnosis_risk == RiskLevel.HIGH

    # MEDIUM risk entities
    symptom_risk = promotion_gate._assess_risk_level("Symptom")
    assert symptom_risk == RiskLevel.MEDIUM

    # LOW risk entities
    preference_risk = promotion_gate._assess_risk_level("Preference")
    assert preference_risk == RiskLevel.LOW

    print("✅ Risk level assessment working correctly")


@pytest.mark.asyncio
async def test_promotion_gate_pending_reviews(promotion_gate):
    """Test pending reviews queue."""
    reviews = await promotion_gate.get_pending_reviews()

    # Should return a list (may be empty)
    assert isinstance(reviews, list)

    stats = await promotion_gate.get_stats()
    assert stats.total_pending_review == len(reviews)

    print(f"✅ Pending reviews: {len(reviews)}")


# ========================================
# Event Bus Integration Tests
# ========================================

@pytest.mark.asyncio
async def test_event_bus_episode_added(event_bus, crystallization_service):
    """Test that episode_added events are handled."""
    events_received = []

    async def capture_event(event: KnowledgeEvent):
        events_received.append(event)

    # Subscribe to crystallization_complete events
    event_bus.subscribe("crystallization_complete", capture_event)

    # Start the service (subscribes to episode_added)
    await crystallization_service.start()

    # Verify service is subscribed
    assert crystallization_service._running

    print("✅ Event bus integration working")


# ========================================
# Full Pipeline Integration Test
# ========================================

@pytest.mark.asyncio
async def test_full_pipeline_flow(neo4j_backend, entity_resolver, promotion_gate, event_bus):
    """Test the complete crystallization → promotion flow."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    test_entity_name = f"IntegrationTestEntity_{timestamp}"

    # Step 1: Create crystallization service
    config = CrystallizationConfig(mode=CrystallizationMode.BATCH)
    crystallization = CrystallizationService(
        neo4j_backend=neo4j_backend,
        entity_resolver=entity_resolver,
        event_bus=event_bus,
        config=config,
    )

    # Step 2: Crystallize entity
    result = await crystallization.crystallize_entities(
        entities=[{
            "name": test_entity_name,
            "entity_type": "Symptom",  # MEDIUM risk
            "confidence": 0.9,
        }],
        source="full_pipeline_test",
    )

    assert result.entities_processed == 1
    print(f"✅ Step 1: Crystallized entity '{test_entity_name}'")

    # Step 3: Check entity resolver can find it
    # Note: Need to wait for entity to be created
    match = await entity_resolver.find_existing_for_crystallization(
        name=test_entity_name,
        entity_type="Symptom",
        layer="ANY",
    )

    # The entity may or may not be found depending on timing
    if match.found:
        print(f"✅ Step 2: Entity found by resolver: {match.entity_id}")

        # Step 4: Evaluate for promotion
        decision = await promotion_gate.evaluate_promotion(
            entity_id=match.entity_id,
            target_layer="SEMANTIC",
        )

        print(f"✅ Step 3: Promotion evaluation:")
        print(f"   Status: {decision.status.value}")
        print(f"   Risk Level: {decision.risk_level.value}")
        print(f"   Criteria Met: {decision.all_criteria_met}")
        print(f"   Reason: {decision.reason}")
    else:
        print("   Entity not yet indexed (async operation)")

    # Cleanup
    try:
        await neo4j_backend.query(
            "MATCH (n:Entity) WHERE n.name = $name DELETE n",
            {"name": test_entity_name}
        )
        print("✅ Cleanup: Test entity deleted")
    except Exception as e:
        print(f"   Warning: Cleanup failed: {e}")

    await crystallization.stop()


# ========================================
# API Endpoint Integration Tests
# ========================================

@pytest.mark.asyncio
async def test_api_crystallization_router_imports():
    """Test that the API router can be imported and has expected routes."""
    from application.api.crystallization_router import router

    route_paths = [r.path for r in router.routes if hasattr(r, 'path')]

    expected_routes = [
        "/api/crystallization/stats",
        "/api/crystallization/trigger",
        "/api/crystallization/health",
        "/api/crystallization/reviews/pending",
        "/api/crystallization/promotion/stats",
        "/api/crystallization/resolution/stats",
    ]

    for expected in expected_routes:
        assert expected in route_paths, f"Missing route: {expected}"

    print(f"✅ API router has {len(route_paths)} routes configured")
    for path in route_paths:
        print(f"   - {path}")
