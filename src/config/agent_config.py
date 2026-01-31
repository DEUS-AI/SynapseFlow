"""
Agent Infrastructure Configuration

Loads and validates configuration from config/agents.yaml.
Provides typed models and a builder for instantiating infrastructure components.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class DeploymentMode(str, Enum):
    """Deployment mode for agents."""
    LOCAL = "local"           # In-process, same FastAPI app
    DISTRIBUTED = "distributed"  # Isolated containers


class EventBusType(str, Enum):
    """Event bus implementation type."""
    MEMORY = "memory"
    RABBITMQ = "rabbitmq"


class ChannelType(str, Enum):
    """Communication channel implementation type."""
    MEMORY = "memory"
    A2A = "a2a"
    RABBITMQ = "rabbitmq"


class DiscoveryType(str, Enum):
    """Agent discovery implementation type."""
    LOCAL = "local"    # In-memory registry
    NEO4J = "neo4j"    # Neo4j-backed discovery


@dataclass
class RabbitMQConfig:
    """RabbitMQ connection configuration."""
    url: str = "amqp://guest:guest@localhost:5672/"
    exchange_name: str = "knowledge_events"
    queue_prefix: str = "kg_"
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class A2AConfig:
    """Agent-to-Agent HTTP communication configuration."""
    base_url: str = "http://localhost:8000"


@dataclass
class Neo4jDiscoveryConfig:
    """Neo4j discovery configuration."""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"


@dataclass
class EventBusConfig:
    """Event bus configuration."""
    type: EventBusType = EventBusType.MEMORY
    rabbitmq: RabbitMQConfig = field(default_factory=RabbitMQConfig)


@dataclass
class ChannelConfig:
    """Communication channel configuration."""
    type: ChannelType = ChannelType.MEMORY
    a2a: A2AConfig = field(default_factory=A2AConfig)
    rabbitmq: RabbitMQConfig = field(default_factory=RabbitMQConfig)


@dataclass
class DiscoveryConfig:
    """Agent discovery configuration."""
    type: DiscoveryType = DiscoveryType.LOCAL
    neo4j: Neo4jDiscoveryConfig = field(default_factory=Neo4jDiscoveryConfig)
    heartbeat_interval_seconds: int = 30
    stale_threshold_seconds: int = 300


@dataclass
class AgentConfig:
    """Individual agent configuration."""
    enabled: bool = True
    url: str = ""
    capabilities: List[str] = field(default_factory=list)


@dataclass
class AgentInfraConfig:
    """Complete agent infrastructure configuration."""
    deployment_mode: DeploymentMode = DeploymentMode.LOCAL
    event_bus: EventBusConfig = field(default_factory=EventBusConfig)
    communication_channel: ChannelConfig = field(default_factory=ChannelConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    agents: Dict[str, AgentConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfraConfig":
        """Create config from dictionary (parsed YAML)."""
        # Parse deployment mode
        deployment_mode = DeploymentMode(data.get("deployment_mode", "local"))

        # Parse event bus config
        eb_data = data.get("event_bus", {})
        event_bus = EventBusConfig(
            type=EventBusType(eb_data.get("type", "memory")),
            rabbitmq=RabbitMQConfig(**eb_data.get("rabbitmq", {})) if eb_data.get("rabbitmq") else RabbitMQConfig()
        )

        # Parse channel config
        ch_data = data.get("communication_channel", {})
        channel = ChannelConfig(
            type=ChannelType(ch_data.get("type", "memory")),
            a2a=A2AConfig(**ch_data.get("a2a", {})) if ch_data.get("a2a") else A2AConfig(),
            rabbitmq=RabbitMQConfig(**ch_data.get("rabbitmq", {})) if ch_data.get("rabbitmq") else RabbitMQConfig()
        )

        # Parse discovery config
        disc_data = data.get("discovery", {})
        discovery = DiscoveryConfig(
            type=DiscoveryType(disc_data.get("type", "local")),
            neo4j=Neo4jDiscoveryConfig(**disc_data.get("neo4j", {})) if disc_data.get("neo4j") else Neo4jDiscoveryConfig(),
            heartbeat_interval_seconds=disc_data.get("heartbeat_interval_seconds", 30),
            stale_threshold_seconds=disc_data.get("stale_threshold_seconds", 300)
        )

        # Parse agent configs
        agents_data = data.get("agents", {})
        agents = {
            name: AgentConfig(
                enabled=cfg.get("enabled", True),
                url=cfg.get("url", ""),
                capabilities=cfg.get("capabilities", [])
            )
            for name, cfg in agents_data.items()
        }

        return cls(
            deployment_mode=deployment_mode,
            event_bus=event_bus,
            communication_channel=channel,
            discovery=discovery,
            agents=agents
        )

    @classmethod
    def from_yaml(cls, path: Optional[str] = None) -> "AgentInfraConfig":
        """Load config from YAML file."""
        if path is None:
            # Default path relative to project root
            path = os.getenv("AGENT_CONFIG_PATH", "config/agents.yaml")

        config_path = Path(path)
        if not config_path.is_absolute():
            # Try relative to current working directory
            config_path = Path.cwd() / path

        if not config_path.exists():
            # Return default config if file doesn't exist
            return cls()

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_env(cls) -> "AgentInfraConfig":
        """
        Create config from environment variables.

        Environment variables override YAML config.
        Useful for container deployments.
        """
        # Start with YAML config
        config = cls.from_yaml()

        # Override with environment variables
        if os.getenv("DEPLOYMENT_MODE"):
            config.deployment_mode = DeploymentMode(os.getenv("DEPLOYMENT_MODE"))

        if os.getenv("EVENT_BUS_TYPE"):
            config.event_bus.type = EventBusType(os.getenv("EVENT_BUS_TYPE"))

        if os.getenv("RABBITMQ_URL"):
            config.event_bus.rabbitmq.url = os.getenv("RABBITMQ_URL")
            config.communication_channel.rabbitmq.url = os.getenv("RABBITMQ_URL")

        if os.getenv("CHANNEL_TYPE"):
            config.communication_channel.type = ChannelType(os.getenv("CHANNEL_TYPE"))

        if os.getenv("AGENT_URL"):
            config.communication_channel.a2a.base_url = os.getenv("AGENT_URL")

        if os.getenv("DISCOVERY_TYPE"):
            config.discovery.type = DiscoveryType(os.getenv("DISCOVERY_TYPE"))

        if os.getenv("NEO4J_URI"):
            config.discovery.neo4j.uri = os.getenv("NEO4J_URI")

        if os.getenv("NEO4J_USERNAME"):
            config.discovery.neo4j.username = os.getenv("NEO4J_USERNAME")

        if os.getenv("NEO4J_PASSWORD"):
            config.discovery.neo4j.password = os.getenv("NEO4J_PASSWORD")

        return config


# Global config instance (lazy loaded)
_config: Optional[AgentInfraConfig] = None


def get_agent_config() -> AgentInfraConfig:
    """Get the global agent configuration (lazy loaded)."""
    global _config
    if _config is None:
        _config = AgentInfraConfig.from_env()
    return _config


def reload_config(path: Optional[str] = None) -> AgentInfraConfig:
    """Reload configuration from file."""
    global _config
    _config = AgentInfraConfig.from_yaml(path)
    return _config
