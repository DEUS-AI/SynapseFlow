"""
Conversational Intent Service - Classify user message intent.

Uses pattern matching for common intents (fast path) and LLM
classification for ambiguous cases (fallback).
"""

import re
import logging
from typing import Optional, Dict, List
from openai import AsyncOpenAI
import os

from domain.conversation_models import (
    IntentType,
    IntentResult,
    Urgency,
    MemoryContext
)

logger = logging.getLogger(__name__)


class ConversationalIntentService:
    """
    Classify user intent for response modulation.

    Two-phase classification:
    1. Pattern matching (fast, high confidence for common intents)
    2. LLM classification (slower, handles ambiguous cases)
    """

    # Pattern matching rules (lowercase for case-insensitive matching)
    # Note: Order matters! More specific patterns should come first
    INTENT_PATTERNS = {
        IntentType.GREETING_RETURN: [
            r"\b(i'm back|im back|back again|i'm here again|returned)\b",
            r"\b(hello again|hi again|hey again)\b"
        ],
        IntentType.GREETING: [
            r"\b(hello|hi|hey|greetings|good morning|good afternoon|good evening)\b",
            r"^(hi|hello|hey)[\s!?]*$"
        ],
        IntentType.SYMPTOM_REPORT: [
            r"\b(hurts?|hurt|pain|painful|ache|aching|feeling|symptoms?|discomfort)\b",
            r"\b(i have|i've got|experiencing|suffering from)\b.*(pain|ache|symptom)",
            r"\b(my .* (hurts?|aches?|is painful))\b"
        ],
        IntentType.FOLLOW_UP: [
            r"\b(about|regarding|concerning|related to)\b.*(you (said|mentioned|told))",
            r"\b(earlier|before|previously) you (said|mentioned)\b",
            r"^(what about|how about)",
            r"\b(going back to|returning to)\b"
        ],
        IntentType.MEDICAL_QUERY: [
            r"^(what is|what are|what's|whats)\s+(a|an|the)?\s*\w+",  # "What is ibuprofen?"
            r"^(how (does|do|can|should|would)|why (does|do|is|are))\b.*\?",  # Medical questions
            r"\b(can i take|should i take|is it safe)\b",
            r"\b(side effects?|interactions?|contraindications?)\b",
            r"\b(treat(s|ment)?|cure|prevent|diagnos(is|e))\b.*\?"
        ],
        IntentType.ACKNOWLEDGMENT: [
            r"^(thanks?|thank you|thx|ty|appreciate it|got it|ok|okay)[\s!.]*$",
            r"\b(thanks?|thank you)\b.*\b(much|lot|help)\b",
            r"^(understood|got it|makes sense|i see)[\s!.]*$"
        ],
        IntentType.FAREWELL: [
            r"^(goodbye|bye|see you|later|farewell|take care)[\s!.]*$",
            r"\b(have to go|gotta go|heading out)\b"
        ],
        IntentType.CLARIFICATION: [
            r"\b(what do you mean|what does that mean|i don't understand)\b",
            r"^(huh|what\?|pardon|sorry\?)[\s!?]*$",
            r"\b(can you (explain|clarify|elaborate|rephrase))\b"
        ]
    }

    # Urgency keywords
    URGENCY_KEYWORDS = {
        Urgency.CRITICAL: ["emergency", "urgent", "critical", "severe", "can't breathe", "chest pain", "bleeding heavily"],
        Urgency.HIGH: ["very painful", "getting worse", "spreading", "swollen", "high fever"],
        Urgency.MEDIUM: ["concerned", "worried", "uncomfortable", "bothering me"],
        Urgency.LOW: ["minor", "slight", "occasional", "wondering about"]
    }

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize intent service.

        Args:
            openai_api_key: OpenAI API key for LLM fallback (optional)
        """
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            self.llm_available = True
        else:
            logger.warning("OpenAI API key not found - LLM fallback disabled")
            self.llm_available = False
            self.openai_client = None

    async def classify(
        self,
        message: str,
        context: Optional[MemoryContext] = None
    ) -> IntentResult:
        """
        Classify intent using pattern matching + LLM fallback.

        Args:
            message: User message to classify
            context: Optional memory context for context-aware classification

        Returns:
            IntentResult with intent_type, confidence, and metadata
        """
        logger.debug(f"Classifying intent for message: {message[:50]}...")

        # 1. Try pattern matching first (fast path)
        pattern_result = self._pattern_match(message, context)
        if pattern_result and pattern_result.confidence >= 0.8:
            logger.info(f"Pattern match: {pattern_result.intent_type.value} (confidence: {pattern_result.confidence:.2f})")
            return pattern_result

        # 2. Fall back to LLM classification for ambiguous cases
        if self.llm_available:
            try:
                llm_result = await self._llm_classify(message, context)
                logger.info(f"LLM classification: {llm_result.intent_type.value} (confidence: {llm_result.confidence:.2f})")
                return llm_result
            except Exception as e:
                logger.error(f"LLM classification failed: {e}", exc_info=True)

        # 3. Default to pattern result or UNKNOWN
        if pattern_result:
            return pattern_result

        return IntentResult(
            intent_type=IntentType.UNKNOWN,
            confidence=0.5,
            urgency=Urgency.MEDIUM
        )

    def _pattern_match(
        self,
        message: str,
        context: Optional[MemoryContext] = None
    ) -> Optional[IntentResult]:
        """
        Pattern-based intent classification.

        Args:
            message: User message
            context: Optional memory context

        Returns:
            IntentResult if pattern matches, None otherwise
        """
        message_lower = message.lower().strip()

        # Check each intent's patterns
        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    # Distinguish GREETING vs GREETING_RETURN based on context
                    if intent_type == IntentType.GREETING and context and context.is_returning_user():
                        intent_type = IntentType.GREETING_RETURN

                    # Extract metadata
                    topic_hint = self._extract_topic(message_lower)
                    urgency = self._detect_urgency(message_lower)
                    emotional_tone = self._detect_emotion(message_lower)

                    # Determine if medical knowledge is required
                    requires_medical = intent_type in [
                        IntentType.SYMPTOM_REPORT,
                        IntentType.MEDICAL_QUERY
                    ]

                    # Determine if memory context is required
                    requires_memory = intent_type in [
                        IntentType.GREETING_RETURN,
                        IntentType.FOLLOW_UP
                    ]

                    return IntentResult(
                        intent_type=intent_type,
                        confidence=0.9,  # High confidence for pattern matches
                        topic_hint=topic_hint,
                        urgency=urgency,
                        emotional_tone=emotional_tone,
                        requires_medical_knowledge=requires_medical,
                        requires_memory_context=requires_memory
                    )

        # If no pattern matches, check if it's a medical query (question words + medical context)
        if self._is_medical_question(message_lower):
            return IntentResult(
                intent_type=IntentType.MEDICAL_QUERY,
                confidence=0.7,
                topic_hint=self._extract_topic(message_lower),
                urgency=Urgency.MEDIUM,
                requires_medical_knowledge=True
            )

        return None

    async def _llm_classify(
        self,
        message: str,
        context: Optional[MemoryContext] = None
    ) -> IntentResult:
        """
        LLM-based intent classification for ambiguous cases.

        Args:
            message: User message
            context: Optional memory context

        Returns:
            IntentResult from LLM classification
        """
        # Build context information
        context_info = ""
        if context and context.is_returning_user():
            context_info = f"\nUser context: Returning user (last session {context.days_since_last_session} days ago)"
            if context.recent_topics:
                context_info += f", recent topics: {', '.join(context.recent_topics[:3])}"

        # System prompt for classification
        system_prompt = f"""You are a medical assistant intent classifier. Classify the user's message into one of these intents:

