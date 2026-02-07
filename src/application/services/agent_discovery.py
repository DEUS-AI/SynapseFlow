"""Agent Discovery Service.

Provides KG-based service registration and discovery for agents.
Uses Neo4j as the single source of truth for agent metadata.

Key Features:
- Standardized AgentService node schema
- Capability-based discovery
- Health status tracking
- Heartbeat mechanism
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Status of an agent service."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    STARTING = "starting"


class AgentTier(str, Enum):
    """Service tier for agents."""
    CORE = "core"  # Essential system agents
    OPTIONAL = "optional"  # Optional/plugin agents


@dataclass
class AgentServiceInfo:
    """
    Standardized agent service information.

    This is the canonical schema for AgentService nodes in Neo4j.
    """
    agent_id: str
    name: str
    description: str
    version: str
    url: str
    capabilities: List[str]
    status: AgentStatus = AgentStatus.ACTIVE
    tier: AgentTier = AgentTier.OPTIONAL
    health_check_url: Optional[str] = None
    heartbeat_interval_seconds: int = 60
    registered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_neo4j_properties(self) -> Dict[str, Any]:
        """Convert to Neo4j node properties."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "url": self.url,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "tier": self.tier.value,
            "health_check_url": self.health_check_url,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "layer": "APPLICATION",  # Agents belong to APPLICATION layer
        }

    @classmethod
    def from_neo4j_record(cls, record: Dict[str, Any]) -> "AgentServiceInfo":
        """Create from Neo4j query result."""
        def parse_datetime(val):
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            return None

        return cls(
            agent_id=record.get("agent_id", ""),
            name=record.get("name", ""),
            description=record.get("description", ""),
            version=record.get("version", "1.0.0"),
            url=record.get("url", ""),
            capabilities=record.get("capabilities", []),
            status=AgentStatus(record.get("status", "active")),
            tier=AgentTier(record.get("tier", "optional")),
            health_check_url=record.get("health_check_url"),
            heartbeat_interval_seconds=record.get("heartbeat_interval_seconds", 60),
            registered_at=parse_datetime(record.get("registered_at")),
            updated_at=parse_datetime(record.get("updated_at")),
            last_heartbeat=parse_datetime(record.get("last_heartbeat")),
            metadata=record.get("metadata", {}),
        )


@dataclass
class DiscoveryResult:
    """Result of an agent discovery query."""
    agents: List[AgentServiceInfo]
    query_capability: str
    total_found: int
    active_count: int


