"""Experiment System Configuration.

Configures the autonomous agent experimentation loop.
Loads from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass


@dataclass
class ExperimentSystemConfig:
    """Configuration for the agent experiment system."""

    enabled: bool = False
    cycle_interval_seconds: int = 3600  # 1 hour between cycles
    max_experiments_per_cycle: int = 10
    default_experiment_duration_seconds: int = 300  # 5 minutes
    min_improvement_pct: float = 0.05  # 5% minimum improvement to keep
    auto_revert_on_degradation: bool = True
    require_approval_for_changes: bool = False  # if True, only log proposals

    @classmethod
    def from_env(cls) -> "ExperimentSystemConfig":
        """Create configuration from environment variables."""
        return cls(
            enabled=os.getenv(
                "ENABLE_AGENT_EXPERIMENTS", "false"
            ).lower() in ("true", "1", "yes"),
            cycle_interval_seconds=int(
                os.getenv("EXPERIMENT_CYCLE_INTERVAL", "3600")
            ),
            max_experiments_per_cycle=int(
                os.getenv("EXPERIMENT_MAX_PER_CYCLE", "10")
            ),
            default_experiment_duration_seconds=int(
                os.getenv("EXPERIMENT_DURATION_SECONDS", "300")
            ),
            min_improvement_pct=float(
                os.getenv("EXPERIMENT_MIN_IMPROVEMENT_PCT", "0.05")
            ),
            auto_revert_on_degradation=os.getenv(
                "EXPERIMENT_AUTO_REVERT", "true"
            ).lower() in ("true", "1", "yes"),
            require_approval_for_changes=os.getenv(
                "EXPERIMENT_REQUIRE_APPROVAL", "false"
            ).lower() in ("true", "1", "yes"),
        )
