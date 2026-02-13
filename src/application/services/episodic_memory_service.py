"""
Episodic Memory Service - Graphiti-based conversation memory.

This service provides episodic memory for conversations using Graphiti
with FalkorDB as the backend. It complements the existing 3-layer
memory architecture (Redis + Mem0 + Neo4j) by adding:

1. Automatic entity extraction from conversations
2. Temporal awareness with episode timestamps
3. Relationship discovery between conversation topics
4. Hybrid search (semantic + keyword)

Architecture:
- FalkorDB: Episodic graph storage (separate from Neo4j DIKW)
- Graphiti: Episode processing, entity extraction, edge inference
- Hybrid Episodes: Sessions contain turns for hierarchical organization

Event Integration:
- Emits "episode_added" events for CrystallizationService integration
- Events include extracted entities for DIKW pipeline processing
"""

import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from application.event_bus import EventBus

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType, EpisodicNode, EntityNode
from graphiti_core.edges import EntityEdge
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.search.search import search
from graphiti_core.search.search_config import SearchResults
from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_CROSS_ENCODER
from graphiti_core.search.search_filters import SearchFilters

logger = logging.getLogger(__name__)


@dataclass
class EpisodeResult:
    """Result from adding an episode."""
    episode_id: str
    entities_extracted: List[str]
    relationships_created: int
    processing_time_ms: float


@dataclass
class ConversationEpisode:
    """A conversation episode with metadata."""
    episode_id: str
    content: str
    timestamp: datetime
    patient_id: str
    session_id: Optional[str]
    turn_number: Optional[int]
    mode: Optional[str]  # casual_chat, medical_consult, etc.
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)


