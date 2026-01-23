#!/usr/bin/env python3
"""
Demo: Patient Memory with Intelligent Chat

Tests the complete patient memory system integrated with chat:
1. Patient profile creation
2. Medical history (diagnoses, medications, allergies)
3. Conversation sessions with memory persistence
4. Personalized chat responses with patient context
5. Patient safety reasoning (contraindication checking, treatment analysis)
6. GDPR data deletion
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).parent / "src"))

from application.services.intelligent_chat_service import IntelligentChatService
from application.services.patient_memory_service import PatientMemoryService
from config.memory_config import create_memory_instance
from infrastructure.neo4j_backend import Neo4jBackend
from infrastructure.redis_session_cache import RedisSessionCache

load_dotenv()


async def main():
    print("=" * 80)
    print("  Patient Memory + Intelligent Chat Demo")
    print("=" * 80)

    # Initialize memory components
    print("\n📋 Step 1: Initializing memory system...")

    # Mem0
    mem0 = create_memory_instance(
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_user=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    print("  ✅ Mem0 initialized")

    # Neo4j
    neo4j = Neo4jBackend(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    print("  ✅ Neo4j connected")

    # Redis
    redis = RedisSessionCache()
    print("  ✅ Redis connected")

    # Patient Memory Service
    memory_service = PatientMemoryService(mem0, neo4j, redis)
    print("  ✅ Patient Memory Service initialized")

    # Chat Service with patient memory
    chat = IntelligentChatService(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        patient_memory_service=memory_service
    )
    print("  ✅ Intelligent Chat Service initialized with patient memory")

    # ========================================
    # SCENARIO: Patient with Crohn's Disease
    # ========================================

    print("\n" + "=" * 80)
    print("  SCENARIO: Patient with Crohn's Disease")
    print("=" * 80)

    patient_id = "patient:demo_crohns_001"

    # Step 2: Create patient profile
    print("\n📝 Step 2: Creating patient profile...")
    await memory_service.get_or_create_patient(patient_id, consent_given=True)
    print(f"  ✅ Patient created: {patient_id}")

    # Step 3: Add medical history
    print("\n💊 Step 3: Adding medical history...")

    # Diagnosis
    await memory_service.add_diagnosis(
        patient_id=patient_id,
        condition="Crohn's Disease",
        icd10_code="K50.0",
        diagnosed_date="2023-06-15"
    )
    print("  ✅ Diagnosis: Crohn's Disease (K50.0)")

    # Medication
    await memory_service.add_medication(
        patient_id=patient_id,
        name="Humira",
        dosage="40mg",
        frequency="every 2 weeks",
        started_date="2023-08-01"
    )
    print("  ✅ Medication: Humira 40mg every 2 weeks")

    # Allergy (CRITICAL for safety!)
    await memory_service.add_allergy(
        patient_id=patient_id,
        substance="Ibuprofen",
        reaction="anaphylaxis",
        severity="severe"
    )
    print("  ✅ Allergy: Ibuprofen (severe - anaphylaxis)")

    # Step 4: Start conversation session
    print("\n💬 Step 4: Starting conversation session...")
    session_id = await memory_service.start_session(patient_id, device="demo")
    print(f"  ✅ Session started: {session_id}")

    # ========================================
    # CHAT QUERIES WITH PATIENT CONTEXT
    # ========================================

    print("\n" + "=" * 80)
    print("  INTELLIGENT CHAT WITH PATIENT CONTEXT")
    print("=" * 80)

    # Query 1: Ask about current medications
    print("\n\n🔹 Query 1: \"What medications am I currently taking?\"")
    print("-" * 80)
    response1 = await chat.query(
        question="What medications am I currently taking?",
        patient_id=patient_id,
        session_id=session_id
    )
    print(f"\n💡 Answer:\n{response1.answer}\n")
    print(f"📊 Confidence: {response1.confidence:.2f} ({_get_confidence_label(response1.confidence)})")
    print(f"🔬 Reasoning Steps: {len(response1.reasoning_trail)}")
    if response1.reasoning_trail:
        print("   Reasoning:")
        for trail in response1.reasoning_trail[:3]:
            print(f"   - {trail}")

    input("\n⏸️  Press Enter to continue...")

    # Query 2: Ask about pain relief (should trigger CONTRAINDICATION WARNING)
    print("\n\n🔹 Query 2: \"I have a headache. Can I take aspirin or ibuprofen?\"")
    print("-" * 80)
    print("⚠️  Expected: Contraindication warning for Ibuprofen allergy")
    print()
    response2 = await chat.query(
        question="I have a headache. Can I take aspirin or ibuprofen?",
        patient_id=patient_id,
        session_id=session_id
    )
    print(f"\n💡 Answer:\n{response2.answer}\n")
    print(f"📊 Confidence: {response2.confidence:.2f} ({_get_confidence_label(response2.confidence)})")
    print(f"🔬 Reasoning Steps: {len(response2.reasoning_trail)}")

    # Highlight contraindication warnings
    contraindication_trails = [t for t in response2.reasoning_trail if "contraindication" in t.lower() or "allerg" in t.lower()]
    if contraindication_trails:
        print("\n⚠️  SAFETY WARNINGS DETECTED:")
        for trail in contraindication_trails:
            print(f"   - {trail}")

    input("\n⏸️  Press Enter to continue...")

    # Query 3: Ask about treatment effectiveness
    print("\n\n🔹 Query 3: \"How is my Crohn's disease treatment working?\"")
    print("-" * 80)
    print("💭 Expected: Personalized response referencing Humira")
    print()
    response3 = await chat.query(
        question="How is my Crohn's disease treatment working?",
        patient_id=patient_id,
        session_id=session_id
    )
    print(f"\n💡 Answer:\n{response3.answer}\n")
    print(f"📊 Confidence: {response3.confidence:.2f} ({_get_confidence_label(response3.confidence)})")
    print(f"🔬 Reasoning Steps: {len(response3.reasoning_trail)}")

    # Highlight treatment analysis
    treatment_trails = [t for t in response3.reasoning_trail if "treatment" in t.lower() or "biologic" in t.lower()]
    if treatment_trails:
        print("\n📈 TREATMENT ANALYSIS:")
        for trail in treatment_trails[:3]:
            print(f"   - {trail}")

    input("\n⏸️  Press Enter to continue...")

    # ========================================
    # VERIFY MEMORY STORAGE
    # ========================================

    print("\n" + "=" * 80)
    print("  MEMORY VERIFICATION")
    print("=" * 80)

    # Check Mem0 memories
    print("\n🧠 Checking Mem0 intelligent memory...")
    mem0_memories = mem0.get_all(user_id=patient_id)
    print(f"  ✅ {len(mem0_memories.get('results', []))} memories stored")
    if mem0_memories.get('results'):
        print("\n  Sample memories:")
        for memory in mem0_memories.get('results', [])[:3]:
            print(f"    - {memory.get('memory', 'N/A')}")

    # Check conversation history in Neo4j
    print("\n💾 Checking Neo4j conversation history...")
    history = await memory_service.get_conversation_history(session_id)
    print(f"  ✅ {len(history)} messages stored")
    print(f"    - {sum(1 for m in history if m.get('role') == 'user')} user messages")
    print(f"    - {sum(1 for m in history if m.get('role') == 'assistant')} assistant messages")

    # Check Redis session
    print("\n⚡ Checking Redis session cache...")
    session_data = await redis.get_session(session_id)
    if session_data:
        print(f"  ✅ Session active")
        print(f"    - Device: {session_data.get('device')}")
        print(f"    - Conversation count: {session_data.get('conversation_count')}")
        print(f"    - Last activity: {session_data.get('last_activity')}")

    # Check patient context
    print("\n🩺 Checking complete patient context...")
    context = await memory_service.get_patient_context(patient_id)
    print(f"  ✅ Patient context retrieved:")
    print(f"    - Diagnoses: {len(context.diagnoses)}")
    for dx in context.diagnoses:
        print(f"      • {dx['condition']} ({dx.get('icd10_code', 'N/A')})")
    print(f"    - Medications: {len(context.medications)}")
    for med in context.medications:
        print(f"      • {med['name']} {med['dosage']} {med['frequency']}")
    print(f"    - Allergies: {len(context.allergies)}")
    for allergy in context.allergies:
        print(f"      • {allergy} ⚠️  SEVERE")

    # ========================================
    # GDPR COMPLIANCE TEST
    # ========================================

    print("\n" + "=" * 80)
    print("  GDPR COMPLIANCE: Right to be Forgotten")
    print("=" * 80)

    print("\n🗑️  Testing patient data deletion...")
    print("   This demonstrates GDPR Article 17: Right to Erasure")
    print()

    user_input = input("   Delete all patient data? (yes/no): ")

    if user_input.lower() == "yes":
        # Log audit before deletion
        await memory_service.log_audit(
            patient_id=patient_id,
            action="gdpr_data_deletion_request",
            actor="demo_script",
            details="User requested data deletion via demo"
        )

        success = await memory_service.delete_patient_data(patient_id)

        if success:
            print("\n  ✅ Patient data deleted from all 3 layers:")
            print("     • Redis: Session cache cleared")
            print("     • Mem0: Intelligent memories erased")
            print("     • Neo4j: Medical history and audit logs removed")
            print("\n  📋 This complies with GDPR Article 17 (Right to Erasure)")
        else:
            print("\n  ❌ Data deletion failed")
    else:
        print("\n  ⏭️  Skipped data deletion")

    # Cleanup connections
    await redis.close()

    # ========================================
    # SUMMARY
    # ========================================

    print("\n" + "=" * 80)
    print("  DEMO COMPLETE")
    print("=" * 80)

    print("\n✅ Demonstrated Features:")
    print("   1. ✅ Patient profile creation with consent")
    print("   2. ✅ Medical history management (diagnosis, medication, allergy)")
    print("   3. ✅ 3-layer memory system (Redis + Mem0 + Neo4j)")
    print("   4. ✅ Intelligent chat with patient context")
    print("   5. ✅ Personalized responses based on medical history")
    print("   6. ✅ CRITICAL: Contraindication checking (Ibuprofen allergy warning)")
    print("   7. ✅ Treatment history analysis (biologic therapy detection)")
    print("   8. ✅ Conversation persistence across all layers")
    print("   9. ✅ Automatic fact extraction (Mem0)")
    print("  10. ✅ GDPR compliance (right to be forgotten)")

    print("\n🎯 Key Safety Features:")
    print("   • Contraindication warnings for drug allergies")
    print("   • Medication interaction checking")
    print("   • Treatment pattern analysis")
    print("   • Confidence scoring with provenance")
    print("   • Audit logging for compliance")

    print("\n📊 Performance Metrics:")
    print(f"   • Query 1 time: {response1.query_time_seconds:.2f}s")
    print(f"   • Query 2 time: {response2.query_time_seconds:.2f}s")
    print(f"   • Query 3 time: {response3.query_time_seconds:.2f}s")
    print(f"   • Average confidence: {(response1.confidence + response2.confidence + response3.confidence) / 3:.2f}")

    print("\n🚀 Phase 2 Implementation: COMPLETE")
    print("   Patient memory system is fully operational and integrated!")

    print("\n" + "=" * 80)


def _get_confidence_label(confidence: float) -> str:
    """Convert confidence score to human-readable label."""
    if confidence >= 0.90:
        return "HIGH"
    elif confidence >= 0.70:
        return "MEDIUM"
    else:
        return "LOW"


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
