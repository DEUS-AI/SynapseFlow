"""Tests for ExperimentLoopJob."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from application.jobs.experiment_loop import ExperimentLoopJob
from application.services.experiment_runner import ExperimentRunner
from application.services.metrics_collector import MetricsCollector
from application.services.agent_tuner import AgentTuner
from config.experiment_config import ExperimentSystemConfig
from domain.experiment import AgentDirective, ExperimentConfig, ExperimentResult, ExperimentStatus


class FakeReasoningEngine:
    def __init__(self):
        from application.agents.knowledge_manager.reasoning_config import ReasoningEngineConfig
        self.config = ReasoningEngineConfig()


class FakeAgent:
    def __init__(self):
        self.reasoning_engine = FakeReasoningEngine()


@pytest.fixture
def loop_job():
    agent = FakeAgent()
    collector = MetricsCollector()
    tuner = AgentTuner(agents={"knowledge_manager_1": agent})
    config = ExperimentSystemConfig(enabled=True, min_improvement_pct=0.01)
    runner = ExperimentRunner(collector, tuner, None, config)

    directive = AgentDirective(
        agent_id="knowledge_manager_1",
        primary_metric="validation_accuracy",
        parameter_bounds={"confidence.medical_high_threshold": (0.5, 0.95)},
        experiment_budget_seconds=0,  # instant
        max_experiments_per_cycle=3,
    )

    job = ExperimentLoopJob(
        experiment_runner=runner,
        agent_tuner=tuner,
        directives={"knowledge_manager_1": directive},
        cycle_interval_seconds=1,
        max_experiments_per_cycle=3,
    )
    return job


@pytest.mark.asyncio
async def test_run_once(loop_job):
    """Test single manual cycle execution."""
    stats = await loop_job.run_once()
    assert stats.total_experiments == 3
    assert stats.cycle_id == "cycle_000001"
    assert "knowledge_manager_1" in stats.agents_tuned


@pytest.mark.asyncio
async def test_get_statistics(loop_job):
    """Test statistics tracking."""
    await loop_job.run_once()
    stats = loop_job.get_statistics()
    assert stats["total_cycles"] == 1
    assert stats["total_experiments"] == 3
    assert stats["running"] is False


@pytest.mark.asyncio
async def test_set_and_remove_directive(loop_job):
    """Test directive management."""
    new_directive = AgentDirective(
        agent_id="other_agent",
        primary_metric="latency",
    )
    loop_job.set_directive("other_agent", new_directive)
    assert "other_agent" in loop_job.directives

    loop_job.remove_directive("other_agent")
    assert "other_agent" not in loop_job.directives


@pytest.mark.asyncio
async def test_disabled_directive_skipped(loop_job):
    """Test that disabled directives are skipped."""
    loop_job.directives["knowledge_manager_1"].enabled = False
    stats = await loop_job.run_once()
    assert stats.total_experiments == 0
    assert stats.agents_tuned == []


@pytest.mark.asyncio
async def test_max_experiments_cap(loop_job):
    """Test that global experiment cap is respected."""
    loop_job.max_experiments_per_cycle = 2
    stats = await loop_job.run_once()
    assert stats.total_experiments <= 2


@pytest.mark.asyncio
async def test_start_stop(loop_job):
    """Test start/stop lifecycle."""
    await loop_job.start()
    assert loop_job._running is True

    await loop_job.stop()
    assert loop_job._running is False
