"""
Domain models for chat session management.

Defines data structures for session metadata, message history,
and session summaries for chat history retrieval.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SessionStatus(Enum):
    """Session status types."""
    ACTIVE = "active"
    ENDED = "ended"
    ARCHIVED = "archived"


@dataclass
class SessionMetadata:
    """
    Metadata for a conversation session.

    Contains session information without full message history
    for efficient session listing.
    """
    session_id: str
    patient_id: str
    title: Optional[str] = None

    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    last_activity: datetime = field(default_factory=datetime.now)

    # Statistics
    message_count: int = 0
    status: SessionStatus = SessionStatus.ACTIVE

    # Context
    device_type: str = "web"

    # Preview (for session list)
    preview_text: Optional[str] = None  # First user message

    # Phase 6 integration: Intent and topics
    primary_intent: Optional[str] = None  # Main intent of session
    urgency: str = "medium"
    topics: List[str] = field(default_factory=list)  # From Mem0
    unresolved_symptoms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "title": self.title or "New Conversation",
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "message_count": self.message_count,
            "status": self.status.value,
            "device_type": self.device_type,
            "preview_text": self.preview_text,
            "primary_intent": self.primary_intent,
            "urgency": self.urgency,
            "topics": self.topics,
            "unresolved_symptoms": self.unresolved_symptoms
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        """Create from dictionary.

        Handles missing fields gracefully with sensible defaults.
        """
        # Handle different session_id field names
        session_id = data.get("session_id") or data.get("id") or "unknown"

        # Handle different patient_id field names
        patient_id = data.get("patient_id") or data.get("patient") or "unknown"

        return cls(
            session_id=session_id,
            patient_id=patient_id,
            title=data.get("title"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.now(),
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            last_activity=datetime.fromisoformat(data["last_activity"]) if data.get("last_activity") else datetime.now(),
            message_count=data.get("message_count", 0),
            status=SessionStatus(data.get("status", "active")),
            device_type=data.get("device_type", "web"),
            preview_text=data.get("preview_text"),
            primary_intent=data.get("primary_intent"),
            urgency=data.get("urgency", "medium"),
            topics=data.get("topics", []),
            unresolved_symptoms=data.get("unresolved_symptoms", [])
        )

    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.status == SessionStatus.ACTIVE

    def is_recent(self, days: int = 7) -> bool:
        """Check if session activity is within last N days."""
        if not self.last_activity:
            return False
        delta = datetime.now() - self.last_activity
        return delta.days <= days


@dataclass
class Message:
    """
    Single message in a conversation.

    Represents either user or assistant message with metadata.
    """
    id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Optional metadata
    patient_id: Optional[str] = None
    confidence: Optional[float] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)  # Array of source objects
    intent: Optional[str] = None
    urgency: Optional[str] = None

    # Additional metadata for response attribution
    reasoning_trail: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    response_id: Optional[str] = None  # For feedback tracking
    query_time: Optional[float] = None  # Response generation time in seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "patient_id": self.patient_id,
            "confidence": self.confidence,
            "sources": self.sources,
            "intent": self.intent,
            "urgency": self.urgency,
            "reasoning_trail": self.reasoning_trail,
            "related_concepts": self.related_concepts,
            "response_id": self.response_id,
            "query_time": self.query_time
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create from dictionary.

        Handles missing fields gracefully with sensible defaults.
        """
        # Handle different id field names
        msg_id = data.get("id") or data.get("message_id") or f"msg-{hash(data.get('content', ''))}"

        # Handle missing session_id gracefully
        session_id = data.get("session_id") or data.get("session") or "unknown"

        # Parse sources - handle both string arrays and object arrays
        raw_sources = data.get("sources", [])
        if raw_sources and isinstance(raw_sources[0], str):
            # Convert string sources to object format for consistency
            sources = [{"type": "KnowledgeGraph", "name": s} for s in raw_sources]
        else:
            sources = raw_sources if raw_sources else []

        return cls(
            id=msg_id,
            session_id=session_id,
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            patient_id=data.get("patient_id"),
            confidence=data.get("confidence"),
            sources=sources,
            intent=data.get("intent"),
            urgency=data.get("urgency"),
            reasoning_trail=data.get("reasoning_trail", []),
            related_concepts=data.get("related_concepts", []),
            response_id=data.get("response_id"),
            query_time=data.get("query_time")
        )

    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == "user"

    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == "assistant"


@dataclass
class SessionSummary:
    """
    AI-generated summary of a conversation session.

    Provides high-level overview of session content for
    quick understanding without reading full history.
    """
    session_id: str
    summary_text: str

    # Extracted information
    key_topics: List[str] = field(default_factory=list)
    main_symptoms: List[str] = field(default_factory=list)
    recommendations_given: List[str] = field(default_factory=list)

    # Sentiment
    overall_sentiment: str = "neutral"  # concerned, grateful, frustrated, etc.

    # Follow-up needed
    requires_followup: bool = False
    followup_reason: Optional[str] = None

    # Generation metadata
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "session_id": self.session_id,
            "summary_text": self.summary_text,
            "key_topics": self.key_topics,
            "main_symptoms": self.main_symptoms,
            "recommendations_given": self.recommendations_given,
            "overall_sentiment": self.overall_sentiment,
            "requires_followup": self.requires_followup,
            "followup_reason": self.followup_reason,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None
        }


@dataclass
class SessionListResponse:
    """
    Response for session list API endpoint.

    Contains sessions grouped by time periods with pagination.
    """
    sessions: List[SessionMetadata]
    total_count: int
    has_more: bool

    # Time-grouped sessions (for UI)
    today: List[SessionMetadata] = field(default_factory=list)
    yesterday: List[SessionMetadata] = field(default_factory=list)
    this_week: List[SessionMetadata] = field(default_factory=list)
    this_month: List[SessionMetadata] = field(default_factory=list)
    older: List[SessionMetadata] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "sessions": [s.to_dict() for s in self.sessions],
            "total_count": self.total_count,
            "has_more": self.has_more,
            "grouped": {
                "today": [s.to_dict() for s in self.today],
                "yesterday": [s.to_dict() for s in self.yesterday],
                "this_week": [s.to_dict() for s in self.this_week],
                "this_month": [s.to_dict() for s in self.this_month],
                "older": [s.to_dict() for s in self.older]
            }
        }

    @staticmethod
    def group_by_time(sessions: List[SessionMetadata]) -> "SessionListResponse":
        """Group sessions by time periods."""
        now = datetime.now()
        today = []
        yesterday = []
        this_week = []
        this_month = []
        older = []

        for session in sessions:
            if not session.last_activity:
                older.append(session)
                continue

            delta = now - session.last_activity

            if delta.days == 0:
                today.append(session)
            elif delta.days == 1:
                yesterday.append(session)
            elif delta.days <= 7:
                this_week.append(session)
            elif delta.days <= 30:
                this_month.append(session)
            else:
                older.append(session)

        return SessionListResponse(
            sessions=sessions,
            total_count=len(sessions),
            has_more=False,  # Set by caller based on pagination
            today=today,
            yesterday=yesterday,
            this_week=this_week,
            this_month=this_month,
            older=older
        )
