"""
Patient Memory Service - Core 3-layer memory management.

Manages patient memory across three layers:
1. Redis: Short-term session state (24h TTL)
2. Mem0: Intelligent memory with fact extraction
3. Neo4j: Long-term medical history
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import logging

from mem0 import Memory
from infrastructure.neo4j_backend import Neo4jBackend
from infrastructure.redis_session_cache import RedisSessionCache

logger = logging.getLogger(__name__)


@dataclass
class PatientContext:
    """Complete patient context for reasoning."""
    patient_id: str
    diagnoses: List[Dict[str, Any]]
    medications: List[Dict[str, Any]]
    allergies: List[str]
    recent_symptoms: List[Dict[str, Any]]
    conversation_summary: str
    last_updated: datetime


@dataclass
class ConversationMessage:
    """Message with patient context."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    patient_id: str
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class PatientMemoryService:
    """
    Manages patient memory across three layers:
    1. Redis: Short-term session state (24h TTL)
    2. Mem0: Intelligent memory with fact extraction
    3. Neo4j: Long-term medical history
    """

    def __init__(
        self,
        mem0: Memory,
        neo4j_backend: Neo4jBackend,
        redis_cache: RedisSessionCache
    ):
        """
        Initialize patient memory service.

        Args:
            mem0: Mem0 Memory instance for intelligent memory layer
            neo4j_backend: Neo4j backend for long-term storage
            redis_cache: Redis session cache for short-term storage
        """
        self.mem0 = mem0
        self.neo4j = neo4j_backend
        self.redis = redis_cache
        logger.info("Patient Memory Service initialized with 3-layer architecture")

    # ========================================
    # Patient Profile Operations
    # ========================================

    async def get_or_create_patient(
        self,
        patient_id: str,
        consent_given: bool = True
    ) -> str:
        """
        Get existing patient or create new one.

        Args:
            patient_id: External patient identifier (from EMR)
            consent_given: Whether patient has consented to data storage

        Returns:
            str: Patient ID
        """
        # Check if patient exists in Neo4j
        query = "MATCH (p:Patient {id: $patient_id}) RETURN p"
        result = await self.neo4j.query_raw(query, {"patient_id": patient_id})

        if result:
            logger.info(f"Patient found: {patient_id}")
            return patient_id

        # Create new patient
        logger.info(f"Creating new patient: {patient_id}")
        await self.neo4j.add_entity(
            patient_id,
            {
                "created_at": datetime.now().isoformat(),
                "consent_given": consent_given,
                "pii_anonymized": True,
                "data_retention_policy": "7_years"
            },
            labels=["Patient"]
        )

        # Initialize Mem0 memory for patient
        self.mem0.add(
            f"Patient {patient_id} registered in system",
            user_id=patient_id,
            metadata={"event": "patient_registration"}
        )

        logger.info(f"Patient created successfully: {patient_id}")
        return patient_id

    async def get_patient_context(
        self,
        patient_id: str
    ) -> PatientContext:
        """
        Retrieve complete patient context from all layers.

        Args:
            patient_id: Patient identifier

        Returns:
            PatientContext: Complete patient context including medical history
        """
        logger.debug(f"Retrieving patient context for: {patient_id}")

        # 1. Get from Mem0 (intelligent memory)
        mem0_memories = self.mem0.get_all(
            user_id=patient_id,
            limit=20  # Recent memories
        )

        # 2. Get from Neo4j (permanent medical record)
        # Only return active medications (filter out discontinued)
        query = """
        MATCH (p:Patient {id: $patient_id})
        OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(dx:Diagnosis)
        OPTIONAL MATCH (p)-[:CURRENT_MEDICATION]->(med:Medication)
            WHERE med.status IS NULL OR med.status = 'active'
        OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(allergy:Allergy)
        RETURN
            p,
            collect(DISTINCT dx) as diagnoses,
            collect(DISTINCT med) as medications,
            collect(DISTINCT allergy.substance) as allergies
        """

        result = await self.neo4j.query_raw(query, {"patient_id": patient_id})

        if not result:
            logger.warning(f"No patient found in Neo4j: {patient_id}")
            return PatientContext(
                patient_id=patient_id,
                diagnoses=[],
                medications=[],
                allergies=[],
                recent_symptoms=[],
                conversation_summary="No history",
                last_updated=datetime.now()
            )

        record = result[0]

        # 3. Extract symptoms from recent Mem0 memories
        symptoms = []
        for memory in mem0_memories.get("results", []):
            if "symptom" in memory.get("memory", "").lower():
                symptoms.append({
                    "text": memory["memory"],
                    "timestamp": memory.get("created_at")
                })

        # 4. Generate conversation summary from Mem0
        summary_memories = [m["memory"] for m in mem0_memories.get("results", [])[:5]]
        conversation_summary = " ".join(summary_memories) if summary_memories else "No recent conversations"

        context = PatientContext(
            patient_id=patient_id,
            diagnoses=[self._parse_diagnosis(dx) for dx in record["diagnoses"] if dx],
            medications=[self._parse_medication(med) for med in record["medications"] if med],
            allergies=[allergy for allergy in record["allergies"] if allergy],
            recent_symptoms=symptoms,
            conversation_summary=conversation_summary,
            last_updated=datetime.now()
        )

        logger.info(f"Patient context retrieved: {len(context.diagnoses)} diagnoses, "
                   f"{len(context.medications)} medications, {len(context.allergies)} allergies")

        return context

    # ========================================
    # Medical History Management
    # ========================================

    async def add_diagnosis(
        self,
        patient_id: str,
        condition: str,
        icd10_code: Optional[str] = None,
        diagnosed_date: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record new diagnosis for patient.

        Args:
            patient_id: Patient identifier
            condition: Diagnosis condition name
            icd10_code: ICD-10 code (optional)
            diagnosed_date: Date of diagnosis (optional)
            metadata: Additional metadata (optional)

        Returns:
            str: Diagnosis ID
        """
        diagnosis_id = f"dx:{uuid.uuid4().hex[:12]}"
        logger.info(f"Adding diagnosis for patient {patient_id}: {condition}")

        # Store in Neo4j (permanent)
        await self.neo4j.add_entity(
            diagnosis_id,
            {
                "condition": condition,
                "icd10_code": icd10_code or "unknown",
                "diagnosed_date": diagnosed_date or "unknown",
                "recorded_at": datetime.now().isoformat(),
                "status": "active",
                **(metadata or {})
            },
            labels=["Diagnosis"]
        )

        await self.neo4j.add_relationship(
            patient_id,
            "HAS_DIAGNOSIS",
            diagnosis_id,
            {"recorded_at": datetime.now().isoformat()}
        )

        # Store in Mem0 (intelligent memory)
        self.mem0.add(
            f"Patient diagnosed with {condition} on {diagnosed_date or 'unknown date'}",
            user_id=patient_id,
            metadata={
                "type": "diagnosis",
                "condition": condition,
                "icd10": icd10_code
            }
        )

        logger.info(f"Diagnosis added successfully: {diagnosis_id}")
        return diagnosis_id

    async def add_medication(
        self,
        patient_id: str,
        name: str,
        dosage: str,
        frequency: str,
        started_date: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record new medication for patient (with deduplication).

        Args:
            patient_id: Patient identifier
            name: Medication name
            dosage: Medication dosage
            frequency: Frequency of administration
            started_date: Start date (optional)
            metadata: Additional metadata (optional)

        Returns:
            str: Medication ID (existing or new)
        """
        logger.info(f"Adding medication for patient {patient_id}: {name}")

        # Check if medication already exists for this patient (case-insensitive)
        existing_med = await self._find_existing_medication(patient_id, name)
        if existing_med:
            # Update existing medication instead of creating duplicate
            med_id = existing_med.get("id") or existing_med.get("med_id")
            logger.info(f"Medication {name} already exists for patient {patient_id}, updating: {med_id}")
            await self._update_medication_properties(
                med_id, dosage, frequency, "active"
            )
            return med_id

        # Create new medication
        med_id = f"med:{uuid.uuid4().hex[:12]}"

        # Store in Neo4j
        await self.neo4j.add_entity(
            med_id,
            {
                "name": name,
                "dosage": dosage,
                "frequency": frequency,
                "started_date": started_date or datetime.now().isoformat(),
                "status": "active",
                **(metadata or {})
            },
            labels=["Medication"]
        )

        await self.neo4j.add_relationship(
            patient_id,
            "CURRENT_MEDICATION",
            med_id,
            {"started_at": started_date or datetime.now().isoformat()}
        )

        # Store in Mem0
        self.mem0.add(
            f"Patient started taking {name} ({dosage}) {frequency}",
            user_id=patient_id,
            metadata={
                "type": "medication",
                "name": name,
                "dosage": dosage
            }
        )

        logger.info(f"Medication added successfully: {med_id}")
        return med_id

    async def _find_existing_medication(
        self, patient_id: str, medication_name: str
    ) -> Optional[Dict[str, Any]]:
        """Find existing medication for patient by name (case-insensitive)."""
        try:
            query = """
            MATCH (p:Patient {id: $patient_id})-[:CURRENT_MEDICATION]->(med:Medication)
            WHERE toLower(med.name) = toLower($med_name)
            RETURN med.id as med_id, med.name as name, med.status as status
            LIMIT 1
            """
            results = await self.neo4j.query_raw(query, {
                "patient_id": patient_id,
                "med_name": medication_name
            })
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"Error finding existing medication: {e}")
            return None

    async def _update_medication_properties(
        self, med_id: str, dosage: str, frequency: str, status: str
    ) -> None:
        """Update medication properties."""
        try:
            query = """
            MATCH (med:Medication)
            WHERE med.id = $med_id
            SET med.dosage = $dosage,
                med.frequency = $frequency,
                med.status = $status,
                med.updated_at = datetime()
            """
            await self.neo4j.query_raw(query, {
                "med_id": med_id,
                "dosage": dosage,
                "frequency": frequency,
                "status": status
            })
        except Exception as e:
            logger.error(f"Error updating medication: {e}")

    async def update_medication_status(
        self,
        patient_id: str,
        medication_name: str,
        new_status: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update medication status (e.g., mark as discontinued).

        Args:
            patient_id: Patient identifier
            medication_name: Name of the medication
            new_status: New status (active, discontinued, paused)
            reason: Reason for status change (optional)

        Returns:
            bool: True if updated, False if not found
        """
        logger.info(f"Updating medication status for {patient_id}: {medication_name} -> {new_status}")

        try:
            query = """
            MATCH (p:Patient {id: $patient_id})-[r:CURRENT_MEDICATION]->(med:Medication)
            WHERE toLower(med.name) = toLower($med_name)
            SET med.status = $new_status,
                med.status_changed_at = datetime(),
                med.status_reason = $reason
            RETURN med.id as med_id
            """
            results = await self.neo4j.query_raw(query, {
                "patient_id": patient_id,
                "med_name": medication_name,
                "new_status": new_status,
                "reason": reason
            })

            if results:
                # Update Mem0
                self.mem0.add(
                    f"Patient {new_status} taking {medication_name}" +
                    (f" - {reason}" if reason else ""),
                    user_id=patient_id,
                    metadata={
                        "type": "medication_status_change",
                        "name": medication_name,
                        "status": new_status
                    }
                )
                logger.info(f"Medication status updated: {medication_name} -> {new_status}")
                return True

            logger.warning(f"Medication not found for status update: {medication_name}")
            return False

        except Exception as e:
            logger.error(f"Error updating medication status: {e}")
            return False

    async def remove_medication(
        self,
        patient_id: str,
        medication_name: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Remove/discontinue medication for patient.

        Args:
            patient_id: Patient identifier
            medication_name: Name of the medication to remove
            reason: Reason for removal (optional)

        Returns:
            bool: True if removed, False if not found
        """
        return await self.update_medication_status(
            patient_id, medication_name, "discontinued", reason
        )

    async def deduplicate_medications(self, patient_id: str) -> int:
        """
        Remove duplicate medications for a patient, keeping only the most recent.

        Returns:
            int: Number of duplicates removed
        """
        logger.info(f"Deduplicating medications for patient {patient_id}")

        try:
            # Find duplicates and delete all but the most recent
            query = """
            MATCH (p:Patient {id: $patient_id})-[:CURRENT_MEDICATION]->(med:Medication)
            WITH toLower(med.name) as med_name, collect(med) as meds
            WHERE size(meds) > 1
            UNWIND meds[1..] as duplicate
            DETACH DELETE duplicate
            RETURN count(*) as deleted_count
            """
            results = await self.neo4j.query_raw(query, {"patient_id": patient_id})
            deleted = results[0]["deleted_count"] if results else 0
            logger.info(f"Removed {deleted} duplicate medications for patient {patient_id}")
            return deleted

        except Exception as e:
            logger.error(f"Error deduplicating medications: {e}")
            return 0

    async def add_allergy(
        self,
        patient_id: str,
        substance: str,
        reaction: str,
        severity: str = "moderate"
    ) -> str:
        """
        Record allergy for patient.

        Args:
            patient_id: Patient identifier
            substance: Allergen substance
            reaction: Allergic reaction
            severity: Severity level (mild/moderate/severe)

        Returns:
            str: Allergy ID
        """
        allergy_id = f"allergy:{uuid.uuid4().hex[:12]}"
        logger.info(f"Adding allergy for patient {patient_id}: {substance} ({severity})")

        # Store in Neo4j
        await self.neo4j.add_entity(
            allergy_id,
            {
                "substance": substance,
                "reaction": reaction,
                "severity": severity,
                "documented_date": datetime.now().isoformat()
            },
            labels=["Allergy"]
        )

        await self.neo4j.add_relationship(
            patient_id,
            "HAS_ALLERGY",
            allergy_id,
            {"documented_at": datetime.now().isoformat()}
        )

        # Store in Mem0 (CRITICAL for contraindication checking)
        self.mem0.add(
            f"Patient has {severity} allergy to {substance}, causes {reaction}",
            user_id=patient_id,
            metadata={
                "type": "allergy",
                "substance": substance,
                "severity": severity,
                "critical": severity == "severe"
            }
        )

        logger.info(f"Allergy added successfully: {allergy_id}")
        return allergy_id

    # ========================================
    # Conversation Management
    # ========================================

    async def start_session(
        self,
        patient_id: str,
        device: str = "web"
    ) -> str:
        """
        Start new conversation session.

        Args:
            patient_id: Patient identifier
            device: Device type (web/mobile/etc)

        Returns:
            str: Session ID
        """
        session_id = f"session:{uuid.uuid4().hex[:12]}"
        logger.info(f"Starting new session for patient {patient_id}: {session_id}")

        # Store in Redis (short-term)
        await self.redis.set_session(
            session_id,
            {
                "session_id": session_id,
                "patient_id": patient_id,
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "device": device,
                "conversation_count": 0
            }
        )

        # Store in Neo4j (long-term)
        await self.neo4j.add_entity(
            session_id,
            {
                "started_at": datetime.now().isoformat(),
                "ended_at": None,
                "device_type": device
            },
            labels=["ConversationSession"]
        )

        await self.neo4j.add_relationship(
            patient_id,
            "HAS_SESSION",
            session_id,
            {}
        )

        logger.info(f"Session started successfully: {session_id}")
        return session_id

    async def store_message(
        self,
        message: ConversationMessage
    ) -> str:
        """
        Store conversation message in all layers.

        Args:
            message: Conversation message to store

        Returns:
            str: Message ID
        """
        msg_id = f"msg:{uuid.uuid4().hex[:12]}"
        logger.debug(f"Storing message for patient {message.patient_id}, session {message.session_id}")

        # 1. Store in Mem0 (automatic fact extraction)
        self.mem0.add(
            message.content,
            user_id=message.patient_id,
            metadata={
                "role": message.role,
                "session_id": message.session_id,
                "timestamp": message.timestamp.isoformat()
            }
        )

        # 2. Store in Neo4j (full message log)
        await self.neo4j.add_entity(
            msg_id,
            {
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
                "patient_id": message.patient_id,
                **message.metadata
            },
            labels=["Message"]
        )

        await self.neo4j.add_relationship(
            message.session_id,
            "HAS_MESSAGE",
            msg_id,
            {"timestamp": message.timestamp.isoformat()}
        )

        # 3. Update Redis session
        session_data = await self.redis.get_session(message.session_id)
        if session_data:
            session_data["last_activity"] = datetime.now().isoformat()
            session_data["conversation_count"] = session_data.get("conversation_count", 0) + 1
            await self.redis.set_session(message.session_id, session_data)

        logger.debug(f"Message stored successfully: {msg_id}")
        return msg_id

    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history from Neo4j.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve

        Returns:
            List[Dict]: List of messages ordered by timestamp
        """
        logger.debug(f"Retrieving conversation history for session: {session_id}")

        query = """
        MATCH (session:ConversationSession {id: $session_id})-[:HAS_MESSAGE]->(msg:Message)
        RETURN msg
        ORDER BY msg.timestamp ASC
        LIMIT $limit
        """

        result = await self.neo4j.query_raw(query, {
            "session_id": session_id,
            "limit": limit
        })

        messages = [dict(record["msg"]) for record in result]
        logger.debug(f"Retrieved {len(messages)} messages for session {session_id}")
        return messages

    # ========================================
    # Privacy & Compliance
    # ========================================

    async def check_consent(
        self,
        patient_id: str
    ) -> bool:
        """
        Verify patient has given consent for data storage.

        Args:
            patient_id: Patient identifier

        Returns:
            bool: True if consent given, False otherwise
        """
        query = "MATCH (p:Patient {id: $patient_id}) RETURN p.consent_given as consent"
        result = await self.neo4j.query_raw(query, {"patient_id": patient_id})

        if result:
            consent = result[0]["consent"] == True
            logger.debug(f"Consent check for patient {patient_id}: {consent}")
            return consent

        logger.warning(f"Patient not found for consent check: {patient_id}")
        return False

    async def delete_patient_data(
        self,
        patient_id: str
    ) -> bool:
        """
        Delete all patient data (right to be forgotten).

        Implements GDPR right to erasure by removing data from all three layers.

        Args:
            patient_id: Patient identifier

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Deleting all data for patient: {patient_id} (GDPR right to be forgotten)")

        try:
            # 1. Delete from Mem0
            self.mem0.delete_all(user_id=patient_id)
            logger.debug("Deleted Mem0 memories")

            # 2. Delete from Redis sessions
            sessions = await self.redis.list_patient_sessions(patient_id)
            for session_id in sessions:
                await self.redis.delete_session(session_id)
            logger.debug(f"Deleted {len(sessions)} Redis sessions")

            # 3. Delete from Neo4j (cascade)
            query = """
            MATCH (p:Patient {id: $patient_id})
            OPTIONAL MATCH (p)-[r]->(related)
            DETACH DELETE p, related
            """
            await self.neo4j.query_raw(query, {"patient_id": patient_id})
            logger.debug("Deleted Neo4j patient data")

            logger.info(f"Patient data successfully deleted: {patient_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting patient data for {patient_id}: {e}", exc_info=True)
            return False

    async def log_audit(
        self,
        patient_id: str,
        action: str,
        actor: str,
        details: str
    ) -> str:
        """
        Log data access for compliance.

        Args:
            patient_id: Patient identifier
            action: Action performed
            actor: Agent/user who performed the action
            details: Additional details

        Returns:
            str: Audit log ID
        """
        audit_id = f"audit:{uuid.uuid4().hex[:12]}"
        logger.debug(f"Logging audit for patient {patient_id}: {action} by {actor}")

        await self.neo4j.add_entity(
            audit_id,
            {
                "action": action,
                "actor": actor,
                "timestamp": datetime.now().isoformat(),
                "details": details
            },
            labels=["AuditLog"]
        )

        await self.neo4j.add_relationship(
            patient_id,
            "HAS_AUDIT_LOG",
            audit_id,
            {}
        )

        return audit_id

    # ========================================
    # Conversational Memory Helpers (Phase 6)
    # ========================================

    async def get_recent_topics(
        self,
        patient_id: str,
        limit: int = 5
    ) -> List[str]:
        """
        Get recent conversation topics from Mem0.

        Args:
            patient_id: Patient identifier
            limit: Maximum number of topics to return

        Returns:
            List of recent topics
        """
        logger.debug(f"Retrieving recent topics for patient: {patient_id}")

        try:
            # Get recent memories from Mem0
            memories = self.mem0.get_all(
                user_id=patient_id,
                limit=limit * 2  # Get more to filter
            )

            if not memories or "results" not in memories:
                return []

            # Extract topics from memories
            topics = []
            for memory in memories["results"][:limit]:
                memory_text = memory.get("memory", "")
                # Extract meaningful keywords
                extracted = self._extract_keywords(memory_text)
                topics.extend(extracted)

            # Remove duplicates while preserving order
            seen = set()
            unique_topics = []
            for topic in topics:
                if topic not in seen:
                    seen.add(topic)
                    unique_topics.append(topic)

            return unique_topics[:limit]

        except Exception as e:
            logger.error(f"Error retrieving recent topics: {e}", exc_info=True)
            return []

    async def get_last_session_summary(
        self,
        patient_id: str
    ) -> Optional[str]:
        """
        Get summary of last conversation session.

        Args:
            patient_id: Patient identifier

        Returns:
            Last session summary or None
        """
        logger.debug(f"Retrieving last session summary for patient: {patient_id}")

        try:
            # Get most recent memories from Mem0
            memories = self.mem0.get_all(
                user_id=patient_id,
                limit=5
            )

            if not memories or "results" not in memories:
                return None

            # Combine recent memories into summary
            recent_memories = [m.get("memory", "") for m in memories["results"][:3]]
            summary = " ".join(recent_memories) if recent_memories else None

            return summary

        except Exception as e:
            logger.error(f"Error retrieving last session summary: {e}", exc_info=True)
            return None

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract medical keywords from text.

        Args:
            text: Text to extract keywords from

        Returns:
            List of extracted keywords
        """
        # Medical keywords to look for
        medical_keywords = [
            "pain", "knee", "back", "head", "headache", "fever", "cough",
            "medication", "treatment", "diagnosis", "ibuprofen", "aspirin",
            "therapy", "physical therapy", "exercise", "diet", "allergy",
            "symptom", "condition", "prescription"
        ]

        text_lower = text.lower()
        found_keywords = []

        for keyword in medical_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)

        # Extract "X pain" patterns
        import re
        pain_patterns = re.findall(r"(\w+)\s+pain", text_lower)
        found_keywords.extend([f"{part} pain" for part in pain_patterns])

        return found_keywords

    # ========================================
    # Session Management (Chat History)
    # ========================================

    async def get_sessions_by_patient(
        self,
        patient_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve sessions for a patient with pagination.

        Args:
            patient_id: Patient identifier
            limit: Maximum sessions to return
            offset: Pagination offset
            status: Filter by status (active, ended, archived)

        Returns:
            List of session dictionaries
        """
        logger.debug(f"Retrieving sessions for patient {patient_id}")

        query = """
        MATCH (p:Patient {id: $patient_id})-[:HAS_SESSION]->(s:ConversationSession)
        WHERE $status IS NULL OR s.status = $status
        OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
        WITH s, count(m) as message_count, max(m.timestamp) as last_message_time
        RETURN s, message_count, last_message_time
        ORDER BY COALESCE(last_message_time, s.started_at) DESC
        SKIP $offset
        LIMIT $limit
        """

        result = await self.neo4j.query_raw(query, {
            "patient_id": patient_id,
            "status": status,
            "offset": offset,
            "limit": limit
        })

        sessions = []
        for record in result:
            session_node = record["s"]
            session_data = dict(session_node)

            # Add session_id from node ID
            if "id" in session_data:
                session_data["session_id"] = session_data["id"]

            session_data["message_count"] = record["message_count"]

            if record["last_message_time"]:
                session_data["last_activity"] = record["last_message_time"]

            sessions.append(session_data)

        logger.debug(f"Retrieved {len(sessions)} sessions for patient {patient_id}")
        return sessions

    async def get_session_by_id(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get session metadata by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session dictionary or None
        """
        query = """
        MATCH (s:ConversationSession {id: $session_id})
        OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
        WITH s, count(m) as message_count, max(m.timestamp) as last_message_time
        RETURN s, message_count, last_message_time
        """

        result = await self.neo4j.query_raw(query, {"session_id": session_id})

        if not result:
            return None

        record = result[0]
        session_data = dict(record["s"])
        session_data["message_count"] = record["message_count"]

        if record["last_message_time"]:
            session_data["last_activity"] = record["last_message_time"]

        return session_data

    async def get_messages_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a session with pagination.

        Args:
            session_id: Session identifier
            limit: Maximum messages to return
            offset: Pagination offset

        Returns:
            List of message dictionaries
        """
        query = """
        MATCH (s:ConversationSession {id: $session_id})-[:HAS_MESSAGE]->(m:Message)
        RETURN m
        ORDER BY m.timestamp ASC
        SKIP $offset
        LIMIT $limit
        """

        result = await self.neo4j.query_raw(query, {
            "session_id": session_id,
            "offset": offset,
            "limit": limit
        })

        messages = []
        for record in result:
            message_node = record["m"]
            message_data = dict(message_node)

            # Add id from node ID if not present
            if "id" not in message_data and hasattr(message_node, "id"):
                message_data["id"] = message_node.id
            elif "id" not in message_data:
                message_data["id"] = message_data.get("message_id", f"msg-{len(messages)}")

            # Add session_id (from parameter since messages belong to this session)
            message_data["session_id"] = session_id

            messages.append(message_data)

        return messages

    async def create_session(
        self,
        session_id: str,
        patient_id: str,
        title: str = "New Conversation",
        device_type: str = "web"
    ) -> bool:
        """
        Create a new conversation session.

        Args:
            session_id: Session identifier
            patient_id: Patient identifier
            title: Session title
            device_type: Device type (web, mobile)

        Returns:
            True if successful
        """
        logger.info(f"Creating session {session_id} for patient {patient_id}")

        try:
            # Ensure patient exists first
            await self.get_or_create_patient(patient_id)

            # Create session node
            await self.neo4j.add_entity(
                session_id,
                {
                    "patient_id": patient_id,
                    "title": title,
                    "started_at": datetime.now().isoformat(),
                    "status": "active",
                    "device_type": device_type
                },
                labels=["ConversationSession"]
            )

            # Link to patient
            await self.neo4j.add_relationship(
                patient_id,
                "HAS_SESSION",
                session_id,
                {}
            )

            return True

        except Exception as e:
            logger.error(f"Error creating session: {e}", exc_info=True)
            return False

    async def update_session_status(
        self,
        session_id: str,
        status: str,
        ended_at: Optional[datetime] = None
    ) -> bool:
        """
        Update session status.

        Args:
            session_id: Session identifier
            status: New status (active, ended, archived)
            ended_at: Optional end timestamp

        Returns:
            True if successful
        """
        logger.info(f"Updating session {session_id} status to {status}")

        try:
            properties = {"status": status}

            if ended_at:
                properties["ended_at"] = ended_at.isoformat()

            await self.neo4j.update_entity_properties(
                session_id,
                properties
            )

            return True

        except Exception as e:
            logger.error(f"Error updating session status: {e}", exc_info=True)
            return False

    async def update_session_title(
        self,
        session_id: str,
        title: str
    ) -> bool:
        """
        Update session title.

        Args:
            session_id: Session identifier
            title: New title

        Returns:
            True if successful
        """
        logger.info(f"Updating session {session_id} title to '{title}'")

        try:
            await self.neo4j.update_entity_properties(
                session_id,
                {"title": title}
            )

            return True

        except Exception as e:
            logger.error(f"Error updating session title: {e}", exc_info=True)
            return False

    async def delete_session(
        self,
        session_id: str
    ) -> bool:
        """
        Delete session and all messages (GDPR compliance).

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        logger.warning(f"Deleting session {session_id} (GDPR)")

        try:
            # Delete all messages first
            query = """
            MATCH (s:ConversationSession {id: $session_id})-[:HAS_MESSAGE]->(m:Message)
            DETACH DELETE m
            """
            await self.neo4j.query_raw(query, {"session_id": session_id})

            # Delete session
            query = """
            MATCH (s:ConversationSession {id: $session_id})
            DETACH DELETE s
            """
            await self.neo4j.query_raw(query, {"session_id": session_id})

            return True

        except Exception as e:
            logger.error(f"Error deleting session: {e}", exc_info=True)
            return False

    async def search_sessions(
        self,
        patient_id: str,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search sessions by content or title.

        Args:
            patient_id: Patient identifier
            query: Search query
            limit: Maximum results

        Returns:
            List of matching sessions
        """
        logger.debug(f"Searching sessions for patient {patient_id}: '{query}'")

        cypher_query = """
        MATCH (p:Patient {id: $patient_id})-[:HAS_SESSION]->(s:ConversationSession)
        -[:HAS_MESSAGE]->(m:Message)
        WHERE m.content CONTAINS $query OR s.title CONTAINS $query
        WITH DISTINCT s, count(m) as match_count
        OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(all_m:Message)
        RETURN s, count(all_m) as message_count
        ORDER BY match_count DESC
        LIMIT $limit
        """

        result = await self.neo4j.query_raw(cypher_query, {
            "patient_id": patient_id,
            "query": query,
            "limit": limit
        })

        sessions = []
        for record in result:
            session_data = dict(record["s"])
            session_data["message_count"] = record["message_count"]
            sessions.append(session_data)

        return sessions

    # ========================================
    # Helper Methods
    # ========================================

    def _parse_diagnosis(self, dx_node) -> Dict[str, Any]:
        """
        Parse Neo4j diagnosis node to dict.

        Args:
            dx_node: Neo4j diagnosis node

        Returns:
            Dict: Parsed diagnosis data
        """
        if not dx_node:
            return {}

        return {
            "condition": dx_node.get("condition"),
            "icd10_code": dx_node.get("icd10_code"),
            "diagnosed_date": dx_node.get("diagnosed_date"),
            "status": dx_node.get("status", "active")
        }

    def _parse_medication(self, med_node) -> Dict[str, Any]:
        """
        Parse Neo4j medication node to dict.

        Args:
            med_node: Neo4j medication node

        Returns:
            Dict: Parsed medication data
        """
        if not med_node:
            return {}

        return {
            "name": med_node.get("name"),
            "dosage": med_node.get("dosage"),
            "frequency": med_node.get("frequency"),
            "status": med_node.get("status", "active")
        }
