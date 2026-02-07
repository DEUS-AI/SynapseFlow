"""
Conversation Graph - LangGraph-based Conversation Engine.

Assembles the conversation state machine using LangGraph,
connecting nodes with conditional routing based on mode.

Usage:
    graph = build_conversation_graph(
        patient_memory_service=memory_service,
        neurosymbolic_service=ns_service,
    )

    # Invoke with state
    result = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "patient:123:session:abc"}}
    )
"""

import logging
from typing import Optional, Any, Dict
import os
import json

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from domain.conversation_state import (
    ConversationState,
    ConversationMode,
    create_initial_state,
    PatientContext,
)
from application.services.conversation_nodes import ConversationNodes
from application.services.conversation_router import (
    route_by_mode,
    should_skip_synthesizer,
    should_persist_memory,
)

logger = logging.getLogger(__name__)


class ConversationGraph:
    """
    LangGraph-based conversation engine.

    Manages multi-turn conversations with mode-based routing,
    goal tracking, and memory persistence.
    """

    def __init__(
        self,
        patient_memory_service=None,
        neurosymbolic_service=None,
        episodic_memory_service=None,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o",
        checkpointer=None,
    ):
        """
        Initialize the conversation graph.

        Args:
            patient_memory_service: Service for patient memory operations
            neurosymbolic_service: Service for knowledge graph queries
            episodic_memory_service: Service for Graphiti-based episodic memory
            openai_api_key: OpenAI API key
            model: LLM model to use
            checkpointer: LangGraph checkpointer for state persistence
        """
        self.patient_memory = patient_memory_service
        self.neurosymbolic = neurosymbolic_service
        self.episodic_memory = episodic_memory_service
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

        # Initialize nodes
        self.nodes = ConversationNodes(
            openai_api_key=self.api_key,
            patient_memory_service=patient_memory_service,
            neurosymbolic_service=neurosymbolic_service,
            episodic_memory_service=episodic_memory_service,
            model=model,
        )

        # Build and compile the graph
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = self._build_graph()

        logger.info(f"ConversationGraph initialized with model={model}, episodic_memory={episodic_memory_service is not None}")

    def _build_graph(self) -> StateGraph:
        """
        Build the conversation state graph.

        Graph structure:
            entry -> classifier -> [mode nodes] -> synthesizer -> memory_persist -> END

        Returns:
            Compiled StateGraph
        """
        # Create graph with ConversationState schema
        graph = StateGraph(ConversationState)

        # Add nodes
        graph.add_node("entry", self.nodes.entry_node)
        graph.add_node("classifier", self.nodes.classifier_node)
        graph.add_node("casual_chat", self.nodes.casual_chat_node)
        graph.add_node("medical_consult", self.nodes.medical_consult_node)
        graph.add_node("research_explorer", self.nodes.research_explorer_node)
        graph.add_node("goal_driven", self.nodes.goal_driven_node)
        graph.add_node("closing", self.nodes.closing_node)
        graph.add_node("response_synthesizer", self.nodes.response_synthesizer_node)
        graph.add_node("memory_persist", self.nodes.memory_persist_node)

        # Set entry point
        graph.set_entry_point("entry")

        # Entry -> Classifier
        graph.add_edge("entry", "classifier")

        # Classifier -> Mode nodes (conditional routing)
        graph.add_conditional_edges(
            "classifier",
            route_by_mode,
            {
                "casual_chat": "casual_chat",
                "medical_consult": "medical_consult",
                "research_explorer": "research_explorer",
                "goal_driven": "goal_driven",
                "closing": "closing",
            }
        )

        # Mode nodes -> Response Synthesizer
        for mode_node in ["casual_chat", "medical_consult", "research_explorer", "goal_driven"]:
            graph.add_edge(mode_node, "response_synthesizer")

        # Closing -> Memory Persist (skip synthesizer)
        graph.add_edge("closing", "memory_persist")

        # Response Synthesizer -> Memory Persist
        graph.add_edge("response_synthesizer", "memory_persist")

        # Memory Persist -> END
        graph.add_edge("memory_persist", END)

        # Compile with checkpointer
        return graph.compile(checkpointer=self.checkpointer)

    async def process_message(
        self,
        message: str,
        thread_id: str,
        patient_id: str,
        session_id: Optional[str] = None,
        response_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the conversation graph.

        Args:
            message: User's message
            thread_id: Unique thread identifier for conversation continuity
            patient_id: Patient identifier
            session_id: Optional session identifier
            response_id: Optional response ID for feedback tracking

        Returns:
            Dict with response and metadata
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Check if this is a new conversation or continuation
        is_new = True
        loaded_turn_count = None
        loaded_message_count = 0

        try:
            current_state = await self.graph.aget_state(config)

            # Check if we have any meaningful state
            # A conversation exists if we have messages OR turn_count > 0
            loaded_turn_count = current_state.values.get("turn_count")
            loaded_messages = current_state.values.get("messages", [])
            loaded_message_count = len(loaded_messages)

            # More robust check: consider it an existing conversation if:
            # 1. We have messages in state, OR
            # 2. turn_count is not None and > 0
            has_state = loaded_message_count > 0 or (loaded_turn_count is not None and loaded_turn_count > 0)
            is_new = not has_state

            # Debug logging for state persistence
            print(f"[PROCESS_MSG] thread_id={thread_id}")
            print(f"[PROCESS_MSG] Loaded state: turn_count={loaded_turn_count}, messages={loaded_message_count}")
            print(f"[PROCESS_MSG] is_new={is_new} (has_state={has_state})")

            if not is_new:
                active_goal = current_state.values.get("active_goal")
                if active_goal:
                    print(f"[PROCESS_MSG] active_goal exists: type={active_goal.get('goal_type')}, progress={active_goal.get('progress')}")
                    for slot_name, slot_info in active_goal.get("slots", {}).items():
                        print(f"[PROCESS_MSG] Loaded slot '{slot_name}': filled={slot_info.get('filled')}, value={slot_info.get('value')}")
                else:
                    print("[PROCESS_MSG] No active_goal in loaded state")

                # Log loaded mode for debugging
                loaded_mode = current_state.values.get("mode")
                print(f"[PROCESS_MSG] Loaded mode: {loaded_mode}")

        except Exception as e:
            logger.warning(f"[PROCESS_MSG] Failed to get state for thread {thread_id}: {e}")
            print(f"[PROCESS_MSG] EXCEPTION getting state: {e}")
            is_new = True

        if is_new:
            print(f"[PROCESS_MSG] Creating NEW conversation for thread {thread_id}")
            # Create initial state for new conversation
            initial_state = create_initial_state(
                thread_id=thread_id,
                patient_id=patient_id,
                session_id=session_id,
            )
            # Add the user message
            initial_state["messages"] = [HumanMessage(content=message)]

            # Invoke graph with initial state
            result = await self.graph.ainvoke(initial_state, config)
        else:
            print(f"[PROCESS_MSG] CONTINUING conversation for thread {thread_id} (turn {loaded_turn_count} -> {(loaded_turn_count or 0) + 1})")
            # Continue existing conversation - just add new message
            # The checkpointer will automatically load existing state
            result = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=message)]},
                config
            )

        # Extract response
        messages = result.get("messages", [])
        response_text = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                response_text = msg.content
                break

        return {
            "response": response_text,
            "mode": result.get("mode"),
            "topics": result.get("current_topics", []),
            "turn_count": result.get("turn_count", 0),
            "urgency": result.get("urgency_level"),
            "has_active_goal": result.get("active_goal") is not None,
            "response_id": response_id,  # Pass through for feedback tracking
        }

    async def get_conversation_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a conversation.

        Args:
            thread_id: Thread identifier

        Returns:
            Current state dict or None if not found
        """
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = await self.graph.aget_state(config)
            return dict(state.values) if state else None
        except Exception as e:
            logger.warning(f"Failed to get conversation state: {e}")
            return None

    async def reset_conversation(self, thread_id: str) -> bool:
        """
        Reset a conversation to initial state.

        This clears all state for the given thread, forcing the next
        message to start a fresh conversation.

        Args:
            thread_id: Thread identifier

        Returns:
            True if reset successful
        """
        config = {"configurable": {"thread_id": thread_id}}

        try:
            # For MemorySaver, we need to clear the storage directly
            if hasattr(self.checkpointer, 'storage') and isinstance(self.checkpointer.storage, dict):
                # MemorySaver stores state with thread_id as part of the key
                keys_to_delete = [
                    key for key in self.checkpointer.storage.keys()
                    if thread_id in str(key)
                ]
                for key in keys_to_delete:
                    del self.checkpointer.storage[key]
                logger.info(f"Cleared {len(keys_to_delete)} state entries for thread {thread_id}")
            else:
                # For other checkpointers, we can't directly delete
                # The conversation will reset when a new initial state is provided
                # by forcing is_new=True in process_message
                logger.info(f"Conversation reset requested for thread {thread_id} (checkpointer type: {type(self.checkpointer).__name__})")

            return True

        except Exception as e:
            logger.warning(f"Failed to reset conversation for thread {thread_id}: {e}")
            return False

    async def process_message_stream(
        self,
        message: str,
        thread_id: str,
        patient_id: str,
        session_id: Optional[str] = None,
        response_id: Optional[str] = None,
    ):
        """
        Process a user message with streaming response.

        Yields partial responses as they're generated.

        Args:
            message: User's message
            thread_id: Unique thread identifier
            patient_id: Patient identifier
            session_id: Optional session identifier
            response_id: Optional response ID for feedback tracking

        Yields:
            Dict with partial response data
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Check if new conversation (same logic as process_message)
        is_new = True
        try:
            current_state = await self.graph.aget_state(config)
            loaded_turn_count = current_state.values.get("turn_count")
            loaded_messages = current_state.values.get("messages", [])

            # Consider it an existing conversation if we have messages or turn_count > 0
            has_state = len(loaded_messages) > 0 or (loaded_turn_count is not None and loaded_turn_count > 0)
            is_new = not has_state
        except Exception as e:
            logger.warning(f"[STREAM] Failed to get state: {e}")
            is_new = True

        if is_new:
            initial_state = create_initial_state(
                thread_id=thread_id,
                patient_id=patient_id,
                session_id=session_id,
            )
            initial_state["messages"] = [HumanMessage(content=message)]
            input_state = initial_state
        else:
            input_state = {"messages": [HumanMessage(content=message)]}

        # Stream the graph execution
        try:
            async for event in self.graph.astream(input_state, config, stream_mode="values"):
                # Yield intermediate state updates
                messages = event.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    if isinstance(last_msg, AIMessage):
                        yield {
                            "type": "response_chunk",
                            "content": last_msg.content,
                            "mode": event.get("mode"),
                            "turn_count": event.get("turn_count", 0),
                        }

            # Final yield with complete state
            final_state = await self.graph.aget_state(config)
            yield {
                "type": "response_complete",
                "mode": final_state.values.get("mode"),
                "topics": final_state.values.get("current_topics", []),
                "turn_count": final_state.values.get("turn_count", 0),
            }

        except Exception as e:
            logger.error(f"Stream processing error: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": str(e),
            }


