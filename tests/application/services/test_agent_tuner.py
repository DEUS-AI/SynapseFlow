"""Tests for AgentTuner service."""

import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

from application.services.agent_tuner import AgentTuner, TUNABLE_PARAMETER_REGISTRY, _ensure_registry
from domain.experiment import AgentDirective


@dataclass
class FakeSubConfig:
    threshold_a: float = 0.8
    threshold_b: float = 0.6


@dataclass
class FakeConfig:
    sub: FakeSubConfig = None

    def __post_init__(self):
        if self.sub is None:
            self.sub = FakeSubConfig()


class FakeReasoningEngine:
    def __init__(self):
        from application.agents.knowledge_manager.reasoning_config import ReasoningEngineConfig
        self.config = ReasoningEngineConfig()


class FakeKMAgent:
    """Minimal mock of KnowledgeManagerAgent for tuner tests."""
    def __init__(self):
        self.reasoning_engine = FakeReasoningEngine()


class TestAgentTuner:
    def setup_method(self):
        self.agent = FakeKMAgent()
        self.tuner = AgentTuner(agents={"knowledge_manager_1": self.agent})

    def test_registry_populated(self):
        _ensure_registry()
        assert "knowledge_manager" in TUNABLE_PARAMETER_REGISTRY
        km_params = TUNABLE_PARAMETER_REGISTRY["knowledge_manager"]
        assert len(km_params) > 0
        assert "confidence.medical_high_threshold" in km_params

    def test_get_current_value(self):
        val = self.tuner.get_current_value(
            "knowledge_manager_1", "confidence.medical_high_threshold"
        )
        assert val == pytest.approx(0.8)

    def test_apply_parameter(self):
        ok = self.tuner.apply_parameter(
            "knowledge_manager_1", "confidence.medical_high_threshold", 0.9
        )
        assert ok is True
        assert self.agent.reasoning_engine.config.confidence.medical_high_threshold == pytest.approx(0.9)

    def test_apply_unknown_agent(self):
        ok = self.tuner.apply_parameter("unknown", "confidence.x", 0.5)
        assert ok is False

    def test_apply_unknown_parameter(self):
        ok = self.tuner.apply_parameter("knowledge_manager_1", "nonexistent.param", 0.5)
        assert ok is False

    def test_propose_experiments(self):
        directive = AgentDirective(
            agent_id="knowledge_manager_1",
            primary_metric="validation_accuracy",
            parameter_bounds={
                "confidence.medical_high_threshold": (0.5, 0.95),
            },
            max_experiments_per_cycle=3,
        )
        proposals = self.tuner.propose_experiments(
            "knowledge_manager_1", directive, max_proposals=3
        )
        assert len(proposals) == 3
        for p in proposals:
            assert p.agent_id == "knowledge_manager_1"
            assert p.parameter_path == "confidence.medical_high_threshold"
            assert 0.5 <= p.proposed_value <= 0.95

    def test_propose_empty_no_bounds(self):
        directive = AgentDirective(
            agent_id="knowledge_manager_1",
            primary_metric="accuracy",
        )
        proposals = self.tuner.propose_experiments("knowledge_manager_1", directive)
        assert proposals == []

    def test_list_tunable_parameters(self):
        params = self.tuner.list_tunable_parameters("knowledge_manager_1")
        assert len(params) > 0
        assert "confidence.medical_high_threshold" in params

    def test_register_agent(self):
        agent2 = FakeKMAgent()
        self.tuner.register_agent("knowledge_manager_2", agent2)
        val = self.tuner.get_current_value(
            "knowledge_manager_2", "confidence.medical_high_threshold"
        )
        assert val == pytest.approx(0.8)

    def test_validate_bounds(self):
        directive = AgentDirective(
            agent_id="km",
            primary_metric="m",
            parameter_bounds={"confidence.medical_high_threshold": (0.5, 0.95)},
        )
        assert self.tuner.validate_bounds("confidence.medical_high_threshold", 0.7, directive)
        assert not self.tuner.validate_bounds("confidence.medical_high_threshold", 0.3, directive)
