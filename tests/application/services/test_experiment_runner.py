"""Tests for ExperimentRunner service."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from application.services.experiment_runner import ExperimentRunner
from application.services.metrics_collector import MetricsCollector
from application.services.agent_tuner import AgentTuner
from config.experiment_config import ExperimentSystemConfig
from domain.experiment import ExperimentConfig, ExperimentStatus
from domain.agent_metrics import AgentMetricSnapshot


class FakeReasoningEngine:
    def __init__(self):
        from application.agents.knowledge_manager.reasoning_config import ReasoningEngineConfig
        self.config = ReasoningEngineConfig()


class FakeAgent:
    def __init__(self):
        self.reasoning_engine = FakeReasoningEngine()


@pytest.fixture
def agent():
    return FakeAgent()


@pytest.fixture
def runner(agent):
    collector = MetricsCollector()
    tuner = AgentTuner(agents={"knowledge_manager_1": agent})
    config = ExperimentSystemConfig(
        enabled=True,
        min_improvement_pct=0.01,
        auto_revert_on_degradation=True,
    )
    return ExperimentRunner(
        metrics_collector=collector,
        agent_tuner=tuner,
        experiment_store=None,
        system_config=config,
    )


@pytest.mark.asyncio
async def test_run_experiment_basic(runner):
    """Test that an experiment runs and returns a result."""
    config = ExperimentConfig(
        agent_id="knowledge_manager_1",
        parameter_path="confidence.medical_high_threshold",
        original_value=0.8,
        proposed_value=0.85,
        duration_seconds=0,  # instant for testing
        primary_metric="validation_accuracy",
        experiment_id="test_exp_1",
    )
    result = await runner.run_experiment(config)
    assert result.experiment_id == "test_exp_1"
    assert result.status in (ExperimentStatus.COMPLETED, ExperimentStatus.REVERTED)
    assert result.started_at is not None
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_run_experiment_failed_apply(runner):
    """Test that a failed parameter application returns FAILED."""
    config = ExperimentConfig(
        agent_id="nonexistent_agent",
        parameter_path="confidence.x",
        original_value=0.5,
        proposed_value=0.6,
        duration_seconds=0,
        primary_metric="validation_accuracy",
        experiment_id="test_exp_fail",
    )
    result = await runner.run_experiment(config)
    assert result.status == ExperimentStatus.FAILED
    assert result.kept is False
    assert "Failed to apply" in result.rejection_reason


@pytest.mark.asyncio
async def test_run_experiment_with_store(agent):
    """Test that results are persisted to store."""
    store = MagicMock()
    store.save_experiment = AsyncMock(return_value=True)

    collector = MetricsCollector()
    tuner = AgentTuner(agents={"knowledge_manager_1": agent})
    config = ExperimentSystemConfig(enabled=True, min_improvement_pct=0.01)
    runner = ExperimentRunner(collector, tuner, store, config)

    exp_config = ExperimentConfig(
        agent_id="knowledge_manager_1",
        parameter_path="confidence.medical_high_threshold",
        original_value=0.8,
        proposed_value=0.85,
        duration_seconds=0,
        primary_metric="validation_accuracy",
    )
    await runner.run_experiment(exp_config)
    store.save_experiment.assert_called_once()


@pytest.mark.asyncio
async def test_approval_gate_prevents_keeping(agent):
    """Test that require_approval_for_changes prevents automatic keeping."""
    collector = MagicMock(spec=MetricsCollector)
    # Simulate improvement
    baseline_snap = AgentMetricSnapshot(agent_id="km", metric_name="validation_accuracy", value=0.7)
    post_snap = AgentMetricSnapshot(agent_id="km", metric_name="validation_accuracy", value=0.9)
    collector.collect_metric = MagicMock(side_effect=[baseline_snap, post_snap])
    collector.update_baseline = MagicMock()

    tuner = AgentTuner(agents={"knowledge_manager_1": agent})
    config = ExperimentSystemConfig(
        enabled=True,
        min_improvement_pct=0.01,
        require_approval_for_changes=True,
        auto_revert_on_degradation=True,
    )
    runner = ExperimentRunner(collector, tuner, None, config)

    exp_config = ExperimentConfig(
        agent_id="knowledge_manager_1",
        parameter_path="confidence.medical_high_threshold",
        original_value=0.8,
        proposed_value=0.85,
        duration_seconds=0,
        primary_metric="validation_accuracy",
    )
    result = await runner.run_experiment(exp_config)
    assert result.kept is False
    assert "approval" in result.rejection_reason.lower()
