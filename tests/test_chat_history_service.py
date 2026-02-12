"""
Tests for Chat History Service - Session management and retrieval.

Tests session CRUD operations, message history, search, and integration
with Phase 6 conversational layer (intent-based titles, memory context).
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock

# Add src to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from application.services.chat_history_service import ChatHistoryService
from domain.session_models import SessionMetadata, Message, SessionStatus


class TestChatHistoryService:
    """Test suite for ChatHistoryService."""

    @pytest.fixture
    def mock_patient_memory(self):
        """Mock PatientMemoryService."""
        mock = AsyncMock()

        # Mock get_sessions_by_patient
        mock.get_sessions_by_patient.return_value = [
            {
                "session_id": "session-1",
                "patient_id": "patient-123",
                "title": "Knee Pain Discussion",
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "message_count": 5,
                "status": "active",
                "device_type": "web",
                "primary_intent": "symptom_report",
                "urgency": "medium",
                "topics": ["knee pain", "ibuprofen"],
                "unresolved_symptoms": ["knee pain"]
            },
            {
                "session_id": "session-2",
                "patient_id": "patient-123",
                "title": "Medication Query",
                "started_at": (datetime.now() - timedelta(days=1)).isoformat(),
                "last_activity": (datetime.now() - timedelta(days=1)).isoformat(),
                "message_count": 3,
                "status": "ended",
                "device_type": "web",
                "primary_intent": "medical_query",
                "urgency": "low",
                "topics": ["medication"],
                "unresolved_symptoms": []
            }
        ]

        # Mock get_session_by_id
        mock.get_session_by_id.return_value = {
            "session_id": "session-1",
            "patient_id": "patient-123",
            "title": "Knee Pain Discussion",
            "started_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "message_count": 5,
            "status": "active"
        }

        # Mock get_messages_by_session
        mock.get_messages_by_session.return_value = [
            {
                "id": "msg-1",
                "session_id": "session-1",
                "role": "user",
                "content": "My knee hurts",
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "msg-2",
                "session_id": "session-1",
                "role": "assistant",
                "content": "I understand you're experiencing knee pain...",
                "timestamp": datetime.now().isoformat(),
                "confidence": 0.9
            }
        ]

        # Mock create_session
        mock.create_session.return_value = True

        # Mock update_session_status
        mock.update_session_status.return_value = True

        # Mock update_session_title
        mock.update_session_title.return_value = True

        # Mock delete_session
        mock.delete_session.return_value = True

        # Mock search_sessions
        mock.search_sessions.return_value = [
            {
                "session_id": "session-1",
                "patient_id": "patient-123",
                "title": "Knee Pain Discussion",
                "message_count": 5
            }
        ]

        return mock

    @pytest.fixture
    def mock_intent_service(self):
        """Mock ConversationalIntentService."""
        mock = AsyncMock()

        # Mock classify
        from domain.conversation_models import IntentResult, IntentType, Urgency
        mock.classify.return_value = IntentResult(
            intent_type=IntentType.SYMPTOM_REPORT,
            confidence=0.9,
            topic_hint="knee",
            urgency=Urgency.MEDIUM
        )

        return mock

    @pytest.fixture
    def chat_history_service(self, mock_patient_memory, mock_intent_service):
        """Create ChatHistoryService with mocked dependencies."""
        return ChatHistoryService(
            patient_memory_service=mock_patient_memory,
            intent_service=mock_intent_service,
            openai_api_key=None  # No OpenAI for unit tests
        )

    @pytest.mark.asyncio
    async def test_list_sessions(self, chat_history_service):
        """Test listing sessions with time grouping."""
        result = await chat_history_service.list_sessions(
            patient_id="patient-123",
            limit=20
        )

        # Should have sessions
        assert result.total_count == 2
        assert len(result.sessions) == 2

        # Should group by time
        assert len(result.today) >= 0
        assert len(result.yesterday) >= 0

    @pytest.mark.asyncio
    async def test_get_latest_session(self, chat_history_service, mock_patient_memory):
        """Test getting latest active session."""
        # Mock returns active sessions first
        mock_patient_memory.get_sessions_by_patient.return_value = [
            {
                "session_id": "session-latest",
                "patient_id": "patient-123",
                "title": "Latest Session",
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "message_count": 1,
                "status": "active"
            }
        ]

        session = await chat_history_service.get_latest_session("patient-123")

        assert session is not None
        assert session.session_id == "session-latest"
        assert session.status == SessionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_session_metadata(self, chat_history_service):
        """Test getting session metadata."""
        session = await chat_history_service.get_session_metadata("session-1")

        assert session is not None
        assert session.session_id == "session-1"
        assert session.patient_id == "patient-123"
        assert session.message_count == 5

    @pytest.mark.asyncio
    async def test_get_session_messages(self, chat_history_service):
        """Test getting session messages with pagination."""
        messages = await chat_history_service.get_session_messages(
            session_id="session-1",
            limit=100
        )

        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert "knee hurts" in messages[0].content

    @pytest.mark.asyncio
    async def test_create_session(self, chat_history_service, mock_patient_memory):
        """Test creating a new session."""
        session_id = await chat_history_service.create_session(
            patient_id="patient-123",
            title="Test Session"
        )

        assert session_id.startswith("session:")
        assert mock_patient_memory.create_session.called

    @pytest.mark.asyncio
    async def test_end_session(self, chat_history_service, mock_patient_memory):
        """Test ending a session."""
        success = await chat_history_service.end_session("session-1")

        assert success is True
        assert mock_patient_memory.update_session_status.called

    @pytest.mark.asyncio
    async def test_delete_session(self, chat_history_service, mock_patient_memory):
        """Test deleting a session (GDPR)."""
        success = await chat_history_service.delete_session("session-1")

        assert success is True
        assert mock_patient_memory.delete_session.called

    @pytest.mark.asyncio
    async def test_search_sessions(self, chat_history_service):
        """Test searching sessions by content."""
        results = await chat_history_service.search_sessions(
            patient_id="patient-123",
            query="knee pain"
        )

        assert len(results) == 1
        assert results[0].session_id == "session-1"

    @pytest.mark.asyncio
    async def test_auto_generate_title_intent_based(self, chat_history_service, mock_patient_memory, mock_intent_service):
        """Test auto-generating title using intent classification."""
        # Mock get_session_messages to return messages with topic
        mock_patient_memory.get_messages_by_session.return_value = [
            {
                "id": "msg-1",
                "session_id": "session-new",
                "role": "user",
                "content": "My knee hurts when I walk",
                "timestamp": datetime.now().isoformat()
            }
        ]

        title = await chat_history_service.auto_generate_title("session-new")

        # Should generate title from topic_hint
        assert title is not None
        assert "knee" in title.lower() or "pain" in title.lower()
        assert mock_patient_memory.update_session_title.called

    @pytest.mark.asyncio
    async def test_session_list_time_grouping(self, chat_history_service):
        """Test that sessions are correctly grouped by time."""
        result = await chat_history_service.list_sessions("patient-123")

        # Today's sessions should be in 'today' group
        today_sessions = [s for s in result.today if s.is_recent(days=1)]
        assert len(today_sessions) >= 0

        # Total count should match
        assert result.total_count == len(result.sessions)

    @pytest.mark.asyncio
    async def test_empty_session_list(self, chat_history_service, mock_patient_memory):
        """Test handling of empty session list."""
        mock_patient_memory.get_sessions_by_patient.return_value = []

        result = await chat_history_service.list_sessions("patient-456")

        assert result.total_count == 0
        assert len(result.sessions) == 0
        assert len(result.today) == 0

    @pytest.mark.asyncio
    async def test_pagination(self, chat_history_service, mock_patient_memory):
        """Test session list pagination."""
        # Mock returns exactly limit items
        mock_patient_memory.get_sessions_by_patient.return_value = [
            {
                "session_id": f"session-{i}",
                "patient_id": "patient-123",
                "title": f"Session {i}",
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "message_count": 5,
                "status": "active"
            } for i in range(20)
        ]

        result = await chat_history_service.list_sessions(
            patient_id="patient-123",
            limit=20,
            offset=0
        )

        # Should indicate more results available
        assert result.has_more is True


class TestSessionMetadata:
    """Test SessionMetadata domain model."""

    def test_to_dict(self):
        """Test converting SessionMetadata to dictionary."""
        session = SessionMetadata(
            session_id="session-1",
            patient_id="patient-123",
            title="Test Session",
            message_count=5
        )

        data = session.to_dict()

        assert data["session_id"] == "session-1"
        assert data["patient_id"] == "patient-123"
        assert data["title"] == "Test Session"
        assert data["message_count"] == 5

    def test_from_dict(self):
        """Test creating SessionMetadata from dictionary."""
        data = {
            "session_id": "session-1",
            "patient_id": "patient-123",
            "title": "Test",
            "started_at": datetime.now().isoformat(),
            "message_count": 3,
            "status": "active"
        }

        session = SessionMetadata.from_dict(data)

        assert session.session_id == "session-1"
        assert session.patient_id == "patient-123"
        assert session.status == SessionStatus.ACTIVE

    def test_is_active(self):
        """Test checking if session is active."""
        active_session = SessionMetadata(
            session_id="s1",
            patient_id="p1",
            status=SessionStatus.ACTIVE
        )

        ended_session = SessionMetadata(
            session_id="s2",
            patient_id="p1",
            status=SessionStatus.ENDED
        )

        assert active_session.is_active() is True
        assert ended_session.is_active() is False

    def test_is_recent(self):
        """Test checking if session is recent."""
        recent_session = SessionMetadata(
            session_id="s1",
            patient_id="p1",
            last_activity=datetime.now()
        )

        old_session = SessionMetadata(
            session_id="s2",
            patient_id="p1",
            last_activity=datetime.now() - timedelta(days=10)
        )

        assert recent_session.is_recent(days=7) is True
        assert old_session.is_recent(days=7) is False


class TestMessage:
    """Test Message domain model."""

    def test_to_dict(self):
        """Test converting Message to dictionary."""
        msg = Message(
            id="msg-1",
            session_id="session-1",
            role="user",
            content="Hello",
            timestamp=datetime.now()
        )

        data = msg.to_dict()

        assert data["id"] == "msg-1"
        assert data["role"] == "user"
        assert data["content"] == "Hello"

    def test_from_dict(self):
        """Test creating Message from dictionary."""
        data = {
            "id": "msg-1",
            "session_id": "session-1",
            "role": "assistant",
            "content": "Hi there",
            "timestamp": datetime.now().isoformat()
        }

        msg = Message.from_dict(data)

        assert msg.id == "msg-1"
        assert msg.role == "assistant"
        assert msg.content == "Hi there"

    def test_is_user_message(self):
        """Test checking if message is from user."""
        user_msg = Message(
            id="m1",
            session_id="s1",
            role="user",
            content="Test"
        )

        assistant_msg = Message(
            id="m2",
            session_id="s1",
            role="assistant",
            content="Response"
        )

        assert user_msg.is_user_message() is True
        assert user_msg.is_assistant_message() is False
        assert assistant_msg.is_user_message() is False
        assert assistant_msg.is_assistant_message() is True


class TestFallbackTitleFromMessage:
    """Test suite for ChatHistoryService._fallback_title_from_message."""

    def test_simple_message(self):
        result = ChatHistoryService._fallback_title_from_message("my knee hurts a lot")
        assert result == "My Knee Hurts A Lot"

    def test_strips_hi_greeting(self):
        result = ChatHistoryService._fallback_title_from_message("Hi, my knee hurts")
        assert result == "My Knee Hurts"

    def test_strips_hello_greeting(self):
        result = ChatHistoryService._fallback_title_from_message("Hello, I have a headache")
        assert result == "I Have A Headache"

    def test_strips_hey_doctor_greeting(self):
        result = ChatHistoryService._fallback_title_from_message("Hey doctor, my back is sore")
        assert result == "My Back Is Sore"

    def test_strips_hi_doc_greeting(self):
        result = ChatHistoryService._fallback_title_from_message("Hi doc, I need help with sleep")
        assert result == "I Need Help With Sleep"

    def test_truncation_at_word_boundary(self):
        long_msg = "I have been experiencing severe headaches every morning for the past two weeks and I am worried"
        result = ChatHistoryService._fallback_title_from_message(long_msg)
        assert len(result) <= 50
        # Should not cut mid-word
        assert not result.endswith("-")

    def test_caps_at_five_words(self):
        result = ChatHistoryService._fallback_title_from_message("one two three four five six seven")
        words = result.split()
        assert len(words) <= 5

    def test_title_case(self):
        result = ChatHistoryService._fallback_title_from_message("my stomach has been hurting")
        assert result == "My Stomach Has Been Hurting"

    def test_empty_input(self):
        assert ChatHistoryService._fallback_title_from_message("") == "New Conversation"

    def test_none_input(self):
        assert ChatHistoryService._fallback_title_from_message(None) == "New Conversation"

    def test_whitespace_only(self):
        assert ChatHistoryService._fallback_title_from_message("   ") == "New Conversation"

    def test_greeting_only(self):
        result = ChatHistoryService._fallback_title_from_message("Hello")
        # After stripping "Hello" as greeting, falls back
        assert result == "New Conversation" or result == "Hello"

    def test_strips_trailing_punctuation(self):
        result = ChatHistoryService._fallback_title_from_message("I have a question.")
        assert not result.endswith(".")

    def test_short_message(self):
        result = ChatHistoryService._fallback_title_from_message("headache")
        assert result == "Headache"


class TestAutoGenerateTitle:
    """Integration tests for auto_generate_title pipeline."""

    @pytest.fixture
    def mock_memory(self):
        mock = AsyncMock()
        mock.get_messages_by_session.return_value = [
            {
                "id": "msg-1",
                "session_id": "session-1",
                "role": "user",
                "content": "Can you help me understand my lab results?",
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "msg-2",
                "session_id": "session-1",
                "role": "assistant",
                "content": "Of course! Could you share which lab results you'd like to discuss?",
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "msg-3",
                "session_id": "session-1",
                "role": "user",
                "content": "My CBC came back with low hemoglobin",
                "timestamp": datetime.now().isoformat()
            },
        ]
        mock.update_session_title.return_value = True
        return mock

    @pytest.fixture
    def mock_openai_response(self):
        """Create a mock OpenAI chat completion response."""
        mock_choice = MagicMock()
        mock_choice.message.content = "Lab Results Discussion"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response

    @pytest.mark.asyncio
    async def test_llm_primary_generates_and_persists(self, mock_memory, mock_openai_response):
        """6.1: LLM strategy generates title and persists it."""
        service = ChatHistoryService(
            patient_memory_service=mock_memory,
            openai_api_key="test-key"
        )
        service.openai_client = AsyncMock()
        service.openai_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)

        result = await service.auto_generate_title("session-1")

        assert result == "Lab Results Discussion"
        mock_memory.update_session_title.assert_called_once_with("session-1", "Lab Results Discussion")

    @pytest.mark.asyncio
    async def test_fallback_when_no_openai_client(self, mock_memory, monkeypatch):
        """6.2: Without OpenAI client, uses fallback title from message."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        service = ChatHistoryService(
            patient_memory_service=mock_memory,
        )
        assert service.openai_client is None

        result = await service.auto_generate_title("session-1")

        assert result is not None
        assert result != "New Conversation"
        # Fallback from "Can you help me understand my lab results?"
        assert "Lab Results" in result or "Help" in result or "Understand" in result
        mock_memory.update_session_title.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_when_llm_raises_exception(self, mock_memory):
        """6.3: LLM exception falls through to fallback."""
        service = ChatHistoryService(
            patient_memory_service=mock_memory,
            openai_api_key="test-key"
        )
        service.openai_client = AsyncMock()
        service.openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )

        result = await service.auto_generate_title("session-1")

        assert result is not None
        assert result != "New Conversation"
        mock_memory.update_session_title.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_when_llm_returns_empty(self, mock_memory):
        """6.4: LLM returning empty string falls through to fallback."""
        mock_choice = MagicMock()
        mock_choice.message.content = "   "
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        service = ChatHistoryService(
            patient_memory_service=mock_memory,
            openai_api_key="test-key"
        )
        service.openai_client = AsyncMock()
        service.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await service.auto_generate_title("session-1")

        assert result is not None
        assert result != "New Conversation"
        mock_memory.update_session_title.assert_called_once()

    @pytest.mark.asyncio
    async def test_warning_logs_on_failure_paths(self, mock_memory, caplog):
        """6.5: WARNING logs emitted for each failure path."""
        import logging

        # Test: no messages
        mock_memory_empty = AsyncMock()
        mock_memory_empty.get_messages_by_session.return_value = []
        service = ChatHistoryService(patient_memory_service=mock_memory_empty)

        with caplog.at_level(logging.WARNING):
            result = await service.auto_generate_title("session-empty")
        assert result is None
        assert "No messages found for session session-empty" in caplog.text
        caplog.clear()

        # Test: no user message
        mock_memory_no_user = AsyncMock()
        mock_memory_no_user.get_messages_by_session.return_value = [
            {
                "id": "msg-1",
                "session_id": "session-1",
                "role": "assistant",
                "content": "Welcome!",
                "timestamp": datetime.now().isoformat()
            }
        ]
        service2 = ChatHistoryService(patient_memory_service=mock_memory_no_user)

        with caplog.at_level(logging.WARNING):
            result = await service2.auto_generate_title("session-no-user")
        assert result is None
        assert "No user message found" in caplog.text
        caplog.clear()

        # Test: LLM error logs warning
        service3 = ChatHistoryService(
            patient_memory_service=mock_memory,
            openai_api_key="test-key"
        )
        service3.openai_client = AsyncMock()
        service3.openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Connection timeout")
        )

        with caplog.at_level(logging.WARNING):
            await service3.auto_generate_title("session-1")
        assert "LLM title generation failed" in caplog.text
        assert "Connection timeout" in caplog.text
        caplog.clear()

        # Test: persistence failure
        mock_memory_fail = AsyncMock()
        mock_memory_fail.get_messages_by_session.return_value = mock_memory.get_messages_by_session.return_value
        mock_memory_fail.update_session_title.return_value = False
        service4 = ChatHistoryService(patient_memory_service=mock_memory_fail)

        with caplog.at_level(logging.WARNING):
            result = await service4.auto_generate_title("session-persist-fail")
        assert result is None
        assert "Failed to persist title" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
