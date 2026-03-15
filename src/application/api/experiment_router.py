"""Experiment API Router.

REST endpoints for the autonomous agent experiment system.
Gated behind ENABLE_AGENT_EXPERIMENTS=true environment variable.

Follows the same patterns as evaluation_router.py.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from .experiment_models import (
    AgentDirectiveRequest,
    AgentDirectiveResponse,
    CycleResponse,
    DriftResponse,
    ExperimentHealthResponse,
    ExperimentHistoryResponse,
    ExperimentStatsResponse,
    MetricsResponse,
    RunExperimentRequest,
)
from domain.experiment import AgentDirective

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

# These will be injected at startup by composition_root
_experiment_loop = None
_experiment_runner = None
_agent_tuner = None
_metrics_collector = None
_experiment_store = None


def configure_experiment_router(
    experiment_loop: Any,
    experiment_runner: Any,
    agent_tuner: Any,
    metrics_collector: Any,
    experiment_store: Any = None,
) -> None:
    """Inject service dependencies into the router.

    Called during app startup from composition_root.
    """
    global _experiment_loop, _experiment_runner, _agent_tuner
    global _metrics_collector, _experiment_store
    _experiment_loop = experiment_loop
    _experiment_runner = experiment_runner
    _agent_tuner = agent_tuner
    _metrics_collector = metrics_collector
    _experiment_store = experiment_store


def _require_loop():
    if _experiment_loop is None:
        raise HTTPException(status_code=503, detail="Experiment system not initialized")
    return _experiment_loop


# ========================================
# Health & Stats
# ========================================

@router.get("/health", response_model=ExperimentHealthResponse)
async def experiment_health():
    """Get health status of the experiment system."""
    loop = _require_loop()
    stats = loop.get_statistics()
    return ExperimentHealthResponse(
        enabled=True,
        loop_running=stats.get("running", False),
        total_cycles=stats.get("total_cycles", 0),
        active_directives=len(stats.get("active_directives", [])),
        registered_agents=stats.get("active_directives", []),
    )


@router.get("/stats", response_model=ExperimentStatsResponse)
async def experiment_stats():
    """Get cumulative experiment statistics."""
    loop = _require_loop()
    stats = loop.get_statistics()
    return ExperimentStatsResponse(**{
        k: v for k, v in stats.items()
        if k in ExperimentStatsResponse.model_fields
    })


# ========================================
# Directives
# ========================================

@router.get("/directives", response_model=List[AgentDirectiveResponse])
async def list_directives():
    """List all registered directives."""
    loop = _require_loop()
    results = []
    for agent_id, d in loop.directives.items():
        data = d.to_dict()
        data["parameter_bounds"] = {
            k: list(v) for k, v in d.parameter_bounds.items()
        }
        results.append(AgentDirectiveResponse(**data))
    return results


@router.get("/directives/{agent_id}", response_model=AgentDirectiveResponse)
async def get_directive(agent_id: str):
    """Get directive for a specific agent."""
    loop = _require_loop()
    d = loop.directives.get(agent_id)
    if d is None:
        raise HTTPException(status_code=404, detail=f"No directive for agent {agent_id}")
    data = d.to_dict()
    data["parameter_bounds"] = {k: list(v) for k, v in d.parameter_bounds.items()}
    return AgentDirectiveResponse(**data)


@router.put("/directives/{agent_id}", response_model=AgentDirectiveResponse)
async def update_directive(agent_id: str, request: AgentDirectiveRequest):
    """Create or update a directive for an agent."""
    loop = _require_loop()
    bounds = {
        k: (v[0], v[1]) for k, v in request.parameter_bounds.items()
        if len(v) == 2
    }
    directive = AgentDirective(
        agent_id=agent_id,
        primary_metric=request.primary_metric,
        secondary_metrics=request.secondary_metrics,
        parameter_bounds=bounds,
        constraints=request.constraints,
        experiment_budget_seconds=request.experiment_budget_seconds,
        max_experiments_per_cycle=request.max_experiments_per_cycle,
        exploration_strategy=request.exploration_strategy,
        enabled=request.enabled,
    )
    loop.set_directive(agent_id, directive)

    if _experiment_store:
        await _experiment_store.save_directive(directive)

    data = directive.to_dict()
    data["parameter_bounds"] = {k: list(v) for k, v in directive.parameter_bounds.items()}
    return AgentDirectiveResponse(**data)


# ========================================
# Per-agent endpoints
# ========================================

@router.get("/{agent_id}/history", response_model=ExperimentHistoryResponse)
async def get_history(agent_id: str, limit: int = 20):
    """Get experiment history for an agent."""
    if _experiment_store:
        experiments = await _experiment_store.get_experiment_history(agent_id, limit)
    else:
        experiments = []
    return ExperimentHistoryResponse(
        agent_id=agent_id,
        experiments=experiments,
        total=len(experiments),
    )


@router.get("/{agent_id}/metrics", response_model=MetricsResponse)
async def get_metrics(agent_id: str):
    """Get current metrics for an agent."""
    if _metrics_collector is None:
        raise HTTPException(status_code=503, detail="Metrics collector not available")
    profile = _metrics_collector.collect_agent_metrics(agent_id)
    return MetricsResponse(
        agent_id=profile.agent_id,
        metrics=profile.metrics,
        baselines=profile.baselines,
        drift_scores=profile.drift_scores,
        collected_at=profile.collected_at.isoformat(),
    )


@router.get("/{agent_id}/drift", response_model=DriftResponse)
async def get_drift(agent_id: str):
    """Get drift detection for an agent."""
    if _metrics_collector is None:
        raise HTTPException(status_code=503, detail="Metrics collector not available")
    profile = _metrics_collector.collect_agent_metrics(agent_id)
    return DriftResponse(
        agent_id=agent_id,
        has_significant_drift=profile.has_significant_drift(),
        drift_scores=profile.drift_scores,
        metrics=profile.metrics,
    )


@router.post("/{agent_id}/run", response_model=CycleResponse)
async def run_experiments(agent_id: str, request: RunExperimentRequest = RunExperimentRequest()):
    """Manually trigger experiments for an agent."""
    loop = _require_loop()
    directive = loop.directives.get(agent_id)
    if directive is None:
        raise HTTPException(status_code=404, detail=f"No directive for agent {agent_id}")

    if _agent_tuner is None:
        raise HTTPException(status_code=503, detail="Agent tuner not available")

    proposals = _agent_tuner.propose_experiments(
        agent_id, directive, max_proposals=request.max_experiments
    )

    improvements = 0
    reverts = 0
    failures = 0

    for proposal in proposals:
        try:
            result = await _experiment_runner.run_experiment(proposal)
            if result.kept:
                improvements += 1
            elif result.status.value == "reverted":
                reverts += 1
            elif result.status.value == "failed":
                failures += 1
        except Exception as e:
            failures += 1
            logger.error(f"Experiment failed: {e}")

    return CycleResponse(
        cycle_id=f"manual_{agent_id}",
        total_experiments=len(proposals),
        improvements=improvements,
        reverts=reverts,
        failures=failures,
        agents_tuned=[agent_id],
    )


@router.post("/cycle", response_model=CycleResponse)
async def run_cycle():
    """Manually trigger a full experiment cycle across all agents."""
    loop = _require_loop()
    stats = await loop.run_once()
    return CycleResponse(
        cycle_id=stats.cycle_id,
        total_experiments=stats.total_experiments,
        improvements=stats.improvements,
        reverts=stats.reverts,
        failures=stats.failures,
        agents_tuned=stats.agents_tuned,
    )
