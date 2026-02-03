"""Automatic Layer Transition Service.

Implements automatic promotion of entities between knowledge layers based on
configurable thresholds and validation criteria:

- PERCEPTION → SEMANTIC: confidence >= 0.85, ontology match, or 3+ validations
- SEMANTIC → REASONING: confidence >= 0.90, inference rule fires, or 5+ references
- REASONING → APPLICATION: 10+ queries in 24 hours, cache hit rate >= 0.50

Subscribes to:
- entity_created: Check PERCEPTION promotion candidates
- entity_updated: Check SEMANTIC/REASONING promotion candidates
- query_executed: Track APPLICATION layer promotion

Publishes:
- layer_transition_completed: Audit trail for promotions
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

from domain.event import KnowledgeEvent
from domain.roles import Role
from application.event_bus import EventBus
from application.services.layer_transition import (
    LayerTransitionService,
    LayerTransitionRequest,
    LayerTransitionRecord,
    Layer,
    TransitionStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class PromotionThresholds:
    """Configurable thresholds for automatic layer promotion."""

    # PERCEPTION → SEMANTIC
    perception_confidence_threshold: float = 0.85
    perception_validation_count: int = 3
    perception_ontology_match_required: bool = False

    # SEMANTIC → REASONING
    semantic_confidence_threshold: float = 0.90
    semantic_reference_count: int = 5
    semantic_inference_rule_required: bool = False

    # REASONING → APPLICATION
    reasoning_query_frequency: int = 10
    reasoning_time_window_hours: int = 24
    reasoning_cache_hit_rate: float = 0.50


@dataclass
class QueryTracker:
    """Tracks query patterns for APPLICATION layer promotion."""
    entity_id: str
    query_count: int = 0
    first_query_at: Optional[datetime] = None
    last_query_at: Optional[datetime] = None
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class AutomaticLayerTransitionService:
    """
    Service for automatic promotion of entities between knowledge layers.

    Monitors events and promotes entities when they meet configurable
    thresholds for confidence, validation, and usage patterns.
    """

    def __init__(
        self,
        backend: Any,  # Neo4jBackend or compatible
        event_bus: EventBus,
        thresholds: Optional[PromotionThresholds] = None,
        enable_auto_promotion: bool = True,
    ):
        """
        Initialize automatic layer transition service.

        Args:
            backend: Knowledge graph backend with layer-aware methods
            event_bus: Event bus for subscribing to and publishing events
            thresholds: Promotion thresholds (uses defaults if not provided)
            enable_auto_promotion: Whether to automatically promote entities
        """
        self.backend = backend
        self.event_bus = event_bus
        self.thresholds = thresholds or PromotionThresholds()
        self.enable_auto_promotion = enable_auto_promotion

        # Internal transition service for executing promotions
        self._transition_service = LayerTransitionService(
            backend=backend,
            require_approval=False,
            auto_version=True
        )

        # Track queries for APPLICATION promotion
        self._query_trackers: Dict[str, QueryTracker] = {}

        # Promotion statistics
        self.stats = {
            "promotions_attempted": 0,
            "promotions_completed": 0,
            "promotions_rejected": 0,
            "by_layer": {
                "PERCEPTION_TO_SEMANTIC": 0,
                "SEMANTIC_TO_REASONING": 0,
                "REASONING_TO_APPLICATION": 0,
            }
        }

        # Subscribe to events
        self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events on the event bus."""
        self.event_bus.subscribe("entity_created", self._handle_entity_created)
        self.event_bus.subscribe("entity_updated", self._handle_entity_updated)
        self.event_bus.subscribe("query_executed", self._handle_query_executed)
        logger.info("AutomaticLayerTransitionService subscribed to events")

    async def _handle_entity_created(self, event: KnowledgeEvent) -> None:
        """Handle entity_created events for PERCEPTION promotion checks."""
        if not self.enable_auto_promotion:
            return

        entity_data = event.data
        entity_id = entity_data.get("id")
        current_layer = entity_data.get("layer", "PERCEPTION")

        if current_layer != "PERCEPTION":
            return

        logger.debug(f"Checking promotion for new PERCEPTION entity: {entity_id}")

        # Check if entity meets PERCEPTION → SEMANTIC criteria
        if await self._check_perception_promotion(entity_data):
            await self._promote_entity(
                entity_id=entity_id,
                entity_data=entity_data,
                from_layer=Layer.PERCEPTION,
                to_layer=Layer.SEMANTIC,
                reason="Auto-promotion: Met confidence and validation thresholds"
            )

    async def _handle_entity_updated(self, event: KnowledgeEvent) -> None:
        """Handle entity_updated events for SEMANTIC/REASONING promotion checks."""
        if not self.enable_auto_promotion:
            return

        entity_data = event.data
        entity_id = entity_data.get("id")
        current_layer = entity_data.get("layer")

        if current_layer == "SEMANTIC":
            if await self._check_semantic_promotion(entity_data):
                await self._promote_entity(
                    entity_id=entity_id,
                    entity_data=entity_data,
                    from_layer=Layer.SEMANTIC,
                    to_layer=Layer.REASONING,
                    reason="Auto-promotion: Met confidence and reference thresholds"
                )

        elif current_layer == "REASONING":
            # Reasoning promotion is handled by query tracking, not updates
            pass

    async def _handle_query_executed(self, event: KnowledgeEvent) -> None:
        """Handle query_executed events for REASONING → APPLICATION promotion."""
        if not self.enable_auto_promotion:
            return

        query_data = event.data
        entities_involved = query_data.get("entities_involved", [])
        cache_hit = query_data.get("cache_hit", False)

        for entity_ref in entities_involved:
            entity_id = entity_ref.get("id") if isinstance(entity_ref, dict) else entity_ref
            entity_layer = entity_ref.get("layer") if isinstance(entity_ref, dict) else None

            # Only track REASONING layer entities
            if entity_layer != "REASONING":
                # Try to get layer from backend if not provided
                if entity_layer is None and hasattr(self.backend, "get_entity"):
                    try:
                        entity = await self.backend.get_entity(entity_id)
                        if entity:
                            entity_layer = entity.get("layer")
                    except Exception:
                        pass

            if entity_layer != "REASONING":
                continue

            # Update query tracker
            tracker = self._get_or_create_tracker(entity_id)
            tracker.query_count += 1
            tracker.last_query_at = datetime.now()
            if tracker.first_query_at is None:
                tracker.first_query_at = tracker.last_query_at

            if cache_hit:
                tracker.cache_hits += 1
            else:
                tracker.cache_misses += 1

            # Check if entity should be promoted to APPLICATION
            if await self._check_reasoning_promotion(entity_id, tracker):
                # Get full entity data
                entity_data = await self._get_entity_data(entity_id)
                if entity_data:
                    await self._promote_entity(
                        entity_id=entity_id,
                        entity_data=entity_data,
                        from_layer=Layer.REASONING,
                        to_layer=Layer.APPLICATION,
                        reason=f"Auto-promotion: {tracker.query_count} queries, "
                               f"{tracker.cache_hit_rate:.2%} cache hit rate"
                    )
                    # Clear tracker after promotion
                    del self._query_trackers[entity_id]

    def _get_or_create_tracker(self, entity_id: str) -> QueryTracker:
        """Get or create a query tracker for an entity."""
        if entity_id not in self._query_trackers:
            self._query_trackers[entity_id] = QueryTracker(entity_id=entity_id)
        return self._query_trackers[entity_id]

    async def _get_entity_data(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch entity data from backend."""
        if hasattr(self.backend, "get_entity"):
            try:
                return await self.backend.get_entity(entity_id)
            except Exception as e:
                logger.warning(f"Failed to fetch entity {entity_id}: {e}")
        return None

    async def _check_perception_promotion(self, entity_data: Dict[str, Any]) -> bool:
        """
        Check if a PERCEPTION entity should be promoted to SEMANTIC.

        Criteria (any of):
        - confidence >= threshold
        - validation_count >= threshold
        - Has ontology match (SNOMED-CT, ICD-10, UMLS)
        """
        props = entity_data.get("properties", entity_data)

        # Check confidence (PERCEPTION entities use extraction_confidence)
        confidence = props.get("confidence", 0) or props.get("extraction_confidence", 0)
        if confidence >= self.thresholds.perception_confidence_threshold:
            logger.info(f"Entity meets confidence threshold: {confidence:.2f}")
            return True

        # Check validation count
        validation_count = props.get("validation_count", 0)
        if validation_count >= self.thresholds.perception_validation_count:
            logger.info(f"Entity meets validation count: {validation_count}")
            return True

        # Check ontology match
        ontology_codes = props.get("ontology_codes", [])
        snomed_code = props.get("snomed_code")
        umls_cui = props.get("umls_cui")
        icd10_code = props.get("icd10_code")

        has_ontology = bool(ontology_codes or snomed_code or umls_cui or icd10_code)
        if has_ontology:
            logger.info(f"Entity has ontology match")
            return True

        return False

    async def _check_semantic_promotion(self, entity_data: Dict[str, Any]) -> bool:
        """
        Check if a SEMANTIC entity should be promoted to REASONING.

        Criteria (any of):
        - confidence >= threshold after enrichment
        - Has inference rule fired
        - reference_count >= threshold
        """
        props = entity_data.get("properties", entity_data)
        entity_id = entity_data.get("id")

        # Check confidence
        confidence = props.get("confidence", 0)
        if confidence >= self.thresholds.semantic_confidence_threshold:
            logger.info(f"Entity {entity_id} meets semantic confidence: {confidence:.2f}")
            return True

        # Check if inference rule has fired
        inference_rules = props.get("inference_rules_applied", [])
        if inference_rules:
            logger.info(f"Entity {entity_id} has inference rules: {inference_rules}")
            return True

        # Check reference count
        reference_count = props.get("reference_count", 0)
        if reference_count >= self.thresholds.semantic_reference_count:
            logger.info(f"Entity {entity_id} meets reference count: {reference_count}")
            return True

        # Query backend for actual reference count if not in properties
        if hasattr(self.backend, "get_entity_reference_count"):
            try:
                actual_count = await self.backend.get_entity_reference_count(entity_id)
                if actual_count >= self.thresholds.semantic_reference_count:
                    logger.info(f"Entity {entity_id} has {actual_count} references")
                    return True
            except Exception as e:
                logger.debug(f"Could not get reference count: {e}")

        return False

    async def _check_reasoning_promotion(
        self,
        entity_id: str,
        tracker: QueryTracker
    ) -> bool:
        """
        Check if a REASONING entity should be promoted to APPLICATION.

        Criteria (all of):
        - query_count >= threshold within time window
        - cache_hit_rate >= threshold (optional)
        """
        # Check time window
        if tracker.first_query_at is None:
            return False

        time_window = timedelta(hours=self.thresholds.reasoning_time_window_hours)
        window_start = datetime.now() - time_window

        if tracker.first_query_at < window_start:
            # Reset tracker if outside window
            tracker.query_count = 1
            tracker.first_query_at = datetime.now()
            tracker.cache_hits = 0
            tracker.cache_misses = 0
            return False

        # Check query frequency
        if tracker.query_count < self.thresholds.reasoning_query_frequency:
            return False

        # Check cache hit rate
        if tracker.cache_hit_rate < self.thresholds.reasoning_cache_hit_rate:
            logger.debug(
                f"Entity {entity_id} cache hit rate {tracker.cache_hit_rate:.2%} "
                f"below threshold {self.thresholds.reasoning_cache_hit_rate:.2%}"
            )
            return False

        logger.info(
            f"Entity {entity_id} meets APPLICATION promotion: "
            f"{tracker.query_count} queries, {tracker.cache_hit_rate:.2%} cache rate"
        )
        return True

    async def _promote_entity(
        self,
        entity_id: str,
        entity_data: Dict[str, Any],
        from_layer: Layer,
        to_layer: Layer,
        reason: str
    ) -> Optional[LayerTransitionRecord]:
        """
        Execute entity promotion between layers.

        Args:
            entity_id: Entity identifier
            entity_data: Entity data
            from_layer: Source layer
            to_layer: Target layer
            reason: Promotion reason

        Returns:
            Transition record if successful
        """
        self.stats["promotions_attempted"] += 1

        try:
            # Prepare entity data with required properties for target layer
            enriched_data = self._enrich_for_layer(entity_data, to_layer)

            # Create transition request
            request = LayerTransitionRequest(
                entity_id=entity_id,
                from_layer=from_layer,
                to_layer=to_layer,
                reason=reason,
                requested_by="auto_promotion_service",
                metadata={
                    "entity_name": entity_data.get("name", entity_id),
                    "auto_promoted": True,
                    "thresholds_used": {
                        "confidence": self.thresholds.perception_confidence_threshold,
                        "validation_count": self.thresholds.perception_validation_count,
                    }
                }
            )

            # Request and execute transition
            record = self._transition_service.request_transition(request)
            record = await self._transition_service.execute_transition(
                record.transition_id,
                enriched_data
            )

            if record.status == TransitionStatus.COMPLETED:
                self.stats["promotions_completed"] += 1
                layer_key = f"{from_layer.value}_TO_{to_layer.value}"
                if layer_key in self.stats["by_layer"]:
                    self.stats["by_layer"][layer_key] += 1

                # Publish transition completed event
                await self._publish_transition_event(record, entity_data)

                # Update entity in backend
                await self._update_entity_in_backend(entity_id, to_layer, enriched_data)

                logger.info(
                    f"Successfully promoted {entity_id}: "
                    f"{from_layer.value} → {to_layer.value}"
                )
            else:
                self.stats["promotions_rejected"] += 1
                logger.warning(
                    f"Promotion rejected for {entity_id}: {record.error_message}"
                )

            return record

        except Exception as e:
            self.stats["promotions_rejected"] += 1
            logger.error(f"Failed to promote {entity_id}: {e}")
            return None

    def _enrich_for_layer(
        self,
        entity_data: Dict[str, Any],
        target_layer: Layer
    ) -> Dict[str, Any]:
        """
        Enrich entity data with required properties for target layer.

        Args:
            entity_data: Original entity data (can be flat dict or have properties sub-dict)
            target_layer: Target layer

        Returns:
            Enriched entity data
        """
        enriched = entity_data.copy()

        # Handle both flat entity data and nested properties structure
        if "properties" in enriched:
            props = enriched["properties"].copy()
        else:
            # Flat structure - use entity_data itself as properties
            props = enriched.copy()

        # Get name from either location
        entity_name = props.get("name", enriched.get("name", ""))

        # Add layer-specific properties
        if target_layer == Layer.SEMANTIC:
            props.setdefault("domain", "medical")
            props.setdefault("validated", True)
            props.setdefault("validated_at", datetime.now().isoformat())
            props.setdefault("description", entity_name or "Auto-promoted entity")

        elif target_layer == Layer.REASONING:
            props.setdefault("confidence", props.get("confidence", 0.85))
            props.setdefault("reasoning", "Auto-promoted based on validation criteria")
            props.setdefault("inference_rules_applied", [])

        elif target_layer == Layer.APPLICATION:
            props.setdefault("usage_context", "query_pattern")
            props.setdefault("access_pattern", "frequent_query")
            props.setdefault("promoted_at", datetime.now().isoformat())

        # Update layer property
        props["layer"] = target_layer.value
        props["promoted_from"] = entity_data.get("layer", "PERCEPTION")
        props["promotion_timestamp"] = datetime.now().isoformat()

        enriched["properties"] = props
        return enriched

    async def _publish_transition_event(
        self,
        record: LayerTransitionRecord,
        entity_data: Dict[str, Any]
    ) -> None:
        """Publish layer_transition_completed event."""
        event = KnowledgeEvent(
            action="layer_transition_completed",
            data={
                "transition_id": record.transition_id,
                "entity_id": record.entity_id,
                "entity_name": record.entity_name,
                "from_layer": record.from_layer.value,
                "to_layer": record.to_layer.value,
                "reason": record.reason,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                "entity_type": entity_data.get("type", entity_data.get("labels", [])),
            },
            role=Role.SYSTEM_ADMIN
        )
        await self.event_bus.publish(event)

    async def _update_entity_in_backend(
        self,
        entity_id: str,
        new_layer: Layer,
        enriched_data: Dict[str, Any]
    ) -> None:
        """Update entity layer in the backend."""
        if hasattr(self.backend, "promote_entity"):
            try:
                # Import the backend's KnowledgeLayer enum
                from infrastructure.neo4j_backend import KnowledgeLayer as BackendLayer

                # Map our Layer to backend's KnowledgeLayer
                target_layer = BackendLayer(new_layer.value)

                # Get properties - handle both flat and nested structures
                props = enriched_data.get("properties", enriched_data)

                await self.backend.promote_entity(
                    entity_id=entity_id,
                    target_layer=target_layer,
                    promotion_properties=props,
                    create_version=False  # Update in place rather than create new version
                )
            except Exception as e:
                logger.error(f"Failed to update entity in backend: {e}")

    async def scan_for_promotion_candidates(self, layer: str = "PERCEPTION") -> List[str]:
        """
        Scan for entities that are candidates for promotion.

        Args:
            layer: Layer to scan

        Returns:
            List of entity IDs that are promotion candidates
        """
        if not hasattr(self.backend, "get_promotion_candidates"):
            logger.warning("Backend does not support get_promotion_candidates")
            return []

        try:
            if layer == "PERCEPTION":
                return await self.backend.get_promotion_candidates(
                    from_layer="PERCEPTION",
                    confidence_threshold=self.thresholds.perception_confidence_threshold
                )
            elif layer == "SEMANTIC":
                return await self.backend.get_promotion_candidates(
                    from_layer="SEMANTIC",
                    confidence_threshold=self.thresholds.semantic_confidence_threshold
                )
            return []
        except Exception as e:
            logger.error(f"Failed to scan for candidates: {e}")
            return []

    async def run_promotion_scan(self) -> Dict[str, Any]:
        """
        Run a full scan for promotion candidates and promote them.

        Returns:
            Scan results with promotion statistics
        """
        results = {
            "scanned_layers": [],
            "candidates_found": 0,
            "promotions_executed": 0,
            "errors": []
        }

        for layer in ["PERCEPTION", "SEMANTIC"]:
            try:
                candidates = await self.scan_for_promotion_candidates(layer)
                results["scanned_layers"].append(layer)
                results["candidates_found"] += len(candidates)

                for candidate in candidates:
                    # Handle both dict candidates (from Neo4j) and string IDs
                    if isinstance(candidate, dict):
                        entity_id = candidate.get("id")
                        # Use candidate data directly if we have it
                        entity_data = candidate
                    else:
                        entity_id = candidate
                        entity_data = await self._get_entity_data(entity_id)

                    if entity_id and entity_data:
                        from_layer = Layer(layer)
                        to_layer = Layer.SEMANTIC if layer == "PERCEPTION" else Layer.REASONING

                        record = await self._promote_entity(
                            entity_id=entity_id,
                            entity_data=entity_data,
                            from_layer=from_layer,
                            to_layer=to_layer,
                            reason=f"Batch promotion scan"
                        )

                        if record and record.status == TransitionStatus.COMPLETED:
                            results["promotions_executed"] += 1

            except Exception as e:
                results["errors"].append(f"{layer}: {str(e)}")
                logger.error(f"Error scanning {layer}: {e}")

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get promotion statistics."""
        return {
            **self.stats,
            "thresholds": {
                "perception_confidence": self.thresholds.perception_confidence_threshold,
                "perception_validation_count": self.thresholds.perception_validation_count,
                "semantic_confidence": self.thresholds.semantic_confidence_threshold,
                "semantic_reference_count": self.thresholds.semantic_reference_count,
                "reasoning_query_frequency": self.thresholds.reasoning_query_frequency,
                "reasoning_time_window_hours": self.thresholds.reasoning_time_window_hours,
            },
            "active_trackers": len(self._query_trackers),
            "auto_promotion_enabled": self.enable_auto_promotion,
        }
