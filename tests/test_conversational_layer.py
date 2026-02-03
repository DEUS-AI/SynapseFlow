"""
Test script for Phase 6: Conversational Agent Personality Layer

Run this to verify:
1. Intent classification works
2. Memory context is built correctly
3. Personalized greetings are generated
4. Medical responses are modulated with persona
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from application.services.conversational_intent_service import ConversationalIntentService
from application.services.memory_context_builder import MemoryContextBuilder
from application.services.response_modulator import ResponseModulator
from domain.conversation_models import IntentType, MemoryContext
from config.persona_config import get_persona


async def test_intent_classification():
    """Test 1: Intent Classification"""
    print("\n" + "="*70)
    print("TEST 1: Intent Classification")
    print("="*70)

    intent_service = ConversationalIntentService()

    # Test different message types
    test_messages = [
        ("Hello", IntentType.GREETING),
        ("Hey, I'm back", IntentType.GREETING_RETURN),
        ("My knee hurts", IntentType.SYMPTOM_REPORT),
        ("What is ibuprofen?", IntentType.MEDICAL_QUERY),
        ("Thanks", IntentType.ACKNOWLEDGMENT),
        ("Goodbye", IntentType.FAREWELL),
    ]

    for message, expected_intent in test_messages:
        result = await intent_service.classify(message, context=None)
        status = "✅" if result.intent_type == expected_intent else "❌"
        print(f"{status} '{message}' -> {result.intent_type.value} (confidence: {result.confidence:.2f})")

        if result.topic_hint:
            print(f"   Topic: {result.topic_hint}")
        if result.urgency.value != "medium":
            print(f"   Urgency: {result.urgency.value}")


async def test_memory_context_mock():
    """Test 2: Memory Context (Mock)"""
    print("\n" + "="*70)
    print("TEST 2: Memory Context Building (Mock)")
    print("="*70)

    # Create a mock memory context
    mock_context = MemoryContext(
        patient_id="test_patient_123",
        patient_name="Pablo",
        recent_topics=["knee pain", "ibuprofen", "physical therapy"],
        last_session_summary="Discussed knee pain, recommended ibuprofen and PT",
        days_since_last_session=2,
        active_conditions=["Knee Pain"],
        current_medications=["Ibuprofen 400mg"],
        allergies=[],
        current_session_topics=[],
        conversation_turn_count=0
    )

    print(f"✅ Mock memory context created:")
    print(f"   Patient: {mock_context.patient_name}")
    print(f"   Recent topics: {', '.join(mock_context.recent_topics)}")
    print(f"   Days since last session: {mock_context.days_since_last_session}")
    print(f"   Has history: {mock_context.has_history()}")
    print(f"   Is returning user: {mock_context.is_returning_user()}")
    print(f"   Time context: {mock_context.get_time_context()}")

    return mock_context


async def test_response_modulation(mock_context):
    """Test 3: Response Modulation"""
    print("\n" + "="*70)
    print("TEST 3: Response Modulation")
    print("="*70)

    # Test with default persona
    persona = get_persona("default")
    print(f"✅ Using persona: {persona.name} ({persona.tone})")

    response_modulator = ResponseModulator(persona=persona)

    # Test greeting with memory
    intent_service = ConversationalIntentService()

    # Test 1: Greeting return
    print("\n--- Test 3a: Greeting Return with Memory ---")
    intent = await intent_service.classify("Hey, I'm back", mock_context)
    try:
        response = await response_modulator.generate_response(
            user_message="Hey, I'm back",
            intent=intent,
            memory_context=mock_context
        )
        print(f"✅ Generated greeting:")
        print(f"   {response}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 2: New user greeting
    print("\n--- Test 3b: New User Greeting (No Memory) ---")
    new_user_context = MemoryContext(
        patient_id="new_patient_456",
        recent_topics=[],
        days_since_last_session=None
    )
    intent = await intent_service.classify("Hello", new_user_context)
    try:
        response = await response_modulator.generate_response(
            user_message="Hello",
            intent=intent,
            memory_context=new_user_context
        )
        print(f"✅ Generated greeting:")
        print(f"   {response}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 3: Medical query wrapping
    print("\n--- Test 3c: Medical Query with Persona Wrapping ---")
    intent = await intent_service.classify("What is ibuprofen?", mock_context)
    medical_response = "Ibuprofen is a nonsteroidal anti-inflammatory drug (NSAID) used to reduce pain and inflammation."
    try:
        response = await response_modulator.generate_response(
            user_message="What is ibuprofen?",
            intent=intent,
            memory_context=mock_context,
            medical_response=medical_response
        )
        print(f"✅ Wrapped medical response:")
        print(f"   {response}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_different_personas():
    """Test 4: Different Personas"""
    print("\n" + "="*70)
    print("TEST 4: Different Personas")
    print("="*70)

    personas = ["default", "clinical", "friendly"]

    for persona_name in personas:
        persona = get_persona(persona_name)
        print(f"\n--- {persona.name} ({persona.tone}) ---")
        print(f"   Use patient name: {persona.use_patient_name}")
        print(f"   Proactive followups: {persona.proactive_followups}")
        print(f"   Show empathy: {persona.show_empathy}")


async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("PHASE 6: CONVERSATIONAL AGENT PERSONALITY LAYER - TEST SUITE")
    print("="*70)

    # Test 1: Intent Classification
    await test_intent_classification()

    # Test 2: Memory Context
    mock_context = await test_memory_context_mock()

    # Test 3: Response Modulation
    await test_response_modulation(mock_context)

    # Test 4: Different Personas
    await test_different_personas()

    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED")
    print("="*70)
    print("\nNext Steps:")
    print("1. Start backend: docker-compose -f docker-compose.services.yml up -d")
    print("2. Start API: uv run uvicorn application.api.main:app --reload")
    print("3. Test via WebSocket at http://localhost:8000/docs")
    print("4. Try: 'Hey, I'm back' to test greeting with memory")


if __name__ == "__main__":
    asyncio.run(main())
