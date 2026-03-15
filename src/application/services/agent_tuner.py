"""Agent Tuner Service.

Provides a generic mechanism to read, modify, and propose parameter changes
for agents at runtime. Uses a registry of tunable parameters per agent type.

For KnowledgeManagerAgent, the tunable surface is the ReasoningEngineConfig
(ConfidenceThresholds, ScoringConfig, StrategyConfig, CrossLayerConfig).
Other agents can be added by registering their parameter descriptors.
"""

import logging
import random
from dataclasses import fields
from typing import Any, Callable, Dict, List, Optional, Tuple

from domain.experiment import AgentDirective, ExperimentConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunable parameter descriptor
# ---------------------------------------------------------------------------

class TunableParameter:
    """Descriptor for a single tunable parameter on an agent."""

    def __init__(
        self,
        path: str,
        getter: Callable[[Any], float],
        setter: Callable[[Any, float], None],
        default: float = 0.0,
    ):
        self.path = path
        self.getter = getter
        self.setter = setter
        self.default = default


# ---------------------------------------------------------------------------
# KnowledgeManager parameter registration
# ---------------------------------------------------------------------------

def _build_km_parameters() -> Dict[str, TunableParameter]:
    """Build tunable parameter descriptors for KnowledgeManagerAgent.

    Maps dot-path strings like "confidence.medical_high_threshold" to
    getter/setter lambdas that operate on agent.reasoning_engine.config.
    """
    params: Dict[str, TunableParameter] = {}

    # Helper to create getter/setter for a nested config dataclass field
    def _register(section: str, field_name: str, default: float):
        path = f"{section}.{field_name}"

        def getter(agent: Any) -> float:
            config = agent.reasoning_engine.config
            sub = getattr(config, section)
            return getattr(sub, field_name)

        def setter(agent: Any, value: float) -> None:
            config = agent.reasoning_engine.config
            sub = getattr(config, section)
            setattr(sub, field_name, value)

        params[path] = TunableParameter(path=path, getter=getter, setter=setter, default=default)

    # Import the config dataclasses to enumerate their fields + defaults
    from application.agents.knowledge_manager.reasoning_config import (
        ConfidenceThresholds,
        ScoringConfig,
        StrategyConfig,
        CrossLayerConfig,
    )

    for section_name, section_cls in [
        ("confidence", ConfidenceThresholds),
        ("scoring", ScoringConfig),
        ("strategy", StrategyConfig),
        ("cross_layer", CrossLayerConfig),
    ]:
        for f in fields(section_cls):
            if f.type in ("float", "int", float, int):
                _register(section_name, f.name, f.default if f.default is not f.default_factory else 0.0)  # type: ignore[arg-type]

    return params


# ---------------------------------------------------------------------------
# Global parameter registry
# ---------------------------------------------------------------------------

TUNABLE_PARAMETER_REGISTRY: Dict[str, Dict[str, TunableParameter]] = {}


def _ensure_registry():
    """Lazily populate the parameter registry."""
    if "knowledge_manager" not in TUNABLE_PARAMETER_REGISTRY:
        try:
            TUNABLE_PARAMETER_REGISTRY["knowledge_manager"] = _build_km_parameters()
        except Exception as e:
            logger.warning(f"Failed to build KM parameter registry: {e}")
            TUNABLE_PARAMETER_REGISTRY["knowledge_manager"] = {}


# ---------------------------------------------------------------------------
# AgentTuner service
# ---------------------------------------------------------------------------