class EpisodicMemoryService:
    """
    Episodic memory service using Graphiti with FalkorDB.

    Provides temporally-aware conversation memory with automatic
    entity extraction and relationship inference.

    Episode Types:
    - SESSION: High-level session episode (JSON metadata)
    - TURN: Individual conversation turn (message format)

    Group ID Strategy:
    - patient_id: Top-level partition for patient isolation
    - Session episodes have group_id = _sanitize_group_id(patient_id)
    - Turn episodes have group_id = f"{_sanitize_group_id(patient_id)}--{_sanitize_group_id(session_id)}"
    - IDs are sanitized (colons replaced with dashes) for Graphiti/FalkorDB compatibility
    """

    @staticmethod
    def _sanitize_group_id(raw_id: str) -> str:
        """Sanitize an ID for use as a Graphiti group_id.

        Graphiti/FalkorDB only accepts alphanumeric characters, dashes, and underscores.
        This replaces colons (used in patient:id and session:id formats) with dashes.
        """
        return raw_id.replace(":", "-") if raw_id else raw_id

    def __init__(
        self,
        graphiti: Graphiti,
        store_raw_content: bool = True,
        event_bus: Optional["EventBus"] = None,
    ):
        """
        Initialize the episodic memory service.

        Args:
            graphiti: Configured Graphiti instance with FalkorDB driver
            store_raw_content: Whether to store raw episode content
            event_bus: Optional EventBus for emitting episode_added events
        """
        self.graphiti = graphiti
        self.store_raw_content = store_raw_content
        self.event_bus = event_bus
        self._initialized = False

        logger.info("EpisodicMemoryService initialized")

    async def initialize(self) -> None:
        """Initialize indices and constraints in FalkorDB."""
        if self._initialized:
            return

        try:
            await self.graphiti.build_indices_and_constraints()
            self._initialized = True
            logger.info("EpisodicMemoryService indices initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize indices (may already exist): {e}")
            self._initialized = True  # Continue anyway

    async def close(self) -> None:
        """Close the Graphiti connection."""
        await self.graphiti.close()

    # ========================================
    # Episode Storage
    # ========================================

    async def store_turn_episode(
        self,
        patient_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str,
        turn_number: int,
        mode: Optional[str] = None,
        topics: Optional[List[str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> EpisodeResult:
        """
        Store a conversation turn as an episode.

        The turn is formatted in Graphiti's message format:
        "user: {message}\nassistant: {response}"

        Args:
            patient_id: Patient identifier
            session_id: Session identifier
            user_message: User's message
            assistant_message: Assistant's response
            turn_number: Turn number within session
            mode: Conversation mode (casual_chat, medical_consult, etc.)
            topics: Extracted topics from the conversation
            timestamp: Timestamp of the turn (defaults to now)

        Returns:
            EpisodeResult with episode details
        """
        await self.initialize()

        timestamp = timestamp or datetime.now()
        group_id = f"{self._sanitize_group_id(patient_id)}--{self._sanitize_group_id(session_id)}"

        # Format as Graphiti message format
        episode_body = f"user: {user_message}\nassistant: {assistant_message}"

        # Create episode name
        episode_name = f"Turn {turn_number}"
        if mode:
            episode_name += f" ({mode})"

        # Source description includes metadata
        source_description = f"Conversation turn {turn_number} in session {session_id} for patient {patient_id}"
        if topics:
            source_description += f". Topics: {', '.join(topics[:5])}"

        start_time = datetime.now()

        try:
            result = await self.graphiti.add_episode(
                name=episode_name,
                episode_body=episode_body,
                source_description=source_description,
                reference_time=timestamp,
                source=EpisodeType.message,
                group_id=group_id,
            )

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Extract entity names from result
            entity_names = [node.name for node in result.nodes] if result.nodes else []

            logger.info(
                f"Stored turn episode: session={session_id}, turn={turn_number}, "
                f"entities={len(entity_names)}, edges={len(result.edges) if result.edges else 0}, "
                f"time={processing_time:.1f}ms"
            )

            episode_result = EpisodeResult(
                episode_id=result.episode.uuid,
                entities_extracted=entity_names,
                relationships_created=len(result.edges) if result.edges else 0,
                processing_time_ms=processing_time,
            )

            # Emit episode_added event for CrystallizationService
            await self._emit_episode_added_event(
                episode_id=result.episode.uuid,
                patient_id=patient_id,
                session_id=session_id,
                entities_extracted=entity_names,
                timestamp=timestamp,
            )

            return episode_result

        except Exception as e:
            logger.error(f"Failed to store turn episode: {e}", exc_info=True)
            raise

    async def store_session_episode(
        self,
        patient_id: str,
        session_id: str,
        session_summary: str,
        topics: List[str],
        turn_count: int,
        started_at: datetime,
        ended_at: Optional[datetime] = None,
    ) -> EpisodeResult:
        """
        Store a session summary as an episode.

        This creates a higher-level episode that summarizes an entire
        conversation session, useful for long-term context.

        Args:
            patient_id: Patient identifier
            session_id: Session identifier
            session_summary: Summary of the session
            topics: Topics discussed in the session
            turn_count: Number of turns in the session
            started_at: Session start time
            ended_at: Session end time (optional)

        Returns:
            EpisodeResult with episode details
        """
        await self.initialize()

        # Use patient_id as group_id for session-level episodes
        group_id = patient_id

        # Format as JSON episode
        import json
        episode_body = json.dumps({
            "type": "session_summary",
            "session_id": session_id,
            "summary": session_summary,
            "topics": topics,
            "turn_count": turn_count,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat() if ended_at else None,
        })

        episode_name = f"Session {session_id[:12]}"
        source_description = f"Conversation session summary for patient {patient_id}"

        start_time = datetime.now()

        try:
            result = await self.graphiti.add_episode(
                name=episode_name,
                episode_body=episode_body,
                source_description=source_description,
                reference_time=ended_at or datetime.now(),
                source=EpisodeType.json,
                group_id=group_id,
            )

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            entity_names = [node.name for node in result.nodes] if result.nodes else []

            logger.info(
                f"Stored session episode: session={session_id}, "
                f"topics={len(topics)}, entities={len(entity_names)}"
            )

            return EpisodeResult(
                episode_id=result.episode.uuid,
                entities_extracted=entity_names,
                relationships_created=len(result.edges) if result.edges else 0,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Failed to store session episode: {e}", exc_info=True)
            raise

    # ========================================
    # Episode Retrieval
    # ========================================

    async def retrieve_recent_episodes(
        self,
        patient_id: str,
        session_id: Optional[str] = None,
        limit: int = 10,
        before: Optional[datetime] = None,
        source_type: Optional[EpisodeType] = None,
    ) -> List[ConversationEpisode]:
        """
        Retrieve recent episodes for a patient.

        Args:
            patient_id: Patient identifier
            session_id: Optional session to filter by
            limit: Maximum number of episodes to return
            before: Only return episodes before this time
            source_type: Filter by episode type (message, json, text)

        Returns:
            List of ConversationEpisode objects
        """
        await self.initialize()

        # Determine group_id based on whether session is specified
        group_ids = []
        if session_id:
            group_ids.append(f"{self._sanitize_group_id(patient_id)}--{self._sanitize_group_id(session_id)}")
        else:
            # Include both session-level and turn-level episodes
            group_ids.append(self._sanitize_group_id(patient_id))
            # Note: We'd need to query for all session-specific group_ids
            # For now, we'll use semantic search which handles this better

        reference_time = before or datetime.now()

        try:
            episodes = await self.graphiti.retrieve_episodes(
                reference_time=reference_time,
                last_n=limit,
                group_ids=group_ids if group_ids else None,
                source=source_type,
            )

            return [self._convert_episode(ep, patient_id) for ep in episodes]

        except Exception as e:
            logger.error(f"Failed to retrieve episodes: {e}", exc_info=True)
            return []

    async def search_episodes(
        self,
        patient_id: str,
        query: str,
        limit: int = 10,
        session_id: Optional[str] = None,
    ) -> List[ConversationEpisode]:
        """
        Search episodes using hybrid search (semantic + keyword).

        Args:
            patient_id: Patient identifier
            query: Search query
            limit: Maximum results to return
            session_id: Optional session to filter by

        Returns:
            List of matching ConversationEpisode objects
        """
        await self.initialize()

        group_ids = [self._sanitize_group_id(patient_id)]
        if session_id:
            group_ids.append(f"{self._sanitize_group_id(patient_id)}--{self._sanitize_group_id(session_id)}")

        try:
            results: SearchResults = await search(
                clients=self.graphiti.clients,
                query=query,
                group_ids=group_ids,
                search_filter=SearchFilters(),
                config=COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
            )

            # Convert search results to episodes
            episodes = []
            for ep in results.episodes[:limit]:
                episodes.append(self._convert_episode(ep, patient_id))

            logger.debug(f"Episode search for '{query}': {len(episodes)} results")
            return episodes

        except Exception as e:
            logger.error(f"Failed to search episodes: {e}", exc_info=True)
            return []

    async def get_related_entities(
        self,
        patient_id: str,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get entities related to a query from episodic memory.

        This leverages Graphiti's automatic entity extraction to find
        entities mentioned in past conversations.

        Args:
            patient_id: Patient identifier
            query: Query to find related entities
            limit: Maximum entities to return

        Returns:
            List of entity dictionaries with name, summary, and attributes
        """
        await self.initialize()

        try:
            results: SearchResults = await search(
                clients=self.graphiti.clients,
                query=query,
                group_ids=[patient_id],
                search_filter=SearchFilters(),
                config=COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
            )

            entities = []
            for node in results.nodes[:limit]:
                entities.append({
                    "name": node.name,
                    "summary": node.summary,
                    "labels": node.labels,
                    "attributes": node.attributes,
                    "created_at": node.created_at.isoformat() if node.created_at else None,
                })

            return entities

        except Exception as e:
            logger.error(f"Failed to get related entities: {e}", exc_info=True)
            return []

    async def get_conversation_context(
        self,
        patient_id: str,
        current_query: str,
        session_id: Optional[str] = None,
        max_episodes: int = 5,
    ) -> Dict[str, Any]:
        """
        Get relevant conversation context for a new query.

        This retrieves both:
        1. Recent episodes from the current/recent sessions
        2. Semantically similar episodes from past conversations
        3. Related entities mentioned in those episodes

        Args:
            patient_id: Patient identifier
            current_query: The current user query
            session_id: Current session ID
            max_episodes: Maximum episodes to include

        Returns:
            Dict with recent_episodes, related_episodes, and entities
        """
        await self.initialize()

        # Get recent episodes from current session (if provided)
        recent = []
        if session_id:
            recent = await self.retrieve_recent_episodes(
                patient_id=patient_id,
                session_id=session_id,
                limit=3,
                source_type=EpisodeType.message,
            )

        # Search for semantically related episodes
        related = await self.search_episodes(
            patient_id=patient_id,
            query=current_query,
            limit=max_episodes,
        )

        # Get related entities
        entities = await self.get_related_entities(
            patient_id=patient_id,
            query=current_query,
            limit=5,
        )

        # Deduplicate (recent might overlap with related)
        recent_ids = {ep.episode_id for ep in recent}
        related = [ep for ep in related if ep.episode_id not in recent_ids]

        return {
            "recent_episodes": [self._episode_to_dict(ep) for ep in recent],
            "related_episodes": [self._episode_to_dict(ep) for ep in related[:max_episodes - len(recent)]],
            "entities": entities,
            "total_context_items": len(recent) + len(related) + len(entities),
        }

    # ========================================
    # Helper Methods
    # ========================================

    async def _emit_episode_added_event(
        self,
        episode_id: str,
        patient_id: str,
        session_id: str,
        entities_extracted: List[str],
        timestamp: datetime,
    ) -> None:
        """
        Emit episode_added event for CrystallizationService integration.

        This enables the crystallization pipeline to process newly
        extracted entities and promote them through the DIKW hierarchy.
        """
        if not self.event_bus:
            return

        try:
            from domain.event import KnowledgeEvent
            from domain.roles import Role

            event = KnowledgeEvent(
                action="episode_added",
                data={
                    "episode_id": episode_id,
                    "patient_id": patient_id,
                    "session_id": session_id,
                    "entities_extracted": entities_extracted,
                    "timestamp": timestamp.isoformat(),
                    "source": "episodic_memory",
                },
                role=Role.KNOWLEDGE_MANAGER,
            )

            await self.event_bus.publish(event)
            logger.debug(
                f"Emitted episode_added event: {episode_id} with {len(entities_extracted)} entities"
            )

        except Exception as e:
            # Don't fail the main operation if event emission fails
            logger.warning(f"Failed to emit episode_added event: {e}")

    def _convert_episode(
        self,
        ep: EpisodicNode,
        patient_id: str,
    ) -> ConversationEpisode:
        """Convert Graphiti EpisodicNode to ConversationEpisode."""
        # Parse group_id to extract session_id
        group_id = ep.group_id
        session_id = None
        if "--" in group_id:
            parts = group_id.split("--", 1)
            if len(parts) == 2:
                session_id = parts[1]

        # Try to extract turn number from name
        turn_number = None
        if ep.name and ep.name.startswith("Turn "):
            try:
                turn_str = ep.name.split()[1]
                turn_number = int(turn_str)
            except (IndexError, ValueError):
                pass

        # Extract mode from name if present
        mode = None
        if ep.name and "(" in ep.name and ")" in ep.name:
            mode = ep.name.split("(")[1].split(")")[0]

        return ConversationEpisode(
            episode_id=ep.uuid,
            content=ep.content,
            timestamp=ep.valid_at or ep.created_at,
            patient_id=patient_id,
            session_id=session_id,
            turn_number=turn_number,
            mode=mode,
            topics=[],  # Would need separate query to get topics
            entities=[],  # Would need separate query to get entities
        )

    def _episode_to_dict(self, ep: ConversationEpisode) -> Dict[str, Any]:
        """Convert ConversationEpisode to dictionary."""
        return {
            "episode_id": ep.episode_id,
            "content": ep.content,
            "timestamp": ep.timestamp.isoformat() if ep.timestamp else None,
            "session_id": ep.session_id,
            "turn_number": ep.turn_number,
            "mode": ep.mode,
            "topics": ep.topics,
        }


# ========================================
# Factory Function
# ========================================

async def create_episodic_memory_service(
    falkordb_host: Optional[str] = None,
    falkordb_port: Optional[int] = None,
    database_name: str = "episodic_memory",
    openai_api_key: Optional[str] = None,
) -> EpisodicMemoryService:
    """
    Factory function to create an EpisodicMemoryService.

    Args:
        falkordb_host: FalkorDB host (defaults to env FALKORDB_HOST or localhost)
        falkordb_port: FalkorDB port (defaults to env FALKORDB_PORT or 6379)
        database_name: FalkorDB database name for episodic memory
        openai_api_key: OpenAI API key (defaults to env OPENAI_API_KEY)

    Returns:
        Configured EpisodicMemoryService instance
    """
    host = falkordb_host or os.getenv("FALKORDB_HOST", "localhost")
    port = falkordb_port or int(os.getenv("FALKORDB_PORT", "6379"))
    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OpenAI API key required for episodic memory service")

    # Create FalkorDB driver
    driver = FalkorDriver(
        host=host,
        port=port,
        database=database_name,
    )

    # Create Graphiti instance with FalkorDB
    graphiti = Graphiti(
        graph_driver=driver,
        store_raw_episode_content=True,
    )

    service = EpisodicMemoryService(graphiti=graphiti)

    # Initialize indices
    await service.initialize()

    logger.info(f"Created EpisodicMemoryService with FalkorDB at {host}:{port}/{database_name}")

    return service
