"""Layer Transition Service.

Manages entity promotion between knowledge layers (DIKW hierarchy):
PERCEPTION → SEMANTIC → REASONING → APPLICATION

Features:
- Entity promotion with validation
- Lineage tracking across transitions
- Version control for evolving entities
- Audit trail for compliance
- Transition eligibility checks
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Layer(str, Enum):
    """Knowledge layer enumeration."""
    PERCEPTION = "PERCEPTION"
    SEMANTIC = "SEMANTIC"
    REASONING = "REASONING"
    APPLICATION = "APPLICATION"


class TransitionStatus(str, Enum):
    """Transition status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class LayerTransitionRequest:
    """Request to transition an entity between layers."""
    entity_id: str
    from_layer: Layer
    to_layer: Layer
    reason: str
    requested_by: str = "system"
    requested_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerTransitionRecord:
    """Record of a layer transition."""
    transition_id: str
    entity_id: str
    entity_name: str
    from_layer: Layer
    to_layer: Layer
    reason: str
    status: TransitionStatus
    requested_by: str
    requested_at: datetime
    completed_at: Optional[datetime] = None
    approval_required: bool = False
    approved_by: Optional[str] = None
    validation_results: Dict[str, Any] = field(default_factory=dict)
    lineage: List[str] = field(default_factory=list)  # Previous entity versions
    properties_changed: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class LayerTransitionService:
    """
    Service for managing entity transitions between knowledge layers.

    Ensures:
    - Valid layer transitions (following DIKW hierarchy)
    - Required properties for target layer
    - Lineage and provenance tracking
    - Audit trail for compliance
    """

    # Layer hierarchy (can transition upward or laterally, not downward)
    LAYER_HIERARCHY = {
        Layer.PERCEPTION: 0,
        Layer.SEMANTIC: 1,
        Layer.REASONING: 2,
        Layer.APPLICATION: 3
    }

    # Required properties per layer
    LAYER_REQUIREMENTS = {
        Layer.PERCEPTION: ["source", "origin"],
        Layer.SEMANTIC: ["description", "domain"],
        Layer.REASONING: ["confidence", "reasoning"],
        Layer.APPLICATION: ["usage_context", "access_pattern"]
    }

    def __init__(
        self,
        backend: Any,
        require_approval: bool = False,
        auto_version: bool = True
    ):
        """
        Initialize layer transition service.

        Args:
            backend: Knowledge graph backend
            require_approval: Whether transitions need manual approval
            auto_version: Automatically version entities on transition
        """
        self.backend = backend
        self.require_approval = require_approval
        self.auto_version = auto_version

        # Track transitions
        self.transition_history: List[LayerTransitionRecord] = []
        self.pending_transitions: Dict[str, LayerTransitionRecord] = {}

        self._transition_counter = 0

    def validate_transition(
        self,
        entity_data: Dict[str, Any],
        from_layer: Layer,
        to_layer: Layer
    ) -> Tuple[bool, List[str]]:
        """
        Validate if a transition is allowed.

        Args:
            entity_data: Entity data
            from_layer: Current layer
            to_layer: Target layer

        Returns:
            Tuple of (is_valid, list of validation errors)
        """
        errors = []

        # Check layer hierarchy (can't go backwards)
        from_level = self.LAYER_HIERARCHY[from_layer]
        to_level = self.LAYER_HIERARCHY[to_layer]

        if to_level < from_level:
            errors.append(
                f"Cannot transition backwards from {from_layer.value} to {to_layer.value}. "
                f"Transitions should follow DIKW hierarchy upward."
            )

        # Check if entity has required properties for target layer
        required_props = self.LAYER_REQUIREMENTS.get(to_layer, [])
        entity_props = entity_data.get("properties", {})

        for prop in required_props:
            if prop not in entity_props or not entity_props[prop]:
                errors.append(
                    f"Missing required property '{prop}' for {to_layer.value} layer"
                )

        # Layer-specific validations
        if to_layer == Layer.REASONING:
            # Reasoning layer must have confidence score
            if "confidence" not in entity_props:
                errors.append("REASONING layer entities must have confidence scores")
            elif not (0.0 <= entity_props.get("confidence", -1) <= 1.0):
                errors.append("Confidence score must be between 0.0 and 1.0")

        if to_layer == Layer.SEMANTIC:
            # Semantic layer should have domain classification
            if "domain" not in entity_props:
                errors.append("SEMANTIC layer entities should have domain classification")

        is_valid = len(errors) == 0
        return is_valid, errors

    def request_transition(
        self,
        request: LayerTransitionRequest
    ) -> LayerTransitionRecord:
        """
        Request a layer transition.

        Args:
            request: Transition request

        Returns:
            Transition record
        """
        self._transition_counter += 1
        transition_id = f"transition_{self._transition_counter:06d}"

        # Create transition record
        record = LayerTransitionRecord(
            transition_id=transition_id,
            entity_id=request.entity_id,
            entity_name=request.metadata.get("entity_name", "unknown"),
            from_layer=request.from_layer,
            to_layer=request.to_layer,
            reason=request.reason,
            status=TransitionStatus.PENDING,
            requested_by=request.requested_by,
            requested_at=request.requested_at,
            approval_required=self.require_approval
        )

        # If approval required, add to pending queue
        if self.require_approval:
            self.pending_transitions[transition_id] = record
            logger.info(
                f"Transition {transition_id} pending approval: "
                f"{request.entity_id} {request.from_layer.value} → {request.to_layer.value}"
            )
        else:
            # Auto-approve
            record.status = TransitionStatus.APPROVED
            record.approved_by = "system"
            logger.info(
                f"Transition {transition_id} auto-approved: "
                f"{request.entity_id} {request.from_layer.value} → {request.to_layer.value}"
            )

        self.transition_history.append(record)
        return record

    async def execute_transition(
        self,
        transition_id: str,
        entity_data: Dict[str, Any]
    ) -> LayerTransitionRecord:
        """
        Execute a layer transition.

        Args:
            transition_id: Transition identifier
            entity_data: Current entity data

        Returns:
            Updated transition record
        """
        # Find transition record
        record = next(
            (t for t in self.transition_history if t.transition_id == transition_id),
            None
        )

        if not record:
            raise ValueError(f"Transition {transition_id} not found")

        if record.status not in [TransitionStatus.PENDING, TransitionStatus.APPROVED]:
            raise ValueError(f"Transition {transition_id} is not executable (status: {record.status})")

        try:
            # Validate transition
            is_valid, errors = self.validate_transition(
                entity_data,
                record.from_layer,
                record.to_layer
            )

            record.validation_results = {
                "is_valid": is_valid,
                "errors": errors,
                "validated_at": datetime.now().isoformat()
            }

            if not is_valid:
                record.status = TransitionStatus.REJECTED
                record.error_message = f"Validation failed: {'; '.join(errors)}"
                logger.warning(f"Transition {transition_id} rejected: {record.error_message}")
                return record

            # Create new version if auto_version enabled
            if self.auto_version:
                new_entity_id = await self._create_versioned_entity(
                    entity_data,
                    record.to_layer
                )
                record.lineage.append(record.entity_id)
                record.entity_id = new_entity_id
                logger.info(f"Created new version: {new_entity_id}")

            # Update entity layer in graph
            await self._update_entity_layer(
                record.entity_id,
                record.to_layer
            )

            # Track property changes
            record.properties_changed = self._compute_property_changes(
                entity_data,
                record.to_layer
            )

            # Mark as completed
            record.status = TransitionStatus.COMPLETED
            record.completed_at = datetime.now()

            # Remove from pending if applicable
            if transition_id in self.pending_transitions:
                del self.pending_transitions[transition_id]

            logger.info(
                f"Transition {transition_id} completed: "
                f"{record.entity_id} now in {record.to_layer.value} layer"
            )

        except Exception as e:
            record.status = TransitionStatus.FAILED
            record.error_message = str(e)
            record.completed_at = datetime.now()
            logger.error(f"Transition {transition_id} failed: {str(e)}")

        return record

    async def _create_versioned_entity(
        self,
        entity_data: Dict[str, Any],
        new_layer: Layer
    ) -> str:
        """
        Create a new version of an entity for the target layer.

        Args:
            entity_data: Original entity data
            new_layer: Target layer

        Returns:
            New entity ID
        """
        original_id = entity_data.get("id", "")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate new ID with version suffix
        new_id = f"{original_id}_v{timestamp}"

        # Create new entity in graph (pseudo-code, actual implementation depends on backend)
        new_entity_data = entity_data.copy()
        new_entity_data["id"] = new_id
        new_entity_data["previous_version"] = original_id
        new_entity_data["layer"] = new_layer.value
        new_entity_data["version_created_at"] = datetime.now().isoformat()

        # Here you would actually create the entity in the graph
        # await self.backend.create_entity(new_entity_data)

        return new_id

    async def _update_entity_layer(
        self,
        entity_id: str,
        new_layer: Layer
    ) -> None:
        """
        Update entity's layer property in the graph.

        Args:
            entity_id: Entity identifier
            new_layer: New layer
        """
        # Pseudo-code for updating layer property
        # await self.backend.update_property(entity_id, "layer", new_layer.value)
        logger.debug(f"Updated {entity_id} layer to {new_layer.value}")

    def _compute_property_changes(
        self,
        entity_data: Dict[str, Any],
        new_layer: Layer
    ) -> Dict[str, Any]:
        """
        Compute what properties were added/modified for the new layer.

        Args:
            entity_data: Entity data
            new_layer: New layer

        Returns:
            Dictionary of property changes
        """
        changes = {
            "layer": {"old": entity_data.get("layer"), "new": new_layer.value},
            "added_properties": [],
            "modified_properties": []
        }

        # Check required properties for new layer
        required_props = self.LAYER_REQUIREMENTS.get(new_layer, [])
        entity_props = entity_data.get("properties", {})

        for prop in required_props:
            if prop in entity_props:
                changes["added_properties"].append(prop)

        return changes

    def approve_transition(
        self,
        transition_id: str,
        approved_by: str
    ) -> Optional[LayerTransitionRecord]:
        """
        Approve a pending transition.

        Args:
            transition_id: Transition identifier
            approved_by: Approver identifier

        Returns:
            Updated transition record or None if not found
        """
        if transition_id not in self.pending_transitions:
            logger.warning(f"Transition {transition_id} not in pending queue")
            return None

        record = self.pending_transitions[transition_id]
        record.status = TransitionStatus.APPROVED
        record.approved_by = approved_by

        logger.info(f"Transition {transition_id} approved by {approved_by}")

        return record

    def reject_transition(
        self,
        transition_id: str,
        reason: str
    ) -> Optional[LayerTransitionRecord]:
        """
        Reject a pending transition.

        Args:
            transition_id: Transition identifier
            reason: Rejection reason

        Returns:
            Updated transition record or None if not found
        """
        if transition_id not in self.pending_transitions:
            logger.warning(f"Transition {transition_id} not in pending queue")
            return None

        record = self.pending_transitions[transition_id]
        record.status = TransitionStatus.REJECTED
        record.error_message = reason
        record.completed_at = datetime.now()

        # Remove from pending
        del self.pending_transitions[transition_id]

        logger.info(f"Transition {transition_id} rejected: {reason}")

        return record

    def get_entity_lineage(self, entity_id: str) -> List[LayerTransitionRecord]:
        """
        Get transition lineage for an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            List of transition records in chronological order
        """
        lineage = [
            t for t in self.transition_history
            if entity_id in [t.entity_id] + t.lineage
        ]

        # Sort by request time
        lineage.sort(key=lambda t: t.requested_at)

        return lineage

    def get_layer_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about layer transitions.

        Returns:
            Statistics dictionary
        """
        completed = [t for t in self.transition_history if t.status == TransitionStatus.COMPLETED]

        # Count transitions per layer pair
        transition_counts: Dict[str, int] = {}
        for trans in completed:
            key = f"{trans.from_layer.value} → {trans.to_layer.value}"
            transition_counts[key] = transition_counts.get(key, 0) + 1

        # Average transition time for completed transitions
        transition_times = [
            (t.completed_at - t.requested_at).total_seconds()
            for t in completed
            if t.completed_at
        ]
        avg_time = sum(transition_times) / len(transition_times) if transition_times else 0

        return {
            "total_transitions": len(self.transition_history),
            "completed": len(completed),
            "pending": len(self.pending_transitions),
            "rejected": len([t for t in self.transition_history if t.status == TransitionStatus.REJECTED]),
            "failed": len([t for t in self.transition_history if t.status == TransitionStatus.FAILED]),
            "transition_counts": transition_counts,
            "avg_transition_time_seconds": avg_time
        }

    def get_pending_transitions(self) -> List[LayerTransitionRecord]:
        """
        Get all pending transitions.

        Returns:
            List of pending transition records
        """
        return list(self.pending_transitions.values())