class AgentTuner:
    """Service for reading, modifying, and proposing agent parameter changes.

    Works with any agent whose type is registered in TUNABLE_PARAMETER_REGISTRY.
    """

    def __init__(self, agents: Optional[Dict[str, Any]] = None):
        """Initialize with a mapping of agent_id -> agent instance.

        Args:
            agents: Dict mapping agent ID to the live agent object.
                    Can be updated at runtime via register_agent().
        """
        _ensure_registry()
        self._agents: Dict[str, Any] = agents or {}

    def register_agent(self, agent_id: str, agent: Any) -> None:
        """Register a live agent for tuning."""
        self._agents[agent_id] = agent

    def get_current_value(self, agent_id: str, parameter_path: str) -> Optional[float]:
        """Read the current value of a tunable parameter."""
        agent = self._agents.get(agent_id)
        if agent is None:
            logger.warning(f"Agent {agent_id} not registered for tuning")
            return None

        agent_type = self._resolve_type(agent_id)
        params = TUNABLE_PARAMETER_REGISTRY.get(agent_type, {})
        param = params.get(parameter_path)
        if param is None:
            logger.warning(f"Parameter {parameter_path} not registered for {agent_type}")
            return None

        try:
            return param.getter(agent)
        except Exception as e:
            logger.error(f"Failed to read {parameter_path} on {agent_id}: {e}")
            return None

    def apply_parameter(self, agent_id: str, parameter_path: str, value: float) -> bool:
        """Apply a parameter value to a live agent.

        Returns True on success.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            return False

        agent_type = self._resolve_type(agent_id)
        params = TUNABLE_PARAMETER_REGISTRY.get(agent_type, {})
        param = params.get(parameter_path)
        if param is None:
            return False

        try:
            param.setter(agent, value)
            logger.info(f"Applied {parameter_path}={value} to {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to apply {parameter_path}={value} on {agent_id}: {e}")
            return False

    def validate_bounds(
        self, parameter_path: str, value: float, directive: AgentDirective
    ) -> bool:
        """Check if a value is within directive bounds."""
        return directive.validate_value(parameter_path, value)

    def propose_experiments(
        self,
        agent_id: str,
        directive: AgentDirective,
        max_proposals: Optional[int] = None,
    ) -> List[ExperimentConfig]:
        """Generate experiment proposals by perturbing current parameters.

        Strategy is selected from the directive (random, grid, perturbation).
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            return []

        agent_type = self._resolve_type(agent_id)
        params = TUNABLE_PARAMETER_REGISTRY.get(agent_type, {})
        if not params:
            return []

        limit = max_proposals or directive.max_experiments_per_cycle
        proposals: List[ExperimentConfig] = []

        # Only propose for parameters with declared bounds
        bounded_paths = [p for p in directive.parameter_bounds if p in params]
        if not bounded_paths:
            return []

        strategy = directive.exploration_strategy

        for _ in range(limit):
            path = random.choice(bounded_paths)
            low, high = directive.parameter_bounds[path]
            current = self.get_current_value(agent_id, path)
            if current is None:
                continue

            if strategy == "perturbation":
                # Small perturbation ±10% of range
                range_size = high - low
                delta = random.uniform(-0.1, 0.1) * range_size
                proposed = max(low, min(high, current + delta))
            elif strategy == "grid":
                # Pick from evenly spaced grid points
                steps = min(limit, 5)
                step_size = (high - low) / max(steps, 1)
                idx = random.randint(0, steps)
                proposed = low + idx * step_size
            else:
                # random: uniform within bounds
                proposed = random.uniform(low, high)

            proposals.append(ExperimentConfig(
                agent_id=agent_id,
                parameter_path=path,
                original_value=current,
                proposed_value=round(proposed, 6),
                duration_seconds=directive.experiment_budget_seconds,
                primary_metric=directive.primary_metric,
            ))

        return proposals

    def list_tunable_parameters(self, agent_id: str) -> List[str]:
        """List all tunable parameter paths for an agent."""
        agent_type = self._resolve_type(agent_id)
        return list(TUNABLE_PARAMETER_REGISTRY.get(agent_type, {}).keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_type(self, agent_id: str) -> str:
        """Resolve agent_id to a registered agent type."""
        for t in TUNABLE_PARAMETER_REGISTRY:
            if t in agent_id:
                return t
        return agent_id
