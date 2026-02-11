#!/usr/bin/env python3
"""Data Sync Utility for PostgreSQL Migration.

Syncs existing data from Neo4j to PostgreSQL for migration.
Supports incremental sync and full sync modes.

Usage:
    python scripts/sync_data_to_postgres.py --mode full
    python scripts/sync_data_to_postgres.py --mode incremental
    python scripts/sync_data_to_postgres.py --verify
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DataSyncUtility:
    """Utility for syncing data between Neo4j and PostgreSQL."""

    def __init__(self, neo4j_backend, pg_session):
        """Initialize sync utility.

        Args:
            neo4j_backend: Neo4j backend instance
            pg_session: PostgreSQL async session
        """
        self.neo4j = neo4j_backend
        self.pg_session = pg_session
        self.stats = {
            "sessions_synced": 0,
            "messages_synced": 0,
            "sessions_skipped": 0,
            "messages_skipped": 0,
            "errors": []
        }

    async def sync_sessions(self, full_sync: bool = False) -> Dict[str, Any]:
        """Sync sessions from Neo4j to PostgreSQL.

        Args:
            full_sync: If True, sync all sessions. Otherwise, only sync new ones.

        Returns:
            Sync statistics
        """
        from infrastructure.database.repositories import SessionRepository
        from infrastructure.database.models import Session as PgSession

        logger.info(f"Starting session sync (mode: {'full' if full_sync else 'incremental'})")

        session_repo = SessionRepository(self.pg_session)

        # Query all sessions from Neo4j
        # Note: Sessions are stored as ConversationSession nodes linked from Patient nodes
        query = """
        MATCH (p:Patient)-[:HAS_SESSION]->(s:ConversationSession)
        OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
        WITH s, p.id as patient_id, count(m) as msg_count
        RETURN
            s.id as session_id,
            patient_id,
            s.title as title,
            s.status as status,
            s.started_at as created_at,
            s.updated_at as updated_at,
            s.last_activity as last_activity,
            msg_count as message_count,
            s.device_type as device_type
        ORDER BY s.started_at ASC
        """

        result = await self.neo4j.query_raw(query, {})

        for record in result or []:
            try:
                session_id = record.get("session_id", "")

                # Extract UUID from session ID
                if session_id.startswith("session:"):
                    uuid_str = session_id[8:]
                else:
                    uuid_str = session_id

                try:
                    session_uuid = UUID(uuid_str)
                except ValueError:
                    logger.warning(f"Invalid session UUID: {session_id}")
                    self.stats["sessions_skipped"] += 1
                    continue

                # Check if session already exists in PostgreSQL
                if not full_sync:
                    existing = await session_repo.get_by_id(session_uuid)
                    if existing:
                        self.stats["sessions_skipped"] += 1
                        continue

                # Create session in PostgreSQL
                pg_session = PgSession(
                    id=session_uuid,
                    patient_id=record.get("patient_id", ""),
                    title=record.get("title", "New Conversation"),
                    status=record.get("status", "active"),
                    message_count=record.get("message_count", 0),
                    metadata={
                        "device": record.get("device_type", "web"),
                        "neo4j_id": session_id,
                        "synced_at": datetime.now().isoformat()
                    }
                )

                # Handle timestamps
                if record.get("created_at"):
                    if isinstance(record["created_at"], str):
                        pg_session.created_at = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
                    else:
                        pg_session.created_at = record["created_at"]

                await session_repo.create(pg_session)
                self.stats["sessions_synced"] += 1

                if self.stats["sessions_synced"] % 100 == 0:
                    logger.info(f"Synced {self.stats['sessions_synced']} sessions...")

            except Exception as e:
                logger.error(f"Error syncing session {record.get('session_id')}: {e}")
                self.stats["errors"].append(f"Session {record.get('session_id')}: {e}")

        logger.info(f"Session sync complete: {self.stats['sessions_synced']} synced, "
                    f"{self.stats['sessions_skipped']} skipped")

        return self.stats

    async def sync_messages(self, full_sync: bool = False) -> Dict[str, Any]:
        """Sync messages from Neo4j to PostgreSQL.

        Args:
            full_sync: If True, sync all messages. Otherwise, only sync new ones.

        Returns:
            Sync statistics
        """
        from infrastructure.database.repositories import MessageRepository, SessionRepository
        from infrastructure.database.models import Message as PgMessage

        logger.info(f"Starting message sync (mode: {'full' if full_sync else 'incremental'})")

        message_repo = MessageRepository(self.pg_session)
        session_repo = SessionRepository(self.pg_session)

        # Query all messages from Neo4j
        # Note: Messages are linked from ConversationSession nodes
        query = """
        MATCH (p:Patient)-[:HAS_SESSION]->(s:ConversationSession)-[:HAS_MESSAGE]->(m:Message)
        RETURN
            m.id as message_id,
            s.id as session_id,
            p.id as patient_id,
            m.role as role,
            m.content as content,
            m.timestamp as created_at,
            m.response_id as response_id
        ORDER BY m.timestamp ASC
        """

        result = await self.neo4j.query_raw(query, {})

        for record in result or []:
            try:
                session_id = record.get("session_id", "")

                # Extract UUID from session ID
                if session_id.startswith("session:"):
                    uuid_str = session_id[8:]
                else:
                    uuid_str = session_id

                try:
                    session_uuid = UUID(uuid_str)
                except ValueError:
                    logger.warning(f"Invalid session UUID for message: {session_id}")
                    self.stats["messages_skipped"] += 1
                    continue

                # Check if session exists in PostgreSQL
                existing_session = await session_repo.get_by_id(session_uuid)
                if not existing_session:
                    logger.warning(f"Session {session_uuid} not found in PostgreSQL, skipping message")
                    self.stats["messages_skipped"] += 1
                    continue

                # Create message in PostgreSQL
                pg_message = PgMessage(
                    session_id=session_uuid,
                    patient_id=record.get("patient_id", ""),
                    role=record.get("role", "user"),
                    content=record.get("content", ""),
                    response_id=record.get("response_id"),
                    metadata={"synced_at": datetime.now().isoformat()}
                )

                # Handle timestamps
                if record.get("created_at"):
                    if isinstance(record["created_at"], str):
                        pg_message.created_at = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
                    else:
                        pg_message.created_at = record["created_at"]

                await message_repo.create(pg_message)
                self.stats["messages_synced"] += 1

                if self.stats["messages_synced"] % 500 == 0:
                    logger.info(f"Synced {self.stats['messages_synced']} messages...")

            except Exception as e:
                logger.error(f"Error syncing message: {e}")
                self.stats["errors"].append(f"Message: {e}")

        logger.info(f"Message sync complete: {self.stats['messages_synced']} synced, "
                    f"{self.stats['messages_skipped']} skipped")

        return self.stats

    async def verify_sync(self) -> Dict[str, Any]:
        """Verify data consistency between Neo4j and PostgreSQL.

        Returns:
            Verification results
        """
        from infrastructure.database.repositories import SessionRepository, MessageRepository

        logger.info("Verifying data consistency...")

        session_repo = SessionRepository(self.pg_session)
        message_repo = MessageRepository(self.pg_session)

        # Count sessions in Neo4j
        neo4j_sessions_query = "MATCH (s:ConversationSession) RETURN count(s) as count"
        neo4j_result = await self.neo4j.query_raw(neo4j_sessions_query, {})
        neo4j_sessions = neo4j_result[0]["count"] if neo4j_result else 0

        # Count sessions in PostgreSQL
        pg_sessions = await session_repo.count()

        # Count messages in Neo4j
        neo4j_messages_query = "MATCH (m:Message) RETURN count(m) as count"
        neo4j_result = await self.neo4j.query_raw(neo4j_messages_query, {})
        neo4j_messages = neo4j_result[0]["count"] if neo4j_result else 0

        # Count messages in PostgreSQL
        pg_messages = await message_repo.count()

        results = {
            "neo4j": {
                "sessions": neo4j_sessions,
                "messages": neo4j_messages
            },
            "postgresql": {
                "sessions": pg_sessions,
                "messages": pg_messages
            },
            "sync_status": {
                "sessions_synced": pg_sessions >= neo4j_sessions,
                "messages_synced": pg_messages >= neo4j_messages,
                "sessions_diff": neo4j_sessions - pg_sessions,
                "messages_diff": neo4j_messages - pg_messages
            }
        }

        # Log results
        logger.info("=" * 50)
        logger.info("Verification Results")
        logger.info("=" * 50)
        logger.info(f"Neo4j Sessions:      {neo4j_sessions}")
        logger.info(f"PostgreSQL Sessions: {pg_sessions}")
        logger.info(f"Sessions Diff:       {results['sync_status']['sessions_diff']}")
        logger.info("-" * 50)
        logger.info(f"Neo4j Messages:      {neo4j_messages}")
        logger.info(f"PostgreSQL Messages: {pg_messages}")
        logger.info(f"Messages Diff:       {results['sync_status']['messages_diff']}")
        logger.info("=" * 50)

        if results["sync_status"]["sessions_synced"] and results["sync_status"]["messages_synced"]:
            logger.info("Sync status: COMPLETE")
        else:
            logger.warning("Sync status: INCOMPLETE - run sync again")

        return results


async def main():
    """Main entry point for sync utility."""
    parser = argparse.ArgumentParser(description="Sync data from Neo4j to PostgreSQL")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
        help="Sync mode: full (all data) or incremental (new data only)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify sync status only, don't sync"
    )
    parser.add_argument(
        "--sessions-only",
        action="store_true",
        help="Sync sessions only"
    )
    parser.add_argument(
        "--messages-only",
        action="store_true",
        help="Sync messages only"
    )

    args = parser.parse_args()

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    # Initialize Neo4j
    from infrastructure.neo4j_backend import create_neo4j_backend
    neo4j = await create_neo4j_backend()

    # Initialize PostgreSQL
    from infrastructure.database.session import init_database, db_session

    await init_database(create_tables=True)

    async with db_session() as pg_sess:
        sync = DataSyncUtility(neo4j, pg_sess)

        if args.verify:
            await sync.verify_sync()
        else:
            full_sync = args.mode == "full"

            if not args.messages_only:
                await sync.sync_sessions(full_sync)

            if not args.sessions_only:
                await sync.sync_messages(full_sync)

            # Verify after sync
            await sync.verify_sync()

            # Print errors if any
            if sync.stats["errors"]:
                logger.warning(f"\n{len(sync.stats['errors'])} errors occurred during sync:")
                for error in sync.stats["errors"][:10]:
                    logger.warning(f"  - {error}")
                if len(sync.stats["errors"]) > 10:
                    logger.warning(f"  ... and {len(sync.stats['errors']) - 10} more")


if __name__ == "__main__":
    asyncio.run(main())
