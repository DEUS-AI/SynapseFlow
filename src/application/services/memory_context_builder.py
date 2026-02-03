"""
Memory Context Builder - Aggregate memory from multiple layers.

Retrieves and summarizes patient memory from:
- Mem0: Recent conversation facts and topics
- Neo4j: Medical profile (conditions, medications, allergies)
- Redis: Current session state

Builds a unified MemoryContext for response generation.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import Counter

from mem0 import Memory

from domain.conversation_models import MemoryContext
from application.services.patient_memory_service import PatientMemoryService

logger = logging.getLogger(__name__)


class MemoryContextBuilder:
    """
    Build conversation context from memory layers.

    Aggregates data from:
    1. Mem0 - Recent conversation facts (last 5 sessions)
    2. Neo4j - Medical profile via PatientMemoryService
    3. Redis - Current session state
    """

    def __init__(
        self,
        patient_memory_service: PatientMemoryService,
        mem0: Memory
    ):
        """
        Initialize memory context builder.

        Args:
            patient_memory_service: Patient memory service instance
            mem0: Mem0 Memory instance
        """
        self.memory = patient_memory_service
        self.mem0 = mem0
        logger.info("MemoryContextBuilder initialized")

    async def build_context(
        self,
        patient_id: str,
        session_id: Optional[str] = None
    ) -> MemoryContext:
        """
        Build complete memory context for response generation.

        Args:
            patient_id: Patient identifier
            session_id: Optional current session ID

        Returns:
            MemoryContext with aggregated memory data
        """
        logger.debug(f"Building memory context for patient: {patient_id}")

        # 1. Get patient profile from Neo4j (via PatientMemoryService)
        patient_context = await self.memory.get_patient_context(patient_id)

        # 2. Get recent memories from Mem0
        recent_topics, last_session_summary, last_session_date = await self._get_mem0_memories(patient_id)

        # 3. Calculate days since last session
        days_since_last = self._calculate_days_since_last_session(last_session_date)

        # 4. Get current session state from Redis
        current_session_topics, turn_count = await self._get_session_state(session_id) if session_id else ([], 0)

        # 5. Extract proactive hints
        unresolved_symptoms = self._extract_unresolved_symptoms(patient_context, recent_topics)
        pending_followups = self._extract_pending_followups(recent_topics, last_session_summary)

        # 6. Build unified context
        context = MemoryContext(
            patient_id=patient_id,
            patient_name=self._extract_patient_name(patient_id),
            # Mem0 data
            recent_topics=recent_topics,
            last_session_summary=last_session_summary,
            days_since_last_session=days_since_last,
            last_session_date=last_session_date,
            # Neo4j data
            active_conditions=[d.get("condition", "") for d in patient_context.diagnoses if d],
            current_medications=[m.get("name", "") for m in patient_context.medications if m],
            allergies=patient_context.allergies,
            # Redis data
            current_session_id=session_id,
            current_session_topics=current_session_topics,
            conversation_turn_count=turn_count,
            # Proactive hints
            unresolved_symptoms=unresolved_symptoms,
            pending_followups=pending_followups
        )

        logger.info(f"Memory context built: {len(recent_topics)} topics, {len(context.active_conditions)} conditions, "
                   f"returning_user={context.is_returning_user()}")
        return context

    async def _get_mem0_memories(
        self,
        patient_id: str
    ) -> tuple[List[str], Optional[str], Optional[datetime]]:
        """
        Get recent memories from Mem0.

        Args:
            patient_id: Patient identifier

        Returns:
            Tuple of (recent_topics, last_session_summary, last_session_date)
        """
        try:
            # Get recent memories (last 20, covering ~5 sessions)
            memories = self.mem0.get_all(
                user_id=patient_id,
                limit=20
            )

            if not memories or "results" not in memories:
                logger.debug(f"No Mem0 memories found for patient {patient_id}")
                return ([], None, None)

            results = memories["results"]

            # Extract topics from memories
            topics = []
            for memory in results:
                memory_text = memory.get("memory", "")
                # Extract meaningful keywords/topics
                extracted_topics = self._extract_topics_from_text(memory_text)
                topics.extend(extracted_topics)

            # Count frequency and get top topics
            topic_counts = Counter(topics)
            recent_topics = [topic for topic, _ in topic_counts.most_common(5)]

            # Build last session summary from most recent memories
            recent_memories = [m.get("memory", "") for m in results[:3]]
            last_session_summary = " ".join(recent_memories) if recent_memories else None

            # Get last session date
            last_session_date = None
            if results:
                # Parse created_at from first (most recent) memory
                created_at_str = results[0].get("created_at")
                if created_at_str:
                    try:
                        last_session_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    except Exception as e:
                        logger.warning(f"Failed to parse last session date: {e}")

            logger.debug(f"Extracted {len(recent_topics)} topics from Mem0: {recent_topics}")
            return (recent_topics, last_session_summary, last_session_date)

        except Exception as e:
            logger.error(f"Error retrieving Mem0 memories: {e}", exc_info=True)
            return ([], None, None)

    async def _get_session_state(
        self,
        session_id: str
    ) -> tuple[List[str], int]:
        """
        Get current session state from Redis.

        Args:
            session_id: Session identifier

        Returns:
            Tuple of (current_session_topics, conversation_turn_count)
        """
        try:
            session_data = await self.memory.redis.get_session(session_id)
            if not session_data:
                return ([], 0)

            # Extract topics from session metadata
            topics = session_data.get("topics", [])
            turn_count = session_data.get("conversation_count", 0)

            return (topics, turn_count)

        except Exception as e:
            logger.error(f"Error retrieving session state: {e}", exc_info=True)
            return ([], 0)

    def _extract_topics_from_text(self, text: str) -> List[str]:
        """
        Extract medical topics from memory text.

        Args:
            text: Memory text

        Returns:
            List of extracted topics
        """
        # Medical keywords to extract
        medical_keywords = [
            "pain", "knee", "back", "head", "headache", "fever", "cough",
            "medication", "treatment", "diagnosis", "ibuprofen", "aspirin",
            "therapy", "physical therapy", "exercise", "diet", "allergy"
        ]

        text_lower = text.lower()
        topics = []

        for keyword in medical_keywords:
            if keyword in text_lower:
                topics.append(keyword)

        # Extract "X pain" patterns
        import re
        pain_patterns = re.findall(r"(\w+)\s+pain", text_lower)
        topics.extend([f"{part} pain" for part in pain_patterns])

        return topics

    def _calculate_days_since_last_session(
        self,
        last_session_date: Optional[datetime]
    ) -> Optional[int]:
        """
        Calculate days since last session.

        Args:
            last_session_date: Last session datetime

        Returns:
            Number of days or None if no last session
        """
        if not last_session_date:
            return None

        now = datetime.now(last_session_date.tzinfo) if last_session_date.tzinfo else datetime.now()
        delta = now - last_session_date
        return delta.days

    def _extract_patient_name(self, patient_id: str) -> Optional[str]:
        """
        Extract patient name from patient ID or stored data.

        Args:
            patient_id: Patient identifier

        Returns:
            Patient name or None
        """
        # For now, return None (could be enhanced to query Neo4j for stored name)
        # In a real system, this would query the patient record
        return None

    def _extract_unresolved_symptoms(
        self,
        patient_context: Any,
        recent_topics: List[str]
    ) -> List[str]:
        """
        Extract unresolved symptoms from recent topics.

        Args:
            patient_context: Patient context from Neo4j
            recent_topics: Recent conversation topics

        Returns:
            List of unresolved symptoms
        """
        # Symptoms that appear in recent topics but not in diagnoses
        unresolved = []

        symptom_keywords = ["pain", "ache", "fever", "cough", "headache", "dizziness"]

        for topic in recent_topics:
            # Check if it's a symptom
            if any(keyword in topic.lower() for keyword in symptom_keywords):
                # Check if it's not in active conditions
                # Diagnoses are dicts, extract name/condition field
                diagnosis_names = []
                for condition in patient_context.diagnoses:
                    if isinstance(condition, dict):
                        # Try common field names for condition name
                        name = condition.get("name") or condition.get("condition") or condition.get("diagnosis") or ""
                        if name:
                            diagnosis_names.append(name.lower())
                    elif isinstance(condition, str):
                        diagnosis_names.append(condition.lower())

                is_resolved = any(topic.lower() in diag for diag in diagnosis_names)
                if not is_resolved:
                    unresolved.append(topic)

        return unresolved[:3]  # Limit to top 3

    def _extract_pending_followups(
        self,
        recent_topics: List[str],
        last_session_summary: Optional[str]
    ) -> List[str]:
        """
        Extract pending follow-up items.

        Args:
            recent_topics: Recent conversation topics
            last_session_summary: Summary of last session

        Returns:
            List of pending follow-ups
        """
        followups = []

        # Look for medication mentions in last session
        if last_session_summary:
            summary_lower = last_session_summary.lower()

            # Check for medication recommendations
            if "recommended" in summary_lower or "prescribed" in summary_lower:
                # Extract medication names
                medication_keywords = ["ibuprofen", "aspirin", "therapy", "treatment"]
                for med in medication_keywords:
                    if med in summary_lower:
                        followups.append(f"Check on {med}")

            # Check for pending actions
            if "should" in summary_lower or "try" in summary_lower:
                followups.append("Follow up on recommendations")

        return followups[:3]  # Limit to top 3

    async def get_proactive_topics(self, patient_id: str) -> List[str]:
        """
        Get topics to proactively mention in greeting.

        Prioritizes:
        1. Unresolved symptoms from last session
        2. Medication check-ins (adherence)
        3. Follow-up on recommendations

        Args:
            patient_id: Patient identifier

        Returns:
            List of proactive topics
        """
        context = await self.build_context(patient_id)

        proactive_topics = []

        # 1. Unresolved symptoms (highest priority)
        if context.unresolved_symptoms:
            proactive_topics.extend(context.unresolved_symptoms[:2])

        # 2. Medication adherence check
        if context.current_medications and context.days_since_last_session and context.days_since_last_session >= 7:
            proactive_topics.append(f"medication adherence ({context.current_medications[0]})")

        # 3. Pending follow-ups
        if context.pending_followups:
            proactive_topics.extend(context.pending_followups[:1])

        return proactive_topics[:3]  # Limit to top 3

    def get_personalized_greeting_context(self, context: MemoryContext) -> str:
        """
        Generate personalized greeting context string.

        Args:
            context: Memory context

        Returns:
            Personalized context string for greeting
        """
        if not context.has_history():
            return ""

        parts = []

        # Time context
        if context.days_since_last_session is not None:
            time_context = context.get_time_context()
            if time_context:
                parts.append(time_context)

        # Recent topics
        if context.recent_topics:
            main_topic = context.recent_topics[0]
            parts.append(f"We last talked about your {main_topic}")

        # Unresolved symptoms
        if context.unresolved_symptoms:
            symptom = context.unresolved_symptoms[0]
            parts.append(f"How is your {symptom}?")

        return ". ".join(parts) if parts else ""
