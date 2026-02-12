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
    # Temporal awareness fields (Phase 2A)
    recent_conditions: List[Dict[str, Any]] = field(default_factory=list)  # Mentioned in last 7 days
    historical_conditions: List[Dict[str, Any]] = field(default_factory=list)  # Older than 7 days
    recently_resolved: List[str] = field(default_factory=list)  # Conditions marked resolved recently
    context_timestamp: str = ""  # ISO timestamp when context was built
    # Patient identity (extracted from Mem0 memories)
    patient_name: Optional[str] = None  # Extracted from user introductions
    mem0_memories: List[str] = field(default_factory=list)  # Raw Mem0 memories for LLM context
    # Procedures and medical devices (Phase 2B)
    procedures: List[Dict[str, Any]] = field(default_factory=list)  # Tests, surgeries, screenings
    medical_devices: List[Dict[str, Any]] = field(default_factory=list)  # Colostomy, ileostomy, pacemaker, etc.


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
        Retrieve complete patient context from all layers with temporal awareness.

        Args:
            patient_id: Patient identifier

        Returns:
            PatientContext: Complete patient context including medical history
                           with temporal metadata for freshness filtering
        """
        logger.debug(f"Retrieving patient context for: {patient_id}")
        now = datetime.now()

        # 1. Get from Mem0 (intelligent memory)
        # CRITICAL: user_id MUST be the patient_id to ensure data isolation
        # Mem0 stores user_id as metadata in Qdrant and filters on it
        logger.debug(f"[MEM0_ISOLATION] Requesting memories for user_id={patient_id}")
        mem0_memories = self.mem0.get_all(
            user_id=patient_id,
            limit=30  # Get more for better temporal filtering
        )

        # SECURITY CHECK: Verify all returned memories belong to this patient
        mem0_results_raw = mem0_memories.get("results", []) if mem0_memories else []
        filtered_results = []
        for mem in mem0_results_raw:
            mem_user_id = mem.get("user_id") or mem.get("metadata", {}).get("user_id")
            if mem_user_id and mem_user_id != patient_id:
                logger.error(f"[MEM0_ISOLATION_VIOLATION] Memory for user {mem_user_id} "
                            f"returned for patient {patient_id}! Memory: {mem.get('memory', '')[:100]}")
                # CRITICAL: Skip this memory - it belongs to another patient!
                continue
            filtered_results.append(mem)

        if len(filtered_results) != len(mem0_results_raw):
            logger.warning(f"[MEM0_ISOLATION] Filtered out {len(mem0_results_raw) - len(filtered_results)} "
                          f"memories belonging to other patients from {patient_id}'s context")

        logger.debug(f"[MEM0_ISOLATION] Retrieved {len(filtered_results)} memories for {patient_id}")

        # 2. Sort Mem0 memories by timestamp (most recent first)
        sorted_memories = sorted(
            filtered_results,  # Use filtered results to ensure patient isolation
            key=lambda m: m.get("created_at", ""),
            reverse=True  # Most recent first
        )

        # 3. Get from Neo4j (permanent medical record)
        # Include resolved diagnoses to track recently_resolved
        # Include procedures and medical devices
        query = """
        MATCH (p:Patient {id: $patient_id})
        OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(dx:Diagnosis)
        OPTIONAL MATCH (p)-[:CURRENT_MEDICATION]->(med:Medication)
            WHERE med.status IS NULL OR med.status = 'active'
        OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(allergy:Allergy)
        OPTIONAL MATCH (p)-[:HAS_PROCEDURE]->(proc:Procedure)
        OPTIONAL MATCH (p)-[:HAS_DEVICE]->(device:MedicalDevice)
        RETURN
            p,
            collect(DISTINCT dx) as diagnoses,
            collect(DISTINCT med) as medications,
            collect(DISTINCT allergy.substance) as allergies,
            collect(DISTINCT proc) as procedures,
            collect(DISTINCT device) as medical_devices
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
                last_updated=now,
                recent_conditions=[],
                historical_conditions=[],
                recently_resolved=[],
                context_timestamp=now.isoformat()
            )

        record = result[0]

        # 4. Parse diagnoses with temporal freshness
        all_diagnoses = []
        recent_conditions = []
        historical_conditions = []
        recently_resolved = []

        for dx in record["diagnoses"]:
            if dx:
                parsed = self._parse_diagnosis_with_freshness(dx, now)
                all_diagnoses.append(parsed)

                # Categorize by status and freshness
                if parsed.get("status") == "resolved":
                    # Check if resolved recently (within 7 days)
                    if parsed.get("freshness") == "recent":
                        recently_resolved.append(parsed.get("condition", "unknown"))
                elif parsed.get("freshness") == "recent":
                    recent_conditions.append(parsed)
                else:
                    historical_conditions.append(parsed)

        # 5. Extract symptoms from recent Mem0 memories (sorted by recency)
        symptoms = []
        for memory in sorted_memories:
            memory_text = memory.get("memory", "").lower()
            if "symptom" in memory_text or "pain" in memory_text:
                created_at = memory.get("created_at", "")
                freshness = self._calculate_freshness(created_at, now)
                symptoms.append({
                    "text": memory["memory"],
                    "timestamp": created_at,
                    "freshness": freshness
                })

        # Only include recent symptoms (from last 7 days)
        recent_symptoms = [s for s in symptoms if s.get("freshness") == "recent"]

        # 6. Generate conversation summary from most recent memories
        summary_memories = [m["memory"] for m in sorted_memories[:5]]
        conversation_summary = " ".join(summary_memories) if summary_memories else "No recent conversations"

        # 7. Also check Mem0 for recently resolved conditions
        mem0_resolved = await self._get_mem0_resolved_conditions(sorted_memories, now)
        recently_resolved.extend([c for c in mem0_resolved if c not in recently_resolved])

        # 8. Extract patient name from Mem0 memories
        patient_name = self._extract_patient_name_from_memories(sorted_memories)

        # 9. Keep raw Mem0 memories for LLM context (last 10)
        raw_memories = [m.get("memory", "") for m in sorted_memories[:10] if m.get("memory")]

        # 10. Parse procedures and medical devices
        procedures = []
        for proc in record.get("procedures", []):
            if proc:
                procedures.append({
                    "name": proc.get("name", ""),
                    "type": proc.get("procedure_type", "test"),
                    "status": proc.get("status", "scheduled"),
                    "scheduled_date": proc.get("scheduled_date"),
                    "completion_date": proc.get("completion_date"),
                    "notes": proc.get("notes")
                })

        medical_devices = []
        for device in record.get("medical_devices", []):
            if device:
                medical_devices.append({
                    "name": device.get("name", ""),
                    "type": device.get("device_type", "device"),
                    "status": device.get("status", "active"),
                    "body_location": device.get("body_location"),
                    "placement_date": device.get("placement_date"),
                    "notes": device.get("notes")
                })

        context = PatientContext(
            patient_id=patient_id,
            diagnoses=[d for d in all_diagnoses if d.get("status") != "resolved"],
            medications=[self._parse_medication(med) for med in record["medications"] if med],
            allergies=[allergy for allergy in record["allergies"] if allergy],
            recent_symptoms=recent_symptoms,
            conversation_summary=conversation_summary,
            last_updated=now,
            recent_conditions=recent_conditions,
            historical_conditions=historical_conditions,
            recently_resolved=recently_resolved,
            context_timestamp=now.isoformat(),
            patient_name=patient_name,
            mem0_memories=raw_memories,
            procedures=procedures,
            medical_devices=medical_devices,
        )

        logger.info(f"Patient context retrieved: {len(context.diagnoses)} diagnoses "
                   f"({len(recent_conditions)} recent, {len(historical_conditions)} historical), "
                   f"{len(context.medications)} medications, {len(context.allergies)} allergies, "
                   f"{len(procedures)} procedures, {len(medical_devices)} medical devices, "
                   f"{len(recently_resolved)} recently resolved")

        return context

    def _parse_diagnosis_with_freshness(
        self,
        dx_node,
        now: datetime
    ) -> Dict[str, Any]:
        """
        Parse Neo4j diagnosis node with freshness calculation.

        Args:
            dx_node: Neo4j diagnosis node
            now: Current timestamp for freshness calculation

        Returns:
            Dict with diagnosis data including freshness marker
        """
        if not dx_node:
            return {}

        # Get the most relevant timestamp for freshness
        # Priority: status_changed_at > recorded_at > diagnosed_date
        timestamp = (
            dx_node.get("status_changed_at") or
            dx_node.get("recorded_at") or
            dx_node.get("diagnosed_date")
        )

        freshness = self._calculate_freshness(timestamp, now)

        return {
            "condition": dx_node.get("condition"),
            "icd10_code": dx_node.get("icd10_code"),
            "diagnosed_date": dx_node.get("diagnosed_date"),
            "status": dx_node.get("status", "active"),
            "freshness": freshness,
            "last_updated": timestamp
        }

    def _calculate_freshness(
        self,
        timestamp: str,
        now: datetime,
        threshold_days: int = 7
    ) -> str:
        """
        Calculate freshness of information based on timestamp.

        Args:
            timestamp: ISO format timestamp string
            now: Current datetime
            threshold_days: Days within which info is considered "recent"

        Returns:
            "recent" if within threshold, "stale" otherwise
        """
        if not timestamp:
            return "stale"  # Unknown timestamp = assume stale

        try:
            # Handle various datetime formats
            if isinstance(timestamp, str):
                # Remove timezone info if present for simpler parsing
                timestamp_clean = timestamp.replace("Z", "").split("+")[0]
                ts = datetime.fromisoformat(timestamp_clean)
            else:
                ts = timestamp

            days_ago = (now - ts).days
            return "recent" if days_ago < threshold_days else "stale"

        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse timestamp '{timestamp}': {e}")
            return "stale"

    async def _get_mem0_resolved_conditions(
        self,
        sorted_memories: List[Dict[str, Any]],
        now: datetime
    ) -> List[str]:
        """
        Extract recently resolved conditions from Mem0 memories.

        Args:
            sorted_memories: Mem0 memories sorted by recency
            now: Current timestamp

        Returns:
            List of condition names that were resolved recently
        """
        resolved = []

        resolution_phrases = [
            "no longer have", "has resolved", "is gone",
            "went away", "has cleared", "is better",
            "has been marked as resolved", "stopped having"
        ]

        for memory in sorted_memories[:15]:  # Check last 15 memories
            memory_text = memory.get("memory", "").lower()
            metadata = memory.get("metadata", {})
            created_at = memory.get("created_at", "")

            # Only consider recent memories
            if self._calculate_freshness(created_at, now) != "recent":
                continue

            # Check metadata for explicit resolution events
            if metadata.get("event") == "condition_resolved":
                condition = metadata.get("condition")
                if condition and condition not in resolved:
                    resolved.append(condition)
                continue

            # Check text for resolution phrases
            for phrase in resolution_phrases:
                if phrase in memory_text:
                    condition = self._extract_condition_from_resolution(memory_text)
                    if condition and condition not in resolved:
                        resolved.append(condition)
                    break

        return resolved

    def _extract_patient_name_from_memories(
        self,
        sorted_memories: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Extract patient name from Mem0 memories.

        Looks for patterns like:
        - "I'm [Name]", "I am [Name]"
        - "My name is [Name]"
        - "Hi, I'm [Name]"
        - "Call me [Name]"

        Args:
            sorted_memories: Mem0 memories sorted by recency

        Returns:
            Patient name if found, None otherwise
        """
        import re
        from application.services.medication_validator import get_medication_validator

        # Get medication validator to filter out medication names
        try:
            validator = get_medication_validator()
        except Exception:
            validator = None

        # Patterns to match name introductions (ordered by specificity)
        # More explicit patterns are matched first
        name_patterns = [
            # Highest priority: Explicit name introductions
            (r"my name is\s+([A-Z][a-z]+)", 3),  # "my name is Pablo"
            (r"i am\s+([A-Z][a-z]+)(?:\s+and|\s*$)", 3),  # "I am Pablo and..."
            (r"(?:hi|hello|hey),?\s+(?:my name is|i'm|i am)\s+([A-Z][a-z]+)", 3),
            (r"call me\s+([A-Z][a-z]+)", 3),

            # Medium priority: Less specific introductions
            (r"i'm\s+([A-Z][a-z]+)(?:\s+and|\s*,|\s*$)", 2),  # "I'm Pablo,"
            (r"this is\s+([A-Z][a-z]+)(?:\s+speaking|\s*$)", 2),

            # Lower priority: Ambiguous patterns (more likely false positives)
            (r"^([A-Z][a-z]+)\s+here", 1),
        ]

        # Common false positives to filter out (lowercase)
        excluded_words = {
            # System/role words
            "matucha", "assistant", "doctor", "nurse", "patient", "user",
            # Common responses
            "help", "okay", "yes", "no", "thanks", "thank", "please",
            # Medical terms that might look like names
            "chronic", "acute", "severe", "mild", "moderate",
            # Time-related words
            "morning", "evening", "night", "today", "yesterday", "monday", "tuesday",
            "wednesday", "thursday", "friday", "saturday", "sunday",
        }

        candidates = []  # (name, priority)

        for memory in sorted_memories[:30]:  # Check last 30 memories
            memory_text = memory.get("memory", "")

            for pattern, priority in name_patterns:
                match = re.search(pattern, memory_text, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    name_lower = name.lower()

                    # Skip if it's in the exclusion list
                    if name_lower in excluded_words:
                        continue

                    # Skip if it looks like a medication name
                    if validator and validator.is_likely_medication(name):
                        logger.debug(f"Skipping potential name '{name}' - looks like a medication")
                        continue

                    # Skip if the name is too short (likely abbreviation)
                    if len(name) < 3:
                        continue

                    candidates.append((name, priority))

        if not candidates:
            return None

        # Sort by priority (highest first) and return best candidate
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_name = candidates[0][0]

        logger.info(f"Extracted patient name from memories: {best_name} (priority: {candidates[0][1]})")
        return best_name

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

    async def add_pending_medication(
        self,
        patient_id: str,
        name: str,
        suggestions: List[str],
        confidence: float,
        dosage: str = "unknown",
        frequency: str = "unknown"
    ) -> str:
        """
        Record an unrecognized medication in pending state for review.

        This is used when medication validation fails but the user mentioned
        a medication-like term. It allows for manual review and correction.

        Args:
            patient_id: Patient identifier
            name: Original medication name (unvalidated)
            suggestions: List of suggested valid medications
            confidence: Confidence score from validation (0.0 to 1.0)
            dosage: Medication dosage
            frequency: Frequency of administration

        Returns:
            str: Pending medication ID
        """
        logger.info(f"Adding pending medication for patient {patient_id}: {name} (confidence: {confidence})")

        pending_id = f"pending_med:{uuid.uuid4().hex[:12]}"

        # Store in Neo4j as PendingMedication node
        await self.neo4j.add_entity(
            pending_id,
            {
                "original_name": name,
                "suggestions": ",".join(suggestions) if suggestions else "",
                "confidence": confidence,
                "dosage": dosage,
                "frequency": frequency,
                "status": "pending_review",
                "created_at": datetime.now().isoformat()
            },
            labels=["PendingMedication"]
        )

        await self.neo4j.add_relationship(
            patient_id,
            "PENDING_MEDICATION",
            pending_id,
            {"created_at": datetime.now().isoformat()}
        )

        logger.info(f"Pending medication stored for review: {pending_id}")
        return pending_id

    async def remove_pending_medication(
        self,
        patient_id: str,
        medication_name: str
    ) -> bool:
        """
        Remove a pending medication from review queue.

        Called when a medication is corrected or denied by the patient.

        Args:
            patient_id: Patient identifier
            medication_name: Original medication name to remove

        Returns:
            bool: True if removed, False if not found
        """
        try:
            query = """
            MATCH (p:Patient {id: $patient_id})-[:PENDING_MEDICATION]->(pm:PendingMedication)
            WHERE toLower(pm.original_name) = toLower($med_name)
            DETACH DELETE pm
            RETURN count(*) as deleted
            """
            results = await self.neo4j.query_raw(query, {
                "patient_id": patient_id,
                "med_name": medication_name
            })
            deleted = results[0]["deleted"] if results else 0
            if deleted > 0:
                logger.info(f"Removed pending medication '{medication_name}' for {patient_id}")
            return deleted > 0
        except Exception as e:
            logger.warning(f"Error removing pending medication: {e}")
            return False

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

    async def remove_allergy(
        self,
        patient_id: str,
        substance: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Remove an allergy record from patient.

        Used when patient denies having an allergy that was previously recorded.

        Args:
            patient_id: Patient identifier
            substance: Allergen substance to remove
            reason: Reason for removal (optional)

        Returns:
            bool: True if removed, False if not found
        """
        logger.info(f"Removing allergy '{substance}' for patient {patient_id}")

        try:
            # Find and update the allergy status to "denied" or delete
            query = """
            MATCH (p:Patient {id: $patient_id})-[r:HAS_ALLERGY]->(a:Allergy)
            WHERE toLower(a.substance) = toLower($substance)
            SET a.status = 'denied',
                a.denial_reason = $reason,
                a.denied_at = datetime()
            DELETE r
            RETURN count(*) as updated
            """
            results = await self.neo4j.query_raw(query, {
                "patient_id": patient_id,
                "substance": substance,
                "reason": reason or "Patient denied allergy"
            })

            updated = results[0]["updated"] if results else 0
            if updated > 0:
                logger.info(f"Allergy '{substance}' removed for patient {patient_id}")
            else:
                logger.info(f"Allergy '{substance}' not found for patient {patient_id}")

            return updated > 0

        except Exception as e:
            logger.error(f"Error removing allergy: {e}")
            return False

    # ========================================
    # Procedures and Tests
    # ========================================

    async def add_procedure(
        self,
        patient_id: str,
        name: str,
        procedure_type: str = "test",  # test, surgery, screening, imaging
        scheduled_date: Optional[str] = None,
        status: str = "scheduled",  # scheduled, completed, cancelled
        location: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a medical procedure or test for patient.

        Examples: colonoscopy, endoscopy, MRI, blood test, CT scan, biopsy, surgery

        Args:
            patient_id: Patient identifier
            name: Procedure name (e.g., "colonoscopy", "MRI", "blood test")
            procedure_type: Type of procedure (test, surgery, screening, imaging)
            scheduled_date: When procedure is/was scheduled
            status: Current status (scheduled, completed, cancelled)
            location: Where the procedure takes place
            notes: Additional notes
            metadata: Additional metadata

        Returns:
            str: Procedure ID
        """
        procedure_id = f"procedure:{uuid.uuid4().hex[:12]}"
        logger.info(f"Adding procedure for patient {patient_id}: {name} ({procedure_type})")

        # Normalize the name
        normalized_name = name.strip().lower()

        # Store in Neo4j
        await self.neo4j.add_entity(
            procedure_id,
            {
                "name": name,
                "normalized_name": normalized_name,
                "procedure_type": procedure_type,
                "status": status,
                "scheduled_date": scheduled_date,
                "location": location,
                "notes": notes,
                "created_at": datetime.now().isoformat(),
                **(metadata or {})
            },
            labels=["Procedure", "MedicalEvent"]
        )

        await self.neo4j.add_relationship(
            patient_id,
            "HAS_PROCEDURE",
            procedure_id,
            {
                "recorded_at": datetime.now().isoformat(),
                "status": status
            }
        )

        # Store in Mem0 for conversational recall
        status_text = f"is scheduled for" if status == "scheduled" else f"had"
        self.mem0.add(
            f"Patient {status_text} a {name} ({procedure_type})" +
            (f" on {scheduled_date}" if scheduled_date else ""),
            user_id=patient_id,
            metadata={
                "type": "procedure",
                "name": name,
                "procedure_type": procedure_type,
                "status": status
            }
        )

        logger.info(f"Procedure added successfully: {procedure_id}")
        return procedure_id

    async def update_procedure_status(
        self,
        patient_id: str,
        procedure_name: str,
        new_status: str,
        completion_date: Optional[str] = None,
        results: Optional[str] = None
    ) -> bool:
        """
        Update the status of a procedure.

        Args:
            patient_id: Patient identifier
            procedure_name: Name of the procedure
            new_status: New status (completed, cancelled)
            completion_date: When completed
            results: Results if completed

        Returns:
            bool: True if updated
        """
        logger.info(f"Updating procedure '{procedure_name}' status to '{new_status}' for patient {patient_id}")

        try:
            query = """
            MATCH (p:Patient {id: $patient_id})-[r:HAS_PROCEDURE]->(proc:Procedure)
            WHERE toLower(proc.name) CONTAINS toLower($procedure_name)
               OR toLower(proc.normalized_name) CONTAINS toLower($procedure_name)
            SET proc.status = $new_status,
                proc.completion_date = $completion_date,
                proc.results = $results,
                proc.updated_at = $updated_at,
                r.status = $new_status
            RETURN count(proc) as updated
            """

            results_data = await self.neo4j.query_raw(query, {
                "patient_id": patient_id,
                "procedure_name": procedure_name.lower(),
                "new_status": new_status,
                "completion_date": completion_date,
                "results": results,
                "updated_at": datetime.now().isoformat()
            })

            updated = results_data[0]["updated"] if results_data else 0
            return updated > 0

        except Exception as e:
            logger.error(f"Error updating procedure status: {e}")
            return False

    # ========================================
    # Medical Devices and Implants
    # ========================================

    async def add_medical_device(
        self,
        patient_id: str,
        name: str,
        device_type: str,  # stoma, implant, prosthetic, pump, monitor
        placement_date: Optional[str] = None,
        status: str = "active",  # active, removed, replaced
        location: Optional[str] = None,  # body location
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a medical device or implant for patient.

        Examples: colostomy, ileostomy, pacemaker, insulin pump, cochlear implant,
                  feeding tube, port-a-cath, prosthetic limb

        Args:
            patient_id: Patient identifier
            name: Device name (e.g., "colostomy", "pacemaker", "insulin pump")
            device_type: Type of device (stoma, implant, prosthetic, pump, monitor)
            placement_date: When device was placed/implanted
            status: Current status (active, removed, replaced)
            location: Body location of the device
            notes: Additional notes
            metadata: Additional metadata

        Returns:
            str: Device ID
        """
        device_id = f"device:{uuid.uuid4().hex[:12]}"
        logger.info(f"Adding medical device for patient {patient_id}: {name} ({device_type})")

        # Normalize the name
        normalized_name = name.strip().lower()

        # Store in Neo4j
        await self.neo4j.add_entity(
            device_id,
            {
                "name": name,
                "normalized_name": normalized_name,
                "device_type": device_type,
                "status": status,
                "placement_date": placement_date,
                "body_location": location,
                "notes": notes,
                "created_at": datetime.now().isoformat(),
                **(metadata or {})
            },
            labels=["MedicalDevice", "MedicalEntity"]
        )

        await self.neo4j.add_relationship(
            patient_id,
            "HAS_DEVICE",
            device_id,
            {
                "recorded_at": datetime.now().isoformat(),
                "status": status
            }
        )

        # Store in Mem0 for conversational recall - important for dietary/lifestyle advice
        self.mem0.add(
            f"Patient has a {name} ({device_type})" +
            (f" placed on {placement_date}" if placement_date else "") +
            (f" at {location}" if location else ""),
            user_id=patient_id,
            metadata={
                "type": "medical_device",
                "name": name,
                "device_type": device_type,
                "status": status,
                "important": True  # Devices are important for care planning
            }
        )

        logger.info(f"Medical device added successfully: {device_id}")
        return device_id

    async def update_device_status(
        self,
        patient_id: str,
        device_name: str,
        new_status: str,
        removal_date: Optional[str] = None,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update the status of a medical device.

        Args:
            patient_id: Patient identifier
            device_name: Name of the device
            new_status: New status (active, removed, replaced)
            removal_date: When removed/replaced
            reason: Reason for status change

        Returns:
            bool: True if updated
        """
        logger.info(f"Updating device '{device_name}' status to '{new_status}' for patient {patient_id}")

        try:
            query = """
            MATCH (p:Patient {id: $patient_id})-[r:HAS_DEVICE]->(dev:MedicalDevice)
            WHERE toLower(dev.name) CONTAINS toLower($device_name)
               OR toLower(dev.normalized_name) CONTAINS toLower($device_name)
            SET dev.status = $new_status,
                dev.removal_date = $removal_date,
                dev.status_change_reason = $reason,
                dev.updated_at = $updated_at,
                r.status = $new_status
            RETURN count(dev) as updated
            """

            results = await self.neo4j.query_raw(query, {
                "patient_id": patient_id,
                "device_name": device_name.lower(),
                "new_status": new_status,
                "removal_date": removal_date,
                "reason": reason,
                "updated_at": datetime.now().isoformat()
            })

            updated = results[0]["updated"] if results else 0
            return updated > 0

        except Exception as e:
            logger.error(f"Error updating device status: {e}")
            return False

    # ========================================
    # Diagnosis Status Management
    # ========================================

    async def resolve_diagnosis(
        self,
        patient_id: str,
        diagnosis_name: str,
        resolution_date: Optional[datetime] = None,
        resolution_reason: Optional[str] = None
    ) -> bool:
        """
        Mark a diagnosis/condition as resolved.

        Args:
            patient_id: Patient identifier
            diagnosis_name: Name of the condition to resolve
            resolution_date: When the condition resolved (optional)
            resolution_reason: Why/how it resolved (optional)

        Returns:
            bool: True if resolved, False if not found
        """
        return await self.update_diagnosis_status(
            patient_id=patient_id,
            diagnosis_name=diagnosis_name,
            new_status="resolved",
            reason=resolution_reason,
            status_date=resolution_date
        )

    async def remove_diagnosis(
        self,
        patient_id: str,
        diagnosis_name: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Remove a diagnosis record from patient.

        Used when patient denies having a condition that was previously recorded.

        Args:
            patient_id: Patient identifier
            diagnosis_name: Name of the condition to remove
            reason: Reason for removal (optional)

        Returns:
            bool: True if removed, False if not found
        """
        return await self.update_diagnosis_status(
            patient_id=patient_id,
            diagnosis_name=diagnosis_name,
            new_status="denied",
            reason=reason or "Patient denied having this condition"
        )

    async def update_diagnosis_status(
        self,
        patient_id: str,
        diagnosis_name: str,
        new_status: str,
        reason: Optional[str] = None,
        status_date: Optional[datetime] = None
    ) -> bool:
        """
        Update diagnosis status (e.g., mark as resolved, chronic, in_remission).

        Args:
            patient_id: Patient identifier
            diagnosis_name: Name of the diagnosis
            new_status: New status (active, resolved, chronic, in_remission)
            reason: Reason for status change (optional)
            status_date: Date of status change (optional)

        Returns:
            bool: True if updated, False if not found
        """
        logger.info(f"Updating diagnosis status for {patient_id}: {diagnosis_name} -> {new_status}")

        try:
            # Update in Neo4j using fuzzy match on condition name
            query = """
            MATCH (p:Patient {id: $patient_id})-[:HAS_DIAGNOSIS]->(dx:Diagnosis)
            WHERE toLower(dx.condition) CONTAINS toLower($diagnosis_name)
               OR toLower(dx.name) CONTAINS toLower($diagnosis_name)
            SET dx.status = $new_status,
                dx.status_changed_at = datetime(),
                dx.resolution_date = $resolution_date,
                dx.resolution_reason = $reason
            RETURN dx.id as dx_id, dx.condition as condition
            """
            results = await self.neo4j.query_raw(query, {
                "patient_id": patient_id,
                "diagnosis_name": diagnosis_name,
                "new_status": new_status,
                "resolution_date": (status_date or datetime.now()).isoformat() if new_status == "resolved" else None,
                "reason": reason
            })

            if results:
                condition = results[0].get("condition", diagnosis_name)
                # Update Mem0 with status change
                self.mem0.add(
                    f"Patient's {condition} has been marked as {new_status}" +
                    (f" - {reason}" if reason else ""),
                    user_id=patient_id,
                    metadata={
                        "type": "diagnosis_status_change",
                        "condition": condition,
                        "status": new_status,
                        "event": "condition_resolved" if new_status == "resolved" else "status_update"
                    }
                )
                logger.info(f"Diagnosis status updated: {condition} -> {new_status}")
                return True

            # No formal diagnosis found in Neo4j, but still record in Mem0
            # This handles cases where the condition was only stored in Mem0 memories
            logger.warning(f"No formal diagnosis found for '{diagnosis_name}', recording resolution in memory only")
            self.mem0.add(
                f"Patient reported that their {diagnosis_name} has {new_status}" +
                (f" - {reason}" if reason else ""),
                user_id=patient_id,
                metadata={
                    "type": "condition_resolution",
                    "condition": diagnosis_name,
                    "status": new_status,
                    "event": "condition_resolved",
                    "note": "No formal diagnosis record existed"
                }
            )
            return True  # Return True since we recorded the resolution in memory

        except Exception as e:
            logger.error(f"Error updating diagnosis status: {e}", exc_info=True)
            return False

    async def get_active_diagnoses(
        self,
        patient_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get only active (non-resolved) diagnoses for a patient.

        Args:
            patient_id: Patient identifier

        Returns:
            List of active diagnosis dictionaries
        """
        logger.debug(f"Retrieving active diagnoses for patient: {patient_id}")

        try:
            query = """
            MATCH (p:Patient {id: $patient_id})-[:HAS_DIAGNOSIS]->(dx:Diagnosis)
            WHERE dx.status IS NULL OR dx.status IN ['active', 'chronic']
            RETURN dx
            ORDER BY dx.recorded_at DESC
            """
            results = await self.neo4j.query_raw(query, {"patient_id": patient_id})

            diagnoses = []
            for record in results:
                dx_node = record["dx"]
                diagnoses.append(self._parse_diagnosis(dx_node))

            logger.debug(f"Retrieved {len(diagnoses)} active diagnoses for patient {patient_id}")
            return diagnoses

        except Exception as e:
            logger.error(f"Error retrieving active diagnoses: {e}", exc_info=True)
            return []

    async def get_recently_resolved_conditions(
        self,
        patient_id: str,
        days: int = 7
    ) -> List[str]:
        """
        Get conditions resolved within the last N days.

        Checks both Neo4j (formal diagnoses) and Mem0 (informal mentions).
        Useful for providing continuity in conversations
        (e.g., "Glad your knee pain has resolved!").

        Args:
            patient_id: Patient identifier
            days: Number of days to look back

        Returns:
            List of recently resolved condition names
        """
        logger.debug(f"Retrieving recently resolved conditions for patient: {patient_id}")
        resolved_conditions = set()

        # 1. Check Neo4j for formal diagnoses marked as resolved
        try:
            query = """
            MATCH (p:Patient {id: $patient_id})-[:HAS_DIAGNOSIS]->(dx:Diagnosis)
            WHERE dx.status = 'resolved'
            RETURN dx.condition as condition
            """
            results = await self.neo4j.query_raw(query, {"patient_id": patient_id})

            for record in results:
                if record.get("condition"):
                    resolved_conditions.add(record["condition"])

        except Exception as e:
            logger.warning(f"Error querying Neo4j for resolved conditions: {e}")

        # 2. Check Mem0 for resolution events (catches informal resolutions)
        try:
            memories = self.mem0.get_all(
                user_id=patient_id,
                limit=30  # Check recent memories
            )

            if memories and "results" in memories:
                # Filter to only include memories for this patient (security check)
                filtered_memories = [
                    m for m in memories["results"]
                    if (m.get("user_id") or m.get("metadata", {}).get("user_id")) in (None, patient_id)
                ]
                for memory in filtered_memories:
                    memory_text = memory.get("memory", "").lower()
                    metadata = memory.get("metadata", {})

                    # Check for resolution metadata
                    if metadata.get("event") == "condition_resolved":
                        condition = metadata.get("condition")
                        if condition:
                            resolved_conditions.add(condition)

                    # Also check memory text for resolution phrases
                    resolution_phrases = [
                        "no longer have", "has resolved", "is gone",
                        "went away", "has cleared", "is better",
                        "has been marked as resolved"
                    ]
                    if any(phrase in memory_text for phrase in resolution_phrases):
                        # Extract condition from memory text
                        condition = self._extract_condition_from_resolution(memory_text)
                        if condition:
                            resolved_conditions.add(condition)

        except Exception as e:
            logger.warning(f"Error checking Mem0 for resolved conditions: {e}")

        logger.debug(f"Found {len(resolved_conditions)} recently resolved conditions")
        return list(resolved_conditions)

    def _extract_condition_from_resolution(self, text: str) -> Optional[str]:
        """
        Extract condition name from a resolution statement.

        Args:
            text: Memory text (lowercased)

        Returns:
            Condition name or None
        """
        import re

        # Patterns to extract conditions from resolution statements
        patterns = [
            r"(?:no longer have|has resolved|is gone|went away|is better|has cleared)[:\s]+(?:the\s+)?([a-z\s]+?)(?:\s*[-.]|$)",
            r"(?:their|my)\s+([a-z\s]+?)\s+(?:has\s+)?(?:resolved|gone|better|cleared)",
            r"([a-z\s]+?)\s+(?:has been marked as resolved|is no longer)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                condition = match.group(1).strip()
                # Filter out common words
                if condition and condition not in ["it", "this", "that", "the"]:
                    return condition

        return None

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

        # 1. Store in Mem0 (automatic fact extraction) - ONLY for user messages
        # We only want to extract facts from what the PATIENT says, not from
        # assistant responses (which contain generic advice, not patient facts)
        if message.role == "user":
            # Add context to help Mem0's LLM extract facts correctly
            # This prevents confusion between the patient and the assistant "Matucha"
            context_prefix = (
                "The following is a message from the PATIENT (user) to the medical assistant named Matucha. "
                "Extract facts about the PATIENT only, not about Matucha who is the AI assistant. "
                "Patient message: "
            )
            self.mem0.add(
                context_prefix + message.content,
                user_id=message.patient_id,
                metadata={
                    "role": message.role,
                    "session_id": message.session_id,
                    "timestamp": message.timestamp.isoformat()
                }
            )

        # 2. Store in Neo4j (full message log) - both user and assistant
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

            # Filter to only include memories for this patient (security check)
            filtered_memories = [
                m for m in memories["results"]
                if (m.get("user_id") or m.get("metadata", {}).get("user_id")) in (None, patient_id)
            ]

            # Extract topics from memories
            topics = []
            for memory in filtered_memories[:limit]:
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

            # Filter to only include memories for this patient (security check)
            filtered_memories = [
                m for m in memories["results"]
                if (m.get("user_id") or m.get("metadata", {}).get("user_id")) in (None, patient_id)
            ]

            # Combine recent memories into summary
            recent_memories = [m.get("memory", "") for m in filtered_memories[:3]]
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
            # Use specific query for ConversationSession to ensure we update the correct node
            query = """
            MATCH (s:ConversationSession {id: $session_id})
            SET s.title = $title, s.updated_at = $updated_at
            RETURN s.title as new_title
            """
            result = await self.neo4j.query_raw(query, {
                "session_id": session_id,
                "title": title,
                "updated_at": datetime.now().isoformat()
            })

            if result and len(result) > 0:
                logger.info(f"Session {session_id} title updated to '{result[0].get('new_title')}'")
                return True
            else:
                logger.warning(f"Session {session_id} not found for title update")
                return False

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
