"""Metrics Collector Service.

Collects agent performance metrics from existing SynapseFlow services:
- FeedbackIntegrator for operation stats, drift detection, calibration
- AgentDiscoveryService for agent health/heartbeat status

Produces AgentMetricSnapshot and AgentPerformanceProfile domain objects
consumed by the ExperimentRunner.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from domain.agent_metrics import AgentMetricSnapshot, AgentPerformanceProfile

logger = logging.getLogger(__name__)

# Metric definitions per agent type — extensible registry.
# Each agent that participates in experiments registers its collectible metrics here.
AGENT_METRIC_DEFINITIONS: Dict[str, List[str]] = {
    "knowledge_manager": [
        "validation_accuracy",
        "conflict_resolution_rate",
        "reasoning_confidence",
        "escalation_rate",
        "calibration_error",
        "drift_score",
    ],
}


class MetricsCollector:
    """Collects and aggregates agent performance metrics.

    Acts as a facade over FeedbackIntegrator and AgentDiscoveryService,
    translating their raw data into domain metric objects.
    """

    def __init__(
        self,
        feedback_integrator: Any = None,
        discovery_service: Any = None,
    ):
        """Initialize with optional service dependencies.

        Args:
            feedback_integrator: FeedbackIntegrator instance
            discovery_service: AgentDiscoveryService instance
        """
        self.feedback_integrator = feedback_integrator
        self.discovery_service = discovery_service
        # In-memory baseline cache
        self._baselines: Dict[str, Dict[str, float]] = {}

    def collect_metric(
        self, agent_id: str, metric_name: str
    ) -> AgentMetricSnapshot:
        """Collect a single metric value for an agent.

        Pulls from FeedbackIntegrator operation stats and drift detection.
        Falls back to 0.0 if the metric cannot be collected.
        """
        value = 0.0

        if self.feedback_integrator is not None:
            value = self._extract_metric(agent_id, metric_name)

        return AgentMetricSnapshot(
            agent_id=agent_id,
            metric_name=metric_name,
            value=value,
        )

    def collect_agent_metrics(self, agent_id: str) -> AgentPerformanceProfile:
        """Collect all defined metrics for an agent and return a full profile."""
        agent_type = self._resolve_agent_type(agent_id)
        metric_names = AGENT_METRIC_DEFINITIONS.get(agent_type, [])

        metrics: Dict[str, float] = {}
        for name in metric_names:
            snapshot = self.collect_metric(agent_id, name)
            metrics[name] = snapshot.value

        baselines = self._baselines.get(agent_id, {})
        drift_scores: Dict[str, float] = {}
        for name, current_val in metrics.items():
            baseline_val = baselines.get(name)
            if baseline_val is not None and baseline_val != 0:
                drift_scores[name] = (baseline_val - current_val) / abs(baseline_val)

        return AgentPerformanceProfile(
            agent_id=agent_id,
            metrics=metrics,
            baselines=baselines,
            drift_scores=drift_scores,
        )

    def update_baseline(self, agent_id: str, metric_name: str, value: float) -> None:
        """Record a metric value as the new baseline."""
        if agent_id not in self._baselines:
            self._baselines[agent_id] = {}
        self._baselines[agent_id][metric_name] = value

    def get_baseline(self, agent_id: str, metric_name: str) -> Optional[float]:
        """Get the current baseline for a metric."""
        return self._baselines.get(agent_id, {}).get(metric_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_metric(self, agent_id: str, metric_name: str) -> float:
        """Extract a metric value from FeedbackIntegrator data."""
        fi = self.feedback_integrator
        if fi is None:
            return 0.0

        if metric_name == "validation_accuracy":
            stats = fi.get_operation_stats("entity_creation")
            total = stats.get("total", 0)
            if total > 0:
                return stats.get("successes", 0) / total
            return 0.0

        if metric_name == "conflict_resolution_rate":
            stats = fi.get_operation_stats("conflict_resolution")
            total = stats.get("total", 0)
            if total > 0:
                return stats.get("successes", 0) / total
            return 0.0

        if metric_name == "reasoning_confidence":
            stats = fi.get_operation_stats()
            if stats:
                confidences = [
                    s.get("avg_confidence", 0) for s in stats.values() if s.get("avg_confidence")
                ]
                if confidences:
                    return sum(confidences) / len(confidences)
            return 0.0

        if metric_name == "escalation_rate":
            stats = fi.get_operation_stats("escalation")
            total_all = sum(
                s.get("total", 0) for s in fi.get_operation_stats().values()
            ) if fi.get_operation_stats() else 0
            if total_all > 0:
                return stats.get("total", 0) / total_all
            return 0.0

        if metric_name == "calibration_error":
            report = fi.generate_calibration_report()
            return report.get("overall_calibration_error", 0.0)

        if metric_name == "drift_score":
            drift = fi.detect_drift()
            if drift is not None:
                return drift.drift_score
            return 0.0

        return 0.0

    def _resolve_agent_type(self, agent_id: str) -> str:
        """Resolve agent_id to a known agent type string.

        Simple heuristic: if the agent_id contains a known type, use it.
        """
        for agent_type in AGENT_METRIC_DEFINITIONS:
            if agent_type in agent_id:
                return agent_type
        return agent_id
