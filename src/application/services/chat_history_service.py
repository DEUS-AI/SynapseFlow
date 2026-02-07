"""
Chat History Service - Manage conversation sessions and message history.

Provides session CRUD operations, message retrieval with pagination,
and integration with Phase 6 conversational layer for auto-titles
and intent-aware session metadata.

Supports dual-write to PostgreSQL for migration via feature flags.
"""

import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
import uuid

from domain.session_models import (
    SessionMetadata,
    SessionStatus,
    Message,
    SessionSummary,
    SessionListResponse
)
from application.services.patient_memory_service import PatientMemoryService
from application.services.conversational_intent_service import ConversationalIntentService
from application.services.feature_flag_service import (
    dual_write_enabled,
    use_postgres_sessions,
)
from openai import AsyncOpenAI
import os

if TYPE_CHECKING:
    from infrastructure.database.repositories import SessionRepository, MessageRepository

logger = logging.getLogger(__name__)


class ChatHistoryService:
    """
    Service for managing chat history and session retrieval.

    Integrates with Phase 6 conversational layer for:
    - Auto-generated session titles using intent classification
    - Session metadata enriched with topics and urgency
    - Memory-aware session resumption

    Supports dual-write to PostgreSQL via feature flags:
    - dual_write_sessions: Write to both Neo4j and PostgreSQL
    - use_postgres_sessions: Read from PostgreSQL (migration complete)
    """

    def __init__(
        self,
        patient_memory_service: PatientMemoryService,
        intent_service: Optional[ConversationalIntentService] = None,
        openai_api_key: Optional[str] = None,
        pg_session_repo: Optional["SessionRepository"] = None,
        pg_message_repo: Optional["MessageRepository"] = None,
    ):
        """
        Initialize chat history service.

        Args:
            patient_memory_service: Service for Neo4j and Mem0 operations
            intent_service: Optional intent classification for auto-titles
            openai_api_key: OpenAI API key for LLM summaries
            pg_session_repo: Optional PostgreSQL session repository for dual-write
            pg_message_repo: Optional PostgreSQL message repository for dual-write
        """
        self.memory = patient_memory_service
        self.intent_service = intent_service
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        # PostgreSQL repositories for dual-write/migration
        self.pg_session_repo = pg_session_repo
        self.pg_message_repo = pg_message_repo

        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None

        # Log migration mode
        if self.pg_session_repo:
            logger.info(
                "ChatHistoryService initialized with PostgreSQL support "
                f"(dual_write={dual_write_enabled('sessions')}, "
                f"use_postgres={use_postgres_sessions()})"
            )
        else:
            logger.info("ChatHistoryService initialized (Neo4j only)")

    async def list_sessions(
        self,
        patient_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None
    ) -> SessionListResponse:
        """
        List all sessions for a patient with time grouping.

        Reads from PostgreSQL when use_postgres_sessions flag is enabled.

        Args:
            patient_id: Patient identifier
            limit: Maximum sessions to return
            offset: Pagination offset
            status: Filter by status (active, ended, archived)

        Returns:
            SessionListResponse with grouped sessions
        """
        logger.debug(f"Listing sessions for patient {patient_id} (limit={limit}, offset={offset})")

        # Check if we should read from PostgreSQL
        if self.pg_session_repo and use_postgres_sessions():
            return await self._list_sessions_postgres(patient_id, limit, offset, status)

        # Default: Get sessions from Neo4j via PatientMemoryService
        sessions_data = await self.memory.get_sessions_by_patient(
            patient_id=patient_id,
            limit=limit,
            offset=offset,
            status=status
        )

        # Convert to SessionMetadata objects
        sessions = [SessionMetadata.from_dict(s) for s in sessions_data]

        # Group by time periods
        response = SessionListResponse.group_by_time(sessions)
        response.has_more = len(sessions) == limit  # More if we hit limit

        logger.info(f"Retrieved {len(sessions)} sessions for patient {patient_id}")
        return response

    async def _list_sessions_postgres(
        self,
        patient_id: str,
        limit: int,
        offset: int,
        status: Optional[str]
    ) -> SessionListResponse:
        """List sessions from PostgreSQL."""
        logger.debug(f"Listing sessions from PostgreSQL for patient {patient_id}")

        pg_sessions = await self.pg_session_repo.get_by_patient(
            patient_id=patient_id,
            status=status,
            limit=limit
        )

        # Convert to SessionMetadata objects
        sessions = []
        for pg_session in pg_sessions:
            session = SessionMetadata(
                session_id=f"session:{pg_session.id}",
                patient_id=pg_session.patient_id,
                title=pg_session.title,
                status=SessionStatus(pg_session.status) if pg_session.status else SessionStatus.ACTIVE,
                created_at=pg_session.created_at,
                updated_at=pg_session.updated_at,
                last_activity=pg_session.last_activity,
                message_count=pg_session.message_count or 0,
            )
            sessions.append(session)

        # Group by time periods
        response = SessionListResponse.group_by_time(sessions)
        response.has_more = len(sessions) == limit

        logger.info(f"Retrieved {len(sessions)} sessions from PostgreSQL for patient {patient_id}")
        return response

    async def get_latest_session(
        self,
        patient_id: str
    ) -> Optional[SessionMetadata]:
        """
        Get most recent active session for a patient.

        Used for auto-resume functionality.

        Args:
            patient_id: Patient identifier

        Returns:
            Most recent session or None
        """
        sessions = await self.list_sessions(patient_id, limit=1, status="active")

        if sessions.sessions:
            logger.info(f"Found latest session: {sessions.sessions[0].session_id}")
            return sessions.sessions[0]

        logger.info(f"No active sessions found for patient {patient_id}")
        return None

    async def get_session_metadata(
        self,
        session_id: str
    ) -> Optional[SessionMetadata]:
        """
        Get metadata for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            Session metadata or None
        """
        session_data = await self.memory.get_session_by_id(session_id)

        if session_data:
            return SessionMetadata.from_dict(session_data)

        logger.warning(f"Session not found: {session_id}")
        return None

    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """
        Get messages for a session with pagination.

        Returns messages ordered by timestamp (oldest first for display).
        Reads from PostgreSQL when use_postgres_sessions flag is enabled.

        Args:
            session_id: Session identifier
            limit: Maximum messages to return
            offset: Pagination offset

        Returns:
            List of messages
        """
        logger.debug(f"Getting messages for session {session_id} (limit={limit}, offset={offset})")

        # Check if we should read from PostgreSQL
        if self.pg_message_repo and use_postgres_sessions():
            return await self._get_session_messages_postgres(session_id, limit, offset)

        # Default: Get from Neo4j
        messages_data = await self.memory.get_messages_by_session(
            session_id=session_id,
            limit=limit,
            offset=offset
        )

        messages = [Message.from_dict(m) for m in messages_data]

        logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
        return messages

    async def _get_session_messages_postgres(
        self,
        session_id: str,
        limit: int,
        offset: int
    ) -> List[Message]:
        """Get messages from PostgreSQL."""
        logger.debug(f"Getting messages from PostgreSQL for session {session_id}")

        pg_uuid = self._extract_uuid_from_session_id(session_id)
        if not pg_uuid:
            return []

        pg_messages = await self.pg_message_repo.get_by_session(
            session_id=pg_uuid,
            limit=limit,
            offset=offset
        )

        messages = []
        for pg_msg in pg_messages:
            message = Message(
                message_id=str(pg_msg.id),
                role=pg_msg.role,
                content=pg_msg.content,
                timestamp=pg_msg.created_at,
                response_id=pg_msg.response_id,
            )
            messages.append(message)

        logger.info(f"Retrieved {len(messages)} messages from PostgreSQL for session {session_id}")
        return messages

    async def create_session(
        self,
        patient_id: str,
        title: Optional[str] = None,
        device: str = "web"
    ) -> str:
        """
        Create a new conversation session.

        Title will be auto-generated after 2-3 messages if not provided.

        Supports dual-write to PostgreSQL when feature flag is enabled.

        Args:
            patient_id: Patient identifier
            title: Optional session title
            device: Device type (web, mobile)

        Returns:
            New session ID
        """
        session_uuid = uuid.uuid4()
        session_id = f"session:{session_uuid}"
        session_title = title or "New Conversation"

        logger.info(f"Creating new session {session_id} for patient {patient_id}")

        # Create session in Neo4j (primary)
        await self.memory.create_session(
            session_id=session_id,
            patient_id=patient_id,
            title=session_title,
            device_type=device
        )

        # Dual-write to PostgreSQL if enabled
        if self.pg_session_repo and dual_write_enabled("sessions"):
            try:
                from infrastructure.database.models import Session as PgSession
                pg_session = PgSession(
                    id=session_uuid,
                    patient_id=patient_id,
                    title=session_title,
                    status="active",
                    extra_data={"device": device, "neo4j_id": session_id}
                )
                await self.pg_session_repo.create(pg_session)
                logger.debug(f"Dual-write: Created session {session_id} in PostgreSQL")
            except Exception as e:
                # Log but don't fail - Neo4j is primary
                logger.error(f"Dual-write to PostgreSQL failed for session {session_id}: {e}")

        return session_id

    async def store_message(
        self,
        session_id: str,
        patient_id: str,
        role: str,
        content: str,
        response_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Store a message in the conversation.

        Supports dual-write to PostgreSQL when feature flag is enabled.

        Args:
            session_id: Session identifier
            patient_id: Patient identifier
            role: Message role (user, assistant, system)
            content: Message content
            response_id: Optional ID for feedback attribution
            metadata: Optional message metadata

        Returns:
            Message ID or None
        """
        from application.services.patient_memory_service import ConversationMessage

        message_id = response_id or f"msg:{uuid.uuid4()}"
        timestamp = datetime.now()

        logger.debug(f"Storing {role} message in session {session_id}")

        # Store in Neo4j via PatientMemoryService (primary)
        try:
            await self.memory.store_message(
                ConversationMessage(
                    role=role,
                    content=content,
                    timestamp=timestamp,
                    patient_id=patient_id,
                    session_id=session_id,
                    metadata=metadata or {}
                )
            )
        except Exception as e:
            logger.error(f"Failed to store message in Neo4j: {e}")
            return None

        # Dual-write to PostgreSQL if enabled
        if self.pg_message_repo and dual_write_enabled("sessions"):
            try:
                from infrastructure.database.models import Message as PgMessage

                pg_uuid = self._extract_uuid_from_session_id(session_id)
                if pg_uuid:
                    pg_message = PgMessage(
                        session_id=pg_uuid,
                        patient_id=patient_id,
                        role=role,
                        content=content,
                        response_id=message_id,
                        extra_data=metadata or {}
                    )
                    await self.pg_message_repo.create(pg_message)
                    logger.debug(f"Dual-write: Stored message in PostgreSQL")

                    # Increment session message count
                    if self.pg_session_repo:
                        await self.pg_session_repo.increment_message_count(pg_uuid)

            except Exception as e:
                # Log but don't fail - Neo4j is primary
                logger.error(f"Dual-write to PostgreSQL failed for message: {e}")

        return message_id

    async def end_session(
        self,
        session_id: str
    ) -> bool:
        """
        Mark session as ended.

        Supports dual-write to PostgreSQL when feature flag is enabled.

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        logger.info(f"Ending session {session_id}")

        success = await self.memory.update_session_status(
            session_id=session_id,
            status="ended",
            ended_at=datetime.now()
        )

        # Dual-write to PostgreSQL if enabled
        if self.pg_session_repo and dual_write_enabled("sessions"):
            try:
                pg_uuid = self._extract_uuid_from_session_id(session_id)
                if pg_uuid:
                    pg_session = await self.pg_session_repo.get_by_id(pg_uuid)
                    if pg_session:
                        pg_session.status = "ended"
                        await self.pg_session_repo.update(pg_session)
                        logger.debug(f"Dual-write: Ended session {session_id} in PostgreSQL")
            except Exception as e:
                logger.error(f"Dual-write to PostgreSQL failed for end_session {session_id}: {e}")

        return success

    def _extract_uuid_from_session_id(self, session_id: str) -> Optional[uuid.UUID]:
        """Extract UUID from session ID string (e.g., 'session:uuid-here')."""
        try:
            if session_id.startswith("session:"):
                return uuid.UUID(session_id[8:])
            return uuid.UUID(session_id)
        except ValueError:
            logger.warning(f"Could not extract UUID from session_id: {session_id}")
            return None

    async def delete_session(
        self,
        session_id: str
    ) -> bool:
        """
        Delete session and all messages (GDPR compliance).

        Supports dual-write to PostgreSQL when feature flag is enabled.

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        logger.warning(f"Deleting session {session_id} (GDPR)")

        success = await self.memory.delete_session(session_id)

        # Dual-delete from PostgreSQL if enabled
        if self.pg_session_repo and dual_write_enabled("sessions"):
            try:
                pg_uuid = self._extract_uuid_from_session_id(session_id)
                if pg_uuid:
                    # Messages are cascade deleted in PostgreSQL
                    await self.pg_session_repo.delete_by_id(pg_uuid)
                    logger.debug(f"Dual-write: Deleted session {session_id} from PostgreSQL")
            except Exception as e:
                logger.error(f"Dual-delete from PostgreSQL failed for session {session_id}: {e}")

        return success

    async def search_sessions(
        self,
        patient_id: str,
        query: str,
        limit: int = 20
    ) -> List[SessionMetadata]:
        """
        Search sessions by content or title.

        Uses Neo4j full-text search on message content.

        Args:
            patient_id: Patient identifier
            query: Search query
            limit: Maximum results

        Returns:
            List of matching sessions
        """
        logger.debug(f"Searching sessions for patient {patient_id}: '{query}'")

        sessions_data = await self.memory.search_sessions(
            patient_id=patient_id,
            query=query,
            limit=limit
        )

        sessions = [SessionMetadata.from_dict(s) for s in sessions_data]

        logger.info(f"Found {len(sessions)} sessions matching '{query}'")
        return sessions

    async def auto_generate_title(
        self,
        session_id: str
    ) -> Optional[str]:
        """
        Auto-generate session title from first 2-3 messages.

        Uses Phase 6 intent classification for faster, more consistent titles.

        Strategy:
        1. Try intent-based title (fast, no LLM call)
        2. Fallback to LLM generation if no clear intent

        Args:
            session_id: Session identifier

        Returns:
            Generated title or None
        """
        logger.debug(f"Auto-generating title for session {session_id}")

        # Get first 3 messages
        messages = await self.get_session_messages(session_id, limit=3)

        if not messages:
            return None

        # Get first user message
        first_user_msg = next((m for m in messages if m.is_user_message()), None)

        if not first_user_msg:
            return None

        # Try intent-based title first (fast)
        if self.intent_service:
            try:
                intent = await self.intent_service.classify(first_user_msg.content)

                # Generate title from topic hint
                if intent.topic_hint:
                    # "knee" → "Knee Pain Discussion"
                    # "ibuprofen" → "Ibuprofen Query"
                    topic = intent.topic_hint.title()
                    if intent.intent_type.value == "symptom_report":
                        title = f"{topic} Discussion"
                    elif intent.intent_type.value == "medical_query":
                        title = f"{topic} Query"
                    else:
                        title = f"{topic}"

                    logger.info(f"Generated intent-based title: '{title}'")

                    # Update session title
                    success = await self.memory.update_session_title(session_id, title)
                    if success:
                        return title
                    else:
                        logger.warning(f"Failed to persist intent-based title for session {session_id}")
                        return None

            except Exception as e:
                logger.warning(f"Intent-based title generation failed: {e}")

        # Fallback to LLM generation
        if self.openai_client:
            try:
                # Build message context
                message_context = "\n".join([
                    f"{m.role}: {m.content}" for m in messages[:3]
                ])

                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "Generate a short (3-5 word) title for this medical conversation. Be specific and descriptive."
                        },
                        {
                            "role": "user",
                            "content": f"Conversation:\n{message_context}\n\nTitle:"
                        }
                    ],
                    temperature=0.3,
                    max_tokens=20
                )

                title = response.choices[0].message.content.strip().strip('"')
                logger.info(f"Generated LLM-based title: '{title}'")

                # Update session title
                success = await self.memory.update_session_title(session_id, title)
                if success:
                    return title
                else:
                    logger.warning(f"Failed to persist LLM-based title for session {session_id}")
                    return None

            except Exception as e:
                logger.error(f"LLM title generation failed: {e}")

        return None

    async def get_session_summary(
        self,
        session_id: str
    ) -> Optional[SessionSummary]:
        """
        Generate AI summary of session content.

        Args:
            session_id: Session identifier

        Returns:
            SessionSummary or None
        """
        if not self.openai_client:
            logger.warning("OpenAI client not available for summary generation")
            return None

        logger.debug(f"Generating summary for session {session_id}")

        # Get all messages
        messages = await self.get_session_messages(session_id, limit=1000)

        if not messages:
            return None

        # Build conversation context
        message_context = "\n".join([
            f"{m.role}: {m.content}" for m in messages
        ])

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Summarize this medical conversation in 2-3 sentences.

Extract:
- Key topics discussed
- Main symptoms mentioned
- Recommendations given
- Overall sentiment (concerned, grateful, frustrated, neutral)
- Whether follow-up is needed

Respond in JSON format:
{
  "summary": "...",
  "key_topics": ["...", "..."],
  "main_symptoms": ["...", "..."],
  "recommendations": ["...", "..."],
  "sentiment": "...",
  "requires_followup": true/false,
  "followup_reason": "..."
}"""
                    },
                    {
                        "role": "user",
                        "content": f"Conversation:\n{message_context}"
                    }
                ],
                temperature=0.3,
                max_tokens=300
            )

            import json
            result = json.loads(response.choices[0].message.content)

            summary = SessionSummary(
                session_id=session_id,
                summary_text=result["summary"],
                key_topics=result.get("key_topics", []),
                main_symptoms=result.get("main_symptoms", []),
                recommendations_given=result.get("recommendations", []),
                overall_sentiment=result.get("sentiment", "neutral"),
                requires_followup=result.get("requires_followup", False),
                followup_reason=result.get("followup_reason")
            )

            logger.info(f"Generated summary for session {session_id}")
            return summary

        except Exception as e:
            logger.error(f"Summary generation failed: {e}", exc_info=True)
            return None
