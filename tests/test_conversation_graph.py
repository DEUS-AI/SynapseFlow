"""
Tests for the LangGraph-based Conversation Engine.

Tests cover:
- Conversation state management
- Mode classification and routing
- Goal tracking and slot filling
- Memory persistence
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from domain.conversation_state import (
    ConversationState,
    ConversationMode,
    UrgencyLevel,
    EmotionalTone,
    GoalType,
    ActiveGoal,
    GoalSlot,
    PatientContext,
    create_initial_state,
    serialize_goal,
    deserialize_goal,
)
from domain.goal_templates import (
    GOAL_TEMPLATES,
    create_goal_from_template,
    detect_goal_type,
    get_slot_question,
)
from application.services.conversation_router import (
    route_by_mode,
    _route_follow_up,
    should_skip_synthesizer,
)


# ============================================================
# CONVERSATION STATE TESTS
# ============================================================

class TestConversationState:
    """Tests for conversation state management."""

    def test_create_initial_state(self):
        """Test creating initial conversation state."""
        state = create_initial_state(
            thread_id="test-thread",
            patient_id="patient:123",
            session_id="session:abc",
        )

        assert state["thread_id"] == "test-thread"
        assert state["patient_id"] == "patient:123"
        assert state["session_id"] == "session:abc"
        assert state["mode"] == ConversationMode.CASUAL_CHAT.value
        assert state["turn_count"] == 0
        assert state["messages"] == []
        assert state["active_goal"] is None
        assert state["urgency_level"] == UrgencyLevel.LOW.value

    def test_create_initial_state_with_patient_context(self):
        """Test creating state with pre-loaded patient context."""
        patient_ctx = PatientContext(
            patient_id="patient:123",
            patient_name="John Doe",
            active_conditions=["Crohn's disease", "Rheumatoid arthritis"],
            current_medications=["Humira", "Prednisone"],
            allergies=["Penicillin"],
        )

        state = create_initial_state(
            thread_id="test-thread",
            patient_id="patient:123",
            patient_context=patient_ctx,
        )

        assert state["patient_context"]["patient_id"] == "patient:123"
        assert "Crohn's disease" in state["patient_context"]["active_conditions"]

    def test_conversation_modes_enum(self):
        """Test all conversation modes are defined."""
        modes = [
            ConversationMode.CASUAL_CHAT,
            ConversationMode.MEDICAL_CONSULT,
            ConversationMode.RESEARCH_EXPLORE,
            ConversationMode.GOAL_DRIVEN,
            ConversationMode.FOLLOW_UP,
            ConversationMode.CLOSING,
        ]
        assert len(modes) == 6

        # Test enum values
        assert ConversationMode.CASUAL_CHAT.value == "casual_chat"
        assert ConversationMode.GOAL_DRIVEN.value == "goal_driven"


# ============================================================
# GOAL MANAGEMENT TESTS
# ============================================================

class TestGoalManagement:
    """Tests for goal tracking and slot filling."""

    def test_create_goal_from_template(self):
        """Test creating a goal from template."""
        goal = create_goal_from_template(GoalType.DIET_PLANNING)

        assert goal.goal_type == GoalType.DIET_PLANNING
        assert "condition" in goal.slots
        assert "dietary_restrictions" in goal.slots
        assert "goals" in goal.slots
        assert goal.progress == 0.0
        assert not goal.is_complete()

    def test_goal_slot_filling(self):
        """Test filling goal slots."""
        goal = create_goal_from_template(GoalType.DIET_PLANNING)

        # Fill a required slot
        assert goal.fill_slot("condition", "Crohn's disease")
        assert goal.slots["condition"].filled
        assert goal.slots["condition"].value == "Crohn's disease"

        # Progress should update
        assert goal.progress > 0.0

    def test_goal_completion(self):
        """Test goal completion detection."""
        goal = create_goal_from_template(GoalType.DIET_PLANNING)

        # Fill all required slots
        goal.fill_slot("condition", "Crohn's disease")
        goal.fill_slot("dietary_restrictions", "Low-FODMAP")
        goal.fill_slot("goals", "Reduce inflammation")

        assert goal.is_complete()
        assert goal.progress == 1.0
        assert len(goal.get_missing_required_slots()) == 0

    def test_goal_serialization(self):
        """Test goal serialization and deserialization."""
        goal = create_goal_from_template(GoalType.EXERCISE_PLANNING)
        goal.fill_slot("condition", "Rheumatoid arthritis")

        # Serialize
        data = serialize_goal(goal)
        assert data["goal_type"] == "exercise_planning"
        assert data["slots"]["condition"]["filled"]

        # Deserialize
        restored = deserialize_goal(data)
        assert restored.goal_type == GoalType.EXERCISE_PLANNING
        assert restored.slots["condition"].value == "Rheumatoid arthritis"

    def test_detect_goal_type(self):
        """Test goal type detection from user messages."""
        # Diet planning keywords
        assert detect_goal_type("Help me plan an anti-inflammatory diet") == GoalType.DIET_PLANNING
        assert detect_goal_type("What foods should I eat?") == GoalType.DIET_PLANNING

        # Exercise planning keywords
        assert detect_goal_type("I need help with an exercise routine") == GoalType.EXERCISE_PLANNING

        # Disease education keywords
        assert detect_goal_type("Tell me about lupus") == GoalType.DISEASE_EDUCATION

        # No match
        assert detect_goal_type("Hello, how are you?") is None

    def test_get_slot_question(self):
        """Test getting questions for slot filling."""
        question = get_slot_question(GoalType.DIET_PLANNING, "condition")
        assert "diet" in question.lower() or "condition" in question.lower()

        question = get_slot_question(GoalType.EXERCISE_PLANNING, "fitness_level")
        assert "fitness" in question.lower()


# ============================================================
# ROUTER TESTS
# ============================================================

class TestConversationRouter:
    """Tests for conversation routing logic."""

    def test_route_by_mode_casual(self):
        """Test routing for casual chat mode."""
        state = {"mode": ConversationMode.CASUAL_CHAT.value}
        assert route_by_mode(state) == "casual_chat"

    def test_route_by_mode_medical(self):
        """Test routing for medical consult mode."""
        state = {"mode": ConversationMode.MEDICAL_CONSULT.value}
        assert route_by_mode(state) == "medical_consult"

    def test_route_by_mode_research(self):
        """Test routing for research exploration mode."""
        state = {"mode": ConversationMode.RESEARCH_EXPLORE.value}
        assert route_by_mode(state) == "research_explorer"

    def test_route_by_mode_goal_driven(self):
        """Test routing for goal-driven mode."""
        state = {"mode": ConversationMode.GOAL_DRIVEN.value}
        assert route_by_mode(state) == "goal_driven"

    def test_route_by_mode_closing(self):
        """Test routing for closing mode."""
        state = {"mode": ConversationMode.CLOSING.value}
        assert route_by_mode(state) == "closing"

    def test_route_by_mode_critical_urgency_override(self):
        """Test that critical urgency overrides mode routing."""
        state = {
            "mode": ConversationMode.CASUAL_CHAT.value,
            "urgency_level": UrgencyLevel.CRITICAL.value,
        }
        # Critical urgency should route to medical_consult
        assert route_by_mode(state) == "medical_consult"

    def test_route_follow_up_to_previous_mode(self):
        """Test that follow-ups route to previous mode."""
        state = {
            "mode": ConversationMode.FOLLOW_UP.value,
            "previous_mode": ConversationMode.RESEARCH_EXPLORE.value,
        }
        assert route_by_mode(state) == "research_explorer"

    def test_route_follow_up_no_previous(self):
        """Test follow-up routing with no previous mode."""
        result = _route_follow_up(None)
        assert result == "casual_chat"

    def test_should_skip_synthesizer_for_closing(self):
        """Test that synthesizer is skipped for closing."""
        state = {"mode": ConversationMode.CLOSING.value}
        assert should_skip_synthesizer(state) is True

        state = {"mode": ConversationMode.MEDICAL_CONSULT.value}
        assert should_skip_synthesizer(state) is False


# ============================================================
# GOAL TEMPLATE TESTS
# ============================================================

class TestGoalTemplates:
    """Tests for goal templates."""

    def test_all_goal_types_have_templates(self):
        """Test that all goal types have templates defined."""
        for goal_type in GoalType:
            assert goal_type in GOAL_TEMPLATES
            template = GOAL_TEMPLATES[goal_type]
            assert template.description
            assert len(template.required_slots) > 0

    def test_diet_planning_template(self):
        """Test diet planning template structure."""
        template = GOAL_TEMPLATES[GoalType.DIET_PLANNING]
        required_slot_names = [s["name"] for s in template.required_slots]

        assert "condition" in required_slot_names
        assert "dietary_restrictions" in required_slot_names
        assert "goals" in required_slot_names

    def test_exercise_planning_template(self):
        """Test exercise planning template structure."""
        template = GOAL_TEMPLATES[GoalType.EXERCISE_PLANNING]
        required_slot_names = [s["name"] for s in template.required_slots]

        assert "condition" in required_slot_names
        assert "fitness_level" in required_slot_names
        assert "limitations" in required_slot_names

    def test_mental_health_template(self):
        """Test mental health support template structure."""
        template = GOAL_TEMPLATES[GoalType.MENTAL_HEALTH_SUPPORT]
        required_slot_names = [s["name"] for s in template.required_slots]

        assert "primary_concern" in required_slot_names


# ============================================================
# INTEGRATION TESTS (require mocking)
# ============================================================

class TestConversationGraphStructure:
    """Tests for conversation graph structure."""

    def test_graph_imports(self):
        """Test that conversation graph can be imported."""
        from application.services.conversation_graph import (
            ConversationGraph,
            build_conversation_graph,
        )
        assert ConversationGraph is not None
        assert build_conversation_graph is not None

    def test_nodes_imports(self):
        """Test that conversation nodes can be imported."""
        from application.services.conversation_nodes import ConversationNodes
        assert ConversationNodes is not None

    @pytest.mark.asyncio
    async def test_graph_creation_without_services(self):
        """Test graph can be created without external services."""
        from application.services.conversation_graph import build_conversation_graph

        # Create graph without patient memory or neurosymbolic services
        # Should not raise an error
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            graph = build_conversation_graph()
            assert graph is not None
            assert graph.graph is not None


# ============================================================
# EMOTIONAL ARC TESTS
# ============================================================

class TestEmotionalTracking:
    """Tests for emotional tone tracking."""

    def test_emotional_tone_enum(self):
        """Test emotional tone enum values."""
        tones = [
            EmotionalTone.NEUTRAL,
            EmotionalTone.CONCERNED,
            EmotionalTone.ANXIOUS,
            EmotionalTone.FRUSTRATED,
            EmotionalTone.RELIEVED,
            EmotionalTone.GRATEFUL,
            EmotionalTone.CONFUSED,
        ]
        assert len(tones) == 7

    def test_emotional_arc_in_state(self):
        """Test emotional arc tracking in state."""
        state = create_initial_state("thread-1", "patient:123")
        assert EmotionalTone.NEUTRAL.value in state["emotional_arc"]

        # Simulate adding emotions
        state["emotional_arc"].append(EmotionalTone.CONCERNED.value)
        state["emotional_arc"].append(EmotionalTone.RELIEVED.value)

        assert len(state["emotional_arc"]) == 3
        assert state["emotional_arc"][-1] == EmotionalTone.RELIEVED.value


# ============================================================
# URGENCY TESTS
# ============================================================

class TestUrgencyLevels:
    """Tests for urgency classification."""

    def test_urgency_level_enum(self):
        """Test urgency level enum values."""
        levels = [
            UrgencyLevel.LOW,
            UrgencyLevel.MEDIUM,
            UrgencyLevel.HIGH,
            UrgencyLevel.CRITICAL,
        ]
        assert len(levels) == 4

    def test_critical_urgency_routing(self):
        """Test that critical urgency triggers special routing."""
        state = {
            "mode": ConversationMode.CASUAL_CHAT.value,
            "urgency_level": UrgencyLevel.CRITICAL.value,
        }
        result = route_by_mode(state)
        assert result == "medical_consult"


# ============================================================
# CLARIFICATION HANDLING TESTS
# ============================================================

class TestClarificationHandling:
    """Tests for clarification request handling."""

    def test_state_has_clarification_fields(self):
        """Test that state includes clarification tracking fields."""
        state = create_initial_state("thread-1", "patient:123")
        assert "is_clarification_request" in state
        assert state["is_clarification_request"] is False
        assert "last_asked_slot" in state
        assert state["last_asked_slot"] is None

    def test_assistant_action_has_slot_tracking(self):
        """Test AssistantAction enum has slot-related actions."""
        from domain.conversation_state import AssistantAction

        assert hasattr(AssistantAction, "ASKED_FOR_SLOT")
        assert hasattr(AssistantAction, "EXPLAINED_SLOT")
        assert AssistantAction.ASKED_FOR_SLOT.value == "asked_for_slot"
        assert AssistantAction.EXPLAINED_SLOT.value == "explained_slot"

    def test_state_can_track_last_asked_slot(self):
        """Test that state can track which slot was last asked for."""
        state = create_initial_state("thread-1", "patient:123")

        # Simulate asking for a slot
        state["last_asked_slot"] = "condition"
        assert state["last_asked_slot"] == "condition"

        # Simulate user asking for clarification
        state["is_clarification_request"] = True
        assert state["is_clarification_request"] is True

        # Verify we can use this to handle clarification
        if state["is_clarification_request"] and state["last_asked_slot"]:
            slot_to_explain = state["last_asked_slot"]
            assert slot_to_explain == "condition"

    @pytest.mark.asyncio
    async def test_conversation_nodes_has_explain_slot_method(self):
        """Test that ConversationNodes has _explain_slot method."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")
        assert hasattr(nodes, "_explain_slot")

    def test_slot_tracking_for_diet_planning(self):
        """Test that we can track slots through a diet planning flow."""
        goal = create_goal_from_template(GoalType.DIET_PLANNING)

        # Get the first missing required slot
        missing = goal.get_missing_required_slots()
        assert len(missing) > 0
        first_slot = missing[0]

        # Verify we can track it
        state = create_initial_state("thread-1", "patient:123")
        state["last_asked_slot"] = first_slot
        state["active_goal"] = serialize_goal(goal)

        # Verify the tracking works
        assert state["last_asked_slot"] == first_slot
        assert state["active_goal"]["goal_type"] == "diet_planning"


