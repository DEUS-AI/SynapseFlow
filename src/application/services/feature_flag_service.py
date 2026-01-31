"""Feature Flag Service.

Provides feature flag management for gradual migration rollout.
Supports both database-backed flags and environment variable overrides.
"""

import os
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FeatureFlagConfig:
    """Feature flag configuration."""
    name: str
    default: bool
    description: str


# Migration feature flags
MIGRATION_FLAGS = {
    "use_postgres_sessions": FeatureFlagConfig(
        name="use_postgres_sessions",
        default=False,
        description="Store sessions in PostgreSQL instead of Neo4j"
    ),
    "use_postgres_feedback": FeatureFlagConfig(
        name="use_postgres_feedback",
        default=False,
        description="Store feedback in PostgreSQL instead of Neo4j"
    ),
    "use_postgres_documents": FeatureFlagConfig(
        name="use_postgres_documents",
        default=False,
        description="Store document metadata in PostgreSQL"
    ),
    "dual_write_sessions": FeatureFlagConfig(
        name="dual_write_sessions",
        default=False,
        description="Write sessions to both Neo4j and PostgreSQL"
    ),
    "dual_write_feedback": FeatureFlagConfig(
        name="dual_write_feedback",
        default=False,
        description="Write feedback to both Neo4j and PostgreSQL"
    ),
    "dual_write_documents": FeatureFlagConfig(
        name="dual_write_documents",
        default=False,
        description="Write document metadata to both Neo4j and PostgreSQL"
    ),
    "enable_query_analytics": FeatureFlagConfig(
        name="enable_query_analytics",
        default=True,
        description="Track query patterns and performance"
    ),
}


class FeatureFlagService:
    """Service for managing feature flags.

    Supports:
    - Database-backed flags (PostgreSQL)
    - Environment variable overrides (FEATURE_FLAG_<NAME>=true/false)
    - In-memory caching
    """

    def __init__(self, db_session=None):
        """Initialize the feature flag service.

        Args:
            db_session: Optional database session for DB-backed flags
        """
        self.db_session = db_session
        self._cache: Dict[str, bool] = {}
        self._loaded = False

    async def load_flags(self) -> None:
        """Load flags from database into cache."""
        if self.db_session is None:
            logger.warning("No database session, using defaults only")
            self._loaded = True
            return

        try:
            from infrastructure.database.repositories import FeatureFlagRepository
            repo = FeatureFlagRepository(self.db_session)
            self._cache = await repo.get_all_flags()
            self._loaded = True
            logger.info(f"Loaded {len(self._cache)} feature flags from database")
        except Exception as e:
            logger.error(f"Failed to load feature flags from database: {e}")
            self._loaded = True

    def is_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled.

        Priority:
        1. Environment variable override (FEATURE_FLAG_<NAME>)
        2. Cached database value
        3. Default value from config
        4. False if unknown

        Args:
            flag_name: Name of the feature flag

        Returns:
            True if enabled, False otherwise
        """
        # Check environment variable override first
        env_key = f"FEATURE_FLAG_{flag_name.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value.lower() in ("true", "1", "yes", "on")

        # Check cache
        if flag_name in self._cache:
            return self._cache[flag_name]

        # Check default config
        if flag_name in MIGRATION_FLAGS:
            return MIGRATION_FLAGS[flag_name].default

        # Unknown flag - default to disabled
        logger.warning(f"Unknown feature flag: {flag_name}")
        return False

    async def set_enabled(self, flag_name: str, enabled: bool) -> bool:
        """Enable or disable a feature flag.

        Args:
            flag_name: Name of the feature flag
            enabled: Whether to enable the flag

        Returns:
            True if successful
        """
        if self.db_session is None:
            # Update cache only
            self._cache[flag_name] = enabled
            return True

        try:
            from infrastructure.database.repositories import FeatureFlagRepository
            repo = FeatureFlagRepository(self.db_session)
            success = await repo.set_enabled(flag_name, enabled)

            if success:
                self._cache[flag_name] = enabled
                logger.info(f"Feature flag '{flag_name}' set to {enabled}")

            return success
        except Exception as e:
            logger.error(f"Failed to set feature flag: {e}")
            return False

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all feature flags with their status and metadata.

        Returns:
            Dictionary of flag name -> {enabled, description, source}
        """
        result = {}

        for name, config in MIGRATION_FLAGS.items():
            # Determine source
            env_key = f"FEATURE_FLAG_{name.upper()}"
            env_value = os.getenv(env_key)

            if env_value is not None:
                source = "environment"
                enabled = env_value.lower() in ("true", "1", "yes", "on")
            elif name in self._cache:
                source = "database"
                enabled = self._cache[name]
            else:
                source = "default"
                enabled = config.default

            result[name] = {
                "enabled": enabled,
                "description": config.description,
                "source": source,
            }

        return result

    def clear_cache(self) -> None:
        """Clear the flag cache."""
        self._cache.clear()
        self._loaded = False


# Global instance for convenience
_service: Optional[FeatureFlagService] = None


def get_feature_flag_service() -> FeatureFlagService:
    """Get the global feature flag service instance."""
    global _service
    if _service is None:
        _service = FeatureFlagService()
    return _service


def is_flag_enabled(flag_name: str) -> bool:
    """Quick check if a feature flag is enabled.

    Convenience function for common usage pattern.

    Args:
        flag_name: Name of the feature flag

    Returns:
        True if enabled
    """
    return get_feature_flag_service().is_enabled(flag_name)


# Specific flag helpers
def use_postgres_sessions() -> bool:
    """Check if sessions should use PostgreSQL."""
    return is_flag_enabled("use_postgres_sessions")


def use_postgres_feedback() -> bool:
    """Check if feedback should use PostgreSQL."""
    return is_flag_enabled("use_postgres_feedback")


def dual_write_enabled(data_type: str) -> bool:
    """Check if dual-write is enabled for a data type."""
    return is_flag_enabled(f"dual_write_{data_type}")
