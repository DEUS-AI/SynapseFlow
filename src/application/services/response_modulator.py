"""
Response Modulator - Generate personalized responses.

Modulates LLM responses based on:
- Intent (greeting, medical query, symptom report, etc.)
- Memory context (patient history, recent topics)
- Persona (warm_professional, clinical, friendly)

Generates natural, contextual responses that feel human-like.
"""

import logging
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
import os

from domain.conversation_models import (
    IntentType,
    IntentResult,
    MemoryContext,
    AgentPersona,
    RESPONSE_TEMPLATES
)

logger = logging.getLogger(__name__)


class ResponseModulator:
    """
    Modulate LLM responses based on intent and context.

    Handles:
    - Proactive greetings with memory context
    - Medical responses wrapped with persona
    - Empathetic symptom responses
    - Natural follow-ups
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        persona: Optional[AgentPersona] = None,
        openai_api_key: Optional[str] = None
    ):
        """
        Initialize response modulator.

        Args:
            llm_client: Optional LLM client (defaults to OpenAI)
            persona: Agent persona configuration
            openai_api_key: OpenAI API key
        """
        self.llm_client = llm_client
        self.persona = persona or AgentPersona()  # Default persona

        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None

        logger.info(f"ResponseModulator initialized with persona: {self.persona.name} ({self.persona.tone})")

    async def generate_response(
        self,
        user_message: str,
        intent: IntentResult,
        memory_context: MemoryContext,
        medical_response: Optional[str] = None
    ) -> str:
        """
        Generate personalized response based on intent and context.

        Args:
            user_message: User's message
            intent: Classified intent
            memory_context: Memory context
            medical_response: Optional pre-generated medical response (for MEDICAL_QUERY intents)

        Returns:
            Personalized response string
        """
        logger.debug(f"Generating response for intent: {intent.intent_type.value}")

        # Route to appropriate handler based on intent
        if intent.intent_type in [IntentType.GREETING, IntentType.GREETING_RETURN]:
            return await self._generate_greeting(intent, memory_context)

        elif intent.intent_type == IntentType.SYMPTOM_REPORT:
            return await self._generate_symptom_response(user_message, intent, memory_context)

        elif intent.intent_type == IntentType.MEDICAL_QUERY:
            return await self._generate_medical_response(user_message, intent, memory_context, medical_response)

        elif intent.intent_type == IntentType.FOLLOW_UP:
            return await self._generate_followup_response(user_message, intent, memory_context, medical_response)

        elif intent.intent_type == IntentType.ACKNOWLEDGMENT:
            return self._generate_acknowledgment(memory_context)

        elif intent.intent_type == IntentType.FAREWELL:
            return self._generate_farewell(memory_context)

        elif intent.intent_type == IntentType.CLARIFICATION:
            return await self._generate_clarification(user_message, memory_context)

        else:
            # Default response for unknown intent
            return "I'm here to help. Could you tell me more about what you need?"

    async def _generate_greeting(
        self,
        intent: IntentResult,
        memory_context: MemoryContext
    ) -> str:
        """
        Generate personalized greeting.

        Args:
            intent: Intent result
            memory_context: Memory context

        Returns:
            Greeting response
        """
        # Select template based on whether user is returning
        if intent.intent_type == IntentType.GREETING_RETURN and memory_context.has_history():
            template_key = IntentType.GREETING_RETURN
        else:
            template_key = IntentType.GREETING

        # Build greeting using LLM with context
        system_prompt = self._build_system_prompt(intent, memory_context)

        user_prompt = f"""Generate a warm, natural greeting for the patient.

Context:
- Intent: {template_key.value}
- Returning user: {memory_context.is_returning_user()}
- Days since last session: {memory_context.days_since_last_session}
- Recent topics: {', '.join(memory_context.recent_topics[:3]) if memory_context.recent_topics else 'none'}
- Unresolved symptoms: {', '.join(memory_context.unresolved_symptoms) if memory_context.unresolved_symptoms else 'none'}