# ============================================================
# PHASE 2 TESTS: TEMPORAL AWARENESS, REFLECTION, SUMMARY
# ============================================================

class TestTemporalAwareness:
    """Tests for temporal awareness in memory context (Phase 2A)."""

    def test_patient_context_has_temporal_fields(self):
        """Test that PatientContext has temporal awareness fields."""
        from application.services.patient_memory_service import PatientContext

        # Check the dataclass has the new temporal fields
        import dataclasses
        fields = {f.name for f in dataclasses.fields(PatientContext)}

        assert "recent_conditions" in fields
        assert "historical_conditions" in fields
        assert "recently_resolved" in fields
        assert "context_timestamp" in fields

    def test_patient_context_dataclass_defaults(self):
        """Test that PatientContext temporal fields have correct defaults."""
        from application.services.patient_memory_service import PatientContext
        from datetime import datetime

        context = PatientContext(
            patient_id="test-patient",
            diagnoses=[],
            medications=[],
            allergies=[],
            recent_symptoms=[],
            conversation_summary="",
            last_updated=datetime.now()
        )

        # Temporal fields should default to empty
        assert context.recent_conditions == []
        assert context.historical_conditions == []
        assert context.recently_resolved == []
        assert context.context_timestamp == ""


class TestConversationSummary:
    """Tests for conversation summary feature (Phase 2D)."""

    def test_state_has_conversation_summary_field(self):
        """Test that ConversationState includes conversation_summary."""
        state = create_initial_state("thread-1", "patient:123")

        assert "conversation_summary" in state
        assert state["conversation_summary"] is None

    def test_conversation_summary_can_be_set(self):
        """Test that conversation_summary can be updated."""
        state = create_initial_state("thread-1", "patient:123")

        state["conversation_summary"] = "Patient discussed knee pain and diet planning."
        assert state["conversation_summary"] == "Patient discussed knee pain and diet planning."

    @pytest.mark.asyncio
    async def test_conversation_nodes_has_summary_method(self):
        """Test that ConversationNodes has _generate_conversation_summary method."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")
        assert hasattr(nodes, "_generate_conversation_summary")


class TestReflectionPattern:
    """Tests for reflection pattern in response synthesis (Phase 2B)."""

    @pytest.mark.asyncio
    async def test_response_synthesizer_has_reflection_prompt(self):
        """Test that ConversationNodes has _build_reflection_prompt method."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")
        assert hasattr(nodes, "_build_reflection_prompt")

    def test_reflection_prompt_includes_stale_check(self):
        """Test that reflection prompt includes stale information check."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")

        prompt = nodes._build_reflection_prompt(
            draft_response="Your knee pain is concerning.",
            patient_context={"active_conditions": ["Crohn's disease"]},
            turn_count=1,
            mode="casual_chat",
            recently_resolved=["knee pain"],
            historical_conditions=["old back pain"],
        )

        # Prompt should mention stale information and historical conditions
        assert "historical conditions" in prompt.lower() or "stale" in prompt.lower()
        assert "old back pain" in prompt or "Historical" in prompt

    def test_reflection_prompt_checks_persona_on_first_turn(self):
        """Test that reflection prompt checks for persona introduction on turn 1."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")

        prompt = nodes._build_reflection_prompt(
            draft_response="Hello! How can I help?",
            patient_context={},
            turn_count=1,
            mode="casual_chat",
            recently_resolved=[],
            historical_conditions=[],
        )

        # Prompt should mention checking for Matucha introduction
        assert "matucha" in prompt.lower() or "turn 1" in prompt.lower()


