"""Agent Metrics Value Objects.

Pure domain models for agent performance measurement.
No external dependencies beyond stdlib.

Used by:
- MetricsCollector: Produces metric snapshots
- ExperimentRunner: Compares baseline vs experiment metrics
- ExperimentStore: Persists metric history
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class AgentMetricSnapshot:
    """A single metric measurement for an agent at a point in time."""
    agent_id: str
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }


@dataclass
class AgentPerformanceProfile:
    """Aggregated performance profile for an agent.

    Contains current metric values, established baselines,
    and drift scores relative to those baselines.
    """
    agent_id: str
    metrics: Dict[str, float] = field(default_factory=dict)
    baselines: Dict[str, float] = field(default_factory=dict)
    drift_scores: Dict[str, float] = field(default_factory=dict)
    collected_at: datetime = field(default_factory=datetime.utcnow)

    def get_drift(self, metric_name: str) -> Optional[float]:
        """Get drift score for a metric (positive = degraded)."""
        return self.drift_scores.get(metric_name)

    def has_significant_drift(self, threshold: float = 0.15) -> bool:
        """Check if any metric has drifted beyond threshold."""
        return any(abs(d) > threshold for d in self.drift_scores.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "metrics": self.metrics,
            "baselines": self.baselines,
            "drift_scores": self.drift_scores,
            "collected_at": self.collected_at.isoformat(),
        }
