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
        query = """
        MATCH (p:Patient {id: $patient_id})
        OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(dx:Diagnosis)
        OPTIONAL MATCH (p)-[:CURRENT_MEDICATION]->(med:Medication)
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
        Record new medication for patient.

        Args:
            patient_id: Patient identifier
            name: Medication name
            dosage: Medication dosage
            frequency: Frequency of administration
            started_date: Start date (optional)
            metadata: Additional metadata (optional)

        Returns:
            str: Medication ID
        """
        med_id = f"med:{uuid.uuid4().hex[:12]}"
        logger.info(f"Adding medication for patient {patient_id}: {name}")

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
