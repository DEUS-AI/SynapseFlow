"""
Persona Configuration - Agent personality presets.

Defines configurable agent personas for different use cases:
- default: Warm, professional medical assistant
- clinical: Precise, professional clinical assistant
- friendly: Casual, approachable health buddy

Persona can be selected via AGENT_PERSONA environment variable.
"""

import os
from domain.conversation_models import AgentPersona


# Predefined persona configurations
PERSONA_CONFIGS = {
    "default": AgentPersona(
        name="Medical Assistant",
        tone="warm_professional",
        use_patient_name=True,
        proactive_followups=True,
        show_empathy=True,
        use_casual_language=False,
        max_greeting_length=50,
        include_safety_reminders=True,
        include_disclaimer=True,
        ask_followup_questions=True,
        mention_recent_topics=True,
        check_medication_adherence=True
    ),

    "clinical": AgentPersona(
        name="Clinical Assistant",
        tone="clinical",
        use_patient_name=False,
        proactive_followups=False,
        show_empathy=False,
        use_casual_language=False,
        max_greeting_length=30,
        include_safety_reminders=True,
        include_disclaimer=True,
        ask_followup_questions=True,
        mention_recent_topics=False,
        check_medication_adherence=False
    ),

    "friendly": AgentPersona(
        name="Health Buddy",
        tone="friendly",
        use_patient_name=True,
        proactive_followups=True,
        show_empathy=True,
        use_casual_language=True,
        max_greeting_length=60,
        include_safety_reminders=True,
        include_disclaimer=True,
        ask_followup_questions=True,
        mention_recent_topics=True,
        check_medication_adherence=True
    )
}


def get_persona(persona_name: str = None) -> AgentPersona:
    """
    Get persona configuration by name.

    Args:
        persona_name: Persona name (default, clinical, friendly)
                      If None, reads from AGENT_PERSONA env var

    Returns:
        AgentPersona configuration
    """
    if persona_name is None:
        persona_name = os.getenv("AGENT_PERSONA", "default")

    persona = PERSONA_CONFIGS.get(persona_name.lower())
    if not persona:
        # Fallback to default if unknown persona
        persona = PERSONA_CONFIGS["default"]

    return persona


def list_personas() -> dict:
    """
    List all available persona configurations.

    Returns:
        Dict of persona name -> description
    """
    return {
        "default": "Warm, professional medical assistant - balanced approach",
        "clinical": "Precise, professional clinical assistant - formal and factual",
        "friendly": "Casual, approachable health buddy - conversational and supportive"
    }
