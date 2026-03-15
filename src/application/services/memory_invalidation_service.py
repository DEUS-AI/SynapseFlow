"""Memory Invalidation Service (SPEC-4).

Provides explicit and TTL-based invalidation of DIKW entities.
Entities are never deleted -- only marked as invalidated with an audit trail.

Invalidation sources:
1. Explicit API call (manual invalidation)
2. Temporal conflict resolution (SPEC-2, automatic)
3. TTL-based staleness sweep (periodic, PERCEPTION layer only)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from domain.kg_backends import KnowledgeGraphBackend

logger = logging.getLogger(__name__)


@dataclass
class InvalidationConfig:
    """Configuration for memory invalidation."""

    stale_threshold_days: int = 90
    stale_check_enabled: bool = True
    episodic_ttl_days: Optional[int] = None  # None = no auto-expiry for episodes


@dataclass
class InvalidationResult:
    """Result of an invalidation operation."""

    entities_invalidated: int
    entity_ids: List[str]
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MemoryInvalidationService:
    """Service for invalidating DIKW entities without deletion.

    Supports:
    - Explicit single-entity invalidation
    - Bulk invalidation by query filters
    - Periodic staleness sweep for PERCEPTION entities
    """

    def __init__(
        self,
        neo4j_backend: "KnowledgeGraphBackend",
        config: Optional[InvalidationConfig] = None,
    ):
        self.neo4j_backend = neo4j_backend
        self.config = config or InvalidationConfig()

        self._stats = {
            "total_invalidated": 0,
            "sweep_runs": 0,
            "last_sweep": None,
        }

    async def invalidate_entity(
        self,
        entity_id: str,
        reason: str = "manual",
    ) -> InvalidationResult:
        """Explicitly invalidate a single DIKW entity.

        Sets is_current=false, invalidated_at=now(), invalidation_reason=reason.
        Does NOT delete the entity.

        Args:
            entity_id: ID of the entity to invalidate.
            reason: Reason for invalidation (stored on the node).

        Returns:
            InvalidationResult with details.
        """
        query = """
        MATCH (n:Entity {id: $entity_id})
        WHERE n.is_current = true OR n.is_current IS NULL
        SET n.is_current = false,
            n.invalidated_at = datetime(),
            n.invalidation_reason = $reason,
            n.valid_until = COALESCE(n.valid_until, datetime())
        RETURN n.id as id
        """

        try:
            result = await self.neo4j_backend.query(
                query, {"entity_id": entity_id, "reason": reason}
            )

            rows = result.get("rows", []) if isinstance(result, dict) else []
            ids = [r.get("id") for r in rows if r.get("id")]

            if ids:
                self._stats["total_invalidated"] += len(ids)
                logger.info(f"Invalidated entity {entity_id}: reason={reason}")

            return InvalidationResult(
                entities_invalidated=len(ids),
                entity_ids=ids,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"Error invalidating entity {entity_id}: {e}")
            return InvalidationResult(
                entities_invalidated=0,
                entity_ids=[],
                reason=reason,
            )

    async def invalidate_by_query(
        self,
        patient_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_name: Optional[str] = None,
        reason: str = "bulk_invalidation",
    ) -> InvalidationResult:
        """Invalidate multiple entities matching filter criteria.

        Args:
            patient_id: Optional patient filter.
            entity_type: Optional entity type filter.
            entity_name: Optional entity name filter (case-insensitive).
            reason: Reason for invalidation.

        Returns:
            InvalidationResult with details.
        """
        conditions = ["(n.is_current = true OR n.is_current IS NULL)"]
        params: Dict[str, Any] = {"reason": reason}

        if patient_id:
            conditions.append("n.patient_id = $patient_id")
            params["patient_id"] = patient_id
        if entity_type:
            conditions.append("n.entity_type = $entity_type")
            params["entity_type"] = entity_type
        if entity_name:
            conditions.append("toLower(n.name) = $entity_name")
            params["entity_name"] = entity_name.lower()

        where_clause = " AND ".join(conditions)
        query = f"""
        MATCH (n:Entity)
        WHERE {where_clause}
        SET n.is_current = false,
            n.invalidated_at = datetime(),
            n.invalidation_reason = $reason,
            n.valid_until = COALESCE(n.valid_until, datetime())
        RETURN n.id as id
        """

        try:
            result = await self.neo4j_backend.query(query, params)

            rows = result.get("rows", []) if isinstance(result, dict) else []
            ids = [r.get("id") for r in rows if r.get("id")]

            if ids:
                self._stats["total_invalidated"] += len(ids)
                logger.info(
                    f"Bulk invalidated {len(ids)} entities: reason={reason}, "
                    f"patient_id={patient_id}, entity_type={entity_type}"
                )

            return InvalidationResult(
                entities_invalidated=len(ids),
                entity_ids=ids,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"Error in bulk invalidation: {e}")
            return InvalidationResult(
                entities_invalidated=0,
                entity_ids=[],
                reason=reason,
            )

    async def sweep_stale_entities(self) -> InvalidationResult:
        """Find and invalidate PERCEPTION entities not observed recently.

        Only targets PERCEPTION layer -- higher layers (SEMANTIC, REASONING,
        APPLICATION) are considered validated and never auto-invalidated.

        Uses config.stale_threshold_days to determine staleness.

        Returns:
            InvalidationResult with details of invalidated entities.
        """
        if not self.config.stale_check_enabled:
            return InvalidationResult(
                entities_invalidated=0,
                entity_ids=[],
                reason="stale_sweep_disabled",
            )

        cutoff = datetime.utcnow() - timedelta(days=self.config.stale_threshold_days)
        cutoff_str = cutoff.isoformat()

        query = """
        MATCH (n:Entity)
        WHERE n.dikw_layer = 'PERCEPTION'
          AND (n.is_current = true OR n.is_current IS NULL)
          AND n.last_observed IS NOT NULL
          AND n.last_observed < $cutoff_date
        SET n.is_current = false,
            n.invalidated_at = datetime(),
            n.invalidation_reason = 'stale_ttl'
        RETURN n.id as id, n.name as name
        """

        try:
            result = await self.neo4j_backend.query(
                query, {"cutoff_date": cutoff_str}
            )

            rows = result.get("rows", []) if isinstance(result, dict) else []
            ids = [r.get("id") for r in rows if r.get("id")]

            self._stats["sweep_runs"] += 1
            self._stats["last_sweep"] = datetime.utcnow().isoformat()

            if ids:
                self._stats["total_invalidated"] += len(ids)
                logger.info(
                    f"Stale sweep: invalidated {len(ids)} PERCEPTION entities "
                    f"(threshold: {self.config.stale_threshold_days} days)"
                )

            return InvalidationResult(
                entities_invalidated=len(ids),
                entity_ids=ids,
                reason="stale_ttl",
            )

        except Exception as e:
            logger.error(f"Error in stale entity sweep: {e}")
            return InvalidationResult(
                entities_invalidated=0,
                entity_ids=[],
                reason="stale_ttl",
            )

    def get_invalidation_stats(self) -> Dict[str, Any]:
        """Return invalidation service statistics."""
        return {
            "total_invalidated": self._stats["total_invalidated"],
            "sweep_runs": self._stats["sweep_runs"],
            "last_sweep": self._stats["last_sweep"],
            "stale_threshold_days": self.config.stale_threshold_days,
            "stale_check_enabled": self.config.stale_check_enabled,
        }
