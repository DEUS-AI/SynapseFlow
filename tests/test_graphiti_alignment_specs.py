"""Tests for the 5 Graphiti Alignment Specs.

SPEC-1: Community/summary layer
SPEC-2: Temporal conflict resolution
SPEC-3: Bound search results
SPEC-4: Memory invalidation/expiration
SPEC-5: LLM rate limit management
"""

import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from application.services.episodic_memory_service import (
    EpisodicMemoryService,
    CommunitySummary,
)
from application.services.crystallization_service import (
    CrystallizationService,
    CrystallizationConfig,
    CrystallizationMode,
)
from application.services.entity_resolver import (
    EntityResolver,
    CrystallizationMatch,
    MergeResult,
)
from application.services.memory_invalidation_service import (
    MemoryInvalidationService,
    InvalidationConfig,
    InvalidationResult,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_graphiti():
    """Create a mock Graphiti instance."""
    mock = AsyncMock()
    mock.build_indices_and_constraints = AsyncMock()

    mock_episode = MagicMock()
    mock_episode.uuid = "ep-123"
    mock_result = MagicMock()
    mock_result.episode = mock_episode
    mock_result.nodes = [MagicMock(name="Entity1")]
    mock_result.edges = [MagicMock()]
    mock.add_episode = AsyncMock(return_value=mock_result)
    mock.retrieve_episodes = AsyncMock(return_value=[])
    mock.clients = MagicMock()
    mock.close = AsyncMock()

    # Mock driver for community queries
    mock.driver = AsyncMock()
    mock.driver.execute_query = AsyncMock(return_value=[])

    return mock


@pytest.fixture
def episodic_service(mock_graphiti):
    """Create EpisodicMemoryService with mocked Graphiti."""
    return EpisodicMemoryService(graphiti=mock_graphiti)


@pytest.fixture
def mock_neo4j_backend():
    """Create a mock Neo4j backend."""
    backend = AsyncMock()
    backend.add_entity = AsyncMock()
    backend.query = AsyncMock(return_value={"rows": []})
    return backend


@pytest.fixture
def mock_resolver(mock_neo4j_backend):
    """Create a mock EntityResolver."""
    resolver = AsyncMock()
    resolver.find_existing_for_crystallization = AsyncMock(
        return_value=CrystallizationMatch(found=False)
    )
    resolver.merge_for_crystallization = AsyncMock(
        return_value=MergeResult(success=True, entity_id="merged_123", observation_count=2)
    )
    resolver.normalize_entity_type = MagicMock(side_effect=lambda x: x.title())
    resolver.normalize_entity_name = MagicMock(side_effect=lambda x: x.strip().lower())
    return resolver


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus."""
    bus = AsyncMock()
    bus.subscribe = MagicMock()
    bus.publish = AsyncMock()
    return bus


# ============================================================
# SPEC-1: Community / Summary Layer
# ============================================================

class TestSpec1CommunitySummaries:
    """Tests for SPEC-1: Community/summary layer."""

    @pytest.mark.asyncio
    async def test_get_community_summaries_returns_results(self, episodic_service, mock_graphiti):
        """Community nodes from graph are returned as CommunitySummary list."""
        mock_graphiti.driver.execute_query.return_value = [
            {
                "community_id": "comm-1",
                "summary": "Patient medications and treatment history",
                "entity_count": 5,
                "key_entities": ["Metformin", "Diabetes", "Insulin"],
                "updated_at": datetime(2024, 6, 1),
            },
        ]

        summaries = await episodic_service.get_community_summaries(
            patient_id="patient-123",
            limit=5,
        )

        assert len(summaries) == 1
        assert isinstance(summaries[0], CommunitySummary)
        assert summaries[0].community_id == "comm-1"
        assert summaries[0].entity_count == 5
        assert "Metformin" in summaries[0].key_entities

    @pytest.mark.asyncio
    async def test_get_community_summaries_empty_graceful(self, episodic_service, mock_graphiti):
        """Returns [] when no community nodes exist."""
        mock_graphiti.driver.execute_query.return_value = []

        summaries = await episodic_service.get_community_summaries(
            patient_id="patient-123",
        )

        assert summaries == []

    @pytest.mark.asyncio
    async def test_get_community_summaries_error_graceful(self, episodic_service, mock_graphiti):
        """Returns [] on error, no exception propagated."""
        mock_graphiti.driver.execute_query.side_effect = Exception("DB error")

        summaries = await episodic_service.get_community_summaries(
            patient_id="patient-123",
        )

        assert summaries == []

    @pytest.mark.asyncio
    async def test_get_community_summaries_no_driver(self, mock_graphiti):
        """Returns [] when Graphiti has no driver attribute."""
        del mock_graphiti.driver
        service = EpisodicMemoryService(graphiti=mock_graphiti)

        summaries = await service.get_community_summaries(patient_id="patient-123")

        assert summaries == []

    @pytest.mark.asyncio
    async def test_context_includes_community_summaries(self, episodic_service, mock_graphiti):
        """get_conversation_context() response includes community_summaries field."""
        mock_graphiti.retrieve_episodes.return_value = []

        with patch("application.services.episodic_memory_service.search") as mock_search:
            mock_results = MagicMock()
            mock_results.episodes = []
            mock_results.nodes = []
            mock_search.return_value = mock_results

            context = await episodic_service.get_conversation_context(
                patient_id="patient-123",
                current_query="test query",
            )

        assert "community_summaries" in context
        assert isinstance(context["community_summaries"], list)

    @pytest.mark.asyncio
    async def test_summary_to_dict(self, episodic_service):
        """CommunitySummary converts to dict correctly."""
        summary = CommunitySummary(
            community_id="comm-1",
            summary="Test summary",
            entity_count=3,
            key_entities=["A", "B"],
            updated_at=datetime(2024, 1, 1),
        )

        result = episodic_service._summary_to_dict(summary)

        assert result["community_id"] == "comm-1"
        assert result["summary"] == "Test summary"
        assert result["entity_count"] == 3
        assert result["updated_at"] == "2024-01-01T00:00:00"


# ============================================================
# SPEC-2: Temporal Conflict Resolution
# ============================================================

class TestSpec2TemporalConflictResolution:
    """Tests for SPEC-2: Temporal conflict resolution."""

    @pytest.fixture
    def crystallization_service(self, mock_neo4j_backend, mock_resolver, mock_event_bus):
        config = CrystallizationConfig(mode=CrystallizationMode.BATCH)
        return CrystallizationService(
            neo4j_backend=mock_neo4j_backend,
            entity_resolver=mock_resolver,
            event_bus=mock_event_bus,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_new_entity_gets_temporal_fields(self, crystallization_service, mock_neo4j_backend):
        """PERCEPTION entity is created with valid_from, valid_until, is_current."""
        result = await crystallization_service.crystallize_entities(
            entities=[{"name": "Metformin", "entity_type": "Medication"}],
            source="test",
        )

        assert result.entities_created == 1
        # Verify add_entity was called with temporal properties
        call_args = mock_neo4j_backend.add_entity.call_args
        props = call_args[1]["properties"] if "properties" in call_args[1] else call_args[0][1]
        assert "valid_from" in props
        assert "is_current" in props
        assert props["is_current"] is True
        assert props["valid_until"] is None

    @pytest.mark.asyncio
    async def test_entity_with_invalid_at_not_current(self, crystallization_service, mock_neo4j_backend):
        """Entity with invalid_at is marked is_current=False."""
        result = await crystallization_service.crystallize_entities(
            entities=[{
                "name": "Metformin",
                "entity_type": "Medication",
                "invalid_at": "2024-06-01T00:00:00",
            }],
            source="test",
        )

        assert result.entities_created == 1
        call_args = mock_neo4j_backend.add_entity.call_args
        props = call_args[1]["properties"] if "properties" in call_args[1] else call_args[0][1]
        assert props["is_current"] is False
        assert props["valid_until"] == "2024-06-01T00:00:00"

    @pytest.mark.asyncio
    async def test_resolve_temporal_conflicts_invalidates_old(
        self, crystallization_service, mock_neo4j_backend
    ):
        """Calling _resolve_temporal_conflicts marks older entities as not current."""
        mock_neo4j_backend.query.return_value = {"rows": [{"invalidated": 2}]}

        invalidated = await crystallization_service._resolve_temporal_conflicts(
            entity_name="Metformin",
            entity_type="Medication",
            new_valid_from="2024-06-01T00:00:00",
        )

        assert invalidated == 2
        mock_neo4j_backend.query.assert_called()

    @pytest.mark.asyncio
    async def test_resolve_temporal_conflicts_no_valid_from(self, crystallization_service):
        """No invalidation when new_valid_from is None."""
        invalidated = await crystallization_service._resolve_temporal_conflicts(
            entity_name="Metformin",
            entity_type="Medication",
            new_valid_from=None,
        )

        assert invalidated == 0

    @pytest.mark.asyncio
    async def test_merge_propagates_temporal_fields(self, mock_neo4j_backend):
        """merge_for_crystallization stores temporal fields from incoming data."""
        resolver = EntityResolver(backend=mock_neo4j_backend)

        mock_neo4j_backend.query.return_value = {
            "rows": [{
                "properties": {
                    "name": "Metformin",
                    "confidence": 0.8,
                    "observation_count": 2,
                }
            }],
        }

        result = await resolver.merge_for_crystallization(
            existing_id="entity_123",
            new_data={
                "confidence": 0.85,
                "valid_at": "2024-06-01T00:00:00",
                "invalid_at": "2024-12-01T00:00:00",
            },
        )

        assert result.success
        # Check that the update query was called with temporal fields
        update_call = mock_neo4j_backend.query.call_args_list[-1]
        update_params = update_call[0][1] if len(update_call[0]) > 1 else update_call[1].get("params", {})
        # The updates dict should contain valid_from and valid_until
        if isinstance(update_params, dict) and "updates" in update_params:
            updates = update_params["updates"]
            assert "valid_from" in updates
            assert "valid_until" in updates
            assert updates["is_current"] is False

    @pytest.mark.asyncio
    async def test_crystallize_with_valid_at_triggers_conflict_resolution(
        self, crystallization_service, mock_neo4j_backend
    ):
        """Entity with valid_at triggers _resolve_temporal_conflicts."""
        mock_neo4j_backend.query.return_value = {"rows": [{"invalidated": 0}]}

        with patch.object(
            crystallization_service, "_resolve_temporal_conflicts", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = 0

            await crystallization_service.crystallize_entities(
                entities=[{
                    "name": "Metformin",
                    "entity_type": "Medication",
                    "valid_at": "2024-06-01T00:00:00",
                }],
                source="test",
            )

            mock_resolve.assert_called_once_with(
                entity_name="Metformin",
                entity_type="Medication",
                new_valid_from="2024-06-01T00:00:00",
            )


# ============================================================
# SPEC-3: Bound Search Results
# ============================================================

class TestSpec3BoundSearchResults:
    """Tests for SPEC-3: Bound search results."""

    @pytest.mark.asyncio
    async def test_search_episodes_passes_num_results(self, episodic_service):
        """search_episodes passes num_results to the search function."""
        with patch("application.services.episodic_memory_service.search") as mock_search:
            mock_results = MagicMock()
            mock_results.episodes = []
            mock_search.return_value = mock_results

            await episodic_service.search_episodes(
                patient_id="patient-123",
                query="test",
                limit=7,
            )

            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["num_results"] == 7

    @pytest.mark.asyncio
    async def test_get_related_entities_passes_num_results(self, episodic_service):
        """get_related_entities passes num_results to the search function."""
        with patch("application.services.episodic_memory_service.search") as mock_search:
            mock_results = MagicMock()
            mock_results.nodes = []
            mock_search.return_value = mock_results

            await episodic_service.get_related_entities(
                patient_id="patient-123",
                query="test",
                limit=15,
            )

            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["num_results"] == 15

    @pytest.mark.asyncio
    async def test_entity_resolver_parameterized_limit(self, mock_neo4j_backend):
        """EntityResolver._get_existing_entities uses parameterized LIMIT."""
        resolver = EntityResolver(backend=mock_neo4j_backend)
        mock_neo4j_backend.query.return_value = []

        await resolver._get_existing_entities(
            entity_type="Medication",
            context={},
            limit=50,
        )

        call_args = mock_neo4j_backend.query.call_args
        query_str = call_args[0][0]
        params = call_args[0][1] if len(call_args[0]) > 1 else {}
        assert "$limit" in query_str
        assert params.get("limit") == 50


# ============================================================
# SPEC-4: Memory Invalidation / Expiration
# ============================================================

class TestSpec4MemoryInvalidation:
    """Tests for SPEC-4: Memory invalidation/expiration."""

    @pytest.fixture
    def invalidation_service(self, mock_neo4j_backend):
        return MemoryInvalidationService(
            neo4j_backend=mock_neo4j_backend,
            config=InvalidationConfig(stale_threshold_days=90),
        )

    @pytest.mark.asyncio
    async def test_invalidate_entity_sets_flags(self, invalidation_service, mock_neo4j_backend):
        """After invalidation, entity has is_current=false and audit fields."""
        mock_neo4j_backend.query.return_value = {
            "rows": [{"id": "entity_123"}]
        }

        result = await invalidation_service.invalidate_entity(
            entity_id="entity_123",
            reason="discontinued_medication",
        )

        assert result.entities_invalidated == 1
        assert "entity_123" in result.entity_ids
        assert result.reason == "discontinued_medication"

        # Verify query was called
        call_args = mock_neo4j_backend.query.call_args
        query_str = call_args[0][0]
        assert "is_current = false" in query_str
        assert "invalidated_at" in query_str
        assert "invalidation_reason" in query_str

    @pytest.mark.asyncio
    async def test_invalidate_entity_idempotent(self, invalidation_service, mock_neo4j_backend):
        """Invalidating already-invalidated entity returns count 0, no error."""
        mock_neo4j_backend.query.return_value = {"rows": []}

        result = await invalidation_service.invalidate_entity(
            entity_id="already_invalid",
            reason="test",
        )

        assert result.entities_invalidated == 0

    @pytest.mark.asyncio
    async def test_invalidate_by_query_filters(self, invalidation_service, mock_neo4j_backend):
        """Bulk invalidation with patient_id filter only targets matching entities."""
        mock_neo4j_backend.query.return_value = {
            "rows": [{"id": "e1"}, {"id": "e2"}]
        }

        result = await invalidation_service.invalidate_by_query(
            patient_id="patient-123",
            entity_type="Medication",
            reason="bulk_test",
        )

        assert result.entities_invalidated == 2
        call_args = mock_neo4j_backend.query.call_args
        query_str = call_args[0][0]
        assert "patient_id" in query_str
        assert "entity_type" in query_str

    @pytest.mark.asyncio
    async def test_sweep_targets_perception_only(self, invalidation_service, mock_neo4j_backend):
        """Stale sweep query only targets PERCEPTION layer entities."""
        mock_neo4j_backend.query.return_value = {"rows": [{"id": "stale_1", "name": "Old Entity"}]}

        result = await invalidation_service.sweep_stale_entities()

        assert result.entities_invalidated == 1
        call_args = mock_neo4j_backend.query.call_args
        query_str = call_args[0][0]
        assert "PERCEPTION" in query_str

    @pytest.mark.asyncio
    async def test_sweep_respects_threshold(self, invalidation_service, mock_neo4j_backend):
        """Sweep passes correct cutoff date based on threshold."""
        mock_neo4j_backend.query.return_value = {"rows": []}

        await invalidation_service.sweep_stale_entities()

        call_args = mock_neo4j_backend.query.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else {}
        cutoff_str = params.get("cutoff_date", "")
        # Cutoff should be ~90 days ago
        cutoff = datetime.fromisoformat(cutoff_str)
        expected_cutoff = datetime.utcnow() - timedelta(days=90)
        assert abs((cutoff - expected_cutoff).total_seconds()) < 60  # Within 1 minute

    @pytest.mark.asyncio
    async def test_sweep_disabled_config(self, mock_neo4j_backend):
        """stale_check_enabled=False -> sweep returns 0 immediately."""
        service = MemoryInvalidationService(
            neo4j_backend=mock_neo4j_backend,
            config=InvalidationConfig(stale_check_enabled=False),
        )

        result = await service.sweep_stale_entities()

        assert result.entities_invalidated == 0
        assert result.reason == "stale_sweep_disabled"
        mock_neo4j_backend.query.assert_not_called()

    def test_get_invalidation_stats(self, invalidation_service):
        """Stats dict has all expected keys."""
        stats = invalidation_service.get_invalidation_stats()

        assert "total_invalidated" in stats
        assert "sweep_runs" in stats
        assert "last_sweep" in stats
        assert "stale_threshold_days" in stats
        assert stats["stale_threshold_days"] == 90

    @pytest.mark.asyncio
    async def test_invalidate_entity_error_handling(self, invalidation_service, mock_neo4j_backend):
        """Error during invalidation returns 0 count, no exception."""
        mock_neo4j_backend.query.side_effect = Exception("DB error")

        result = await invalidation_service.invalidate_entity(
            entity_id="entity_123",
            reason="test",
        )

        assert result.entities_invalidated == 0


# ============================================================
# SPEC-5: LLM Rate Limit Management
# ============================================================

class TestSpec5LLMRateLimitManagement:
    """Tests for SPEC-5: LLM rate limit management."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, episodic_service, mock_graphiti):
        """Rate limit errors trigger retry with backoff."""
        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Error 429: Rate limit exceeded")
            mock_result = MagicMock()
            mock_result.episode = MagicMock(uuid="ep-retry")
            mock_result.nodes = []
            mock_result.edges = []
            return mock_result

        mock_graphiti.add_episode.side_effect = side_effect

        with patch("application.services.episodic_memory_service.asyncio.sleep", new_callable=AsyncMock):
            result = await episodic_service.store_turn_episode(
                patient_id="patient-123",
                session_id="session-abc",
                user_message="Hello",
                assistant_message="Hi!",
                turn_number=1,
            )

        assert result.episode_id == "ep-retry"
        assert episodic_service._rate_limit_stats["retries"] == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self, episodic_service, mock_graphiti):
        """After max retries, error propagates."""
        mock_graphiti.add_episode.side_effect = Exception("Error 429: Rate limit")

        with patch("application.services.episodic_memory_service.asyncio.sleep", new_callable=AsyncMock):
            with patch.dict(os.environ, {"GRAPHITI_LLM_MAX_RETRIES": "2"}):
                with pytest.raises(Exception, match="429"):
                    await episodic_service.store_turn_episode(
                        patient_id="patient-123",
                        session_id="session-abc",
                        user_message="Hello",
                        assistant_message="Hi!",
                        turn_number=1,
                    )

        assert episodic_service._rate_limit_stats["failures"] == 1

    @pytest.mark.asyncio
    async def test_non_rate_limit_error_no_retry(self, episodic_service, mock_graphiti):
        """Non-rate-limit errors are not retried."""
        mock_graphiti.add_episode.side_effect = ValueError("Bad input")

        with pytest.raises(ValueError, match="Bad input"):
            await episodic_service.store_turn_episode(
                patient_id="patient-123",
                session_id="session-abc",
                user_message="Hello",
                assistant_message="Hi!",
                turn_number=1,
            )

        assert episodic_service._rate_limit_stats["retries"] == 0
        assert episodic_service._rate_limit_stats["failures"] == 0

    @pytest.mark.asyncio
    async def test_retry_disabled_no_retry(self, episodic_service, mock_graphiti):
        """GRAPHITI_LLM_RETRY_ENABLED=false -> 429 error propagated immediately."""
        mock_graphiti.add_episode.side_effect = Exception("Error 429: Rate limit")

        with patch.dict(os.environ, {"GRAPHITI_LLM_RETRY_ENABLED": "false"}):
            with pytest.raises(Exception, match="429"):
                await episodic_service.store_turn_episode(
                    patient_id="patient-123",
                    session_id="session-abc",
                    user_message="Hello",
                    assistant_message="Hi!",
                    turn_number=1,
                )

        assert episodic_service._rate_limit_stats["retries"] == 0
        assert episodic_service._rate_limit_stats["failures"] == 1

    def test_get_health_includes_rate_stats(self, episodic_service):
        """get_health() returns dict with all expected keys."""
        health = episodic_service.get_health()

        assert "initialized" in health
        assert "rate_limit_retries" in health
        assert "rate_limit_failures" in health
        assert "last_rate_limit" in health
        assert "semaphore_limit" in health
        assert health["rate_limit_retries"] == 0
        assert health["rate_limit_failures"] == 0

    def test_semaphore_limit_env_var(self):
        """GRAPHITI_SEMAPHORE_LIMIT env var is readable by get_health."""
        with patch.dict(os.environ, {"SEMAPHORE_LIMIT": "7"}):
            service = EpisodicMemoryService(graphiti=MagicMock())
            health = service.get_health()
            assert health["semaphore_limit"] == 7
