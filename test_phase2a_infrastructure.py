#!/usr/bin/env python3
"""
Phase 2A Infrastructure Verification Test

Tests the three-layer memory system components:
1. Redis session cache
2. Mem0 intelligent memory
3. Neo4j patient storage
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.memory_config import create_memory_instance
from infrastructure.redis_session_cache import RedisSessionCache
from infrastructure.neo4j_backend import Neo4jBackend
from application.services.patient_memory_service import PatientMemoryService

load_dotenv()


async def test_redis():
    """Test Redis session cache."""
    print("\n🔴 Testing Redis Session Cache...")

    try:
        redis = RedisSessionCache(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6380))
        )

        # Test set/get
        await redis.set_session("test_session", {"foo": "bar", "patient_id": "test123"})
        result = await redis.get_session("test_session")

        assert result is not None, "Failed to retrieve session"
        assert result["foo"] == "bar", "Session data mismatch"

        # Test list patient sessions
        sessions = await redis.list_patient_sessions("test123")
        assert len(sessions) > 0, "Failed to list patient sessions"

        # Cleanup
        await redis.delete_session("test_session")
        await redis.close()

        print("  ✅ Redis session cache working correctly")
        return True

    except Exception as e:
        print(f"  ❌ Redis test failed: {e}")
        return False


async def test_qdrant():
    """Test Qdrant health endpoint."""
    print("\n🟣 Testing Qdrant Vector Store...")

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            # Qdrant doesn't have /health endpoint, test base endpoint instead
            response = await client.get("http://localhost:6333")
            assert response.status_code == 200, "Qdrant not responding"
            data = response.json()
            assert "title" in data, "Qdrant response invalid"
            assert "qdrant" in data["title"].lower(), "Not a Qdrant instance"

        print("  ✅ Qdrant vector store healthy")
        return True

    except Exception as e:
        print(f"  ❌ Qdrant test failed: {e}")
        return False


async def test_mem0():
    """Test Mem0 memory instance."""
    print("\n🟢 Testing Mem0 Memory Layer...")

    try:
        mem0 = create_memory_instance(
            neo4j_uri=os.getenv("NEO4J_URI"),
            neo4j_user=os.getenv("NEO4J_USERNAME"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        # Test add memory (Mem0 is synchronous, not async)
        result = mem0.add(
            "Test patient has mild headache",
            user_id="test_patient_123",
            metadata={"type": "symptom", "test": True}
        )

        assert result is not None, "Failed to add memory"
        print(f"  ✅ Mem0 add memory successful")

        # Test retrieve memories
        memories = mem0.get_all(user_id="test_patient_123", limit=5)
        assert "results" in memories, "Failed to retrieve memories"
        print(f"  ✅ Mem0 retrieved {len(memories.get('results', []))} memories")

        # Cleanup
        mem0.delete_all(user_id="test_patient_123")
        print("  ✅ Mem0 memory layer working correctly")
        return True

    except Exception as e:
        print(f"  ❌ Mem0 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_neo4j():
    """Test Neo4j backend."""
    print("\n🔵 Testing Neo4j Backend...")

    try:
        neo4j = Neo4jBackend(
            uri=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )

        # Test connection - query_raw() returns a list of dicts
        query = "RETURN 1 as test"
        result = await neo4j.query_raw(query, {})

        assert isinstance(result, list) and len(result) > 0, "Neo4j query returned no records"
        assert result[0].get("test") == 1, "Neo4j query result incorrect"
        print("  ✅ Neo4j backend connected and working")
        return True

    except Exception as e:
        print(f"  ❌ Neo4j test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_patient_memory_service():
    """Test complete patient memory service."""
    print("\n🌟 Testing Patient Memory Service (3-layer integration)...")

    try:
        # Initialize all components
        mem0 = create_memory_instance(
            neo4j_uri=os.getenv("NEO4J_URI"),
            neo4j_user=os.getenv("NEO4J_USERNAME"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        neo4j = Neo4jBackend(
            uri=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )

        redis = RedisSessionCache(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6380))
        )

        memory_service = PatientMemoryService(mem0, neo4j, redis)
        print("  ✅ Patient Memory Service initialized")

        # Test patient creation
        patient_id = "test_patient_infra_verification"
        await memory_service.get_or_create_patient(patient_id, consent_given=True)
        print(f"  ✅ Patient created: {patient_id}")

        # Test medical history
        dx_id = await memory_service.add_diagnosis(
            patient_id=patient_id,
            condition="Test Condition",
            icd10_code="Z00.0"
        )
        print(f"  ✅ Diagnosis added: {dx_id}")

        med_id = await memory_service.add_medication(
            patient_id=patient_id,
            name="Test Medication",
            dosage="10mg",
            frequency="daily"
        )
        print(f"  ✅ Medication added: {med_id}")

        allergy_id = await memory_service.add_allergy(
            patient_id=patient_id,
            substance="Test Allergen",
            reaction="rash",
            severity="mild"
        )
        print(f"  ✅ Allergy added: {allergy_id}")

        # Test session management
        session_id = await memory_service.start_session(patient_id, device="test")
        print(f"  ✅ Session started: {session_id}")

        # Test message storage
        from application.services.patient_memory_service import ConversationMessage
        from datetime import datetime

        msg = ConversationMessage(
            role="user",
            content="I have a headache today",
            timestamp=datetime.now(),
            patient_id=patient_id,
            session_id=session_id
        )
        msg_id = await memory_service.store_message(msg)
        print(f"  ✅ Message stored: {msg_id}")

        # Test patient context retrieval
        context = await memory_service.get_patient_context(patient_id)
        assert len(context.diagnoses) == 1, "Diagnosis not retrieved"
        assert len(context.medications) == 1, "Medication not retrieved"
        assert len(context.allergies) == 1, "Allergy not retrieved"
        print(f"  ✅ Patient context retrieved: {len(context.diagnoses)} diagnoses, "
              f"{len(context.medications)} medications, {len(context.allergies)} allergies")

        # Test consent check
        consent = await memory_service.check_consent(patient_id)
        assert consent == True, "Consent check failed"
        print("  ✅ Consent check passed")

        # Test audit logging
        audit_id = await memory_service.log_audit(
            patient_id=patient_id,
            action="infrastructure_test",
            actor="test_script",
            details="Phase 2A verification"
        )
        print(f"  ✅ Audit log created: {audit_id}")

        # Cleanup
        success = await memory_service.delete_patient_data(patient_id)
        assert success == True, "Patient data deletion failed"
        print("  ✅ Patient data deleted (GDPR right to be forgotten)")

        await redis.close()
        print("\n  🎉 Patient Memory Service fully operational!")
        return True

    except Exception as e:
        print(f"  ❌ Patient Memory Service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all verification tests."""
    print("=" * 70)
    print("  Phase 2A Infrastructure Verification")
    print("=" * 70)

    results = {
        "Redis": await test_redis(),
        "Qdrant": await test_qdrant(),
        "Mem0": await test_mem0(),
        "Neo4j": await test_neo4j(),
        "Patient Memory Service": await test_patient_memory_service()
    }

    print("\n" + "=" * 70)
    print("  Test Results Summary")
    print("=" * 70)

    for component, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {component:30} {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 All infrastructure tests passed!")
        print("✅ Phase 2A infrastructure is fully operational and ready for integration.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
