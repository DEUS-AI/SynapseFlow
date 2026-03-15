"""Background job for autonomous agent experiment cycles.

Follows the PromotionScannerJob pattern: asyncio-based background loop
with start/stop lifecycle, statistics tracking, and graceful shutdown.

Each cycle:
1. Loads enabled directives for registered agents
2. For each agent, proposes parameter perturbations
3. Runs experiments sequentially (to avoid interference)
4. Records results and updates baselines on improvements

Run standalone: uv run python -m application.jobs.experiment_loop
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.experiment import AgentDirective, ExperimentCycleStats

logger = logging.getLogger(__name__)


class ExperimentLoopJob:
    """Background job that periodically runs experiment cycles.

    Features:
    - Configurable cycle interval
    - Per-agent directive-driven experiments
    - Statistics tracking
    - Graceful shutdown
    - Manual trigger via run_once()
    """

    def __init__(
        self,
        experiment_runner: Any,
        agent_tuner: Any,
        directives: Optional[Dict[str, AgentDirective]] = None,
        cycle_interval_seconds: int = 3600,
        max_experiments_per_cycle: int = 10,
    ):
        """Initialize the experiment loop job.

        Args:
            experiment_runner: ExperimentRunner instance
            agent_tuner: AgentTuner instance
            directives: Dict of agent_id -> AgentDirective
            cycle_interval_seconds: Seconds between cycles
            max_experiments_per_cycle: Global cap on experiments per cycle
        """
        self.experiment_runner = experiment_runner
        self.agent_tuner = agent_tuner
        self.directives: Dict[str, AgentDirective] = directives or {}
        self.cycle_interval = cycle_interval_seconds
        self.max_experiments_per_cycle = max_experiments_per_cycle

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._cycle_count = 0

        self.stats: Dict[str, Any] = {
            "total_cycles": 0,
            "total_experiments": 0,
            "total_improvements": 0,
            "total_reverts": 0,
            "total_failures": 0,
            "last_cycle_at": None,
            "last_cycle_duration_ms": 0,
            "errors": 0,
        }

    def set_directive(self, agent_id: str, directive: AgentDirective) -> None:
        """Set or update a directive for an agent."""
        self.directives[agent_id] = directive
        logger.info(f"Directive set for {agent_id}: metric={directive.primary_metric}")

    def remove_directive(self, agent_id: str) -> None:
        """Remove a directive for an agent."""
        self.directives.pop(agent_id, None)

    async def start(self) -> None:
        """Start the background experiment loop."""
        if self._running:
            logger.warning("Experiment loop is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._experiment_loop())
        logger.info(
            f"Experiment loop started (interval: {self.cycle_interval}s, "
            f"directives: {list(self.directives.keys())})"
        )

    async def stop(self) -> None:
        """Stop the experiment loop gracefully."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Experiment loop stopped")

    async def _experiment_loop(self) -> None:
        """Main loop: sleep → run cycle → repeat."""
        while self._running:
            try:
                await self._run_cycle()
                await asyncio.sleep(self.cycle_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error in experiment cycle: {e}")
                await asyncio.sleep(min(self.cycle_interval, 60))

    async def _run_cycle(self) -> ExperimentCycleStats:
        """Execute one full experiment cycle across all active agents."""
        self._cycle_count += 1
        cycle_id = f"cycle_{self._cycle_count:06d}"
        start_time = datetime.utcnow()

        cycle_stats = ExperimentCycleStats(
            cycle_id=cycle_id,
            started_at=start_time,
        )

        logger.info(f"Starting experiment cycle {cycle_id}")

        experiments_remaining = self.max_experiments_per_cycle

        for agent_id, directive in self.directives.items():
            if not directive.enabled:
                continue
            if experiments_remaining <= 0:
                break

            agent_limit = min(
                directive.max_experiments_per_cycle,
                experiments_remaining,
            )

            proposals = self.agent_tuner.propose_experiments(
                agent_id, directive, max_proposals=agent_limit
            )

            if not proposals:
                logger.debug(f"No experiments proposed for {agent_id}")
                continue

            cycle_stats.agents_tuned.append(agent_id)

            for proposal in proposals:
                if experiments_remaining <= 0:
                    break

                try:
                    result = await self.experiment_runner.run_experiment(proposal)
                    cycle_stats.total_experiments += 1
                    experiments_remaining -= 1

                    if result.kept:
                        cycle_stats.improvements += 1
                    elif result.status.value == "reverted":
                        cycle_stats.reverts += 1
                    elif result.status.value == "failed":
                        cycle_stats.failures += 1

                except Exception as e:
                    cycle_stats.failures += 1
                    experiments_remaining -= 1
                    logger.error(f"Experiment failed for {agent_id}: {e}")

        cycle_stats.completed_at = datetime.utcnow()

        # Update global stats
        self.stats["total_cycles"] += 1
        self.stats["total_experiments"] += cycle_stats.total_experiments
        self.stats["total_improvements"] += cycle_stats.improvements
        self.stats["total_reverts"] += cycle_stats.reverts
        self.stats["total_failures"] += cycle_stats.failures
        self.stats["last_cycle_at"] = start_time.isoformat()
        duration_ms = (cycle_stats.completed_at - start_time).total_seconds() * 1000
        self.stats["last_cycle_duration_ms"] = duration_ms

        logger.info(
            f"Cycle {cycle_id} completed in {duration_ms:.0f}ms: "
            f"{cycle_stats.total_experiments} experiments, "
            f"{cycle_stats.improvements} improvements, "
            f"{cycle_stats.reverts} reverts, "
            f"{cycle_stats.failures} failures"
        )

        return cycle_stats

    async def run_once(self) -> ExperimentCycleStats:
        """Run a single cycle (for manual triggering)."""
        return await self._run_cycle()

    def get_statistics(self) -> Dict[str, Any]:
        """Get cumulative statistics."""
        return {
            **self.stats,
            "running": self._running,
            "cycle_interval_seconds": self.cycle_interval,
            "active_directives": [
                aid for aid, d in self.directives.items() if d.enabled
            ],
        }


async def main():
    """Entry point for standalone execution."""
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting experiment loop (standalone)...")

    # In standalone mode we need to bootstrap everything
    from composition_root import bootstrap_knowledge_management
    from application.services.metrics_collector import MetricsCollector
    from application.services.agent_tuner import AgentTuner
    from application.services.experiment_runner import ExperimentRunner
    from infrastructure.experiment_store import ExperimentStore
    from config.experiment_config import ExperimentSystemConfig

    kg_backend, event_bus = await bootstrap_knowledge_management()
    system_config = ExperimentSystemConfig.from_env()
    store = ExperimentStore(kg_backend)
    collector = MetricsCollector()
    tuner = AgentTuner()
    runner = ExperimentRunner(collector, tuner, store, system_config)

    job = ExperimentLoopJob(
        experiment_runner=runner,
        agent_tuner=tuner,
        cycle_interval_seconds=system_config.cycle_interval_seconds,
        max_experiments_per_cycle=system_config.max_experiments_per_cycle,
    )

    try:
        await job.start()
        while True:
            await asyncio.sleep(60)
            stats = job.get_statistics()
            logger.info(
                f"Loop stats: {stats['total_cycles']} cycles, "
                f"{stats['total_experiments']} experiments, "
                f"{stats['total_improvements']} improvements"
            )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await job.stop()


if __name__ == "__main__":
    asyncio.run(main())
