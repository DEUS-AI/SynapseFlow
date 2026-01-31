"""Database Configuration.

Handles PostgreSQL connection settings and URL construction.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration."""

    host: str = "localhost"
    port: int = 5432
    database: str = "synapseflow"
    username: str = "synapseflow"
    password: str = "synapseflow_dev"

    # Connection pool settings
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800  # 30 minutes

    # Echo SQL queries (for debugging)
    echo: bool = False

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        return cls(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "synapseflow"),
            username=os.getenv("POSTGRES_USER", "synapseflow"),
            password=os.getenv("POSTGRES_PASSWORD", "synapseflow_dev"),
            pool_size=int(os.getenv("POSTGRES_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("POSTGRES_MAX_OVERFLOW", "10")),
            echo=os.getenv("POSTGRES_ECHO", "false").lower() == "true",
        )

    def get_url(self, async_driver: bool = True) -> str:
        """Get database URL.

        Args:
            async_driver: Use asyncpg driver (True) or psycopg2 (False)

        Returns:
            Database connection URL
        """
        driver = "postgresql+asyncpg" if async_driver else "postgresql+psycopg2"
        return f"{driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


def get_database_url(async_driver: bool = True) -> str:
    """Get database URL from environment.

    Convenience function for quick URL access.

    Args:
        async_driver: Use asyncpg driver

    Returns:
        Database connection URL
    """
    config = DatabaseConfig.from_env()
    return config.get_url(async_driver)


# Default configuration instance
default_config = DatabaseConfig.from_env()
