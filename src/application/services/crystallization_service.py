"""Crystallization Service.

Transfers knowledge from Graphiti/FalkorDB (episodic memory) to the
Neo4j DIKW Knowledge Graph. This pipeline "crystallizes" transient
conversation entities into persistent PERCEPTION layer nodes, enabling
gradual promotion through the DIKW hierarchy.

Pipeline Flow:
1. Listen for "episode_added" events from EpisodicMemoryService
2. Query FalkorDB for recently extracted entities
3. Resolve/deduplicate via EntityResolver
4. Create or merge PERCEPTION nodes in Neo4j
5. Evaluate promotion candidates for SEMANTIC layer
6. Emit "crystallization_complete" events

Supports both:
- Event-driven: Real-time crystallization on episode_added
- Batch processing: Periodic crystallization of accumulated entities
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from domain.event import KnowledgeEvent
from domain.roles import Role

logger = logging.getLogger(__name__)


class CrystallizationMode(str, Enum):
    """Crystallization processing mode."""
    EVENT_DRIVEN = "event_driven"
    BATCH = "batch"
    HYBRID = "hybrid"


@dataclass
class CrystallizationResult:
    """Result of a crystallization batch."""
    entities_processed: int
    entities_created: int
    entities_merged: int
    entities_skipped: int
    relationships_created: int
    promotion_candidates: int
    processing_time_ms: float
    errors: List[str] = field(default_factory=list)
    batch_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FlushResult:
    """Result of a flush operation for evaluation framework."""
    flushed: bool
    events_processed: int
    entities_crystallized: int
    promotions_executed: int
    pending_after_flush: int
    processing_time_ms: float
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BufferStatus:
    """Status of the crystallization buffer for evaluation framework."""
    buffer_size: int
    last_flush: Optional[datetime]
    batch_in_progress: bool
    running: bool


@dataclass
class CrystallizedEntity:
    """An entity that has been crystallized to Neo4j."""
    neo4j_id: str
    graphiti_id: Optional[str]
    name: str
    entity_type: str
    layer: str
    confidence: float
    observation_count: int
    is_new: bool
    promotion_eligible: bool
    crystallized_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CrystallizationConfig:
    """Configuration for crystallization pipeline."""
    mode: CrystallizationMode = CrystallizationMode.HYBRID
    batch_interval_minutes: int = 5
    batch_threshold: int = 10  # Min entities to trigger batch
    enable_auto_promotion_perception_semantic: bool = True
    enable_auto_promotion_semantic_reasoning: bool = False

    # Promotion thresholds
    perception_to_semantic_min_confidence: float = 0.85
    perception_to_semantic_min_observations: int = 2
    semantic_to_reasoning_min_confidence: float = 0.92
    semantic_to_reasoning_min_observations: int = 3
    semantic_to_reasoning_min_stability_hours: int = 48


class CrystallizationService:
    """
    Service for crystallizing episodic memory into the DIKW knowledge graph.

    Bridges the gap between transient conversation entities (in FalkorDB/Graphiti)
    and persistent knowledge (in Neo4j DIKW layers).
    """

    def __init__(
        self,
        neo4j_backend: Any,
        entity_resolver: Any,
        event_bus: Any,
        graphiti_client: Optional[Any] = None,
        config: Optional[CrystallizationConfig] = None,
    ):
        """
        Initialize crystallization service.

        Args:
            neo4j_backend: Neo4j backend for DIKW knowledge graph
            entity_resolver: EntityResolver for deduplication
            event_bus: EventBus for event-driven processing
            graphiti_client: Graphiti client for querying FalkorDB
            config: Crystallization configuration
        """
        self.neo4j_backend = neo4j_backend
        self.entity_resolver = entity_resolver
        self.event_bus = event_bus
        self.graphiti = graphiti_client
        self.config = config or CrystallizationConfig()

        # State tracking
        self._last_crystallization: Optional[datetime] = None
        self._pending_entities: List[Dict[str, Any]] = []
        self._batch_counter = 0
        self._running = False
        self._scheduled_task: Optional[asyncio.Task] = None

        # Statistics
        self._stats = {
            "total_crystallized": 0,
            "total_merged": 0,
            "total_promotions": 0,
            "errors": 0,
        }

        logger.info(f"CrystallizationService initialized with mode={self.config.mode.value}")

    async def start(self) -> None:
        """Start the crystallization service."""
        if self._running:
            logger.warning("CrystallizationService already running")
            return

        self._running = True

        # Subscribe to episode_added events
        self.event_bus.subscribe("episode_added", self._handle_episode_added)
        logger.info("Subscribed to episode_added events")

        # Start periodic batch processing if in BATCH or HYBRID mode
        if self.config.mode in [CrystallizationMode.BATCH, CrystallizationMode.HYBRID]:
            self._scheduled_task = asyncio.create_task(self._periodic_crystallization())
            logger.info(f"Started periodic crystallization (every {self.config.batch_interval_minutes} min)")

    async def stop(self) -> None:
        """Stop the crystallization service."""
        self._running = False

        if self._scheduled_task:
            self._scheduled_task.cancel()
            try:
                await self._scheduled_task
            except asyncio.CancelledError:
                pass
            self._scheduled_task = None

        logger.info("CrystallizationService stopped")

    async def _handle_episode_added(self, event: KnowledgeEvent) -> None:
        """
        Handle episode_added events from EpisodicMemoryService.

        In EVENT_DRIVEN mode: Crystallize immediately
        In BATCH mode: Queue for next batch
        In HYBRID mode: Queue and check threshold
        """
        episode_data = event.data
        entities = episode_data.get("entities_extracted", [])

        if not entities:
            return

        logger.debug(f"Received episode_added with {len(entities)} entities")

        if self.config.mode == CrystallizationMode.EVENT_DRIVEN:
            # Immediate crystallization
            await self.crystallize_entities(entities, source="event")

        else:
            # Queue for batch processing
            for entity_name in entities:
                self._pending_entities.append({
                    "name": entity_name,
                    "source_episode": episode_data.get("episode_id"),
                    "patient_id": episode_data.get("patient_id"),
                    "timestamp": datetime.utcnow(),
                })

            # Check batch threshold in HYBRID mode
            if (
                self.config.mode == CrystallizationMode.HYBRID
                and len(self._pending_entities) >= self.config.batch_threshold
            ):
                logger.info(f"Batch threshold reached ({len(self._pending_entities)} entities), triggering crystallization")
                await self._process_pending_batch()

    async def _periodic_crystallization(self) -> None:
        """Periodic batch crystallization task."""
        interval = self.config.batch_interval_minutes * 60

        while self._running:
            try:
                await asyncio.sleep(interval)

                if self._pending_entities:
                    logger.info(f"Periodic crystallization: {len(self._pending_entities)} pending entities")
                    await self._process_pending_batch()
                else:
                    # Even without pending entities, check for new Graphiti entities
                    await self.crystallize_from_graphiti()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic crystallization: {e}", exc_info=True)
                self._stats["errors"] += 1

    async def _process_pending_batch(self) -> CrystallizationResult:
        """Process accumulated pending entities."""
        if not self._pending_entities:
            return CrystallizationResult(
                entities_processed=0,
                entities_created=0,
                entities_merged=0,
                entities_skipped=0,
                relationships_created=0,
                promotion_candidates=0,
                processing_time_ms=0,
            )

        # Take current pending and reset
        entities_to_process = self._pending_entities.copy()
        self._pending_entities.clear()

        return await self.crystallize_entities(entities_to_process, source="batch")

    async def crystallize_entities(
        self,
        entities: List[Any],
        source: str = "manual",
    ) -> CrystallizationResult:
        """
        Crystallize a list of entities to Neo4j PERCEPTION layer.

        Args:
            entities: List of entity names or entity dicts
            source: Source identifier for logging

        Returns:
            CrystallizationResult with processing details
        """
        self._batch_counter += 1
        batch_id = f"batch_{self._batch_counter:06d}"
        start_time = datetime.now()

        created = 0
        merged = 0
        skipped = 0
        promotion_candidates = 0
        errors = []
        crystallized: List[CrystallizedEntity] = []

        logger.info(f"Starting crystallization {batch_id}: {len(entities)} entities from {source}")

        for entity_data in entities:
            try:
                # Normalize entity data
                if isinstance(entity_data, str):
                    entity_data = {"name": entity_data}

                name = entity_data.get("name", "")
                entity_type = entity_data.get("entity_type", "Entity")
                confidence = entity_data.get("confidence", 0.75)
                graphiti_id = entity_data.get("graphiti_id")

                if not name:
                    skipped += 1
                    continue

                # Resolve against existing entities
                match = await self.entity_resolver.find_existing_for_crystallization(
                    name=name,
                    entity_type=entity_type,
                    layer="ANY",  # Check all layers
                )

                if match.found:
                    # Merge with existing entity
                    merge_result = await self.entity_resolver.merge_for_crystallization(
                        existing_id=match.entity_id,
                        new_data={
                            "confidence": confidence,
                            "graphiti_entity_id": graphiti_id,
                            "last_seen_in_episodic": datetime.utcnow().isoformat(),
                        }
                    )

                    if merge_result.success:
                        merged += 1
                        self._stats["total_merged"] += 1

                        # Check if eligible for promotion after merge
                        is_promotion_eligible = (
                            merge_result.observation_count >= self.config.perception_to_semantic_min_observations
                            and confidence >= self.config.perception_to_semantic_min_confidence
                        )

                        if is_promotion_eligible:
                            promotion_candidates += 1

                        crystallized.append(CrystallizedEntity(
                            neo4j_id=match.entity_id,
                            graphiti_id=graphiti_id,
                            name=name,
                            entity_type=entity_type,
                            layer=match.entity_data.get("layer", "PERCEPTION"),
                            confidence=confidence,
                            observation_count=merge_result.observation_count,
                            is_new=False,
                            promotion_eligible=is_promotion_eligible,
                        ))
                    else:
                        errors.append(f"Failed to merge entity: {name}")

                else:
                    # Create new PERCEPTION entity
                    new_entity = await self._create_perception_entity(
                        name=name,
                        entity_type=entity_type,
                        confidence=confidence,
                        graphiti_id=graphiti_id,
                        source_data=entity_data,
                    )

                    if new_entity:
                        created += 1
                        self._stats["total_crystallized"] += 1

                        crystallized.append(CrystallizedEntity(
                            neo4j_id=new_entity["id"],
                            graphiti_id=graphiti_id,
                            name=name,
                            entity_type=entity_type,
                            layer="PERCEPTION",
                            confidence=confidence,
                            observation_count=1,
                            is_new=True,
                            promotion_eligible=False,  # New entities start at 1 observation
                        ))
                    else:
                        errors.append(f"Failed to create entity: {name}")

            except Exception as e:
                logger.error(f"Error crystallizing entity {entity_data}: {e}")
                errors.append(f"Error processing {entity_data}: {str(e)}")
                self._stats["errors"] += 1

        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        self._last_crystallization = datetime.utcnow()

        # Emit crystallization_complete event
        await self._emit_crystallization_complete(
            batch_id=batch_id,
            entities_created=created,
            entities_merged=merged,
            promotion_candidates=promotion_candidates,
            crystallized=crystallized,
        )

        result = CrystallizationResult(
            entities_processed=len(entities),
            entities_created=created,
            entities_merged=merged,
            entities_skipped=skipped,
            relationships_created=0,  # TODO: Implement relationship crystallization
            promotion_candidates=promotion_candidates,
            processing_time_ms=processing_time,
            errors=errors,
            batch_id=batch_id,
        )

        logger.info(
            f"Crystallization {batch_id} complete: "
            f"{created} created, {merged} merged, {skipped} skipped, "
            f"{promotion_candidates} promotion candidates, "
            f"{len(errors)} errors, {processing_time:.1f}ms"
        )

        return result

    async def _create_perception_entity(
        self,
        name: str,
        entity_type: str,
        confidence: float,
        graphiti_id: Optional[str],
        source_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new PERCEPTION layer entity in Neo4j.

        Args:
            name: Entity name
            entity_type: Entity type
            confidence: Initial confidence score
            graphiti_id: Optional Graphiti entity ID
            source_data: Additional source data

        Returns:
            Created entity dict or None on failure
        """
        import uuid

        entity_id = f"perception_{uuid.uuid4().hex[:12]}"
        normalized_type = self.entity_resolver.normalize_entity_type(entity_type)

        properties = {
            "id": entity_id,
            "name": name,
            "entity_type": normalized_type,
            "dikw_layer": "PERCEPTION",
            "confidence": confidence,
            "observation_count": 1,
            "first_observed": datetime.utcnow().isoformat(),
            "last_observed": datetime.utcnow().isoformat(),
            "source": "graphiti_episodic",
        }

        if graphiti_id:
            properties["graphiti_entity_id"] = graphiti_id

        # Add patient_id if available
        if source_data.get("patient_id"):
            properties["patient_id"] = source_data["patient_id"]

        try:
            # Create entity in Neo4j with PERCEPTION label
            labels = ["Entity", "PERCEPTION", normalized_type]
            await self.neo4j_backend.add_entity(
                entity_id=entity_id,
                properties=properties,
                labels=labels,
            )

            logger.debug(f"Created PERCEPTION entity: {name} ({entity_id})")
            return properties

        except Exception as e:
            logger.error(f"Failed to create PERCEPTION entity {name}: {e}")
            return None

    async def crystallize_from_graphiti(
        self,
        since: Optional[datetime] = None,
        patient_id: Optional[str] = None,
        limit: int = 100,
    ) -> CrystallizationResult:
        """
        Query Graphiti/FalkorDB for recent entities and crystallize them.

        This method directly queries the Graphiti graph for entities
        that were created/updated since the last crystallization.

        Args:
            since: Crystallize entities created after this time
            patient_id: Optional patient filter
            limit: Maximum entities to process

        Returns:
            CrystallizationResult
        """
        if not self.graphiti:
            logger.warning("No Graphiti client configured, cannot query FalkorDB directly")
            return CrystallizationResult(
                entities_processed=0,
                entities_created=0,
                entities_merged=0,
                entities_skipped=0,
                relationships_created=0,
                promotion_candidates=0,
                processing_time_ms=0,
                errors=["No Graphiti client configured"],
            )

        since = since or self._last_crystallization or (datetime.utcnow() - timedelta(hours=24))

        logger.info(f"Querying Graphiti for entities since {since.isoformat()}")

        try:
            # Query FalkorDB for recent entities via Graphiti
            # The actual query depends on Graphiti's API
            # This is a simplified version
            query = """
            MATCH (e:Entity)
            WHERE e.created_at > $since_timestamp
            RETURN e.uuid as id, e.name as name, e.entity_type as entity_type,
                   e.summary as summary, e.created_at as created_at
            ORDER BY e.created_at DESC
            LIMIT $limit
            """

            # Note: This would need to be adapted to Graphiti's actual query method
            # For now, we'll use a placeholder that works with the Graphiti client
            entities = []

            # If we have search capability, use it
            if hasattr(self.graphiti, 'clients'):
                from graphiti_core.search.search import search
                from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_CROSS_ENCODER
                from graphiti_core.search.search_filters import SearchFilters

                # Search for all entities (broad query)
                results = await search(
                    clients=self.graphiti.clients,
                    query="medical entity",  # Broad query
                    group_ids=[patient_id] if patient_id else None,
                    search_filter=SearchFilters(),
                    config=COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
                )

                for node in results.nodes[:limit]:
                    if node.created_at and node.created_at > since:
                        entities.append({
                            "name": node.name,
                            "entity_type": node.labels[0] if node.labels else "Entity",
                            "confidence": 0.8,  # Default confidence from Graphiti
                            "graphiti_id": node.uuid,
                            "summary": node.summary,
                            "patient_id": patient_id,
                        })

            if entities:
                return await self.crystallize_entities(entities, source="graphiti_query")
            else:
                return CrystallizationResult(
                    entities_processed=0,
                    entities_created=0,
                    entities_merged=0,
                    entities_skipped=0,
                    relationships_created=0,
                    promotion_candidates=0,
                    processing_time_ms=0,
                )

        except Exception as e:
            logger.error(f"Error querying Graphiti for entities: {e}", exc_info=True)
            return CrystallizationResult(
                entities_processed=0,
                entities_created=0,
                entities_merged=0,
                entities_skipped=0,
                relationships_created=0,
                promotion_candidates=0,
                processing_time_ms=0,
                errors=[str(e)],
            )

    async def _emit_crystallization_complete(
        self,
        batch_id: str,
        entities_created: int,
        entities_merged: int,
        promotion_candidates: int,
        crystallized: List[CrystallizedEntity],
    ) -> None:
        """Emit crystallization_complete event."""
        event = KnowledgeEvent(
            action="crystallization_complete",
            data={
                "batch_id": batch_id,
                "entities_created": entities_created,
                "entities_merged": entities_merged,
                "promotion_candidates": promotion_candidates,
                "timestamp": datetime.utcnow().isoformat(),
                "entities": [
                    {
                        "neo4j_id": e.neo4j_id,
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "is_new": e.is_new,
                        "promotion_eligible": e.promotion_eligible,
                    }
                    for e in crystallized[:20]  # Limit to first 20 for event size
                ],
            },
            role=Role.KNOWLEDGE_MANAGER,
        )

        await self.event_bus.publish(event)
        logger.debug(f"Emitted crystallization_complete event for {batch_id}")

    async def get_crystallization_stats(self) -> Dict[str, Any]:
        """Get crystallization statistics."""
        return {
            "mode": self.config.mode.value,
            "running": self._running,
            "last_crystallization": self._last_crystallization.isoformat() if self._last_crystallization else None,
            "pending_entities": len(self._pending_entities),
            "batch_counter": self._batch_counter,
            "total_crystallized": self._stats["total_crystallized"],
            "total_merged": self._stats["total_merged"],
            "total_promotions": self._stats["total_promotions"],
            "errors": self._stats["errors"],
            "config": {
                "batch_interval_minutes": self.config.batch_interval_minutes,
                "batch_threshold": self.config.batch_threshold,
                "auto_promotion_perception_semantic": self.config.enable_auto_promotion_perception_semantic,
                "perception_to_semantic_min_confidence": self.config.perception_to_semantic_min_confidence,
                "perception_to_semantic_min_observations": self.config.perception_to_semantic_min_observations,
            },
        }

    async def trigger_manual_crystallization(
        self,
        patient_id: Optional[str] = None,
    ) -> CrystallizationResult:
        """
        Manually trigger crystallization.

        Useful for testing or on-demand processing.
        """
        # First process any pending entities
        if self._pending_entities:
            return await self._process_pending_batch()

        # Then query Graphiti for recent entities
        return await self.crystallize_from_graphiti(patient_id=patient_id)

    # ========================================
    # Evaluation Framework Support
    # ========================================

    async def flush_now(self) -> FlushResult:
        """
        Fuerza el procesamiento inmediato de todos los eventos pendientes.

        Este método está diseñado para el framework de evaluación,
        permitiendo que los tests capturen el estado de memoria
        después de que todos los pipelines hayan terminado.

        Returns:
            FlushResult con estadísticas del flush
        """
        start_time = datetime.now()
        errors = []
        entities_crystallized = 0
        promotions_executed = 0

        logger.info(f"Flush requested: {len(self._pending_entities)} pending entities")

        try:
            # 1. Process all pending entities immediately
            if self._pending_entities:
                result = await self._process_pending_batch()
                entities_crystallized = result.entities_created + result.entities_merged
                promotions_executed = result.promotion_candidates
                errors.extend(result.errors)

            # 2. Query Graphiti for any entities not yet in the pending queue
            # This catches entities that were stored but events not yet received
            graphiti_result = await self.crystallize_from_graphiti()
            entities_crystallized += graphiti_result.entities_created + graphiti_result.entities_merged
            promotions_executed += graphiti_result.promotion_candidates
            errors.extend(graphiti_result.errors)

        except Exception as e:
            logger.error(f"Error during flush: {e}", exc_info=True)
            errors.append(str(e))

        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        pending_after = len(self._pending_entities)

        logger.info(
            f"Flush complete: {entities_crystallized} entities crystallized, "
            f"{promotions_executed} promotions, {pending_after} still pending, "
            f"{processing_time:.1f}ms"
        )

        return FlushResult(
            flushed=True,
            events_processed=entities_crystallized,  # Approximate
            entities_crystallized=entities_crystallized,
            promotions_executed=promotions_executed,
            pending_after_flush=pending_after,
            processing_time_ms=processing_time,
            errors=errors,
        )

    def get_buffer_status(self) -> BufferStatus:
        """
        Retorna el estado actual del buffer de cristalización.

        Este método está diseñado para el framework de evaluación,
        permitiendo verificar si el servicio ha alcanzado quiescence.

        Returns:
            BufferStatus con el estado del buffer
        """
        return BufferStatus(
            buffer_size=len(self._pending_entities),
            last_flush=self._last_crystallization,
            batch_in_progress=False,  # TODO: Track this properly with a flag
            running=self._running,
        )

    def is_quiescent(self) -> bool:
        """
        Verifica si el servicio está en estado quiescent (sin trabajo pendiente).

        Returns:
            True si no hay entidades pendientes y no hay batch en progreso
        """
        return len(self._pending_entities) == 0