- GREETING: Initial hello/hi (new conversation)
- GREETING_RETURN: Returning user saying hello
- SYMPTOM_REPORT: User reporting symptoms or pain
- FOLLOW_UP: User following up on previous topic
- MEDICAL_QUERY: User asking medical question
- CLARIFICATION: User asking for clarification
- ACKNOWLEDGMENT: User thanking or confirming
- FAREWELL: User saying goodbye
- UNKNOWN: Unclear intent

Also extract:
- topic_hint: Main topic (one word or short phrase)
- urgency: LOW, MEDIUM, HIGH, or CRITICAL
- emotional_tone: User's emotional state (concerned, grateful, frustrated, neutral, etc.)
- requires_medical_knowledge: true if medical knowledge needed
- requires_memory_context: true if needs conversation history

{context_info}

Respond in JSON format:
{{"intent": "INTENT_TYPE", "confidence": 0.0-1.0, "topic_hint": "topic", "urgency": "LEVEL", "emotional_tone": "tone", "requires_medical_knowledge": true/false, "requires_memory_context": true/false}}"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Fast, cheap model for classification
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=150
            )

            # Parse JSON response
            import json
            result = json.loads(response.choices[0].message.content)

            return IntentResult(
                intent_type=IntentType(result["intent"].lower()),
                confidence=float(result["confidence"]),
                topic_hint=result.get("topic_hint"),
                urgency=Urgency(result["urgency"].lower()),
                emotional_tone=result.get("emotional_tone"),
                requires_medical_knowledge=result.get("requires_medical_knowledge", False),
                requires_memory_context=result.get("requires_memory_context", False)
            )

        except Exception as e:
            logger.error(f"LLM classification error: {e}", exc_info=True)
            raise

    def _extract_topic(self, message: str) -> Optional[str]:
        """
        Extract main topic from message.

        Args:
            message: User message (lowercased)

        Returns:
            Topic hint or None
        """
        # Medical terms
        medical_terms = [
            "pain", "knee", "back", "head", "headache", "fever", "cough",
            "medication", "treatment", "diagnosis", "prescription", "doctor",
            "ibuprofen", "aspirin", "therapy", "exercise", "diet"
        ]

        for term in medical_terms:
            if term in message:
                return term

        # Extract noun phrases (simple heuristic)
        words = message.split()
        if len(words) >= 2:
            # Look for "my X" pattern
            for i, word in enumerate(words):
                if word == "my" and i + 1 < len(words):
                    return words[i + 1]

        return None

    def _detect_urgency(self, message: str) -> Urgency:
        """
        Detect urgency level from message.

        Args:
            message: User message (lowercased)

        Returns:
            Urgency level
        """
        for urgency_level, keywords in self.URGENCY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in message:
                    return urgency_level

        return Urgency.MEDIUM

    def _detect_emotion(self, message: str) -> Optional[str]:
        """
        Detect emotional tone from message.

        Args:
            message: User message (lowercased)

        Returns:
            Emotional tone or None
        """
        emotion_keywords = {
            "concerned": ["worried", "concerned", "scared", "afraid"],
            "grateful": ["thanks", "thank you", "appreciate", "grateful"],
            "frustrated": ["frustrated", "annoyed", "upset", "angry"],
            "hopeful": ["hope", "hoping", "better", "improving"],
            "confused": ["confused", "don't understand", "unclear"]
        }

        for emotion, keywords in emotion_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    return emotion

        return "neutral"

    def _is_medical_question(self, message: str) -> bool:
        """
        Check if message is a medical question.

        Args:
            message: User message (lowercased)

        Returns:
            True if likely a medical question
        """
        question_words = ["what", "how", "why", "can", "should", "is", "does", "do"]
        medical_context = ["medication", "treatment", "disease", "condition", "symptom", "pain"]

        has_question = any(message.startswith(qw) for qw in question_words) or "?" in message
        has_medical_context = any(term in message for term in medical_context)

        return has_question and has_medical_context