def build_conversation_graph(
    patient_memory_service=None,
    neurosymbolic_service=None,
    episodic_memory_service=None,
    openai_api_key: Optional[str] = None,
    model: str = "gpt-4o",
    checkpointer=None,
) -> ConversationGraph:
    """
    Factory function to build a conversation graph.

    Args:
        patient_memory_service: Service for patient memory operations
        neurosymbolic_service: Service for knowledge graph queries
        episodic_memory_service: Service for Graphiti-based episodic memory
        openai_api_key: OpenAI API key
        model: LLM model to use
        checkpointer: LangGraph checkpointer for state persistence

    Returns:
        Configured ConversationGraph instance
    """
    return ConversationGraph(
        patient_memory_service=patient_memory_service,
        neurosymbolic_service=neurosymbolic_service,
        episodic_memory_service=episodic_memory_service,
        openai_api_key=openai_api_key,
        model=model,
        checkpointer=checkpointer,
    )


# ============================================================
# REDIS CHECKPOINTER (Optional - for production persistence)
# ============================================================

class RedisCheckpointer:
    """
    Redis-based checkpointer for LangGraph state persistence.

    This provides persistent conversation state across restarts,
    using Redis as the backing store.
    """

    def __init__(
        self,
        redis_client,
        prefix: str = "conv:",
        ttl: int = 86400 * 7,  # 7 days
    ):
        """
        Initialize Redis checkpointer.

        Args:
            redis_client: Redis client instance
            prefix: Key prefix for conversation states
            ttl: Time-to-live in seconds
        """
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = ttl

    def _key(self, thread_id: str) -> str:
        """Generate Redis key for thread."""
        return f"{self.prefix}{thread_id}"

    async def aget(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get state for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None

        try:
            data = await self.redis.get(self._key(thread_id))
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")

        return None

    async def aput(self, config: Dict[str, Any], state: Dict[str, Any]) -> None:
        """Save state for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return

        try:
            # Serialize messages for storage
            serialized = self._serialize_state(state)
            await self.redis.setex(
                self._key(thread_id),
                self.ttl,
                json.dumps(serialized)
            )
        except Exception as e:
            logger.warning(f"Redis put failed: {e}")

    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize state for JSON storage."""
        serialized = dict(state)

        # Convert messages to serializable format
        if "messages" in serialized:
            serialized["messages"] = [
                {
                    "type": type(msg).__name__,
                    "content": msg.content,
                }
                for msg in serialized["messages"]
            ]

        return serialized

    def _deserialize_state(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize state from JSON storage."""
        deserialized = dict(data)

        # Convert messages back to LangChain format
        if "messages" in deserialized:
            messages = []
            for msg_data in deserialized["messages"]:
                msg_type = msg_data.get("type", "HumanMessage")
                content = msg_data.get("content", "")

                if msg_type == "HumanMessage":
                    messages.append(HumanMessage(content=content))
                elif msg_type == "AIMessage":
                    messages.append(AIMessage(content=content))
                elif msg_type == "SystemMessage":
                    messages.append(SystemMessage(content=content))

            deserialized["messages"] = messages

        return deserialized
