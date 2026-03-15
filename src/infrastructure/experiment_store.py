"""Experiment Store — Neo4j-backed persistence for experiment results.

Stores experiment results, directives, and metric snapshots as nodes
in the Knowledge Graph. All nodes are tagged with layer: "APPLICATION"
following the DIKW pyramid convention.

Uses the same patterns as AgentDiscoveryService for Neo4j interaction.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.experiment import (
    AgentDirective,
    ExperimentResult,
    ExperimentStatus,
)
from domain.agent_metrics import AgentMetricSnapshot

logger = logging.getLogger(__name__)


class ExperimentStore:
    """Neo4j-backed storage for experiment results and directives."""

    def __init__(self, backend: Any):
        """Initialize with a KnowledgeGraphBackend.

        Args:
            backend: Any KnowledgeGraphBackend implementation (Neo4j, InMemory, etc.)
        """
        self.backend = backend
        self._initialized = False

    async def initialize(self) -> None:
        """Create indexes for efficient experiment queries."""
        if self._initialized:
            return

        indexes = [
            """
            CREATE INDEX idx_experiment_id IF NOT EXISTS
            FOR (n:Experiment) ON (n.experiment_id)
            """,
            """
            CREATE INDEX idx_experiment_agent IF NOT EXISTS
            FOR (n:Experiment) ON (n.agent_id)
            """,
            """
            CREATE INDEX idx_agent_directive IF NOT EXISTS
            FOR (n:AgentDirective) ON (n.agent_id)
            """,
        ]

        for idx_query in indexes:
            try:
                await self.backend.query_raw(idx_query, {})
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Failed to create index: {e}")

        self._initialized = True
        logger.info("ExperimentStore indexes initialized")

    async def save_experiment(self, result: ExperimentResult) -> bool:
        """Persist an experiment result to Neo4j.

        Creates an Experiment node and links it to the AgentService node.
        """
        await self.initialize()

        query = """
        MERGE (e:Experiment {experiment_id: $experiment_id})
        SET e += $properties,
            e.layer = 'APPLICATION',
            e.updated_at = datetime()
        WITH e
        OPTIONAL MATCH (a:AgentService {agent_id: $agent_id})
        FOREACH (_ IN CASE WHEN a IS NOT NULL THEN [1] ELSE [] END |
            MERGE (e)-[:EXPERIMENTED_ON]->(a)
        )
        RETURN e.experiment_id AS experiment_id
        """

        props = result.to_dict()
        # Neo4j doesn't handle nested dicts well in SET +=, flatten extra_metrics
        props.pop("extra_metrics", None)

        try:
            r = await self.backend.query_raw(query, {
                "experiment_id": result.experiment_id,
                "agent_id": result.agent_id,
                "properties": props,
            })
            return bool(r)
        except Exception as e:
            logger.error(f"Failed to save experiment {result.experiment_id}: {e}")
            return False

    async def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get a single experiment by ID."""
        query = """
        MATCH (e:Experiment {experiment_id: $experiment_id})
        RETURN e
        """
        try:
            result = await self.backend.query_raw(query, {"experiment_id": experiment_id})
            if result:
                return result[0].get("e", {})
            return None
        except Exception as e:
            logger.error(f"Failed to get experiment {experiment_id}: {e}")
            return None

    async def get_experiment_history(
        self, agent_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get experiment history for an agent, most recent first."""
        query = """
        MATCH (e:Experiment {agent_id: $agent_id})
        RETURN e
        ORDER BY e.completed_at DESC
        LIMIT $limit
        """
        try:
            result = await self.backend.query_raw(query, {
                "agent_id": agent_id,
                "limit": limit,
            })
            return [r.get("e", {}) for r in (result or [])]
        except Exception as e:
            logger.error(f"Failed to get history for {agent_id}: {e}")
            return []

    async def save_directive(self, directive: AgentDirective) -> bool:
        """Persist an agent directive."""
        await self.initialize()

        query = """
        MERGE (d:AgentDirective {agent_id: $agent_id})
        SET d += $properties,
            d.layer = 'APPLICATION',
            d.updated_at = datetime()
        RETURN d.agent_id AS agent_id
        """

        try:
            r = await self.backend.query_raw(query, {
                "agent_id": directive.agent_id,
                "properties": {
                    "agent_id": directive.agent_id,
                    "primary_metric": directive.primary_metric,
                    "secondary_metrics": directive.secondary_metrics,
                    "experiment_budget_seconds": directive.experiment_budget_seconds,
                    "max_experiments_per_cycle": directive.max_experiments_per_cycle,
                    "exploration_strategy": directive.exploration_strategy,
                    "enabled": directive.enabled,
                },
            })
            return bool(r)
        except Exception as e:
            logger.error(f"Failed to save directive for {directive.agent_id}: {e}")
            return False

    async def get_directive(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get the current directive for an agent."""
        query = """
        MATCH (d:AgentDirective {agent_id: $agent_id})
        RETURN d
        """
        try:
            result = await self.backend.query_raw(query, {"agent_id": agent_id})
            if result:
                return result[0].get("d", {})
            return None
        except Exception as e:
            logger.error(f"Failed to get directive for {agent_id}: {e}")
            return None

    async def save_metric_snapshot(self, snapshot: AgentMetricSnapshot) -> bool:
        """Save a metric snapshot."""
        query = """
        CREATE (m:MetricSnapshot {
            agent_id: $agent_id,
            metric_name: $metric_name,
            value: $value,
            timestamp: datetime($timestamp),
            layer: 'APPLICATION'
        })
        WITH m
        OPTIONAL MATCH (a:AgentService {agent_id: $agent_id})
        FOREACH (_ IN CASE WHEN a IS NOT NULL THEN [1] ELSE [] END |
            MERGE (a)-[:MEASURED]->(m)
        )
        RETURN m.metric_name AS metric_name
        """
        try:
            r = await self.backend.query_raw(query, {
                "agent_id": snapshot.agent_id,
                "metric_name": snapshot.metric_name,
                "value": snapshot.value,
                "timestamp": snapshot.timestamp.isoformat(),
            })
            return bool(r)
        except Exception as e:
            logger.error(f"Failed to save metric snapshot: {e}")
            return False

    async def get_experiment_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all experiments."""
        query = """
        MATCH (e:Experiment)
        RETURN
            count(e) AS total,
            sum(CASE WHEN e.kept = true THEN 1 ELSE 0 END) AS improvements,
            sum(CASE WHEN e.status = 'reverted' THEN 1 ELSE 0 END) AS reverts,
            sum(CASE WHEN e.status = 'failed' THEN 1 ELSE 0 END) AS failures,
            collect(DISTINCT e.agent_id) AS agents
        """
        try:
            result = await self.backend.query_raw(query, {})
            if result:
                row = result[0]
                return {
                    "total_experiments": row.get("total", 0),
                    "improvements": row.get("improvements", 0),
                    "reverts": row.get("reverts", 0),
                    "failures": row.get("failures", 0),
                    "agents": row.get("agents", []),
                }
            return {"total_experiments": 0, "improvements": 0, "reverts": 0, "failures": 0, "agents": []}
        except Exception as e:
            logger.error(f"Failed to get experiment stats: {e}")
            return {"total_experiments": 0, "improvements": 0, "reverts": 0, "failures": 0, "agents": []}
