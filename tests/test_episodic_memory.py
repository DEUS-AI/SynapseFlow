"""
Tests for EpisodicMemoryService.

Tests the Graphiti-based episodic memory integration with FalkorDB backend.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Test imports
from application.services.episodic_memory_service import (
    EpisodicMemoryService,
    EpisodeResult,
    ConversationEpisode,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_graphiti():
    """Create a mock Graphiti instance."""
    mock = AsyncMock()

    # Mock build_indices_and_constraints
    mock.build_indices_and_constraints = AsyncMock()

    # Mock add_episode
    mock_episode = MagicMock()
    mock_episode.uuid = "ep-123"

    mock_result = MagicMock()
    mock_result.episode = mock_episode
    mock_result.nodes = [
        MagicMock(name="Entity1"),
        MagicMock(name="Entity2"),
    ]
    mock_result.edges = [MagicMock(), MagicMock()]

    mock.add_episode = AsyncMock(return_value=mock_result)

    # Mock retrieve_episodes
    mock.retrieve_episodes = AsyncMock(return_value=[])

    # Mock clients for search
    mock.clients = MagicMock()

    # Mock close
    mock.close = AsyncMock()

    return mock


@pytest.fixture
def episodic_memory_service(mock_graphiti):
    """Create EpisodicMemoryService with mocked Graphiti."""
    return EpisodicMemoryService(graphiti=mock_graphiti)


# ============================================================
# INITIALIZATION TESTS
# ============================================================

@pytest.mark.asyncio
async def test_initialize_creates_indices(episodic_memory_service, mock_graphiti):
    """Test that initialize creates indices in FalkorDB."""
    await episodic_memory_service.initialize()

    mock_graphiti.build_indices_and_constraints.assert_called_once()
    assert episodic_memory_service._initialized is True


@pytest.mark.asyncio
async def test_initialize_only_once(episodic_memory_service, mock_graphiti):
    """Test that initialize only runs once."""
    await episodic_memory_service.initialize()
    await episodic_memory_service.initialize()  # Second call

    # Should only be called once
    assert mock_graphiti.build_indices_and_constraints.call_count == 1


@pytest.mark.asyncio
async def test_close_closes_graphiti(episodic_memory_service, mock_graphiti):
    """Test that close properly closes the Graphiti connection."""
    await episodic_memory_service.close()

    mock_graphiti.close.assert_called_once()


# ============================================================
# EPISODE STORAGE TESTS
# ============================================================

@pytest.mark.asyncio
async def test_store_turn_episode_success(episodic_memory_service, mock_graphiti):
    """Test storing a conversation turn as an episode."""
    result = await episodic_memory_service.store_turn_episode(
        patient_id="patient-123",
        session_id="session-abc",
        user_message="I have knee pain",
        assistant_message="I understand you're experiencing knee pain. Can you tell me more?",
        turn_number=1,
        mode="medical_consult",
        topics=["knee", "pain"],
    )

    assert isinstance(result, EpisodeResult)
    assert result.episode_id == "ep-123"
    assert len(result.entities_extracted) == 2
    assert result.relationships_created == 2

    # Verify add_episode was called with correct arguments
    mock_graphiti.add_episode.assert_called_once()
    call_kwargs = mock_graphiti.add_episode.call_args[1]
    assert call_kwargs["group_id"] == "patient-123--session-abc"
    assert "knee pain" in call_kwargs["episode_body"]
    assert call_kwargs["name"] == "Turn 1 (medical_consult)"


@pytest.mark.asyncio
async def test_store_turn_episode_without_mode(episodic_memory_service, mock_graphiti):
    """Test storing a turn episode without mode."""
    result = await episodic_memory_service.store_turn_episode(
        patient_id="patient-123",
        session_id="session-abc",
        user_message="Hello",
        assistant_message="Hi there!",
        turn_number=1,
    )

    assert result.episode_id == "ep-123"

    call_kwargs = mock_graphiti.add_episode.call_args[1]
    assert call_kwargs["name"] == "Turn 1"


@pytest.mark.asyncio
async def test_store_session_episode_success(episodic_memory_service, mock_graphiti):
    """Test storing a session summary episode."""
    result = await episodic_memory_service.store_session_episode(
        patient_id="patient-123",
        session_id="session-abc",
        session_summary="Patient discussed knee pain and received exercise recommendations.",
        topics=["knee", "pain", "exercise"],
        turn_count=5,
        started_at=datetime(2024, 1, 1, 10, 0, 0),
        ended_at=datetime(2024, 1, 1, 10, 30, 0),
    )

    assert isinstance(result, EpisodeResult)
    assert result.episode_id == "ep-123"

    # Verify add_episode was called with JSON source type
    call_kwargs = mock_graphiti.add_episode.call_args[1]
    assert call_kwargs["group_id"] == "patient-123"  # Session-level uses patient_id only


# ============================================================
# EPISODE RETRIEVAL TESTS
# ============================================================

@pytest.mark.asyncio
async def test_retrieve_recent_episodes_empty(episodic_memory_service, mock_graphiti):
    """Test retrieving episodes when none exist."""
    mock_graphiti.retrieve_episodes.return_value = []

    episodes = await episodic_memory_service.retrieve_recent_episodes(
        patient_id="patient-123",
        limit=10,
    )

    assert episodes == []


@pytest.mark.asyncio
async def test_retrieve_recent_episodes_with_results(episodic_memory_service, mock_graphiti):
    """Test retrieving episodes with results."""
    # Create mock EpisodicNode
    mock_episode = MagicMock()
    mock_episode.uuid = "ep-456"
    mock_episode.content = "user: Hello\nassistant: Hi there!"
    mock_episode.valid_at = datetime(2024, 1, 1, 10, 0, 0)
    mock_episode.created_at = datetime(2024, 1, 1, 10, 0, 0)
    mock_episode.group_id = "patient-123--session-abc"
    mock_episode.name = "Turn 1 (casual_chat)"

    mock_graphiti.retrieve_episodes.return_value = [mock_episode]

    episodes = await episodic_memory_service.retrieve_recent_episodes(
        patient_id="patient-123",
        session_id="session-abc",
        limit=10,
    )

    assert len(episodes) == 1
    assert isinstance(episodes[0], ConversationEpisode)
    assert episodes[0].episode_id == "ep-456"
    assert episodes[0].session_id == "session-abc"
    assert episodes[0].turn_number == 1
    assert episodes[0].mode == "casual_chat"


# ============================================================
# SEARCH TESTS
# ============================================================

@pytest.mark.asyncio
async def test_search_episodes_empty(episodic_memory_service, mock_graphiti):
    """Test searching episodes with no results."""
    with patch("application.services.episodic_memory_service.search") as mock_search:
        mock_results = MagicMock()
        mock_results.episodes = []
        mock_search.return_value = mock_results

        episodes = await episodic_memory_service.search_episodes(
            patient_id="patient-123",
            query="knee pain",
            limit=10,
        )

        assert episodes == []


@pytest.mark.asyncio
async def test_get_related_entities(episodic_memory_service, mock_graphiti):
    """Test getting related entities from episodic memory."""
    with patch("application.services.episodic_memory_service.search") as mock_search:
        # Mock entity node
        mock_node = MagicMock()
        mock_node.name = "Knee Pain"
        mock_node.summary = "Pain in the knee joint"
        mock_node.labels = ["Symptom", "Entity"]
        mock_node.attributes = {"severity": "moderate"}
        mock_node.created_at = datetime(2024, 1, 1)

        mock_results = MagicMock()
        mock_results.nodes = [mock_node]
        mock_search.return_value = mock_results

        entities = await episodic_memory_service.get_related_entities(
            patient_id="patient-123",
            query="knee pain",
            limit=10,
        )

        assert len(entities) == 1
        assert entities[0]["name"] == "Knee Pain"
        assert entities[0]["summary"] == "Pain in the knee joint"


# ============================================================
# CONVERSATION CONTEXT TESTS
# ============================================================

@pytest.mark.asyncio
async def test_get_conversation_context(episodic_memory_service, mock_graphiti):
    """Test getting conversation context for a query."""
    # Mock recent episodes
    mock_episode = MagicMock()
    mock_episode.uuid = "ep-recent"
    mock_episode.content = "user: Previous message\nassistant: Previous response"
    mock_episode.valid_at = datetime(2024, 1, 1)
    mock_episode.created_at = datetime(2024, 1, 1)
    mock_episode.group_id = "patient-123--session-abc"
    mock_episode.name = "Turn 1"

    mock_graphiti.retrieve_episodes.return_value = [mock_episode]

    with patch("application.services.episodic_memory_service.search") as mock_search:
        # Mock search results
        mock_results = MagicMock()
        mock_results.episodes = []
        mock_results.nodes = []
        mock_search.return_value = mock_results

        context = await episodic_memory_service.get_conversation_context(
            patient_id="patient-123",
            current_query="My knee still hurts",
            session_id="session-abc",
            max_episodes=5,
        )

        assert "recent_episodes" in context
        assert "related_episodes" in context
        assert "entities" in context
        assert "total_context_items" in context
        assert len(context["recent_episodes"]) == 1


# ============================================================
# ERROR HANDLING TESTS
# ============================================================

@pytest.mark.asyncio
async def test_store_turn_episode_handles_error(episodic_memory_service, mock_graphiti):
    """Test that errors are properly raised when storage fails."""
    mock_graphiti.add_episode.side_effect = Exception("Database error")

    with pytest.raises(Exception) as exc_info:
        await episodic_memory_service.store_turn_episode(
            patient_id="patient-123",
            session_id="session-abc",
            user_message="Hello",
            assistant_message="Hi!",
            turn_number=1,
        )

    assert "Database error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_retrieve_episodes_handles_error_gracefully(episodic_memory_service, mock_graphiti):
    """Test that retrieval errors return empty list."""
    mock_graphiti.retrieve_episodes.side_effect = Exception("Network error")

    episodes = await episodic_memory_service.retrieve_recent_episodes(
        patient_id="patient-123",
        limit=10,
    )

    # Should return empty list on error, not raise
    assert episodes == []


# ============================================================
# HELPER METHOD TESTS
# ============================================================

def test_convert_episode():
    """Test conversion from EpisodicNode to ConversationEpisode."""
    service = EpisodicMemoryService(graphiti=MagicMock())

    mock_episode = MagicMock()
    mock_episode.uuid = "ep-123"
    mock_episode.content = "user: Hello\nassistant: Hi!"
    mock_episode.valid_at = datetime(2024, 1, 1)
    mock_episode.created_at = datetime(2024, 1, 1)
    mock_episode.group_id = "patient-123--session-abc"
    mock_episode.name = "Turn 5 (medical_consult)"

    result = service._convert_episode(mock_episode, "patient-123")

    assert result.episode_id == "ep-123"
    assert result.patient_id == "patient-123"
    assert result.session_id == "session-abc"
    assert result.turn_number == 5
    assert result.mode == "medical_consult"


def test_episode_to_dict():
    """Test conversion from ConversationEpisode to dictionary."""
    service = EpisodicMemoryService(graphiti=MagicMock())

    episode = ConversationEpisode(
        episode_id="ep-123",
        content="test content",
        timestamp=datetime(2024, 1, 1),
        patient_id="patient-123",
        session_id="session-abc",
        turn_number=1,
        mode="casual_chat",
        topics=["greeting"],
    )

    result = service._episode_to_dict(episode)

    assert result["episode_id"] == "ep-123"
    assert result["session_id"] == "session-abc"
    assert result["turn_number"] == 1
    assert result["mode"] == "casual_chat"
    assert result["topics"] == ["greeting"]


# ============================================================
# SANITIZE GROUP ID TESTS
# ============================================================

class TestSanitizeGroupId:
    """Tests for _sanitize_group_id static method."""

    def test_colon_replaced_with_dash(self):
        """Test that colons are replaced with dashes."""
        assert EpisodicMemoryService._sanitize_group_id("patient:demo") == "patient-demo"

    def test_multiple_colons_replaced(self):
        """Test that all colons in an ID are replaced."""
        assert EpisodicMemoryService._sanitize_group_id("session:19e7d4d9-d33b") == "session-19e7d4d9-d33b"

    def test_clean_id_passes_through(self):
        """Test that IDs without colons are unchanged."""
        assert EpisodicMemoryService._sanitize_group_id("dda_customer_analytics") == "dda_customer_analytics"

    def test_id_with_dashes_and_underscores(self):
        """Test that dashes and underscores are preserved."""
        assert EpisodicMemoryService._sanitize_group_id("my-id_123") == "my-id_123"

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert EpisodicMemoryService._sanitize_group_id("") == ""

    def test_none_returns_none(self):
        """Test that None input returns None."""
        assert EpisodicMemoryService._sanitize_group_id(None) is None


# ============================================================
# CONVERT EPISODE PARSING TESTS
# ============================================================

class TestConvertEpisodeParsing:
    """Tests for _convert_episode group_id parsing with new format."""

    def _make_mock_episode(self, group_id, name="Turn 1"):
        mock_ep = MagicMock()
        mock_ep.uuid = "ep-test"
        mock_ep.content = "user: hi\nassistant: hello"
        mock_ep.valid_at = datetime(2024, 1, 1)
        mock_ep.created_at = datetime(2024, 1, 1)
        mock_ep.group_id = group_id
        mock_ep.name = name
        return mock_ep

    def test_composite_group_id_extracts_session(self):
        """Test that composite group_id with -- separator extracts session_id."""
        service = EpisodicMemoryService(graphiti=MagicMock())
        mock_ep = self._make_mock_episode("patient-demo--session-abc-123")

        result = service._convert_episode(mock_ep, "patient:demo")

        assert result.session_id == "session-abc-123"

    def test_patient_only_group_id_returns_none_session(self):
        """Test that patient-only group_id has no session_id."""
        service = EpisodicMemoryService(graphiti=MagicMock())
        mock_ep = self._make_mock_episode("patient-demo", name="Session summary")

        result = service._convert_episode(mock_ep, "patient:demo")

        assert result.session_id is None

    def test_legacy_colon_format_returns_none_session(self):
        """Test that legacy colon-separated group_id doesn't crash and returns None session."""
        service = EpisodicMemoryService(graphiti=MagicMock())
        mock_ep = self._make_mock_episode("patient:demo:session:abc")

        result = service._convert_episode(mock_ep, "patient:demo")

        assert result.session_id is None

    def test_composite_with_uuid_session(self):
        """Test parsing composite group_id with UUID-style session."""
        service = EpisodicMemoryService(graphiti=MagicMock())
        mock_ep = self._make_mock_episode(
            "patient-demo--session-19e7d4d9-d33b-48c1-b351-97511b67bc12"
        )

        result = service._convert_episode(mock_ep, "patient:demo")

        assert result.session_id == "session-19e7d4d9-d33b-48c1-b351-97511b67bc12"
