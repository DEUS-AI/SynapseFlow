"""
LangGraph Chat Service - Wrapper for ConversationGraph.

Provides a unified interface compatible with IntelligentChatService,
allowing it to be used as a drop-in replacement.

The service manages conversation threads and delegates to the
LangGraph ConversationGraph for multi-turn state management.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from application.services.conversation_graph import ConversationGraph
from application.services.intelligent_chat_service import Message, ChatResponse

logger = logging.getLogger(__name__)


class LangGraphChatService:
    """
    Chat service powered by LangGraph ConversationGraph.

    Provides the same interface as IntelligentChatService but uses
    LangGraph for state management and mode-based routing.
    """

    def __init__(
        self,
        conversation_graph: ConversationGraph,
        patient_memory_service=None,
    ):
        """
        Initialize the LangGraph chat service.

        Args:
            conversation_graph: Configured ConversationGraph instance
            patient_memory_service: Patient memory service for context
        """
        self.graph = conversation_graph
        self.patient_memory = patient_memory_service

        # Thread IDs are now deterministic (patient_id:session_id)
        # No mapping needed - the checkpointer uses thread_id directly

        logger.info("LangGraphChatService initialized")

    def _get_thread_id(self, patient_id: str, session_id: Optional[str]) -> str:
        """
        Get or create a thread ID for a conversation.

        Thread IDs are deterministic and based solely on patient+session,
        so they persist across server restarts and service recreations.

        IMPORTANT: Thread IDs must be consistent for conversation continuity.
        The checkpointer uses thread_id as the key for state storage.
        """
        if session_id:
            # Deterministic thread_id - no random UUID
            # This ensures the same patient+session always gets the same thread
            thread_id = f"thread:{patient_id}:{session_id}"
            logger.debug(f"Thread ID for {patient_id}:{session_id} -> {thread_id}")
            return thread_id
        else:
            # No session provided - use patient-only thread
            # This is less ideal but allows basic conversation continuity
            thread_id = f"thread:{patient_id}:default"
            logger.warning(f"No session_id provided, using default thread: {thread_id}")
            return thread_id

    async def query(
        self,
        question: str,
        conversation_history: Optional[List[Message]] = None,
        patient_id: Optional[str] = None,
        session_id: Optional[str] = None,
        response_id: Optional[str] = None,  # For feedback tracking
    ) -> ChatResponse:
        """
        Process a user question through the LangGraph conversation engine.

        This method provides the same interface as IntelligentChatService.query()
        but uses LangGraph for state management.

        Args:
            question: User's question/message
            conversation_history: Previous messages (used for context if no thread state)
            patient_id: Patient identifier
            session_id: Session identifier
            response_id: Response ID for feedback tracking (passed to graph for storage)

        Returns:
            ChatResponse with answer, confidence, sources, etc.
        """
        start_time = datetime.now()

        # Get thread ID for conversation continuity
        thread_id = self._get_thread_id(patient_id or "anonymous", session_id)

        logger.info(f"Processing message via LangGraph: patient={patient_id}, thread={thread_id}")

        try:
            # Process through conversation graph
            result = await self.graph.process_message(
                message=question,
                thread_id=thread_id,
                patient_id=patient_id or "anonymous",
                session_id=session_id,
                response_id=response_id,  # For feedback tracking
            )

            query_time = (datetime.now() - start_time).total_seconds()

            # Build ChatResponse
            response = ChatResponse(
                answer=result.get("response", "I apologize, I couldn't process your request."),
                confidence=self._calculate_confidence(result),
                sources=self._extract_sources(result),
                related_concepts=self._extract_related_concepts(result),
                reasoning_trail=self._build_reasoning_trail(result),
                query_time_seconds=query_time,
            )

            logger.info(
                f"LangGraph response generated: mode={result.get('mode')}, "
                f"turn={result.get('turn_count')}, time={query_time:.2f}s"
            )

            return response

        except Exception as e:
            logger.error(f"LangGraph query failed: {e}", exc_info=True)

            query_time = (datetime.now() - start_time).total_seconds()

            return ChatResponse(
                answer="I apologize, but I encountered an error processing your request. Please try again.",
                confidence=0.3,
                sources=[],
                related_concepts=[],
                reasoning_trail=[f"Error: {str(e)}"],
                query_time_seconds=query_time,
            )

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate confidence score from graph result."""
        # Base confidence by mode
        mode = result.get("mode", "casual_chat")
        mode_confidence = {
            "casual_chat": 0.9,
            "medical_consult": 0.75,
            "research_explore": 0.8,
            "goal_driven": 0.85,
            "closing": 0.95,
        }

        base = mode_confidence.get(mode, 0.7)

        # Boost if we have an active goal progressing
        if result.get("has_active_goal"):
            base = min(1.0, base + 0.05)

        return base

    def _extract_sources(self, result: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract sources from graph result."""
        sources = []

        # Topics can be considered as conceptual sources
        for topic in result.get("topics", [])[:3]:
            sources.append({
                "type": "Topic",
                "name": topic,
            })

        return sources

    def _extract_related_concepts(self, result: Dict[str, Any]) -> List[str]:
        """Extract related concepts from graph result."""
        return result.get("topics", [])[:5]

    def _build_reasoning_trail(self, result: Dict[str, Any]) -> List[str]:
        """Build reasoning trail from graph result."""
        trail = []

        mode = result.get("mode")
        if mode:
            trail.append(f"Conversation mode: {mode}")

        turn_count = result.get("turn_count")
        if turn_count:
            trail.append(f"Conversation turn: {turn_count}")

        urgency = result.get("urgency")
        if urgency and urgency != "low":
            trail.append(f"Urgency level: {urgency}")

        if result.get("has_active_goal"):
            trail.append("Active goal in progress")

        topics = result.get("topics", [])
        if topics:
            trail.append(f"Topics: {', '.join(topics[:3])}")

        return trail

    async def get_conversation_state(
        self,
        patient_id: str,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a conversation.

        Args:
            patient_id: Patient identifier
            session_id: Session identifier

        Returns:
            Current conversation state or None
        """
        thread_id = self._get_thread_id(patient_id, session_id)
        return await self.graph.get_conversation_state(thread_id)

    async def reset_conversation(
        self,
        patient_id: str,
        session_id: str,
    ) -> bool:
        """
        Reset a conversation to initial state.

        Args:
            patient_id: Patient identifier
            session_id: Session identifier

        Returns:
            True if reset successful
        """
        thread_id = self._get_thread_id(patient_id, session_id)

        # With deterministic thread IDs, reset is handled by the graph
        # which will clear the checkpointer state for this thread
        return await self.graph.reset_conversation(thread_id)

    async def query_stream(
        self,
        question: str,
        conversation_history: Optional[List[Message]] = None,
        patient_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        Process a user question with streaming response.

        This is the streaming version of query() for real-time response delivery.

        Args:
            question: User's question/message
            conversation_history: Previous messages
            patient_id: Patient identifier
            session_id: Session identifier

        Yields:
            Dict with response chunks and metadata
        """
        thread_id = self._get_thread_id(patient_id or "anonymous", session_id)

        logger.info(f"Streaming message via LangGraph: patient={patient_id}, thread={thread_id}")

        try:
            async for event in self.graph.process_message_stream(
                message=question,
                thread_id=thread_id,
                patient_id=patient_id or "anonymous",
                session_id=session_id,
            ):
                yield event

        except Exception as e:
            logger.error(f"Streaming query failed: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"Error: {str(e)}",
            }


async def create_langgraph_chat_service(
    patient_memory_service=None,
    neurosymbolic_service=None,
    episodic_memory_service=None,
    openai_api_key: Optional[str] = None,
) -> LangGraphChatService:
    """
    Factory function to create a LangGraphChatService.

    Args:
        patient_memory_service: Patient memory service
        neurosymbolic_service: Neurosymbolic query service
        episodic_memory_service: Graphiti-based episodic memory service
        openai_api_key: OpenAI API key

    Returns:
        Configured LangGraphChatService instance
    """
    from application.services.conversation_graph import build_conversation_graph

    graph = build_conversation_graph(
        patient_memory_service=patient_memory_service,
        neurosymbolic_service=neurosymbolic_service,
        episodic_memory_service=episodic_memory_service,
        openai_api_key=openai_api_key,
    )

    return LangGraphChatService(
        conversation_graph=graph,
        patient_memory_service=patient_memory_service,
    )
