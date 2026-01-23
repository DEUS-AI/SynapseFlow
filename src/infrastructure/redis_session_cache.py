"""
Redis session cache for temporary patient session state.

Provides 24-hour TTL for active conversation sessions with automatic expiration.
"""

import redis.asyncio as aioredis
from typing import Optional, Dict, Any
import json
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class RedisSessionCache:
    """Manages temporary session state with 24h TTL."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6380,  # Using 6380 to avoid conflict with FalkorDB
        db: int = 0,
        ttl_seconds: int = 86400  # 24 hours
    ):
        """
        Initialize Redis session cache.

        Args:
            host: Redis server host
            port: Redis server port (default: 6380 to avoid FalkorDB conflict)
            db: Redis database number
            ttl_seconds: Time-to-live for sessions in seconds (default: 24h)
        """
        self.redis = aioredis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
        self.ttl = timedelta(seconds=ttl_seconds)
        logger.info(f"Redis session cache initialized: {host}:{port}, TTL={ttl_seconds}s")

    async def set_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Store session data with TTL.

        Args:
            session_id: Unique session identifier
            data: Session data dictionary
            ttl: Optional custom TTL (defaults to instance TTL)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            key = f"session:{session_id}"
            value = json.dumps(data)
            result = await self.redis.setex(
                key,
                ttl or self.ttl,
                value
            )
            logger.debug(f"Session stored: {session_id}")
            return result
        except Exception as e:
            logger.error(f"Error storing session {session_id}: {e}")
            return False

    async def get_session(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data.

        Args:
            session_id: Unique session identifier

        Returns:
            Optional[Dict]: Session data if found, None otherwise
        """
        try:
            key = f"session:{session_id}"
            value = await self.redis.get(key)
            if value:
                logger.debug(f"Session retrieved: {session_id}")
                return json.loads(value)
            logger.debug(f"Session not found: {session_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None

    async def update_session_ttl(
        self,
        session_id: str
    ) -> bool:
        """
        Refresh TTL on session access.

        Args:
            session_id: Unique session identifier

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            key = f"session:{session_id}"
            result = await self.redis.expire(key, self.ttl)
            logger.debug(f"Session TTL refreshed: {session_id}")
            return result
        except Exception as e:
            logger.error(f"Error refreshing TTL for session {session_id}: {e}")
            return False

    async def delete_session(
        self,
        session_id: str
    ) -> bool:
        """
        Delete session data.

        Args:
            session_id: Unique session identifier

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            key = f"session:{session_id}"
            result = await self.redis.delete(key) > 0
            logger.debug(f"Session deleted: {session_id}")
            return result
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    async def list_patient_sessions(
        self,
        patient_id: str
    ) -> list[str]:
        """
        Get all active sessions for a patient.

        Args:
            patient_id: Patient identifier

        Returns:
            list[str]: List of active session IDs for the patient
        """
        try:
            pattern = f"session:*"
            sessions = []

            async for key in self.redis.scan_iter(match=pattern):
                session_data = await self.redis.get(key)
                if session_data:
                    data = json.loads(session_data)
                    if data.get("patient_id") == patient_id:
                        # Extract session ID from key (remove "session:" prefix)
                        session_id = key.split(":", 1)[1]
                        sessions.append(session_id)

            logger.debug(f"Found {len(sessions)} sessions for patient {patient_id}")
            return sessions
        except Exception as e:
            logger.error(f"Error listing sessions for patient {patient_id}: {e}")
            return []

    async def close(self) -> None:
        """Close Redis connection."""
        await self.redis.aclose()
        logger.info("Redis session cache closed")
