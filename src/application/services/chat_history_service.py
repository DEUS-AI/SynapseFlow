"""
Chat History Service - Manage conversation sessions and message history.

Provides session CRUD operations, message retrieval with pagination,
and integration with Phase 6 conversational layer for auto-titles
and intent-aware session metadata.

Supports dual-write to PostgreSQL for migration via feature flags.
Uses per-request database sessions for safe concurrent access.
"""

import logging
from typing import List, Optional, Dict, Any, Callable
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

logger = logging.getLogger(__name__)


class ChatHistoryService:
    """
    Service for managing chat history and session retrieval.

    Supports dual-write to PostgreSQL via feature flags:
    - dual_write_sessions: Write to both Neo4j and PostgreSQL
    - use_postgres_sessions: Read from PostgreSQL (migration complete)

    Uses a db_session_factory for per-request database sessions.
    """

    def __init__(
        self,
        patient_memory_service: PatientMemoryService,
        intent_service: Optional[ConversationalIntentService] = None,
        openai_api_key: Optional[str] = None,
        db_session_factory: Optional[Callable] = None,
    ):
        self.memory = patient_memory_service
        self.intent_service = intent_service
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self._db_session = db_session_factory

        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None

        if self._db_session:
            logger.info(
                "ChatHistoryService initialized with PostgreSQL support "
                f"(dual_write={dual_write_enabled('sessions')}, "
                f"use_postgres={use_postgres_sessions()})"
            )
        else:
            logger.info("ChatHistoryService initialized (Neo4j only)")

    @property
    def _has_postgres(self) -> bool:
        return self._db_session is not None

    # ------------------------------------------------------------------
    # List sessions
    # ------------------------------------------------------------------

    async def list_sessions(
        self,
        patient_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None
    ) -> SessionListResponse:
        logger.debug(f"Listing sessions for patient {patient_id} (limit={limit}, offset={offset})")

        if self._has_postgres and use_postgres_sessions():
            return await self._list_sessions_postgres(patient_id, limit, offset, status)

        sessions_data = await self.memory.get_sessions_by_patient(
            patient_id=patient_id, limit=limit, offset=offset, status=status
        )
        sessions = [SessionMetadata.from_dict(s) for s in sessions_data]
        response = SessionListResponse.group_by_time(sessions)
        response.has_more = len(sessions) == limit
        logger.info(f"Retrieved {len(sessions)} sessions for patient {patient_id}")
        return response

    async def _list_sessions_postgres(
        self, patient_id: str, limit: int, offset: int, status: Optional[str]
    ) -> SessionListResponse:
        from infrastructure.database.repositories import SessionRepository

        async with self._db_session() as session:
            repo = SessionRepository(session)
            pg_sessions = await repo.get_by_patient(
                patient_id=patient_id, status=status, limit=limit
            )

        sessions = []
        for pg_session in pg_sessions:
            sessions.append(SessionMetadata(
                session_id=f"session:{pg_session.id}",
                patient_id=pg_session.patient_id,
                title=pg_session.title,
                status=SessionStatus(pg_session.status) if pg_session.status else SessionStatus.ACTIVE,
                started_at=pg_session.created_at,
                last_activity=pg_session.last_activity or pg_session.created_at,
                message_count=pg_session.message_count or 0,
            ))

        response = SessionListResponse.group_by_time(sessions)
        response.has_more = len(sessions) == limit
        logger.info(f"Retrieved {len(sessions)} sessions from PostgreSQL for patient {patient_id}")
        return response

    # ------------------------------------------------------------------
    # Latest session
    # ------------------------------------------------------------------

    async def get_latest_session(self, patient_id: str) -> Optional[SessionMetadata]:
        sessions = await self.list_sessions(patient_id, limit=1, status="active")
        if sessions.sessions:
            logger.info(f"Found latest session: {sessions.sessions[0].session_id}")
            return sessions.sessions[0]
        logger.info(f"No active sessions found for patient {patient_id}")
        return None

    # ------------------------------------------------------------------
    # Session metadata
    # ------------------------------------------------------------------

    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        if self._has_postgres and use_postgres_sessions():
            return await self._get_session_metadata_postgres(session_id)

        session_data = await self.memory.get_session_by_id(session_id)
        if session_data:
            return SessionMetadata.from_dict(session_data)
        logger.warning(f"Session not found: {session_id}")
        return None

    async def _get_session_metadata_postgres(self, session_id: str) -> Optional[SessionMetadata]:
        from infrastructure.database.repositories import SessionRepository

        pg_uuid = self._extract_uuid_from_session_id(session_id)
        if not pg_uuid:
            return None

        async with self._db_session() as session:
            repo = SessionRepository(session)
            pg_session = await repo.get_by_id(pg_uuid)

        if not pg_session:
            logger.warning(f"Session not found in PostgreSQL: {session_id}")
            return None

        return SessionMetadata(
            session_id=f"session:{pg_session.id}",
            patient_id=pg_session.patient_id,
            title=pg_session.title,
            status=SessionStatus(pg_session.status) if pg_session.status else SessionStatus.ACTIVE,
            started_at=pg_session.created_at,
            last_activity=pg_session.last_activity or pg_session.created_at,
            message_count=pg_session.message_count or 0,
        )

    # ------------------------------------------------------------------
    # Session messages
    # ------------------------------------------------------------------

    async def get_session_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[Message]:
        logger.debug(f"Getting messages for session {session_id} (limit={limit}, offset={offset})")

        if self._has_postgres and use_postgres_sessions():
            return await self._get_session_messages_postgres(session_id, limit, offset)

        messages_data = await self.memory.get_messages_by_session(
            session_id=session_id, limit=limit, offset=offset
        )
        messages = [Message.from_dict(m) for m in messages_data]
        logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
        return messages

    async def _get_session_messages_postgres(
        self, session_id: str, limit: int, offset: int
    ) -> List[Message]:
        from infrastructure.database.repositories import MessageRepository

        pg_uuid = self._extract_uuid_from_session_id(session_id)
        if not pg_uuid:
            return []

        async with self._db_session() as session:
            repo = MessageRepository(session)
            pg_messages = await repo.get_by_session(
                session_id=pg_uuid, limit=limit, offset=offset
            )

        messages = []
        for pg_msg in pg_messages:
            messages.append(Message(
                id=str(pg_msg.id),
                session_id=session_id,
                role=pg_msg.role,
                content=pg_msg.content,
                timestamp=pg_msg.created_at,
                response_id=pg_msg.response_id,
            ))

        logger.info(f"Retrieved {len(messages)} messages from PostgreSQL for session {session_id}")
        return messages

    # ------------------------------------------------------------------
    # Create session
    # ------------------------------------------------------------------

    async def create_session(
        self, patient_id: str, title: Optional[str] = None, device: str = "web"
    ) -> str:
        session_uuid = uuid.uuid4()
        session_id = f"session:{session_uuid}"
        session_title = title or "New Conversation"

        logger.info(f"Creating new session {session_id} for patient {patient_id}")

        await self.memory.create_session(
            session_id=session_id,
            patient_id=patient_id,
            title=session_title,
            device_type=device
        )

        if self._has_postgres and dual_write_enabled("sessions"):
            await self._create_session_postgres(session_uuid, patient_id, session_title, device, session_id)

        return session_id

    async def create_session_postgres(
        self, session_id: str, patient_id: str, title: str = "New Conversation", device: str = "web"
    ) -> None:
        """Create session in Postgres only (idempotent). Used by WebSocket handler."""
        pg_uuid = self._extract_uuid_from_session_id(session_id)
        if pg_uuid:
            await self._create_session_postgres(pg_uuid, patient_id, title, device, session_id)

    async def _create_session_postgres(
        self, session_uuid: uuid.UUID, patient_id: str, title: str, device: str, neo4j_id: str
    ) -> None:
        try:
            from infrastructure.database.models import Session as PgSession
            from infrastructure.database.repositories import SessionRepository
            from sqlalchemy import text

            async with self._db_session() as session:
                # Use INSERT ... ON CONFLICT DO NOTHING for idempotency
                await session.execute(
                    text("""
                        INSERT INTO sessions (id, patient_id, title, status, metadata)
                        VALUES (:id, :patient_id, :title, 'active', :metadata)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": session_uuid,
                        "patient_id": patient_id,
                        "title": title,
                        "metadata": f'{{"device": "{device}", "neo4j_id": "{neo4j_id}"}}',
                    }
                )
            logger.debug(f"Postgres: Created session {neo4j_id}")
        except Exception as e:
            logger.error(f"Postgres session creation failed for {neo4j_id}: {e}")

    # ------------------------------------------------------------------
    # Store message
    # ------------------------------------------------------------------

    async def store_message(
        self,
        session_id: str,
        patient_id: str,
        role: str,
        content: str,
        response_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        postgres_only: bool = False,
    ) -> Optional[str]:
        from application.services.patient_memory_service import ConversationMessage

        message_id = response_id or f"msg:{uuid.uuid4()}"
        timestamp = datetime.now()

        logger.debug(f"Storing {role} message in session {session_id} (postgres_only={postgres_only})")

        if not postgres_only:
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

        # Write to PostgreSQL
        if self._has_postgres and (postgres_only or dual_write_enabled("sessions")):
            await self._store_message_postgres(
                session_id, patient_id, role, content, message_id, timestamp, metadata
            )

        return message_id

    async def _store_message_postgres(
        self,
        session_id: str,
        patient_id: str,
        role: str,
        content: str,
        message_id: str,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        try:
            from infrastructure.database.models import Message as PgMessage
            from infrastructure.database.repositories import MessageRepository, SessionRepository

            pg_uuid = self._extract_uuid_from_session_id(session_id)
            if not pg_uuid:
                return

            async with self._db_session() as session:
                msg_repo = MessageRepository(session)
                pg_message = PgMessage(
                    session_id=pg_uuid,
                    patient_id=patient_id,
                    role=role,
                    content=content,
                    created_at=timestamp,
                    response_id=message_id,
                    extra_data=metadata or {}
                )
                await msg_repo.create(pg_message)

                sess_repo = SessionRepository(session)
                await sess_repo.increment_message_count(pg_uuid)

            logger.debug(f"Postgres: Stored {role} message in session {session_id}")
        except Exception as e:
            logger.error(f"Postgres message write failed for session {session_id}: {e}")

    # ------------------------------------------------------------------
    # End session
    # ------------------------------------------------------------------

    async def end_session(self, session_id: str) -> bool:
        logger.info(f"Ending session {session_id}")

        success = await self.memory.update_session_status(
            session_id=session_id, status="ended", ended_at=datetime.now()
        )

        if self._has_postgres and dual_write_enabled("sessions"):
            try:
                from infrastructure.database.repositories import SessionRepository

                pg_uuid = self._extract_uuid_from_session_id(session_id)
                if pg_uuid:
                    async with self._db_session() as session:
                        repo = SessionRepository(session)
                        pg_session = await repo.get_by_id(pg_uuid)
                        if pg_session:
                            pg_session.status = "ended"
                            await repo.update(pg_session)
                            logger.debug(f"Postgres: Ended session {session_id}")
            except Exception as e:
                logger.error(f"Postgres end_session failed for {session_id}: {e}")

        return success

    # ------------------------------------------------------------------
    # Delete session
    # ------------------------------------------------------------------

    async def delete_session(self, session_id: str) -> bool:
        logger.warning(f"Deleting session {session_id} (GDPR)")
        success = await self.memory.delete_session(session_id)

        if self._has_postgres and dual_write_enabled("sessions"):
            try:
                from infrastructure.database.repositories import SessionRepository

                pg_uuid = self._extract_uuid_from_session_id(session_id)
                if pg_uuid:
                    async with self._db_session() as session:
                        repo = SessionRepository(session)
                        await repo.delete_by_id(pg_uuid)
                        logger.debug(f"Postgres: Deleted session {session_id}")
            except Exception as e:
                logger.error(f"Postgres delete failed for {session_id}: {e}")

        return success

    # ------------------------------------------------------------------
    # Title updates
    # ------------------------------------------------------------------

    async def update_title_postgres(self, session_id: str, title: str) -> None:
        """Update session title in PostgreSQL only."""
        if not self._has_postgres:
            return
        try:
            from infrastructure.database.repositories import SessionRepository

            pg_uuid = self._extract_uuid_from_session_id(session_id)
            if not pg_uuid:
                return

            async with self._db_session() as session:
                repo = SessionRepository(session)
                pg_session = await repo.get_by_id(pg_uuid)
                if pg_session:
                    pg_session.title = title
                    await repo.update(pg_session)
                    logger.debug(f"Postgres: Updated title for {session_id} to '{title}'")
        except Exception as e:
            logger.error(f"Postgres title update failed for {session_id}: {e}")

    # ------------------------------------------------------------------
    # Search sessions
    # ------------------------------------------------------------------

    async def search_sessions(
        self, patient_id: str, query: str, limit: int = 20
    ) -> List[SessionMetadata]:
        logger.debug(f"Searching sessions for patient {patient_id}: '{query}'")

        if self._has_postgres and use_postgres_sessions():
            return await self._search_sessions_postgres(patient_id, query, limit)

        sessions_data = await self.memory.search_sessions(
            patient_id=patient_id, query=query, limit=limit
        )
        sessions = [SessionMetadata.from_dict(s) for s in sessions_data]
        logger.info(f"Found {len(sessions)} sessions matching '{query}'")
        return sessions

    async def _search_sessions_postgres(
        self, patient_id: str, query: str, limit: int
    ) -> List[SessionMetadata]:
        from sqlalchemy import select, or_, distinct
        from infrastructure.database.models import Session as PgSession, Message as PgMessage
        from infrastructure.database.repositories import SessionRepository

        async with self._db_session() as session:
            # Find sessions where title or message content matches
            search_pattern = f"%{query}%"
            stmt = (
                select(PgSession)
                .outerjoin(PgMessage, PgSession.id == PgMessage.session_id)
                .where(PgSession.patient_id == patient_id)
                .where(
                    or_(
                        PgSession.title.ilike(search_pattern),
                        PgMessage.content.ilike(search_pattern),
                    )
                )
                .distinct()
                .order_by(PgSession.last_activity.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            pg_sessions = list(result.scalars().all())

        sessions = []
        for pg_session in pg_sessions:
            sessions.append(SessionMetadata(
                session_id=f"session:{pg_session.id}",
                patient_id=pg_session.patient_id,
                title=pg_session.title,
                status=SessionStatus(pg_session.status) if pg_session.status else SessionStatus.ACTIVE,
                started_at=pg_session.created_at,
                last_activity=pg_session.last_activity or pg_session.created_at,
                message_count=pg_session.message_count or 0,
            ))

        logger.info(f"Found {len(sessions)} sessions from PostgreSQL matching '{query}'")
        return sessions

    # ------------------------------------------------------------------
    # Auto-generate title
    # ------------------------------------------------------------------

    async def auto_generate_title(self, session_id: str) -> Optional[str]:
        logger.debug(f"Auto-generating title for session {session_id}")

        messages = await self.get_session_messages(session_id, limit=3)
        if not messages:
            return None

        first_user_msg = next((m for m in messages if m.is_user_message()), None)
        if not first_user_msg:
            return None

        # Try intent-based title first (fast)
        if self.intent_service:
            try:
                intent = await self.intent_service.classify(first_user_msg.content)
                if intent.topic_hint:
                    topic = intent.topic_hint.title()
                    if intent.intent_type.value == "symptom_report":
                        title = f"{topic} Discussion"
                    elif intent.intent_type.value == "medical_query":
                        title = f"{topic} Query"
                    else:
                        title = f"{topic}"

                    logger.info(f"Generated intent-based title: '{title}'")
                    success = await self.memory.update_session_title(session_id, title)
                    if success:
                        await self.update_title_postgres(session_id, title)
                        return title
                    else:
                        logger.warning(f"Failed to persist intent-based title for session {session_id}")
                        return None
            except Exception as e:
                logger.warning(f"Intent-based title generation failed: {e}")

        # Fallback to LLM generation
        if self.openai_client:
            try:
                message_context = "\n".join([f"{m.role}: {m.content}" for m in messages[:3]])
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Generate a short (3-5 word) title for this medical conversation. Be specific and descriptive."},
                        {"role": "user", "content": f"Conversation:\n{message_context}\n\nTitle:"}
                    ],
                    temperature=0.3,
                    max_tokens=20
                )
                title = response.choices[0].message.content.strip().strip('"')
                logger.info(f"Generated LLM-based title: '{title}'")

                success = await self.memory.update_session_title(session_id, title)
                if success:
                    await self.update_title_postgres(session_id, title)
                    return title
                else:
                    logger.warning(f"Failed to persist LLM-based title for session {session_id}")
                    return None
            except Exception as e:
                logger.error(f"LLM title generation failed: {e}")

        return None

    # ------------------------------------------------------------------
    # Session summary
    # ------------------------------------------------------------------

    async def get_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        if not self.openai_client:
            logger.warning("OpenAI client not available for summary generation")
            return None

        logger.debug(f"Generating summary for session {session_id}")
        messages = await self.get_session_messages(session_id, limit=1000)
        if not messages:
            return None

        message_context = "\n".join([f"{m.role}: {m.content}" for m in messages])

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
                    {"role": "user", "content": f"Conversation:\n{message_context}"}
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_uuid_from_session_id(self, session_id: str) -> Optional[uuid.UUID]:
        try:
            if session_id.startswith("session:"):
                return uuid.UUID(session_id[8:])
            return uuid.UUID(session_id)
        except ValueError:
            logger.warning(f"Could not extract UUID from session_id: {session_id}")
            return None