Generate a greeting that:
1. Welcomes the patient warmly
2. Mentions time context if returning user ("It's been a few days...")
3. Asks about unresolved symptoms proactively if applicable
4. Offers help
5. Keep it under 50 words
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )

            greeting = response.choices[0].message.content.strip()
            logger.info(f"Generated greeting: {greeting[:50]}...")
            return greeting

        except Exception as e:
            logger.error(f"Error generating greeting: {e}", exc_info=True)
            # Fallback to template
            return self._fallback_greeting(template_key, memory_context)

    async def _generate_symptom_response(
        self,
        user_message: str,
        intent: IntentResult,
        memory_context: MemoryContext
    ) -> str:
        """
        Generate empathetic symptom response.

        Args:
            user_message: User's message
            intent: Intent result
            memory_context: Memory context

        Returns:
            Empathetic response
        """
        system_prompt = self._build_system_prompt(intent, memory_context)

        user_prompt = f"""The patient is reporting symptoms: "{user_message}"

Context:
- Topic: {intent.topic_hint or 'unknown'}
- Urgency: {intent.urgency.value}
- Emotional tone: {intent.emotional_tone or 'neutral'}
- Active conditions: {', '.join(memory_context.active_conditions) if memory_context.active_conditions else 'none'}
- Current medications: {', '.join(memory_context.current_medications) if memory_context.current_medications else 'none'}

Generate a response that:
1. Acknowledges the symptom with empathy
2. Asks clarifying questions to understand better (severity, duration, etc.)
3. Mentions if this is related to known conditions
4. Shows you're listening and care
5. Keep it under 75 words
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating symptom response: {e}", exc_info=True)
            return f"I understand you're experiencing {intent.topic_hint or 'discomfort'}. Can you tell me more about it? When did it start, and how severe is it?"

    async def _generate_medical_response(
        self,
        user_message: str,
        intent: IntentResult,
        memory_context: MemoryContext,
        medical_response: Optional[str] = None
    ) -> str:
        """
        Generate or wrap medical query response.

        Args:
            user_message: User's message
            intent: Intent result
            memory_context: Memory context
            medical_response: Pre-generated medical response (if any)

        Returns:
            Medical response wrapped with persona
        """
        if not medical_response:
            # Generate medical response from scratch
            return await self._generate_knowledge_response(user_message, intent, memory_context)

        # Wrap existing medical response with persona
        system_prompt = self._build_system_prompt(intent, memory_context)

        user_prompt = f"""Wrap this medical response with a warm, personalized intro:

Medical Response:
{medical_response}

Patient Context:
- Recent topics: {', '.join(memory_context.recent_topics[:2]) if memory_context.recent_topics else 'none'}
- Active conditions: {', '.join(memory_context.active_conditions[:2]) if memory_context.active_conditions else 'none'}

Instructions:
1. Add a brief, warm intro (1 sentence) before the medical response
2. Keep the medical content exactly as provided (accurate and factual)
3. Add a brief closing that offers further help
4. Total response should be natural and conversational
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_tokens=500
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error wrapping medical response: {e}", exc_info=True)
            # Return original medical response
            return medical_response

    async def _generate_knowledge_response(
        self,
        user_message: str,
        intent: IntentResult,
        memory_context: MemoryContext
    ) -> str:
        """
        Generate medical knowledge response from scratch.

        Args:
            user_message: User's question
            intent: Intent result
            memory_context: Memory context

        Returns:
            Medical response
        """
        system_prompt = self._build_system_prompt(intent, memory_context)

        user_prompt = f"""Answer this medical question: "{user_message}"

Patient Context:
- Active conditions: {', '.join(memory_context.active_conditions) if memory_context.active_conditions else 'none'}
- Current medications: {', '.join(memory_context.current_medications) if memory_context.current_medications else 'none'}
- Allergies: {', '.join(memory_context.allergies) if memory_context.allergies else 'none'}

Instructions:
1. Provide accurate medical information
2. Consider patient's context (conditions, medications)
3. Include safety warnings if relevant
4. Recommend consulting healthcare provider for serious concerns
5. Be clear and conversational
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_tokens=400
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating knowledge response: {e}", exc_info=True)
            return "I'd be happy to help with that. Let me look into this for you."

    async def _generate_followup_response(
        self,
        user_message: str,
        intent: IntentResult,
        memory_context: MemoryContext,
        medical_response: Optional[str] = None
    ) -> str:
        """
        Generate follow-up response that continues context.

        Args:
            user_message: User's follow-up message
            intent: Intent result
            memory_context: Memory context
            medical_response: Optional medical response

        Returns:
            Follow-up response
        """
        system_prompt = self._build_system_prompt(intent, memory_context)

        user_prompt = f"""The patient is following up: "{user_message}"

Recent Context:
- Recent topics: {', '.join(memory_context.recent_topics) if memory_context.recent_topics else 'none'}
- Current session topics: {', '.join(memory_context.current_session_topics) if memory_context.current_session_topics else 'none'}

