"""Ontology Remediation API Router.

REST API endpoints for ontology batch remediation operations:
- Dry-run preview of what would change
- Execute remediation batch
- Rollback a specific batch
- List orphan entities
- Deduplication dry-run and execute

Prefix: /api/ontology/remediation
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology", tags=["ontology-remediation"])

# Lazy singletons — set by dependency injection at startup
_remediation_service = None
_deduplication_service = None


def set_remediation_service(service):
    """Set the remediation service instance (called from lifespan)."""
    global _remediation_service
    _remediation_service = service


def set_deduplication_service(service):
    """Set the deduplication service instance (called from lifespan)."""
    global _deduplication_service
    _deduplication_service = service


def get_remediation():
    """Dependency that provides the remediation service or raises 503."""
    if _remediation_service is None:
        raise HTTPException(
            status_code=503, detail="Remediation service not available (Neo4j not connected)"
        )
    return _remediation_service


def get_deduplication():
    """Dependency that provides the deduplication service or raises 503."""
    if _deduplication_service is None:
        raise HTTPException(
            status_code=503, detail="Deduplication service not available (Neo4j not connected)"
        )
    return _deduplication_service


class ExecuteRequest(BaseModel):
    mark_structural: bool = True
    mark_noise: bool = True


class DismissRequest(BaseModel):
    entity_ids: List[str]
    undo: bool = False


@router.post("/remediation/dry-run")
async def dry_run(service=Depends(get_remediation)):
    """Preview what remediation would change without modifying data."""
    try:
        results = await service.dry_run()
        return results
    except Exception as e:
        logger.error(f"Dry-run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remediation/execute")
async def execute(
    request: ExecuteRequest = ExecuteRequest(),
    service=Depends(get_remediation),
):
    """Execute the full batch remediation pipeline."""
    try:
        results = await service.execute(
            mark_structural=request.mark_structural,
            mark_noise=request.mark_noise,
        )
        return results
    except Exception as e:
        logger.error(f"Remediation execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remediation/rollback/{batch_id}")
async def rollback(batch_id: str, service=Depends(get_remediation)):
    """Rollback a specific remediation batch by its ID."""
    try:
        results = await service.rollback(batch_id)
        return results
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orphans")
async def list_orphans(
    limit: int = Query(100, ge=1, le=1000),
    service=Depends(get_remediation),
):
    """List entities flagged as orphans (zero relationships)."""
    try:
        orphans = await service.get_orphans(limit=limit)
        return {"orphans": orphans, "count": len(orphans), "limit": limit}
    except Exception as e:
        logger.error(f"Failed to list orphans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deduplication/dry-run")
async def deduplication_dry_run(service=Depends(get_deduplication)):
    """Preview categorized merge plan for duplicate entities without modifying data."""
    try:
        # Same-type detection (Neo4j fast path)
        pairs = await service.detect_duplicates()
        plan = service.create_merge_plan(pairs)

        # Cross-type detection (Python normalizer)
        cross_type_groups = await service.detect_cross_type_duplicates()

        return {
            "total_same_type": len(plan),
            "same_type_plan": [
                {
                    "winner_id": m.winner_id,
                    "winner_name": m.winner_name,
                    "loser_id": m.loser_id,
                    "loser_name": m.loser_name,
                    "type": m.entity_type,
                    "rationale": m.rationale,
                }
                for m in plan
            ],
            "total_cross_type": len(cross_type_groups),
            "cross_type_groups": [
                {
                    "canonical_form": g.canonical_form,
                    "entities": g.entities,
                    "entity_count": g.entity_count,
                }
                for g in cross_type_groups
            ],
        }
    except Exception as e:
        logger.error(f"Deduplication dry-run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deduplication/execute")
async def deduplication_execute(service=Depends(get_deduplication)):
    """Execute deduplication — merge same-type duplicate pairs only."""
    try:
        # Only merge same-type pairs
        pairs = await service.detect_duplicates()
        plan = service.create_merge_plan(pairs)
        summary = await service.execute_merge(plan)

        # Count cross-type groups (not merged, just reported)
        cross_type_groups = await service.detect_cross_type_duplicates()

        return {
            "total_merged": summary.total_merged,
            "total_relationships_transferred": summary.total_relationships_transferred,
            "batch_id": summary.batch_id,
            "details": summary.details,
            "skipped_cross_type": len(cross_type_groups),
        }
    except Exception as e:
        logger.error(f"Deduplication execute failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deduplication/dismiss")
async def deduplication_dismiss(
    request: DismissRequest, service=Depends(get_deduplication)
):
    """Dismiss or undismiss entities as false-positive duplicates."""
    try:
        count = await service.dismiss_entities(
            entity_ids=request.entity_ids, undo=request.undo
        )
        action = "undismissed" if request.undo else "dismissed"
        return {"action": action, "count": count, "entity_ids": request.entity_ids}
    except Exception as e:
        logger.error(f"Deduplication dismiss failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
