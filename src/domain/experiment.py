"""Experiment Models for AutoResearch Agent Monitoring.

Defines domain models for the autonomous experimentation loop that monitors
and tunes agent parameters. Inspired by karpathy/autoresearch pattern of
iterative modification → evaluation → decision cycles.

Used by:
- ExperimentRunner: Executes time-boxed experiments
- AgentTuner: Applies parameter changes to agents
- ExperimentLoopJob: Background job orchestrating experiment cycles
- ExperimentStore: Persists experiment results to Neo4j
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ExperimentStatus(str, Enum):
    """Status of an experiment."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"


class MetricDirection(str, Enum):
    """Whether a metric improves by going up or down."""
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


@dataclass
class MetricDefinition:
    """Definition of a trackable metric."""
    name: str
    direction: MetricDirection
    unit: str = ""
    baseline_value: float = 0.0

    def is_improvement(self, new_value: float, old_value: float) -> bool:
        """Check if new_value is an improvement over old_value."""
        if self.direction == MetricDirection.HIGHER_IS_BETTER:
            return new_value > old_value
        return new_value < old_value

    def improvement_pct(self, new_value: float, old_value: float) -> float:
        """Calculate improvement percentage (positive = better)."""
        if old_value == 0:
            return 0.0
        if self.direction == MetricDirection.HIGHER_IS_BETTER:
            return (new_value - old_value) / abs(old_value)
        return (old_value - new_value) / abs(old_value)


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment run.

    Each experiment modifies one parameter and measures one primary metric.
    This mirrors autoresearch's single-modification-per-iteration approach.
    """
    agent_id: str
    parameter_path: str  # dot-path like "confidence.medical_high_threshold"
    original_value: Any
    proposed_value: Any
    duration_seconds: int  # time budget for the experiment
    primary_metric: str  # name of the metric to optimize
    experiment_id: str = ""
    batch_id: str = ""

    def __post_init__(self):
        if not self.experiment_id:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self.experiment_id = f"exp_{self.agent_id}_{ts}"


@dataclass
class ExperimentResult:
    """Result of a completed experiment."""
    experiment_id: str
    agent_id: str
    parameter_path: str
    original_value: Any
    proposed_value: Any
    status: ExperimentStatus

    # Metric measurements
    baseline_metric_value: float
    experiment_metric_value: float
    primary_metric: str
    improvement_pct: float

    # Decision
    kept: bool  # True if the new value was kept (improvement)
    rejection_reason: str = ""

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Additional metrics measured during the experiment
    extra_metrics: Dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses and persistence."""
        return {
            "experiment_id": self.experiment_id,
            "agent_id": self.agent_id,
            "parameter_path": self.parameter_path,
            "original_value": self.original_value,
            "proposed_value": self.proposed_value,
            "status": self.status.value,
            "baseline_metric_value": self.baseline_metric_value,
            "experiment_metric_value": self.experiment_metric_value,
            "primary_metric": self.primary_metric,
            "improvement_pct": self.improvement_pct,
            "kept": self.kept,
            "rejection_reason": self.rejection_reason,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "extra_metrics": self.extra_metrics,
            "notes": self.notes,
        }


@dataclass
class AgentDirective:
    """Strategic direction for an agent's optimization.

    Analogous to autoresearch's program.md — defines what to optimize,
    within what bounds, and how aggressively to explore.
    """
    agent_id: str
    primary_metric: str
    secondary_metrics: List[str] = field(default_factory=list)
    parameter_bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    constraints: Dict[str, float] = field(default_factory=dict)
    experiment_budget_seconds: int = 300  # 5 minutes per experiment
    max_experiments_per_cycle: int = 10
    exploration_strategy: str = "random"  # "random", "grid", "perturbation"
    enabled: bool = True

    def validate_value(self, parameter_path: str, value: float) -> bool:
        """Check if a proposed value is within the directive's bounds."""
        if parameter_path not in self.parameter_bounds:
            return True  # no bounds defined = anything goes
        low, high = self.parameter_bounds[parameter_path]
        return low <= value <= high

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "agent_id": self.agent_id,
            "primary_metric": self.primary_metric,
            "secondary_metrics": self.secondary_metrics,
            "parameter_bounds": {
                k: list(v) for k, v in self.parameter_bounds.items()
            },
            "constraints": self.constraints,
            "experiment_budget_seconds": self.experiment_budget_seconds,
            "max_experiments_per_cycle": self.max_experiments_per_cycle,
            "exploration_strategy": self.exploration_strategy,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentDirective":
        """Create from dictionary."""
        bounds = {}
        for k, v in data.get("parameter_bounds", {}).items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                bounds[k] = (float(v[0]), float(v[1]))
        return cls(
            agent_id=data["agent_id"],
            primary_metric=data.get("primary_metric", ""),
            secondary_metrics=data.get("secondary_metrics", []),
            parameter_bounds=bounds,
            constraints=data.get("constraints", {}),
            experiment_budget_seconds=data.get("experiment_budget_seconds", 300),
            max_experiments_per_cycle=data.get("max_experiments_per_cycle", 10),
            exploration_strategy=data.get("exploration_strategy", "random"),
            enabled=data.get("enabled", True),
        )


@dataclass
class ExperimentCycleStats:
    """Statistics for a single experiment cycle across agents."""
    cycle_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_experiments: int = 0
    improvements: int = 0
    reverts: int = 0
    failures: int = 0
    agents_tuned: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_experiments": self.total_experiments,
            "improvements": self.improvements,
            "reverts": self.reverts,
            "failures": self.failures,
            "agents_tuned": self.agents_tuned,
        }
