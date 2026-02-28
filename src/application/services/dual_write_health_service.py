"""Dual-Write Health Service.

Compares Neo4j and PostgreSQL record counts to assess migration sync health.
"""

import logging
from typing import Any, Dict, Optional, Callable

from application.services.feature_flag_service import (
    dual_write_enabled,
    is_flag_enabled,
)

logger = logging.getLogger(__name__)


def _compute_sync_status(neo4j_count: int, pg_count: int) -> str:
    """Compute sync status from Neo4j vs PostgreSQL counts.

    Since PostgreSQL is the migration target, only flag issues when
    Neo4j has data that PG is missing (neo4j > pg). PG having more
    data than Neo4j is expected and healthy.
    """
    if neo4j_count == 0:
        return "synced"
    missing_in_pg = neo4j_count - pg_count
    if missing_in_pg <= 0:
        return "synced"
    missing_pct = missing_in_pg / neo4j_count
    if missing_pct <= 0.05:
        return "synced"
    elif missing_pct <= 0.20:
        return "minor_drift"
    return "out_of_sync"


class DualWriteHealthService:
    """Service for checking dual-write migration health."""

    def __init__(
        self,
        kg_backend=None,
        db_session_factory: Optional[Callable] = None,
    ):
        self.kg_backend = kg_backend
        self._db_session = db_session_factory

    async def get_health(self) -> Dict[str, Any]:
        """Get dual-write health metrics comparing Neo4j and PostgreSQL counts."""
        health: Dict[str, Any] = {
            "status": "healthy",
            "data_types": {},
            "sync_issues": [],
            "recommendations": [],
        }

        health["data_types"]["sessions"] = await self._check_sessions()
        health["data_types"]["feedback"] = await self._check_feedback()
        health["data_types"]["documents"] = await self._check_documents()

        # Collect sync issues
        for name, dt in health["data_types"].items():
            if dt["sync_status"] == "out_of_sync":
                missing = dt["neo4j_count"] - dt["postgres_count"]
                health["sync_issues"].append(
                    f"{name.capitalize()}: {missing} Neo4j records missing from PostgreSQL"
                )
                health["status"] = "warning"

        # Generate recommendations
        if not any(dt["dual_write_enabled"] for dt in health["data_types"].values()):
            health["recommendations"].append(
                "Enable dual-write for at least one data type to begin migration"
            )
        elif health["sync_issues"]:
            health["recommendations"].append(
                "Run sync_data_to_postgres.py to reconcile differences"
            )
        elif all(
            dt["sync_status"] == "synced"
            for dt in health["data_types"].values()
            if dt["dual_write_enabled"]
        ):
            health["recommendations"].append(
                "All enabled dual-writes are in sync - consider enabling use_postgres flags"
            )

        return health

    async def _check_sessions(self) -> Dict[str, Any]:
        result = {
            "dual_write_enabled": dual_write_enabled("sessions"),
            "use_postgres": is_flag_enabled("use_postgres_sessions"),
            "neo4j_count": 0,
            "postgres_count": 0,
            "neo4j_message_count": 0,
            "postgres_message_count": 0,
            "sync_status": "unknown",
        }

        if self.kg_backend:
            try:
                query = "MATCH (s:ConversationSession) RETURN count(s) as count"
                data = await self.kg_backend.query_raw(query, {})
                if data:
                    result["neo4j_count"] = data[0].get("count", 0)
                msg_query = "MATCH (m:Message) RETURN count(m) as count"
                msg_data = await self.kg_backend.query_raw(msg_query, {})
                if msg_data:
                    result["neo4j_message_count"] = msg_data[0].get("count", 0)
            except Exception as e:
                logger.warning(f"Failed to get Neo4j session/message count: {e}")

        if self._db_session:
            try:
                from infrastructure.database.repositories import SessionRepository, MessageRepository

                async with self._db_session() as session:
                    result["postgres_count"] = await SessionRepository(session).count()
                    result["postgres_message_count"] = await MessageRepository(session).count()
            except Exception as e:
                logger.warning(f"Failed to get PostgreSQL session/message count: {e}")

        if result["dual_write_enabled"]:
            result["sync_status"] = _compute_sync_status(
                result["neo4j_count"], result["postgres_count"]
            )
        else:
            result["sync_status"] = "disabled"

        return result

    async def _check_feedback(self) -> Dict[str, Any]:
        result = {
            "dual_write_enabled": dual_write_enabled("feedback"),
            "use_postgres": is_flag_enabled("use_postgres_feedback"),
            "neo4j_count": 0,
            "postgres_count": 0,
            "sync_status": "unknown",
        }

        if self.kg_backend:
            try:
                query = "MATCH (f:UserFeedback) RETURN count(f) as count"
                data = await self.kg_backend.query_raw(query, {})
                if data:
                    result["neo4j_count"] = data[0].get("count", 0)
            except Exception as e:
                logger.warning(f"Failed to get Neo4j feedback count: {e}")

        if self._db_session:
            try:
                from infrastructure.database.repositories import FeedbackRepository

                async with self._db_session() as session:
                    result["postgres_count"] = await FeedbackRepository(session).count()
            except Exception as e:
                logger.warning(f"Failed to get PostgreSQL feedback count: {e}")

        if result["dual_write_enabled"]:
            result["sync_status"] = _compute_sync_status(
                result["neo4j_count"], result["postgres_count"]
            )
        else:
            result["sync_status"] = "disabled"

        return result

    async def _check_documents(self) -> Dict[str, Any]:
        result = {
            "dual_write_enabled": dual_write_enabled("documents"),
            "use_postgres": is_flag_enabled("use_postgres_documents"),
            "neo4j_count": 0,
            "postgres_count": 0,
            "sync_status": "unknown",
        }

        if self.kg_backend:
            try:
                query = "MATCH (d:Document) RETURN count(d) as count"
                data = await self.kg_backend.query_raw(query, {})
                if data:
                    result["neo4j_count"] = data[0].get("count", 0)
            except Exception as e:
                logger.warning(f"Failed to get Neo4j document count: {e}")

        if self._db_session:
            try:
                from infrastructure.database.repositories import DocumentRepository

                async with self._db_session() as session:
                    result["postgres_count"] = await DocumentRepository(session).count()
            except Exception as e:
                logger.warning(f"Failed to get PostgreSQL document count: {e}")

        if result["dual_write_enabled"]:
            result["sync_status"] = _compute_sync_status(
                result["neo4j_count"], result["postgres_count"]
            )
        else:
            result["sync_status"] = "disabled"

        return result