class TestConversationalSlotFilling:
    """Tests for conversational slot filling (Phase 2C)."""

    @pytest.mark.asyncio
    async def test_has_conversational_slot_question_method(self):
        """Test that ConversationNodes has _generate_conversational_slot_question method."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")
        assert hasattr(nodes, "_generate_conversational_slot_question")

    def test_has_format_filled_slots_summary_method(self):
        """Test that ConversationNodes has _format_filled_slots_summary method."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")
        assert hasattr(nodes, "_format_filled_slots_summary")

    def test_format_filled_slots_summary_for_diet(self):
        """Test formatting filled slots summary for diet planning."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")

        goal = create_goal_from_template(GoalType.DIET_PLANNING)
        goal.fill_slot("condition", "Crohn's disease")
        goal.fill_slot("dietary_restrictions", "none")

        summary = nodes._format_filled_slots_summary(goal)

        # Summary should be natural language, not just slot names
        assert "crohn" in summary.lower()
        assert "dietary restrictions" in summary.lower() or "don't have" in summary.lower()

    def test_format_filled_slots_summary_empty_goal(self):
        """Test formatting when no slots are filled."""
        from application.services.conversation_nodes import ConversationNodes

        nodes = ConversationNodes(openai_api_key="test-key")

        goal = create_goal_from_template(GoalType.DIET_PLANNING)
        # Don't fill any slots

        summary = nodes._format_filled_slots_summary(goal)

        # Should handle empty case gracefully
        assert "haven't gathered" in summary.lower() or len(summary) > 0
