"""
Domain models for conversational agent personality layer.

Defines data structures for intent classification, memory context,
and agent persona configuration.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class IntentType(Enum):
    """User message intent types."""
    GREETING = "greeting"
    GREETING_RETURN = "greeting_return"
    SYMPTOM_REPORT = "symptom_report"
    FOLLOW_UP = "follow_up"
    MEDICAL_QUERY = "medical_query"
    CLARIFICATION = "clarification"
    ACKNOWLEDGMENT = "acknowledgment"
    FAREWELL = "farewell"
    UNKNOWN = "unknown"


class Urgency(Enum):
    """Message urgency level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IntentResult:
    """
    Result of intent classification.

    Contains the classified intent type, confidence score,
    and extracted metadata about the message.
    """
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0

    # Extracted metadata
    topic_hint: Optional[str] = None  # e.g., "knee pain", "medication"
    urgency: Urgency = Urgency.MEDIUM
    emotional_tone: Optional[str] = None  # e.g., "concerned", "grateful", "frustrated"

    # Additional context
    requires_medical_knowledge: bool = False
    requires_memory_context: bool = False

    def __post_init__(self):
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class MemoryContext:
    """
    Aggregated memory context for response generation.

    Combines recent conversation topics (Mem0), medical profile (Neo4j),
    and current session state (Redis) into a single context object.
    """
    patient_id: str
    patient_name: Optional[str] = None

    # Recent conversation topics (from Mem0)
    recent_topics: List[str] = field(default_factory=list)  # ["knee pain", "ibuprofen"]
    last_session_summary: Optional[str] = None
    days_since_last_session: Optional[int] = None
    last_session_date: Optional[datetime] = None

    # Medical profile (from Neo4j)
    active_conditions: List[str] = field(default_factory=list)
    current_medications: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)

    # Session state (from Redis)
    current_session_id: Optional[str] = None
    current_session_topics: List[str] = field(default_factory=list)
    conversation_turn_count: int = 0

    # Proactive context hints
    unresolved_symptoms: List[str] = field(default_factory=list)
    pending_followups: List[str] = field(default_factory=list)

    def has_history(self) -> bool:
        """Check if patient has any conversation history."""
        return bool(self.recent_topics or self.last_session_summary)

    def has_medical_history(self) -> bool:
        """Check if patient has any medical records."""
        return bool(self.active_conditions or self.current_medications or self.allergies)

    def is_returning_user(self) -> bool:
        """Check if this is a returning user (not first session)."""
        return self.days_since_last_session is not None

    def get_time_context(self) -> str:
        """Generate time-based greeting context."""
        if self.days_since_last_session is None:
            return ""

        days = self.days_since_last_session
        if days == 0:
            return "Good to see you again today"
        elif days == 1:
            return "It's been a day since we last spoke"
        elif days <= 3:
            return f"It's been {days} days"
        elif days <= 7:
            return "It's been about a week"
        else:
            return "It's been a while"


@dataclass
class AgentPersona:
    """
    Configurable agent personality settings.

    Defines the agent's tone, behavior flags, and response style
    for personalized interactions.
    """
    name: str = "Medical Assistant"
    tone: str = "warm_professional"  # warm_professional | clinical | friendly

    # Behavior flags
    use_patient_name: bool = True
    proactive_followups: bool = True
    show_empathy: bool = True
    use_casual_language: bool = False

    # Response style
    max_greeting_length: int = 50  # words
    include_safety_reminders: bool = True
    include_disclaimer: bool = True

    # Proactive behavior
    ask_followup_questions: bool = True
    mention_recent_topics: bool = True
    check_medication_adherence: bool = True

    def get_tone_description(self) -> str:
        """Get human-readable tone description for system prompts."""
        tone_descriptions = {
            "warm_professional": "warm, professional, and empathetic",
            "clinical": "clinical, precise, and professional",
            "friendly": "friendly, casual, and approachable"
        }
        return tone_descriptions.get(self.tone, "professional")

    def should_use_name(self, context: MemoryContext) -> bool:
        """Determine if patient name should be used in response."""
        return self.use_patient_name and context.patient_name is not None


@dataclass
class ConversationTurn:
    """
    Single turn in a conversation.

    Used for conversation state tracking and context management.
    """
    turn_number: int
    timestamp: datetime
    user_message: str
    intent: IntentResult
    agent_response: str
    memory_context: MemoryContext
    response_time_ms: Optional[float] = None

    # Metadata
    used_knowledge_graph: bool = False
    entities_mentioned: List[str] = field(default_factory=list)
    layers_traversed: List[str] = field(default_factory=list)


@dataclass
class PrivacySettings:
    """
    Patient privacy preferences for memory and personalization.

    Follows patterns from Claude/ChatGPT/Gemini for memory opt-out,
    transparency, and user control.
    """
    patient_id: str

    # Memory settings
    memory_enabled: bool = True
    proactive_mentions: bool = True
    show_memory_updates: bool = True

    # Data retention
    conversation_retention_days: int = 90
    allow_mem0_extraction: bool = True

    # Personalization
    use_name: bool = True
    contextual_greetings: bool = True

    # Audit trail
    log_memory_access: bool = True

    def is_temporary_chat(self) -> bool:
        """Check if this is a temporary chat session (no memory)."""
        return not self.memory_enabled

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "patient_id": self.patient_id,
            "memory_enabled": self.memory_enabled,
            "proactive_mentions": self.proactive_mentions,
            "show_memory_updates": self.show_memory_updates,
            "conversation_retention_days": self.conversation_retention_days,
            "allow_mem0_extraction": self.allow_mem0_extraction,
            "use_name": self.use_name,
            "contextual_greetings": self.contextual_greetings,
            "log_memory_access": self.log_memory_access
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrivacySettings":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def default(cls, patient_id: str) -> "PrivacySettings":
        """Create default privacy settings."""
        return cls(patient_id=patient_id)


# Response templates by intent type
RESPONSE_TEMPLATES = {
    IntentType.GREETING: {
        "with_memory": "Hello {name}! Good to see you. {proactive_context} How can I help you today?",
        "without_memory": "Hello! I'm your medical assistant. How can I help you today?"
    },
    IntentType.GREETING_RETURN: {
        "with_memory": "Welcome back, {name}! {time_context} {proactive_followup}",
        "without_memory": "Welcome back! How can I assist you today?"
    },
    IntentType.SYMPTOM_REPORT: {
        "with_memory": "I understand you're experiencing {symptom}. {context_connection} Let me help you with that.",
        "without_memory": "I'm sorry to hear that. Can you tell me more about what you're experiencing?"
    },
    IntentType.FOLLOW_UP: {
        "with_memory": "Good question about {topic}. {context_connection}",
        "without_memory": "Let me address that for you."
    },
    IntentType.MEDICAL_QUERY: {
        "with_memory": "Let me help you with that question about {topic}. {safety_context}",
        "without_memory": "Let me look that up for you."
    },
    IntentType.ACKNOWLEDGMENT: {
        "with_memory": "You're welcome, {name}! {next_steps_hint}",
        "without_memory": "You're welcome! Let me know if you need anything else."
    },
    IntentType.FAREWELL: {
        "with_memory": "Take care, {name}! {summary_hint}",
        "without_memory": "Take care! Feel free to come back anytime."
    }
}
