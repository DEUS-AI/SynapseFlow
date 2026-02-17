"""Ontology Remediation API Router.

REST API endpoints for ontology batch remediation operations:
- Dry-run preview of what would change
- Execute remediation batch
- Rollback a specific batch
- List orphan entities

Prefix: /api/ontology/remediation
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology", tags=["ontology-remediation"])

# Lazy singleton — set by dependency injection at startup
_remediation_service = None


def set_remediation_service(service):
    """Set the remediation service instance (called from lifespan)."""
    global _remediation_service
    _remediation_service = service


def get_remediation():
    """Dependency that provides the remediation service or raises 503."""
    if _remediation_service is None:
        raise HTTPException(
            status_code=503, detail="Remediation service not available (Neo4j not connected)"
        )
    return _remediation_service


class ExecuteRequest(BaseModel):
    mark_structural: bool = True
    mark_noise: bool = True


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
