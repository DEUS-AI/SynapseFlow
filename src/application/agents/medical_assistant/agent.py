"""
Medical Assistant Agent - Manages patient memory and context.

Minimal implementation focused on memory operations (Phase 2A).
Advanced reasoning capabilities (contraindication checking, treatment analysis, etc.)
will be added in Phase 2E.
"""

from typing import Optional, Dict, Any
import logging

from domain.agent import Agent
from domain.command_bus import CommandBus
from domain.communication import CommunicationChannel, Message
from application.services.patient_memory_service import PatientMemoryService

logger = logging.getLogger(__name__)


class MedicalAssistantAgent(Agent):
    """
    Medical Assistant Agent - Manages patient memory and context.

    Current Scope (Phase 2A - Minimal):
    - Patient profile operations (get/create)
    - Medical history management (diagnoses, medications, allergies)
    - Conversation persistence
    - Privacy compliance

    Future Expansion (Phase 2E):
    - Contraindication checking
    - Treatment history analysis
    - Symptom tracking over time
    - Medication adherence monitoring
    """

    def __init__(
        self,
        agent_id: str,
        command_bus: CommandBus,
        communication_channel: CommunicationChannel,
        patient_memory_service: PatientMemoryService,
        url: Optional[str] = None
    ):
        """
        Initialize Medical Assistant Agent.

        Args:
            agent_id: Unique agent identifier
            command_bus: Command bus for inter-agent communication
            communication_channel: Communication channel for messages
            patient_memory_service: Patient memory service instance
            url: Optional agent URL
        """
        super().__init__(agent_id, command_bus, communication_channel)
        self.memory_service = patient_memory_service
        self.url = url

        # Agent capabilities (minimal for Phase 2A)
        self.capabilities = {
            "get_patient_context": True,
            "store_conversation": True,
            "manage_medical_history": True,
            "check_consent": True,

            # Future capabilities (Phase 2E)
            "check_contraindications": False,  # TODO: Phase 2E
            "analyze_treatment_history": False,  # TODO: Phase 2E
            "track_symptoms": False,  # TODO: Phase 2E
            "monitor_adherence": False  # TODO: Phase 2E
        }

        logger.info(f"Medical Assistant Agent initialized: {agent_id}")

    async def process_messages(self) -> None:
        """Process incoming messages from other agents."""
        while True:
            message = await self.receive_message()
            if not message:
                continue

            try:
                await self._handle_message(message)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await self.send_message(
                    message.sender_id,
                    {
                        "error": str(e),
                        "original_message_id": message.id
                    }
                )

    async def _handle_message(self, message: Message) -> None:
        """
        Route message to appropriate handler.

        Args:
            message: Incoming message
        """
        content = message.content

        if isinstance(content, dict):
            msg_type = content.get("type")

            if msg_type == "get_patient_context":
                await self._handle_get_patient_context(message, content)

            elif msg_type == "store_conversation":
                await self._handle_store_conversation(message, content)

            elif msg_type == "add_diagnosis":
                await self._handle_add_diagnosis(message, content)

            elif msg_type == "add_medication":
                await self._handle_add_medication(message, content)

            elif msg_type == "add_allergy":
                await self._handle_add_allergy(message, content)

            elif msg_type == "check_consent":
                await self._handle_check_consent(message, content)

            elif msg_type == "delete_patient_data":
                await self._handle_delete_patient_data(message, content)

            else:
                logger.warning(f"Unknown message type: {msg_type}")
                await self.send_message(
                    message.sender_id,
                    {"error": f"Unknown message type: {msg_type}"}
                )
        else:
            logger.warning(f"Invalid message format: {type(content)}")

    # ========================================
    # Message Handlers
    # ========================================

    async def _handle_get_patient_context(
        self,
        message: Message,
        content: Dict[str, Any]
    ) -> None:
        """
        Retrieve complete patient context.

        Args:
            message: Original message
            content: Message content with patient_id
        """
        patient_id = content.get("patient_id")

        if not patient_id:
            await self.send_message(
                message.sender_id,
                {"error": "patient_id required"}
            )
            return

        # Log audit
        await self.memory_service.log_audit(
            patient_id=patient_id,
            action="patient_context_access",
            actor=self.agent_id,
            details=f"Context retrieved by {message.sender_id}"
        )

        # Get context
        context = await self.memory_service.get_patient_context(patient_id)

        await self.send_message(
            message.sender_id,
            {
                "type": "patient_context_response",
                "patient_id": patient_id,
                "context": {
                    "diagnoses": context.diagnoses,
                    "medications": context.medications,
                    "allergies": context.allergies,
                    "recent_symptoms": context.recent_symptoms,
                    "conversation_summary": context.conversation_summary
                }
            }
        )

    async def _handle_store_conversation(
        self,
        message: Message,
        content: Dict[str, Any]
    ) -> None:
        """
        Store conversation message.

        Args:
            message: Original message
            content: Message content with conversation data
        """
        patient_id = content.get("patient_id")
        session_id = content.get("session_id")
        role = content.get("role")
        msg_content = content.get("content")

        if not all([patient_id, session_id, role, msg_content]):
            await self.send_message(
                message.sender_id,
                {"error": "Missing required fields"}
            )
            return

        # Check consent
        consent = await self.memory_service.check_consent(patient_id)
        if not consent:
            await self.send_message(
                message.sender_id,
                {"error": "Patient consent not given"}
            )
            return

        # Store message
        from application.services.patient_memory_service import ConversationMessage
        from datetime import datetime

        msg = ConversationMessage(
            role=role,
            content=msg_content,
            timestamp=datetime.now(),
            patient_id=patient_id,
            session_id=session_id,
            metadata=content.get("metadata", {})
        )

        msg_id = await self.memory_service.store_message(msg)

        await self.send_message(
            message.sender_id,
            {
                "type": "conversation_stored",
                "message_id": msg_id
            }
        )

    async def _handle_add_diagnosis(
        self,
        message: Message,
        content: Dict[str, Any]
    ) -> None:
        """
        Add diagnosis to patient record.

        Args:
            message: Original message
            content: Message content with diagnosis data
        """
        patient_id = content.get("patient_id")
        condition = content.get("condition")

        if not all([patient_id, condition]):
            await self.send_message(
                message.sender_id,
                {"error": "patient_id and condition required"}
            )
            return

        diagnosis_id = await self.memory_service.add_diagnosis(
            patient_id=patient_id,
            condition=condition,
            icd10_code=content.get("icd10_code"),
            diagnosed_date=content.get("diagnosed_date"),
            metadata=content.get("metadata")
        )

        await self.send_message(
            message.sender_id,
            {
                "type": "diagnosis_added",
                "diagnosis_id": diagnosis_id
            }
        )

    async def _handle_add_medication(
        self,
        message: Message,
        content: Dict[str, Any]
    ) -> None:
        """
        Add medication to patient record.

        Args:
            message: Original message
            content: Message content with medication data
        """
        patient_id = content.get("patient_id")
        name = content.get("name")
        dosage = content.get("dosage")
        frequency = content.get("frequency")

        if not all([patient_id, name, dosage, frequency]):
            await self.send_message(
                message.sender_id,
                {"error": "patient_id, name, dosage, frequency required"}
            )
            return

        med_id = await self.memory_service.add_medication(
            patient_id=patient_id,
            name=name,
            dosage=dosage,
            frequency=frequency,
            started_date=content.get("started_date"),
            metadata=content.get("metadata")
        )

        await self.send_message(
            message.sender_id,
            {
                "type": "medication_added",
                "medication_id": med_id
            }
        )

    async def _handle_add_allergy(
        self,
        message: Message,
        content: Dict[str, Any]
    ) -> None:
        """
        Add allergy to patient record.

        Args:
            message: Original message
            content: Message content with allergy data
        """
        patient_id = content.get("patient_id")
        substance = content.get("substance")
        reaction = content.get("reaction")

        if not all([patient_id, substance, reaction]):
            await self.send_message(
                message.sender_id,
                {"error": "patient_id, substance, reaction required"}
            )
            return

        allergy_id = await self.memory_service.add_allergy(
            patient_id=patient_id,
            substance=substance,
            reaction=reaction,
            severity=content.get("severity", "moderate")
        )

        await self.send_message(
            message.sender_id,
            {
                "type": "allergy_added",
                "allergy_id": allergy_id
            }
        )

    async def _handle_check_consent(
        self,
        message: Message,
        content: Dict[str, Any]
    ) -> None:
        """
        Check if patient has given consent.

        Args:
            message: Original message
            content: Message content with patient_id
        """
        patient_id = content.get("patient_id")

        if not patient_id:
            await self.send_message(
                message.sender_id,
                {"error": "patient_id required"}
            )
            return

        consent = await self.memory_service.check_consent(patient_id)

        await self.send_message(
            message.sender_id,
            {
                "type": "consent_check_response",
                "patient_id": patient_id,
                "consent_given": consent
            }
        )

    async def _handle_delete_patient_data(
        self,
        message: Message,
        content: Dict[str, Any]
    ) -> None:
        """
        Delete all patient data (GDPR right to be forgotten).

        Args:
            message: Original message
            content: Message content with patient_id
        """
        patient_id = content.get("patient_id")

        if not patient_id:
            await self.send_message(
                message.sender_id,
                {"error": "patient_id required"}
            )
            return

        # Log before deletion
        await self.memory_service.log_audit(
            patient_id=patient_id,
            action="patient_data_deletion",
            actor=self.agent_id,
            details=f"Data deletion requested by {message.sender_id}"
        )

        success = await self.memory_service.delete_patient_data(patient_id)

        await self.send_message(
            message.sender_id,
            {
                "type": "patient_data_deleted",
                "patient_id": patient_id,
                "success": success
            }
        )
