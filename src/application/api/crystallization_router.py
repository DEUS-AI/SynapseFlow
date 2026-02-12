"""Crystallization Pipeline API Endpoints.

Provides REST API endpoints for:
- Triggering manual crystallization
- Viewing crystallization statistics
- Managing promotion reviews
- Monitoring pipeline health
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from .dependencies import (
    get_kg_backend,
    get_event_bus,
    get_crystallization_service,
    get_promotion_gate,
    get_entity_resolver,
    get_temporal_scoring_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crystallization", tags=["crystallization"])


# ========================================
# Pydantic Models
# ========================================

class CrystallizationStatsResponse(BaseModel):
    """Response model for crystallization statistics."""
    mode: str
    running: bool
    last_crystallization: Optional[str]
    pending_entities: int
    batch_counter: int
    total_crystallized: int
    total_merged: int
    total_promotions: int
    errors: int
    config: dict


class CrystallizationResultResponse(BaseModel):
    """Response model for crystallization result."""
    entities_processed: int
    entities_created: int
    entities_merged: int
    entities_skipped: int
    relationships_created: int
    promotion_candidates: int
    processing_time_ms: float
    errors: List[str]
    batch_id: str
    timestamp: str


class TriggerCrystallizationRequest(BaseModel):
    """Request model for triggering crystallization."""
    patient_id: Optional[str] = None


class PendingReviewResponse(BaseModel):
    """Response model for pending review."""
    entity_id: str
    entity_name: str
    entity_type: str
    from_layer: str
    to_layer: str
    risk_level: str
    submitted_at: str
    priority: int
    patient_id: Optional[str]
    notes: str


class ReviewActionRequest(BaseModel):
    """Request model for review action."""
    reviewer: str
    action: str = Field(..., pattern="^(approve|reject)$")
    reason: str = ""


class ReviewActionResponse(BaseModel):
    """Response model for review action result."""
    success: bool
    entity_id: str
    action: str
    status: str
    message: str


class PromotionStatsResponse(BaseModel):
    """Response model for promotion statistics."""
    total_evaluated: int
    total_approved: int
    total_pending_review: int
    total_rejected: int
    by_risk_level: dict
    by_entity_type: dict


class EntityResolutionStatsResponse(BaseModel):
    """Response model for entity resolution statistics."""
    embedding_cache_size: int
    fuzzy_threshold: float
    semantic_threshold: float
    type_mappings_count: int


# ========================================
# Crystallization Endpoints
# ========================================

@router.get("/stats", response_model=CrystallizationStatsResponse)
async def get_crystallization_stats(
    crystallization_service=Depends(get_crystallization_service),
):
    """Get crystallization pipeline statistics."""
    if not crystallization_service:
        raise HTTPException(
            status_code=503,
            detail="Crystallization service not initialized. Set ENABLE_CRYSTALLIZATION=true"
        )

    stats = await crystallization_service.get_crystallization_stats()
    return CrystallizationStatsResponse(**stats)


@router.post("/trigger", response_model=CrystallizationResultResponse)
async def trigger_crystallization(
    request: TriggerCrystallizationRequest,
    crystallization_service=Depends(get_crystallization_service),
):
    """Manually trigger crystallization."""
    if not crystallization_service:
        raise HTTPException(
            status_code=503,
            detail="Crystallization service not initialized"
        )

    try:
        result = await crystallization_service.trigger_manual_crystallization(
            patient_id=request.patient_id
        )

        return CrystallizationResultResponse(
            entities_processed=result.entities_processed,
            entities_created=result.entities_created,
            entities_merged=result.entities_merged,
            entities_skipped=result.entities_skipped,
            relationships_created=result.relationships_created,
            promotion_candidates=result.promotion_candidates,
            processing_time_ms=result.processing_time_ms,
            errors=result.errors,
            batch_id=result.batch_id,
            timestamp=result.timestamp.isoformat(),
        )

    except Exception as e:
        logger.error(f"Error triggering crystallization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def crystallization_health(
    crystallization_service=Depends(get_crystallization_service),
    promotion_gate=Depends(get_promotion_gate),
    entity_resolver=Depends(get_entity_resolver),
):
    """Check crystallization pipeline health."""
    status = {
        "crystallization_service": crystallization_service is not None,
        "promotion_gate": promotion_gate is not None,
        "entity_resolver": entity_resolver is not None,
        "healthy": all([
            crystallization_service is not None,
            promotion_gate is not None,
            entity_resolver is not None,
        ]),
    }

    if crystallization_service:
        stats = await crystallization_service.get_crystallization_stats()
        status["crystallization_running"] = stats.get("running", False)
        status["crystallization_mode"] = stats.get("mode", "unknown")

    return status


# ========================================
# Promotion Review Endpoints
# ========================================

@router.get("/reviews/pending", response_model=List[PendingReviewResponse])
async def get_pending_reviews(
    risk_level: Optional[str] = Query(None, description="Filter by risk level (LOW, MEDIUM, HIGH)"),
    limit: int = Query(50, ge=1, le=200),
    promotion_gate=Depends(get_promotion_gate),
):
    """Get pending promotion reviews."""
    if not promotion_gate:
        raise HTTPException(
            status_code=503,
            detail="Promotion gate not initialized"
        )

    try:
        from domain.promotion_models import RiskLevel

        risk_filter = None
        if risk_level:
            try:
                risk_filter = RiskLevel(risk_level.upper())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid risk level: {risk_level}. Must be LOW, MEDIUM, or HIGH"
                )

        reviews = await promotion_gate.get_pending_reviews(
            risk_level=risk_filter,
            limit=limit,
        )

        return [
            PendingReviewResponse(
                entity_id=r.entity_id,
                entity_name=r.entity_name,
                entity_type=r.entity_type,
                from_layer=r.from_layer,
                to_layer=r.to_layer,
                risk_level=r.risk_level.value,
                submitted_at=r.submitted_at.isoformat(),
                priority=r.priority,
                patient_id=r.patient_id,
                notes=r.notes,
            )
            for r in reviews
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending reviews: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reviews/{entity_id}/action", response_model=ReviewActionResponse)
async def perform_review_action(
    entity_id: str,
    request: ReviewActionRequest,
    promotion_gate=Depends(get_promotion_gate),
):
    """Approve or reject a pending review."""
    if not promotion_gate:
        raise HTTPException(
            status_code=503,
            detail="Promotion gate not initialized"
        )

    try:
        if request.action == "approve":
            decision = await promotion_gate.approve_review(
                entity_id=entity_id,
                reviewer=request.reviewer,
                notes=request.reason,
            )
        else:
            decision = await promotion_gate.reject_review(
                entity_id=entity_id,
                reviewer=request.reviewer,
                reason=request.reason,
            )

        if not decision:
            raise HTTPException(
                status_code=404,
                detail=f"Review not found for entity: {entity_id}"
            )

        return ReviewActionResponse(
            success=True,
            entity_id=entity_id,
            action=request.action,
            status=decision.status.value,
            message=decision.reason,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing review action: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/promotion/stats", response_model=PromotionStatsResponse)
async def get_promotion_stats(
    promotion_gate=Depends(get_promotion_gate),
):
    """Get promotion statistics."""
    if not promotion_gate:
        raise HTTPException(
            status_code=503,
            detail="Promotion gate not initialized"
        )

    stats = await promotion_gate.get_stats()
    return PromotionStatsResponse(
        total_evaluated=stats.total_evaluated,
        total_approved=stats.total_approved,
        total_pending_review=stats.total_pending_review,
        total_rejected=stats.total_rejected,
        by_risk_level=stats.by_risk_level,
        by_entity_type=stats.by_entity_type,
    )


@router.post("/promotion/evaluate/{entity_id}")
async def evaluate_entity_promotion(
    entity_id: str,
    target_layer: str = Query(..., description="Target layer (SEMANTIC, REASONING, APPLICATION)"),
    promotion_gate=Depends(get_promotion_gate),
):
    """Evaluate if an entity is eligible for promotion."""
    if not promotion_gate:
        raise HTTPException(
            status_code=503,
            detail="Promotion gate not initialized"
        )

    valid_layers = ["SEMANTIC", "REASONING", "APPLICATION"]
    if target_layer.upper() not in valid_layers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target layer: {target_layer}. Must be one of {valid_layers}"
        )

    try:
        decision = await promotion_gate.evaluate_promotion(
            entity_id=entity_id,
            target_layer=target_layer.upper(),
        )

        return decision.to_dict()

    except Exception as e:
        logger.error(f"Error evaluating promotion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Entity Resolution Endpoints
# ========================================

@router.get("/resolution/stats", response_model=EntityResolutionStatsResponse)
async def get_resolution_stats(
    entity_resolver=Depends(get_entity_resolver),
):
    """Get entity resolution statistics."""
    if not entity_resolver:
        raise HTTPException(
            status_code=503,
            detail="Entity resolver not initialized"
        )

    stats = await entity_resolver.get_crystallization_stats()
    return EntityResolutionStatsResponse(**stats)


@router.post("/resolution/find")
async def find_existing_entity(
    name: str = Query(..., description="Entity name to search for"),
    entity_type: str = Query("Entity", description="Entity type"),
    layer: str = Query("ANY", description="DIKW layer to search (or ANY)"),
    entity_resolver=Depends(get_entity_resolver),
):
    """Find if an entity already exists in the knowledge graph."""
    if not entity_resolver:
        raise HTTPException(
            status_code=503,
            detail="Entity resolver not initialized"
        )

    try:
        match = await entity_resolver.find_existing_for_crystallization(
            name=name,
            entity_type=entity_type,
            layer=layer,
        )

        return {
            "found": match.found,
            "entity_id": match.entity_id,
            "match_type": match.match_type,
            "similarity_score": match.similarity_score,
            "match_details": match.match_details,
            "entity_data": match.entity_data if match.found else None,
        }

    except Exception as e:
        logger.error(f"Error finding entity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Temporal Scoring Endpoints
# ========================================

class TemporalScoringStatsResponse(BaseModel):
    """Response model for temporal scoring statistics."""
    config: dict
    decay_configs: dict


class TemporalScoreRequest(BaseModel):
    """Request model for temporal scoring."""
    entity_id: str
    entity_type: str
    last_observed: str = Field(description="ISO 8601 timestamp")
    observation_count: int = 1


class TemporalScoreResponse(BaseModel):
    """Response model for temporal score."""
    entity_id: str
    base_score: float
    frequency_boost: float
    final_score: float
    hours_since_observation: float
    relevance_category: str
    is_stale: bool


class TemporalQueryParseResponse(BaseModel):
    """Response model for parsed temporal query."""
    window: str
    start_time: str
    end_time: str
    duration_hours: float
    confidence: float
    original_text: str


@router.get("/temporal/stats", response_model=TemporalScoringStatsResponse)
async def get_temporal_scoring_stats(
    temporal_service=Depends(get_temporal_scoring_service),
):
    """Get temporal scoring configuration and decay rates."""
    if not temporal_service:
        raise HTTPException(
            status_code=503,
            detail="Temporal scoring service not initialized"
        )

    stats = temporal_service.get_stats()
    return TemporalScoringStatsResponse(**stats)


@router.post("/temporal/score", response_model=TemporalScoreResponse)
async def compute_temporal_score(
    request: TemporalScoreRequest,
    temporal_service=Depends(get_temporal_scoring_service),
):
    """Compute temporal relevance score for an entity."""
    if not temporal_service:
        raise HTTPException(
            status_code=503,
            detail="Temporal scoring service not initialized"
        )

    try:
        # Parse the timestamp
        last_observed = datetime.fromisoformat(request.last_observed.replace("Z", "+00:00"))

        score = temporal_service.compute_temporal_score(
            entity_id=request.entity_id,
            entity_type=request.entity_type,
            last_observed=last_observed,
            observation_count=request.observation_count,
        )

        return TemporalScoreResponse(
            entity_id=score.entity_id,
            base_score=round(score.base_score, 4),
            frequency_boost=round(score.frequency_boost, 4),
            final_score=round(score.final_score, 4),
            hours_since_observation=round(score.hours_since_observation, 2),
            relevance_category=score.relevance_category,
            is_stale=score.is_stale,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp: {e}")
    except Exception as e:
        logger.error(f"Error computing temporal score: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/temporal/parse", response_model=TemporalQueryParseResponse)
async def parse_temporal_query(
    query: str = Query(..., description="Natural language query to parse"),
    temporal_service=Depends(get_temporal_scoring_service),
):
    """Parse temporal context from a natural language query."""
    if not temporal_service:
        raise HTTPException(
            status_code=503,
            detail="Temporal scoring service not initialized"
        )

    try:
        ctx = temporal_service.parse_temporal_query(query)

        return TemporalQueryParseResponse(
            window=ctx.window.value,
            start_time=ctx.start_time.isoformat(),
            end_time=ctx.end_time.isoformat(),
            duration_hours=round(ctx.duration_hours, 2),
            confidence=round(ctx.confidence, 2),
            original_text=ctx.original_text,
        )

    except Exception as e:
        logger.error(f"Error parsing temporal query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal/refresh-recommendation/{entity_type}")
async def get_refresh_recommendation(
    entity_type: str,
    target_relevance: float = Query(0.5, ge=0.0, le=1.0, description="Target relevance threshold"),
    temporal_service=Depends(get_temporal_scoring_service),
):
    """Get recommended hours until an entity type should be refreshed."""
    if not temporal_service:
        raise HTTPException(
            status_code=503,
            detail="Temporal scoring service not initialized"
        )

    try:
        hours = temporal_service.get_refresh_recommendation(
            entity_type=entity_type,
            target_relevance=target_relevance,
        )

        decay_config = temporal_service.get_decay_config(entity_type)

        return {
            "entity_type": entity_type,
            "target_relevance": target_relevance,
            "hours_until_refresh": round(hours, 2) if hours != float("inf") else None,
            "half_life_hours": decay_config.half_life_hours,
            "min_score": decay_config.min_score,
            "description": decay_config.description,
        }

    except Exception as e:
        logger.error(f"Error getting refresh recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