class AgentDiscoveryService:
    """
    Service for agent registration and discovery via the Knowledge Graph.

    This service provides:
    - Agent registration (register_agent)
    - Capability-based discovery (discover_by_capability)
    - Health status management (update_heartbeat, mark_inactive)
    - Agent listing (list_all_agents)

    Uses Neo4j as the backend with standardized AgentService nodes.
    """

    def __init__(
        self,
        backend: Any,  # KnowledgeGraphBackend
        stale_threshold_seconds: int = 300,  # 5 minutes
    ):
        """
        Initialize the discovery service.

        Args:
            backend: Neo4j backend for KG operations
            stale_threshold_seconds: Time after which an agent without
                heartbeat is considered stale/inactive
        """
        self.backend = backend
        self.stale_threshold = timedelta(seconds=stale_threshold_seconds)
        self._initialized = False

    async def initialize(self) -> None:
        """Create indexes for efficient agent queries."""
        if self._initialized:
            return

        try:
            # Create indexes for agent discovery
            indexes = [
                """
                CREATE INDEX idx_agent_service_id IF NOT EXISTS
                FOR (n:AgentService) ON (n.agent_id)
                """,
                """
                CREATE INDEX idx_agent_service_status IF NOT EXISTS
                FOR (n:AgentService) ON (n.status)
                """,
                """
                CREATE INDEX idx_agent_service_capabilities IF NOT EXISTS
                FOR (n:AgentService) ON (n.capabilities)
                """,
            ]

            for idx_query in indexes:
                try:
                    await self.backend.query_raw(idx_query, {})
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to create index: {e}")

            self._initialized = True
            logger.info("AgentDiscoveryService indexes initialized")

        except Exception as e:
            logger.error(f"Failed to initialize discovery service: {e}")
            raise

    async def register_agent(self, agent_info: AgentServiceInfo) -> bool:
        """
        Register an agent in the Knowledge Graph.

        Creates or updates an AgentService node with the agent's metadata.

        Args:
            agent_info: Agent service information

        Returns:
            True if registration succeeded
        """
        await self.initialize()

        now = datetime.now()
        agent_info.registered_at = agent_info.registered_at or now
        agent_info.updated_at = now
        agent_info.last_heartbeat = now

        props = agent_info.to_neo4j_properties()

        query = """
        MERGE (a:AgentService {agent_id: $agent_id})
        SET a += $properties,
            a.registered_at = COALESCE(a.registered_at, datetime($registered_at)),
            a.updated_at = datetime($updated_at),
            a.last_heartbeat = datetime($last_heartbeat)
        RETURN a.agent_id as agent_id
        """

        try:
            result = await self.backend.query_raw(query, {
                "agent_id": agent_info.agent_id,
                "properties": props,
                "registered_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "last_heartbeat": now.isoformat(),
            })

            if result:
                logger.info(f"Registered agent: {agent_info.agent_id} with capabilities: {agent_info.capabilities}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to register agent {agent_info.agent_id}: {e}")
            return False

    async def discover_by_capability(
        self,
        capability: str,
        status_filter: Optional[AgentStatus] = AgentStatus.ACTIVE,
        limit: int = 10,
    ) -> DiscoveryResult:
        """
        Discover agents by capability.

        Queries the KG for AgentService nodes that have the requested
        capability in their capabilities list.

        Args:
            capability: The capability to search for
            status_filter: Optional status filter (default: ACTIVE only)
            limit: Maximum number of agents to return

        Returns:
            DiscoveryResult with matching agents
        """
        await self.initialize()

        # Build query based on filters
        if status_filter:
            query = """
            MATCH (a:AgentService)
            WHERE $capability IN a.capabilities
              AND a.status = $status
            RETURN a
            ORDER BY a.last_heartbeat DESC
            LIMIT $limit
            """
            params = {
                "capability": capability,
                "status": status_filter.value,
                "limit": limit,
            }
        else:
            query = """
            MATCH (a:AgentService)
            WHERE $capability IN a.capabilities
            RETURN a
            ORDER BY a.last_heartbeat DESC
            LIMIT $limit
            """
            params = {
                "capability": capability,
                "limit": limit,
            }

        try:
            result = await self.backend.query_raw(query, params)

            agents = []
            active_count = 0

            for record in result or []:
                node_data = record.get("a", {})
                if node_data:
                    agent = AgentServiceInfo.from_neo4j_record(node_data)
                    agents.append(agent)
                    if agent.status == AgentStatus.ACTIVE:
                        active_count += 1

            return DiscoveryResult(
                agents=agents,
                query_capability=capability,
                total_found=len(agents),
                active_count=active_count,
            )

        except Exception as e:
            logger.error(f"Discovery query failed for capability '{capability}': {e}")
            return DiscoveryResult(
                agents=[],
                query_capability=capability,
                total_found=0,
                active_count=0,
            )

    async def discover_agent(
        self,
        capability: str,
    ) -> Optional[str]:
        """
        Discover a single agent by capability and return its URL.

        This is a convenience method that returns just the URL of the
        first active agent with the requested capability.

        Args:
            capability: The capability to search for

        Returns:
            Agent URL if found, None otherwise
        """
        result = await self.discover_by_capability(capability, limit=1)

        if result.agents:
            agent = result.agents[0]
            logger.info(f"Discovered agent '{agent.name}' at {agent.url} for capability '{capability}'")
            return agent.url

        logger.warning(f"No agent found for capability: {capability}")
        return None

    async def list_all_agents(
        self,
        status_filter: Optional[AgentStatus] = None,
        tier_filter: Optional[AgentTier] = None,
    ) -> List[AgentServiceInfo]:
        """
        List all registered agents.

        Args:
            status_filter: Optional filter by status
            tier_filter: Optional filter by tier

        Returns:
            List of all matching agents
        """
        await self.initialize()

        conditions = []
        params = {}

        if status_filter:
            conditions.append("a.status = $status")
            params["status"] = status_filter.value

        if tier_filter:
            conditions.append("a.tier = $tier")
            params["tier"] = tier_filter.value

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
        MATCH (a:AgentService)
        {where_clause}
        RETURN a
        ORDER BY a.tier, a.name
        """

        try:
            result = await self.backend.query_raw(query, params)

            agents = []
            for record in result or []:
                node_data = record.get("a", {})
                if node_data:
                    agents.append(AgentServiceInfo.from_neo4j_record(node_data))

            return agents

        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []

    async def update_heartbeat(self, agent_id: str) -> bool:
        """
        Update agent heartbeat timestamp.

        Should be called periodically by agents to indicate they are alive.

        Args:
            agent_id: The agent's ID

        Returns:
            True if heartbeat was updated
        """
        query = """
        MATCH (a:AgentService {agent_id: $agent_id})
        SET a.last_heartbeat = datetime(),
            a.status = 'active'
        RETURN a.agent_id as agent_id
        """

        try:
            result = await self.backend.query_raw(query, {"agent_id": agent_id})
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to update heartbeat for {agent_id}: {e}")
            return False

    async def mark_inactive(self, agent_id: str) -> bool:
        """
        Mark an agent as inactive.

        Used when an agent is shutting down gracefully.

        Args:
            agent_id: The agent's ID

        Returns:
            True if status was updated
        """
        query = """
        MATCH (a:AgentService {agent_id: $agent_id})
        SET a.status = 'inactive',
            a.updated_at = datetime()
        RETURN a.agent_id as agent_id
        """

        try:
            result = await self.backend.query_raw(query, {"agent_id": agent_id})
            if result:
                logger.info(f"Agent {agent_id} marked as inactive")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to mark agent {agent_id} as inactive: {e}")
            return False

    async def deregister_agent(self, agent_id: str) -> bool:
        """
        Remove an agent from the registry.

        Args:
            agent_id: The agent's ID

        Returns:
            True if agent was removed
        """
        query = """
        MATCH (a:AgentService {agent_id: $agent_id})
        DELETE a
        RETURN count(*) as deleted
        """

        try:
            result = await self.backend.query_raw(query, {"agent_id": agent_id})
            if result and result[0].get("deleted", 0) > 0:
                logger.info(f"Deregistered agent: {agent_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to deregister agent {agent_id}: {e}")
            return False

    async def scan_stale_agents(self) -> List[str]:
        """
        Find agents with stale heartbeats and mark them as degraded.

        Returns:
            List of agent IDs that were marked as degraded
        """
        threshold_time = datetime.now() - self.stale_threshold

        query = """
        MATCH (a:AgentService)
        WHERE a.status = 'active'
          AND a.last_heartbeat < datetime($threshold)
        SET a.status = 'degraded',
            a.updated_at = datetime()
        RETURN a.agent_id as agent_id
        """

        try:
            result = await self.backend.query_raw(query, {
                "threshold": threshold_time.isoformat()
            })

            stale_ids = [r.get("agent_id") for r in (result or []) if r.get("agent_id")]

            if stale_ids:
                logger.warning(f"Marked {len(stale_ids)} agents as degraded: {stale_ids}")

            return stale_ids

        except Exception as e:
            logger.error(f"Failed to scan for stale agents: {e}")
            return []

    async def get_agent_by_id(self, agent_id: str) -> Optional[AgentServiceInfo]:
        """
        Get agent information by ID.

        Args:
            agent_id: The agent's ID

        Returns:
            AgentServiceInfo if found, None otherwise
        """
        query = """
        MATCH (a:AgentService {agent_id: $agent_id})
        RETURN a
        """

        try:
            result = await self.backend.query_raw(query, {"agent_id": agent_id})
            if result:
                node_data = result[0].get("a", {})
                if node_data:
                    return AgentServiceInfo.from_neo4j_record(node_data)
            return None
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            return None

    async def get_capabilities_summary(self) -> Dict[str, List[str]]:
        """
        Get a summary of all capabilities and which agents provide them.

        Returns:
            Dict mapping capability -> list of agent IDs
        """
        query = """
        MATCH (a:AgentService)
        WHERE a.status = 'active'
        UNWIND a.capabilities as cap
        RETURN cap as capability, collect(a.agent_id) as agents
        ORDER BY cap
        """

        try:
            result = await self.backend.query_raw(query, {})

            summary = {}
            for record in result or []:
                cap = record.get("capability")
                agents = record.get("agents", [])
                if cap:
                    summary[cap] = agents

            return summary

        except Exception as e:
            logger.error(f"Failed to get capabilities summary: {e}")
            return {}
