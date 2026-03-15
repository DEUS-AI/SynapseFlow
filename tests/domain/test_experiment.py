"""Tests for domain experiment models."""

import pytest
from datetime import datetime

from domain.experiment import (
    AgentDirective,
    ExperimentConfig,
    ExperimentCycleStats,
    ExperimentResult,
    ExperimentStatus,
    MetricDefinition,
    MetricDirection,
)


class TestMetricDefinition:
    def test_higher_is_better_improvement(self):
        m = MetricDefinition(name="accuracy", direction=MetricDirection.HIGHER_IS_BETTER)
        assert m.is_improvement(0.9, 0.8) is True
        assert m.is_improvement(0.7, 0.8) is False

    def test_lower_is_better_improvement(self):
        m = MetricDefinition(name="error", direction=MetricDirection.LOWER_IS_BETTER)
        assert m.is_improvement(0.1, 0.2) is True
        assert m.is_improvement(0.3, 0.2) is False

    def test_improvement_pct_higher(self):
        m = MetricDefinition(name="accuracy", direction=MetricDirection.HIGHER_IS_BETTER)
        pct = m.improvement_pct(0.9, 0.8)
        assert abs(pct - 0.125) < 1e-6

    def test_improvement_pct_lower(self):
        m = MetricDefinition(name="error", direction=MetricDirection.LOWER_IS_BETTER)
        pct = m.improvement_pct(0.1, 0.2)
        assert abs(pct - 0.5) < 1e-6

    def test_improvement_pct_zero_baseline(self):
        m = MetricDefinition(name="x", direction=MetricDirection.HIGHER_IS_BETTER)
        assert m.improvement_pct(0.5, 0.0) == 0.0


class TestExperimentConfig:
    def test_auto_id(self):
        c = ExperimentConfig(
            agent_id="km_1",
            parameter_path="confidence.medical_high_threshold",
            original_value=0.8,
            proposed_value=0.85,
            duration_seconds=60,
            primary_metric="validation_accuracy",
        )
        assert c.experiment_id.startswith("exp_km_1_")

    def test_explicit_id(self):
        c = ExperimentConfig(
            agent_id="km_1",
            parameter_path="p",
            original_value=1,
            proposed_value=2,
            duration_seconds=60,
            primary_metric="m",
            experiment_id="my_id",
        )
        assert c.experiment_id == "my_id"


class TestAgentDirective:
    def test_validate_value_in_bounds(self):
        d = AgentDirective(
            agent_id="km",
            primary_metric="accuracy",
            parameter_bounds={"threshold": (0.5, 0.95)},
        )
        assert d.validate_value("threshold", 0.7) is True
        assert d.validate_value("threshold", 0.3) is False
        assert d.validate_value("threshold", 1.0) is False

    def test_validate_value_no_bounds(self):
        d = AgentDirective(agent_id="km", primary_metric="accuracy")
        assert d.validate_value("anything", 999.0) is True

    def test_to_dict_from_dict_roundtrip(self):
        d = AgentDirective(
            agent_id="km",
            primary_metric="accuracy",
            secondary_metrics=["latency"],
            parameter_bounds={"t": (0.5, 0.9)},
            constraints={"min_accuracy": 0.8},
            experiment_budget_seconds=120,
            max_experiments_per_cycle=5,
            exploration_strategy="perturbation",
            enabled=True,
        )
        data = d.to_dict()
        d2 = AgentDirective.from_dict(data)
        assert d2.agent_id == d.agent_id
        assert d2.primary_metric == d.primary_metric
        assert d2.parameter_bounds["t"] == (0.5, 0.9)
        assert d2.exploration_strategy == "perturbation"


class TestExperimentResult:
    def test_to_dict(self):
        r = ExperimentResult(
            experiment_id="exp_1",
            agent_id="km",
            parameter_path="confidence.x",
            original_value=0.8,
            proposed_value=0.85,
            status=ExperimentStatus.COMPLETED,
            baseline_metric_value=0.7,
            experiment_metric_value=0.75,
            primary_metric="accuracy",
            improvement_pct=0.071,
            kept=True,
            started_at=datetime(2026, 1, 1),
            completed_at=datetime(2026, 1, 1, 0, 5),
        )
        d = r.to_dict()
        assert d["experiment_id"] == "exp_1"
        assert d["kept"] is True
        assert d["status"] == "completed"


class TestExperimentCycleStats:
    def test_to_dict(self):
        s = ExperimentCycleStats(
            cycle_id="c1",
            started_at=datetime(2026, 1, 1),
            total_experiments=3,
            improvements=1,
        )
        d = s.to_dict()
        assert d["cycle_id"] == "c1"
        assert d["total_experiments"] == 3
