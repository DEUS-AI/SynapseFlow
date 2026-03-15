"""Pydantic models for Experiment API request/response payloads."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class ExperimentResultResponse(BaseModel):
    """Response model for a single experiment result."""
    experiment_id: str
    agent_id: str
    parameter_path: str
    original_value: Any
    proposed_value: Any
    status: str
    baseline_metric_value: float
    experiment_metric_value: float
    primary_metric: str
    improvement_pct: float
    kept: bool
    rejection_reason: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0


class ExperimentHistoryResponse(BaseModel):
    """Response model for experiment history list."""
    agent_id: str
    experiments: List[Dict[str, Any]]
    total: int


class AgentDirectiveRequest(BaseModel):
    """Request model for creating/updating an agent directive."""
    agent_id: str
    primary_metric: str
    secondary_metrics: List[str] = Field(default_factory=list)
    parameter_bounds: Dict[str, List[float]] = Field(default_factory=dict)
    constraints: Dict[str, float] = Field(default_factory=dict)
    experiment_budget_seconds: int = 300
    max_experiments_per_cycle: int = 10
    exploration_strategy: str = "random"
    enabled: bool = True


class AgentDirectiveResponse(BaseModel):
    """Response model for an agent directive."""
    agent_id: str
    primary_metric: str
    secondary_metrics: List[str] = Field(default_factory=list)
    parameter_bounds: Dict[str, List[float]] = Field(default_factory=dict)
    constraints: Dict[str, float] = Field(default_factory=dict)
    experiment_budget_seconds: int = 300
    max_experiments_per_cycle: int = 10
    exploration_strategy: str = "random"
    enabled: bool = True


class MetricsResponse(BaseModel):
    """Response model for agent metrics."""
    agent_id: str
    metrics: Dict[str, float]
    baselines: Dict[str, float]
    drift_scores: Dict[str, float]
    collected_at: str


class DriftResponse(BaseModel):
    """Response model for drift detection."""
    agent_id: str
    has_significant_drift: bool
    drift_scores: Dict[str, float]
    metrics: Dict[str, float]


class ExperimentStatsResponse(BaseModel):
    """Response model for experiment loop statistics."""
    total_cycles: int = 0
    total_experiments: int = 0
    total_improvements: int = 0
    total_reverts: int = 0
    total_failures: int = 0
    last_cycle_at: Optional[str] = None
    running: bool = False
    active_directives: List[str] = Field(default_factory=list)


class ExperimentHealthResponse(BaseModel):
    """Response model for experiment system health."""
    enabled: bool
    loop_running: bool
    total_cycles: int
    active_directives: int
    registered_agents: List[str]


class RunExperimentRequest(BaseModel):
    """Request model for manually triggering experiments on an agent."""
    max_experiments: int = Field(default=5, ge=1, le=50)


class CycleResponse(BaseModel):
    """Response model for a triggered experiment cycle."""
    cycle_id: str
    total_experiments: int
    improvements: int
    reverts: int
    failures: int
    agents_tuned: List[str]