Generate a response that:
1. Shows you remember the context
2. Directly addresses their follow-up
3. Provides helpful information
4. Maintains conversational flow
"""

        if medical_response:
            user_prompt += f"\n\nMedical information to include:\n{medical_response}"

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.6,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating follow-up response: {e}", exc_info=True)
            return "Let me address that for you. What specifically would you like to know more about?"

    async def _generate_clarification(
        self,
        user_message: str,
        memory_context: MemoryContext
    ) -> str:
        """
        Generate clarification response.

        Args:
            user_message: User's clarification request
            memory_context: Memory context

        Returns:
            Clarification response
        """
        # Default clarification - in real implementation, would reference previous response
        return "I'd be happy to clarify. Could you tell me which part you'd like me to explain in more detail?"

    def _generate_acknowledgment(self, memory_context: MemoryContext) -> str:
        """
        Generate acknowledgment response.

        Args:
            memory_context: Memory context

        Returns:
            Acknowledgment response
        """
        if self.persona.should_use_name(memory_context):
            name = memory_context.patient_name or ""
            return f"You're welcome{', ' + name if name else ''}! Let me know if you need anything else."
        return "You're welcome! Feel free to reach out if you have more questions."

    def _generate_farewell(self, memory_context: MemoryContext) -> str:
        """
        Generate farewell response.

        Args:
            memory_context: Memory context

        Returns:
            Farewell response
        """
        if self.persona.should_use_name(memory_context):
            name = memory_context.patient_name or ""
            return f"Take care{', ' + name if name else ''}! Don't hesitate to reach out if you need anything."
        return "Take care! I'm here whenever you need help."

    def _build_system_prompt(
        self,
        intent: IntentResult,
        memory_context: MemoryContext
    ) -> str:
        """
        Build LLM system prompt with persona and context.

        Args:
            intent: Intent result
            memory_context: Memory context

        Returns:
            System prompt string
        """
        tone_desc = self.persona.get_tone_description()

        prompt = f"""You are a {tone_desc} medical assistant named {self.persona.name}.

Your role:
- Provide helpful, accurate medical information
- Show empathy and understanding
- Remember patient context and history
- Ask clarifying questions when needed
- Always recommend consulting healthcare providers for serious concerns

Patient Context:
"""

        # Add memory context if available
        if memory_context.has_history():
            prompt += f"- This is a returning patient"
            if memory_context.days_since_last_session:
                prompt += f" (last session {memory_context.days_since_last_session} days ago)"
            prompt += "\n"

            if memory_context.recent_topics:
                prompt += f"- Recent discussion topics: {', '.join(memory_context.recent_topics[:3])}\n"

        if memory_context.has_medical_history():
            if memory_context.active_conditions:
                prompt += f"- Active conditions: {', '.join(memory_context.active_conditions)}\n"
            if memory_context.current_medications:
                prompt += f"- Current medications: {', '.join(memory_context.current_medications)}\n"
            if memory_context.allergies:
                prompt += f"- Allergies: {', '.join(memory_context.allergies)}\n"

        # Add persona-specific instructions
        if self.persona.show_empathy:
            prompt += "\nShow genuine empathy and concern for the patient's well-being."

        if self.persona.include_disclaimer:
            prompt += "\nAlways include appropriate medical disclaimers when providing health advice."

        if self.persona.include_safety_reminders:
            prompt += "\nHighlight safety concerns and when to seek immediate medical attention."

        return prompt

    def _fallback_greeting(
        self,
        template_key: IntentType,
        memory_context: MemoryContext
    ) -> str:
        """
        Fallback to template-based greeting.

        Args:
            template_key: Template key
            memory_context: Memory context

        Returns:
            Template-based greeting
        """
        template = RESPONSE_TEMPLATES.get(template_key, {})

        if memory_context.has_history():
            greeting = template.get("with_memory", "Hello! How can I help you today?")

            # Replace {name}
            if memory_context.patient_name:
                greeting = greeting.replace("{name}", memory_context.patient_name)
            else:
                greeting = greeting.replace("{name}", "").replace(", !", "!")

            # Replace {time_context}
            time_context = memory_context.get_time_context()
            greeting = greeting.replace("{time_context}", time_context)

            # Replace {proactive_context}
            if memory_context.recent_topics:
                context = f"We last talked about {memory_context.recent_topics[0]}."
                greeting = greeting.replace("{proactive_context}", context)
            else:
                greeting = greeting.replace("{proactive_context}", "")

            # Replace {proactive_followup}
            if memory_context.unresolved_symptoms:
                followup = f"How's your {memory_context.unresolved_symptoms[0]} today?"
                greeting = greeting.replace("{proactive_followup}", followup)
            elif memory_context.recent_topics:
                followup = f"How are things with {memory_context.recent_topics[0]}?"
                greeting = greeting.replace("{proactive_followup}", followup)
            else:
                greeting = greeting.replace("{proactive_followup}", "How can I help you today?")

        else:
            greeting = template.get("without_memory", "Hello! I'm your medical assistant. How can I help you today?")

        return greeting
