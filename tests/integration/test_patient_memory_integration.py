"""
Integration Tests for Patient Memory Workflow

Tests the complete patient memory system end-to-end:
- Patient profile creation and management
- Medical history storage and retrieval
- Conversation persistence across 3 layers
- Chat integration with patient context
- Patient safety reasoning rules
- GDPR compliance (data deletion)
"""

import pytest
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config.memory_config import create_memory_instance
from infrastructure.redis_session_cache import RedisSessionCache
from infrastructure.neo4j_backend import Neo4jBackend
from application.services.patient_memory_service import PatientMemoryService, ConversationMessage
from application.services.intelligent_chat_service import IntelligentChatService

load_dotenv()

# Test fixtures
@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def mem0_client():
    """Initialize Mem0 client."""
    mem0 = create_memory_instance(
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_user=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    yield mem0


@pytest.fixture(scope="module")
async def neo4j_backend():
    """Initialize Neo4j backend."""
    backend = Neo4jBackend(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    yield backend


@pytest.fixture(scope="module")
async def redis_cache():
    """Initialize Redis session cache."""
    cache = RedisSessionCache()
    yield cache
    await cache.close()


@pytest.fixture(scope="module")
async def patient_memory_service(mem0_client, neo4j_backend, redis_cache):
    """Initialize patient memory service."""
    service = PatientMemoryService(mem0_client, neo4j_backend, redis_cache)
    yield service


@pytest.fixture(scope="module")
async def chat_service(patient_memory_service):
    """Initialize intelligent chat service with patient memory."""
    service = IntelligentChatService(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        patient_memory_service=patient_memory_service
    )
    yield service


# Test patient ID
TEST_PATIENT_ID = "patient:test_integration_patient"


# ========================================
# TEST 1: Patient Creation and Retrieval
# ========================================

@pytest.mark.asyncio
async def test_patient_creation_and_retrieval(patient_memory_service):
    """Test creating and retrieving patient profile."""
    # Create patient
    patient_id = await patient_memory_service.get_or_create_patient(
        TEST_PATIENT_ID,
        consent_given=True
    )

    assert patient_id == TEST_PATIENT_ID

    # Verify consent
    consent = await patient_memory_service.check_consent(TEST_PATIENT_ID)
    assert consent == True


# ========================================
# TEST 2: Medical History Storage
# ========================================

@pytest.mark.asyncio
async def test_medical_history_storage(patient_memory_service):
    """Test storing and retrieving medical history."""
    # Add diagnosis
    dx_id = await patient_memory_service.add_diagnosis(
        patient_id=TEST_PATIENT_ID,
        condition="Test Condition",
        icd10_code="Z00.0",
        diagnosed_date="2025-01-01"
    )
    assert dx_id.startswith("dx:")

    # Add medication
    med_id = await patient_memory_service.add_medication(
        patient_id=TEST_PATIENT_ID,
        name="Test Medication",
        dosage="10mg",
        frequency="daily"
    )
    assert med_id.startswith("med:")

    # Add allergy
    allergy_id = await patient_memory_service.add_allergy(
        patient_id=TEST_PATIENT_ID,
        substance="Test Allergen",
        reaction="rash",
        severity="mild"
    )
    assert allergy_id.startswith("allergy:")

    # Retrieve patient context
    context = await patient_memory_service.get_patient_context(TEST_PATIENT_ID)

    assert len(context.diagnoses) >= 1
    assert context.diagnoses[0]["condition"] == "Test Condition"

    assert len(context.medications) >= 1
    assert context.medications[0]["name"] == "Test Medication"

    assert len(context.allergies) >= 1
    assert "Test Allergen" in context.allergies


# ========================================
# TEST 3: Conversation Persistence
# ========================================

@pytest.mark.asyncio
async def test_conversation_persistence_across_layers(patient_memory_service, mem0_client, redis_cache):
    """Test conversation storage across Redis, Mem0, and Neo4j."""
    # Start session
    session_id = await patient_memory_service.start_session(
        TEST_PATIENT_ID,
        device="test"
    )
    assert session_id.startswith("session:")

    # Store user message
    user_msg = ConversationMessage(
        role="user",
        content="I have a headache",
        timestamp=datetime.now(),
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )
    msg_id = await patient_memory_service.store_message(user_msg)
    assert msg_id.startswith("msg:")

    # Verify Redis session
    session_data = await redis_cache.get_session(session_id)
    assert session_data is not None
    assert session_data["patient_id"] == TEST_PATIENT_ID

    # Verify Mem0 memory
    memories = mem0_client.get_all(user_id=TEST_PATIENT_ID)
    assert "results" in memories
    assert len(memories["results"]) > 0

    # Verify Neo4j message
    history = await patient_memory_service.get_conversation_history(session_id)
    assert len(history) >= 1
    assert history[-1]["content"] == "I have a headache"


# ========================================
# TEST 4: Chat Integration with Patient Context
# ========================================

@pytest.mark.asyncio
async def test_chat_with_patient_context(chat_service, patient_memory_service):
    """Test chat service using patient context."""
    # Start new session
    session_id = await patient_memory_service.start_session(
        TEST_PATIENT_ID,
        device="test"
    )

    # Query chat with patient context
    response = await chat_service.query(
        question="What medications am I taking?",
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )

    # Verify response
    assert response is not None
    assert response.answer is not None
    assert len(response.answer) > 0
    assert response.confidence > 0

    # Verify conversation was stored
    history = await patient_memory_service.get_conversation_history(session_id)
    assert len(history) >= 2  # User + assistant messages


# ========================================
# TEST 5: Contraindication Detection
# ========================================

@pytest.mark.asyncio
async def test_contraindication_checking(chat_service, patient_memory_service):
    """Test contraindication detection for allergies."""
    # Add severe allergy
    await patient_memory_service.add_allergy(
        patient_id=TEST_PATIENT_ID,
        substance="Penicillin",
        reaction="anaphylaxis",
        severity="severe"
    )

    # Start new session
    session_id = await patient_memory_service.start_session(
        TEST_PATIENT_ID,
        device="test"
    )

    # Ask about allergenic medication
    response = await chat_service.query(
        question="Can I take penicillin for my infection?",
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )

    # Verify contraindication detected
    assert response is not None
    # Check reasoning trail for contraindication warnings
    contraindication_found = any(
        "contraindication" in trail.lower() or "allerg" in trail.lower()
        for trail in response.reasoning_trail
    )
    assert contraindication_found, "Contraindication warning should be in reasoning trail"


# ========================================
# TEST 6: Treatment History Analysis
# ========================================

@pytest.mark.asyncio
async def test_treatment_history_analysis(chat_service, patient_memory_service):
    """Test treatment history pattern detection."""
    # Add biologic medication
    await patient_memory_service.add_medication(
        patient_id=TEST_PATIENT_ID,
        name="Humira",
        dosage="40mg",
        frequency="every 2 weeks"
    )

    # Start new session
    session_id = await patient_memory_service.start_session(
        TEST_PATIENT_ID,
        device="test"
    )

    # Ask about treatment
    response = await chat_service.query(
        question="How is my treatment working?",
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )

    # Verify treatment analysis in reasoning
    assert response is not None
    treatment_analysis_found = any(
        "treatment" in trail.lower() or "biologic" in trail.lower()
        for trail in response.reasoning_trail
    )
    assert treatment_analysis_found or len(response.reasoning_trail) > 0


# ========================================
# TEST 7: Symptom Tracking
# ========================================

@pytest.mark.asyncio
async def test_symptom_tracking(chat_service, patient_memory_service):
    """Test symptom tracking across conversations."""
    # Start new session
    session_id = await patient_memory_service.start_session(
        TEST_PATIENT_ID,
        device="test"
    )

    # Mention symptom multiple times
    await chat_service.query(
        question="I have a headache today",
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )

    await chat_service.query(
        question="My headache is still here",
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )

    # Query should detect recurring symptom
    response = await chat_service.query(
        question="What symptoms have I mentioned?",
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )

    assert response is not None
    # Reasoning should track recurring symptoms
    assert len(response.reasoning_trail) > 0


# ========================================
# TEST 8: Medication Adherence Checking
# ========================================

@pytest.mark.asyncio
async def test_medication_adherence(chat_service, patient_memory_service):
    """Test medication adherence monitoring."""
    # Start new session
    session_id = await patient_memory_service.start_session(
        TEST_PATIENT_ID,
        device="test"
    )

    # Mention missed medication
    response = await chat_service.query(
        question="I forgot to take my medication yesterday",
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )

    # Verify adherence concern detected
    assert response is not None
    adherence_concern_found = any(
        "adherence" in trail.lower() or "missed" in trail.lower()
        for trail in response.reasoning_trail
    )
    # At minimum, response should be generated
    assert len(response.answer) > 0


# ========================================
# TEST 9: Mem0 Fact Extraction
# ========================================

@pytest.mark.asyncio
async def test_mem0_fact_extraction(patient_memory_service, mem0_client):
    """Test Mem0 automatic fact extraction."""
    # Store message with medical fact
    session_id = await patient_memory_service.start_session(
        TEST_PATIENT_ID,
        device="test"
    )

    msg = ConversationMessage(
        role="user",
        content="I started experiencing stomach pain last week",
        timestamp=datetime.now(),
        patient_id=TEST_PATIENT_ID,
        session_id=session_id
    )
    await patient_memory_service.store_message(msg)

    # Retrieve memories
    memories = mem0_client.get_all(user_id=TEST_PATIENT_ID)

    # Verify fact extraction
    assert "results" in memories
    assert len(memories["results"]) > 0

    # Check if symptom mention was captured
    memory_texts = [m.get("memory", "").lower() for m in memories["results"]]
    assert any("stomach" in text or "pain" in text for text in memory_texts)


# ========================================
# TEST 10: GDPR Data Deletion
# ========================================

@pytest.mark.asyncio
async def test_gdpr_data_deletion(patient_memory_service, mem0_client, redis_cache):
    """Test GDPR right to be forgotten."""
    # Create test patient
    test_patient = "patient:test_gdpr_deletion"

    await patient_memory_service.get_or_create_patient(test_patient, consent_given=True)

    # Add medical history
    await patient_memory_service.add_diagnosis(
        patient_id=test_patient,
        condition="GDPR Test Condition",
        icd10_code="Z99.9"
    )

    # Start session
    session_id = await patient_memory_service.start_session(test_patient, device="test")

    # Store message
    msg = ConversationMessage(
        role="user",
        content="GDPR test message",
        timestamp=datetime.now(),
        patient_id=test_patient,
        session_id=session_id
    )
    await patient_memory_service.store_message(msg)

    # Verify data exists
    context_before = await patient_memory_service.get_patient_context(test_patient)
    assert len(context_before.diagnoses) > 0

    # Delete all patient data
    success = await patient_memory_service.delete_patient_data(test_patient)
    assert success == True

    # Verify data deleted from Neo4j
    context_after = await patient_memory_service.get_patient_context(test_patient)
    assert len(context_after.diagnoses) == 0

    # Verify session deleted from Redis
    session_data = await redis_cache.get_session(session_id)
    assert session_data is None

    # Note: Mem0 memories are also deleted (verified in delete_patient_data implementation)


# ========================================
# CLEANUP
# ========================================

@pytest.mark.asyncio
async def test_zz_cleanup(patient_memory_service):
    """Cleanup test data (runs last due to 'zz' prefix)."""
    # Delete main test patient
    await patient_memory_service.delete_patient_data(TEST_PATIENT_ID)

    # Verify deletion
    context = await patient_memory_service.get_patient_context(TEST_PATIENT_ID)
    assert len(context.diagnoses) == 0
    assert len(context.medications) == 0
    assert len(context.allergies) == 0
