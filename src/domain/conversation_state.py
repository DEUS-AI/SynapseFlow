"""
Conversation State Schema for LangGraph-based Conversation Engine.

Defines the state machine schema for managing multi-turn conversations
with mode-based routing, goal tracking, and emotional arc awareness.
"""

from typing import Annotated, List, Optional, Dict, Any
from typing_extensions import TypedDict
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from langgraph.graph.message import add_messages


class ConversationMode(str, Enum):
    """
    Conversation modes that persist across turns.

    Unlike per-message intents, modes are "sticky" - they persist
    until explicitly changed by user behavior or goal completion.
    """
    CASUAL_CHAT = "casual_chat"          # Social/greeting, no medical goal
    MEDICAL_CONSULT = "medical_consult"  # Symptom reporting, seeking advice
    RESEARCH_EXPLORE = "research_explore"  # Learning about a topic in depth
    GOAL_DRIVEN = "goal_driven"          # Working toward specific outcome
    FOLLOW_UP = "follow_up"              # Continuing previous thread
    CLOSING = "closing"                  # Wrapping up conversation


class UrgencyLevel(str, Enum):
    """Urgency classification for medical conversations."""
    LOW = "low"              # General questions, no immediate concern
    MEDIUM = "medium"        # Symptoms present but not alarming
    HIGH = "high"            # Symptoms require prompt attention
    CRITICAL = "critical"    # Emergency symptoms - immediate medical care needed


class EmotionalTone(str, Enum):
    """Emotional tone tracking across conversation turns."""
    NEUTRAL = "neutral"
    CONCERNED = "concerned"
    ANXIOUS = "anxious"
    FRUSTRATED = "frustrated"
    RELIEVED = "relieved"
    GRATEFUL = "grateful"
    CONFUSED = "confused"


class AssistantAction(str, Enum):
    """Actions taken by the assistant in responses."""
    GREETED = "greeted"
    ASKED_CLARIFICATION = "asked_clarification"
    PROVIDED_MEDICAL_INFO = "provided_medical_info"
    EXPLAINED_TOPIC = "explained_topic"
    COLLECTED_SLOT = "collected_slot"
    ASKED_FOR_SLOT = "asked_for_slot"  # Specifically asked for a slot value
    EXPLAINED_SLOT = "explained_slot"  # Explained what a slot means
    COMPLETED_GOAL = "completed_goal"
    OFFERED_NEXT_STEPS = "offered_next_steps"
    ACKNOWLEDGED = "acknowledged"
    SAID_FAREWELL = "said_farewell"


class GoalType(str, Enum):
    """Types of goals for GOAL_DRIVEN mode."""
    DIET_PLANNING = "diet_planning"
    EXERCISE_PLANNING = "exercise_planning"
    DISEASE_EDUCATION = "disease_education"
    MEDICATION_MANAGEMENT = "medication_management"
    MENTAL_HEALTH_SUPPORT = "mental_health_support"


@dataclass
class GoalSlot:
    """A slot to be filled for goal completion."""
    name: str
    description: str
    required: bool = True
    value: Optional[Any] = None
    filled: bool = False


@dataclass
class ActiveGoal:
    """
    Represents an active goal being pursued in GOAL_DRIVEN mode.

    Goals have slots that need to be filled through conversation
    before the goal can be completed.
    """
    goal_type: GoalType
    description: str
    slots: Dict[str, GoalSlot] = field(default_factory=dict)
    progress: float = 0.0  # 0.0 to 1.0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def get_missing_required_slots(self) -> List[str]:
        """Get list of required slots that haven't been filled."""
        return [
            name for name, slot in self.slots.items()
            if slot.required and not slot.filled
        ]

    def get_filled_slots(self) -> Dict[str, Any]:
        """Get dict of filled slot values."""
        return {
            name: slot.value
            for name, slot in self.slots.items()
            if slot.filled
        }

    def calculate_progress(self) -> float:
        """Calculate progress based on filled slots."""
        if not self.slots:
            return 1.0
        required_slots = [s for s in self.slots.values() if s.required]
        if not required_slots:
            return 1.0
        filled = sum(1 for s in required_slots if s.filled)
        return filled / len(required_slots)

    def fill_slot(self, name: str, value: Any) -> bool:
        """Fill a slot with a value. Returns True if slot exists."""
        if name in self.slots:
            self.slots[name].value = value
            self.slots[name].filled = True
            self.progress = self.calculate_progress()
            return True
        return False

    def is_complete(self) -> bool:
        """Check if all required slots are filled."""
        return len(self.get_missing_required_slots()) == 0


@dataclass
class PatientContext:
    """
    Patient medical context from Neo4j/memory layers.

    This is a simplified view of the patient's medical profile
    for use in conversation context.
    """
    patient_id: str
    patient_name: Optional[str] = None
    active_conditions: List[str] = field(default_factory=list)
    current_medications: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    recently_resolved: List[str] = field(default_factory=list)


