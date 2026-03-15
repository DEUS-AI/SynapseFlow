"""Experiment Runner Service.

Executes time-boxed experiments following the autoresearch loop:
1. Measure baseline metric
2. Apply parameter change
3. Wait for experiment duration
4. Measure post-experiment metric
5. Decide: keep or revert
6. Record result

Each experiment modifies exactly ONE parameter and measures ONE primary metric.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from domain.experiment import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
    MetricDefinition,
    MetricDirection,
)
from config.experiment_config import ExperimentSystemConfig

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Runs individual time-boxed experiments on agent parameters.

    Dependencies:
    - metrics_collector: MetricsCollector for measuring metrics
    - agent_tuner: AgentTuner for applying/reverting parameter changes
    - experiment_store: ExperimentStore for persisting results
    - system_config: ExperimentSystemConfig for global settings
    """

    # Default metric definitions — direction and interpretation
    METRIC_DIRECTIONS = {
        "validation_accuracy": MetricDirection.HIGHER_IS_BETTER,
        "conflict_resolution_rate": MetricDirection.HIGHER_IS_BETTER,
        "reasoning_confidence": MetricDirection.HIGHER_IS_BETTER,
        "escalation_rate": MetricDirection.LOWER_IS_BETTER,
        "calibration_error": MetricDirection.LOWER_IS_BETTER,
        "drift_score": MetricDirection.LOWER_IS_BETTER,
    }

    def __init__(
        self,
        metrics_collector: Any,
        agent_tuner: Any,
        experiment_store: Any = None,
        system_config: Optional[ExperimentSystemConfig] = None,
    ):
        self.metrics_collector = metrics_collector
        self.agent_tuner = agent_tuner
        self.experiment_store = experiment_store
        self.config = system_config or ExperimentSystemConfig()

    async def run_experiment(self, exp_config: ExperimentConfig) -> ExperimentResult:
        """Execute a single experiment.

        Returns ExperimentResult with kept=True if the change improved the metric.
        """
        started_at = datetime.utcnow()
        logger.info(
            f"Starting experiment {exp_config.experiment_id}: "
            f"{exp_config.parameter_path} {exp_config.original_value} -> {exp_config.proposed_value}"
        )

        # 1. Measure baseline metric
        baseline_snapshot = self.metrics_collector.collect_metric(
            exp_config.agent_id, exp_config.primary_metric
        )
        baseline_value = baseline_snapshot.value

        # 2. Apply proposed parameter
        applied = self.agent_tuner.apply_parameter(
            exp_config.agent_id,
            exp_config.parameter_path,
            exp_config.proposed_value,
        )

        if not applied:
            return self._make_result(
                exp_config, baseline_value, baseline_value, started_at,
                status=ExperimentStatus.FAILED,
                kept=False,
                rejection_reason="Failed to apply parameter",
            )

        # 3. Wait for experiment duration (time-boxed)
        try:
            await asyncio.sleep(exp_config.duration_seconds)
        except asyncio.CancelledError:
            # Graceful shutdown — revert and report
            self.agent_tuner.apply_parameter(
                exp_config.agent_id,
                exp_config.parameter_path,
                exp_config.original_value,
            )
            return self._make_result(
                exp_config, baseline_value, baseline_value, started_at,
                status=ExperimentStatus.FAILED,
                kept=False,
                rejection_reason="Experiment cancelled",
            )

        # 4. Measure post-experiment metric
        post_snapshot = self.metrics_collector.collect_metric(
            exp_config.agent_id, exp_config.primary_metric
        )
        experiment_value = post_snapshot.value

        # 5. Decide: keep or revert
        direction = self.METRIC_DIRECTIONS.get(
            exp_config.primary_metric, MetricDirection.HIGHER_IS_BETTER
        )
        metric_def = MetricDefinition(
            name=exp_config.primary_metric, direction=direction
        )
        improvement = metric_def.improvement_pct(experiment_value, baseline_value)
        is_better = metric_def.is_improvement(experiment_value, baseline_value)
        meets_threshold = improvement >= self.config.min_improvement_pct

        kept = is_better and meets_threshold

        # Approval gate: if require_approval is on, never keep automatically
        if self.config.require_approval_for_changes and kept:
            logger.info(
                f"Experiment {exp_config.experiment_id} would improve by {improvement:.2%} "
                f"but require_approval_for_changes is enabled — reverting"
            )
            kept = False

        status = ExperimentStatus.COMPLETED
        rejection_reason = ""

        if not kept:
            if not is_better:
                rejection_reason = f"Metric degraded: {baseline_value:.4f} -> {experiment_value:.4f}"
            elif not meets_threshold:
                rejection_reason = f"Improvement {improvement:.2%} below threshold {self.config.min_improvement_pct:.2%}"
            elif self.config.require_approval_for_changes:
                rejection_reason = "Awaiting manual approval"

            # Revert parameter
            if self.config.auto_revert_on_degradation:
                reverted = self.agent_tuner.apply_parameter(
                    exp_config.agent_id,
                    exp_config.parameter_path,
                    exp_config.original_value,
                )
                if reverted:
                    status = ExperimentStatus.REVERTED
                    logger.info(f"Reverted {exp_config.parameter_path} to {exp_config.original_value}")
        else:
            # Update baseline
            self.metrics_collector.update_baseline(
                exp_config.agent_id, exp_config.primary_metric, experiment_value
            )
            logger.info(
                f"Keeping improvement: {exp_config.parameter_path}={exp_config.proposed_value} "
                f"(+{improvement:.2%})"
            )

        result = self._make_result(
            exp_config, baseline_value, experiment_value, started_at,
            status=status, kept=kept, rejection_reason=rejection_reason,
        )

        # 6. Persist result
        if self.experiment_store is not None:
            try:
                await self.experiment_store.save_experiment(result)
            except Exception as e:
                logger.error(f"Failed to persist experiment result: {e}")

        return result

    def _make_result(
        self,
        config: ExperimentConfig,
        baseline_value: float,
        experiment_value: float,
        started_at: datetime,
        status: ExperimentStatus,
        kept: bool,
        rejection_reason: str = "",
    ) -> ExperimentResult:
        """Build an ExperimentResult from parts."""
        completed_at = datetime.utcnow()
        direction = self.METRIC_DIRECTIONS.get(
            config.primary_metric, MetricDirection.HIGHER_IS_BETTER
        )
        metric_def = MetricDefinition(name=config.primary_metric, direction=direction)
        improvement = metric_def.improvement_pct(experiment_value, baseline_value)

        return ExperimentResult(
            experiment_id=config.experiment_id,
            agent_id=config.agent_id,
            parameter_path=config.parameter_path,
            original_value=config.original_value,
            proposed_value=config.proposed_value,
            status=status,
            baseline_metric_value=baseline_value,
            experiment_metric_value=experiment_value,
            primary_metric=config.primary_metric,
            improvement_pct=improvement,
            kept=kept,
            rejection_reason=rejection_reason,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
        )
