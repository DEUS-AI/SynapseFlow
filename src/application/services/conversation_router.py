"""
Conversation Router for LangGraph-based Conversation Engine.

Implements conditional routing logic for the conversation graph
based on conversation mode, urgency, and state.
"""

import logging
from typing import Literal

from domain.conversation_state import (
    ConversationState,
    ConversationMode,
    UrgencyLevel,
)

logger = logging.getLogger(__name__)


# Type alias for node names
NodeName = Literal[
    "casual_chat",
    "medical_consult",
    "research_explorer",
    "goal_driven",
    "closing",
    "emergency",
]


def route_by_mode(state: ConversationState) -> NodeName:
    """
    Route to appropriate node based on conversation mode.

    This is the main routing function called after classification.
    It determines which mode-specific node should handle the
    current turn.

    Args:
        state: Current conversation state

    Returns:
        Name of the node to route to
    """
    mode = state.get("mode", ConversationMode.CASUAL_CHAT.value)
    urgency = state.get("urgency_level", UrgencyLevel.LOW.value)
    previous_mode = state.get("previous_mode")

    logger.debug(f"Routing: mode={mode}, urgency={urgency}, previous_mode={previous_mode}")

    # Check for urgency override - critical urgency always goes to medical
    if urgency == UrgencyLevel.CRITICAL.value:
        logger.info("Critical urgency detected - routing to medical_consult")
        return "medical_consult"

    # Route by mode
    if mode == ConversationMode.CLOSING.value:
        return "closing"

    elif mode == ConversationMode.CASUAL_CHAT.value:
        return "casual_chat"

    elif mode == ConversationMode.MEDICAL_CONSULT.value:
        return "medical_consult"

    elif mode == ConversationMode.RESEARCH_EXPLORE.value:
        return "research_explorer"

    elif mode == ConversationMode.GOAL_DRIVEN.value:
        return "goal_driven"

    elif mode == ConversationMode.FOLLOW_UP.value:
        # Route follow-ups to the previous mode's handler
        return _route_follow_up(previous_mode)

    else:
        # Default to casual chat for unknown modes
        logger.warning(f"Unknown mode '{mode}', defaulting to casual_chat")
        return "casual_chat"


def _route_follow_up(previous_mode: str | None) -> NodeName:
    """
    Route follow-up messages to the appropriate handler.

    Follow-ups should continue the context of the previous mode.

    Args:
        previous_mode: The mode before the follow-up

    Returns:
        Name of the node to route to
    """
    if not previous_mode:
        # No previous mode context - treat as casual
        return "casual_chat"

    if previous_mode == ConversationMode.MEDICAL_CONSULT.value:
        return "medical_consult"

    elif previous_mode == ConversationMode.RESEARCH_EXPLORE.value:
        return "research_explorer"

    elif previous_mode == ConversationMode.GOAL_DRIVEN.value:
        return "goal_driven"

    else:
        return "casual_chat"


def should_skip_synthesizer(state: ConversationState) -> bool:
    """
    Determine if the response synthesizer should be skipped.

    Some modes (like closing) produce final responses that
    don't need additional synthesis.

    Args:
        state: Current conversation state

    Returns:
        True if synthesizer should be skipped
    """
    mode = state.get("mode", ConversationMode.CASUAL_CHAT.value)

    # Skip synthesizer for closing messages
    if mode == ConversationMode.CLOSING.value:
        return True

    return False


def should_persist_memory(state: ConversationState) -> bool:
    """
    Determine if conversation should be persisted to memory.

    Args:
        state: Current conversation state

    Returns:
        True if memory should be persisted
    """
    # Always persist if we have a patient_id
    if state.get("patient_id"):
        return True

    return False


def get_routing_metadata(state: ConversationState) -> dict:
    """
    Get metadata about the routing decision for debugging.

    Args:
        state: Current conversation state

    Returns:
        Dict with routing metadata
    """
    return {
        "mode": state.get("mode"),
        "previous_mode": state.get("previous_mode"),
        "urgency": state.get("urgency_level"),
        "turn_count": state.get("turn_count"),
        "mode_turns": state.get("mode_turns"),
        "has_active_goal": state.get("active_goal") is not None,
    }