class ConversationState(TypedDict, total=False):
    """
    LangGraph state schema for conversation management.

    This state is persisted across turns and updated by each node
    in the conversation graph.

    Note: Using TypedDict for LangGraph compatibility.
    Messages are managed by LangGraph's add_messages reducer.
    """
    # === Thread Identification ===
    thread_id: str              # Unique conversation thread ID
    patient_id: str             # Patient identifier
    session_id: Optional[str]   # Session ID for Redis

    # === Message History ===
    # Messages are managed by LangGraph with add_messages reducer
    # Format: List of BaseMessage (HumanMessage, AIMessage, SystemMessage)
    # CRITICAL: Using Annotated[list, add_messages] makes messages ACCUMULATE across turns
    messages: Annotated[list, add_messages]

    # === Conversation Mode ===
    mode: str                           # Current ConversationMode value
    previous_mode: Optional[str]        # Previous mode (for FOLLOW_UP routing)
    mode_turns: int                     # Turns spent in current mode

    # === Goal Tracking (GOAL_DRIVEN mode) ===
    active_goal: Optional[Dict[str, Any]]  # Serialized ActiveGoal
    goal_history: List[Dict[str, Any]]     # Completed goals this session

    # === Topic Tracking ===
    current_topics: List[str]     # Topics being discussed NOW
    explored_topics: List[str]    # Topics already covered
    topic_depth: Dict[str, int]   # How deep we've gone on each topic

    # === Patient Context ===
    patient_context: Dict[str, Any]  # Serialized PatientContext

    # === Turn Metadata ===
    turn_count: int                    # Total turns in this thread
    last_assistant_action: Optional[str]  # AssistantAction value
    last_user_intent: Optional[str]       # Classified intent from last message
    last_asked_slot: Optional[str]        # Name of slot last asked for (for clarification)
    is_clarification_request: bool        # True if user is asking for clarification
    is_request_refinement: bool           # True if user is correcting/refining their request
    refined_context: Optional[str]        # What the user actually wants (extracted when refining)

    # === Emotional/Urgency Tracking ===
    emotional_arc: List[str]    # EmotionalTone values over turns
    urgency_level: str          # Current UrgencyLevel value

    # === Session Flags ===
    has_greeted: bool           # True after greeting has been delivered (prevents double greeting)
    returning_user: bool        # True if patient has prior history (prevents re-introduction)

    # === Timestamps ===
    created_at: str             # ISO format datetime
    last_activity: str          # ISO format datetime

    # === Conversation Summary (Phase 2D) ===
    conversation_summary: Optional[str]  # Rolling summary of key points for long threads

    # === Episodic Context (Graphiti) ===
    episodic_context: Optional[Dict[str, Any]]  # Context from Graphiti episodic memory


def create_initial_state(
    thread_id: str,
    patient_id: str,
    session_id: Optional[str] = None,
    patient_context: Optional[PatientContext] = None
) -> ConversationState:
    """
    Create initial conversation state for a new thread.

    Args:
        thread_id: Unique thread identifier
        patient_id: Patient identifier
        session_id: Optional session ID
        patient_context: Optional pre-loaded patient context

    Returns:
        Initial ConversationState dict
    """
    now = datetime.now().isoformat()

    return ConversationState(
        thread_id=thread_id,
        patient_id=patient_id,
        session_id=session_id,
        messages=[],
        mode=ConversationMode.CASUAL_CHAT.value,
        previous_mode=None,
        mode_turns=0,
        active_goal=None,
        goal_history=[],
        current_topics=[],
        explored_topics=[],
        topic_depth={},
        patient_context=patient_context.__dict__ if patient_context else {},
        turn_count=0,
        last_assistant_action=None,
        last_user_intent=None,
        last_asked_slot=None,
        is_clarification_request=False,
        is_request_refinement=False,
        refined_context=None,
        emotional_arc=[EmotionalTone.NEUTRAL.value],
        urgency_level=UrgencyLevel.LOW.value,
        has_greeted=False,  # Prevents double greetings in a session
        created_at=now,
        last_activity=now,
        conversation_summary=None,
    )


def serialize_goal(goal: ActiveGoal) -> Dict[str, Any]:
    """Serialize ActiveGoal to dict for state storage."""
    return {
        "goal_type": goal.goal_type.value,
        "description": goal.description,
        "slots": {
            name: {
                "name": slot.name,
                "description": slot.description,
                "required": slot.required,
                "value": slot.value,
                "filled": slot.filled,
            }
            for name, slot in goal.slots.items()
        },
        "progress": goal.progress,
        "created_at": goal.created_at.isoformat(),
        "completed_at": goal.completed_at.isoformat() if goal.completed_at else None,
    }


def deserialize_goal(data: Dict[str, Any]) -> ActiveGoal:
    """Deserialize dict to ActiveGoal."""
    goal = ActiveGoal(
        goal_type=GoalType(data["goal_type"]),
        description=data["description"],
        progress=data["progress"],
        created_at=datetime.fromisoformat(data["created_at"]),
        completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
    )

    for name, slot_data in data.get("slots", {}).items():
        goal.slots[name] = GoalSlot(
            name=slot_data["name"],
            description=slot_data["description"],
            required=slot_data["required"],
            value=slot_data["value"],
            filled=slot_data["filled"],
        )

    return goal
