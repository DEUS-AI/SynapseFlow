"""Tests for DeduplicationService.

Covers:
- Duplicate detection (case-insensitive, same-type, exclude merged/structural)
- Merge plan creation (winner selection by relationships, confidence)
- Merge execution (relationship transfer, audit trail)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from application.services.deduplication_service import (
    DeduplicationService,
    DuplicatePair,
)


class TestCreateMergePlan:
    """Test merge plan winner selection logic."""

    def test_winner_has_more_relationships(self):
        pair = DuplicatePair(
            entity_a_id="a1", entity_a_name="Aspirin",
            entity_b_id="b1", entity_b_name="aspirin",
            entity_type="drug",
            a_relationship_count=5, b_relationship_count=2,
            a_confidence=0.8, b_confidence=0.9,
        )
        service = DeduplicationService.__new__(DeduplicationService)
        plans = service.create_merge_plan([pair])
        assert len(plans) == 1
        assert plans[0].winner_id == "a1"
        assert plans[0].loser_id == "b1"

    def test_winner_has_higher_confidence_on_tie(self):
        pair = DuplicatePair(
            entity_a_id="a1", entity_a_name="Aspirin",
            entity_b_id="b1", entity_b_name="aspirin",
            entity_type="drug",
            a_relationship_count=3, b_relationship_count=3,
            a_confidence=0.8, b_confidence=0.95,
        )
        service = DeduplicationService.__new__(DeduplicationService)
        plans = service.create_merge_plan([pair])
        assert plans[0].winner_id == "b1"
        assert plans[0].loser_id == "a1"

    def test_equal_stats_selects_a_as_winner(self):
        pair = DuplicatePair(
            entity_a_id="a1", entity_a_name="Aspirin",
            entity_b_id="b1", entity_b_name="aspirin",
            entity_type="drug",
            a_relationship_count=3, b_relationship_count=3,
            a_confidence=0.9, b_confidence=0.9,
        )
        service = DeduplicationService.__new__(DeduplicationService)
        plans = service.create_merge_plan([pair])
        assert plans[0].winner_id == "a1"

    def test_multiple_pairs_produce_multiple_plans(self):
        pairs = [
            DuplicatePair(
                entity_a_id="a1", entity_a_name="X",
                entity_b_id="b1", entity_b_name="x",
                entity_type="drug",
                a_relationship_count=1, b_relationship_count=0,
            ),
            DuplicatePair(
                entity_a_id="a2", entity_a_name="Y",
                entity_b_id="b2", entity_b_name="y",
                entity_type="gene",
                a_relationship_count=0, b_relationship_count=5,
            ),
        ]
        service = DeduplicationService.__new__(DeduplicationService)
        plans = service.create_merge_plan(pairs)
        assert len(plans) == 2
        assert plans[0].winner_id == "a1"
        assert plans[1].winner_id == "b2"

    def test_rationale_explains_selection(self):
        pair = DuplicatePair(
            entity_a_id="a1", entity_a_name="Test",
            entity_b_id="b1", entity_b_name="test",
            entity_type="drug",
            a_relationship_count=10, b_relationship_count=2,
        )
        service = DeduplicationService.__new__(DeduplicationService)
        plans = service.create_merge_plan([pair])
        assert "more relationships" in plans[0].rationale


class TestDetectDuplicatesQuery:
    """Test that the detection query is well-formed."""

    def test_query_uses_case_insensitive_match(self):
        from application.services.deduplication_service import DETECT_DUPLICATES_QUERY
        assert "toLower" in DETECT_DUPLICATES_QUERY

    def test_query_excludes_merged_entities(self):
        from application.services.deduplication_service import DETECT_DUPLICATES_QUERY
        assert "_merged_into" in DETECT_DUPLICATES_QUERY

    def test_query_excludes_structural_entities(self):
        from application.services.deduplication_service import DETECT_DUPLICATES_QUERY
        assert "_is_structural" in DETECT_DUPLICATES_QUERY

    def test_query_matches_same_type_only(self):
        from application.services.deduplication_service import DETECT_DUPLICATES_QUERY
        assert "a.type = b.type" in DETECT_DUPLICATES_QUERY

    def test_query_excludes_dismissed_entities(self):
        from application.services.deduplication_service import DETECT_DUPLICATES_QUERY
        assert "_dedup_skip" in DETECT_DUPLICATES_QUERY


class TestMergeExecution:
    """Test merge execution queries are well-formed."""

    def test_mark_merged_sets_audit_fields(self):
        from application.services.deduplication_service import MARK_MERGED_QUERY
        assert "_merged_into" in MARK_MERGED_QUERY
        assert "_merged_date" in MARK_MERGED_QUERY
        assert "_dedup_batch" in MARK_MERGED_QUERY

    def test_delete_only_marked_entities(self):
        from application.services.deduplication_service import DELETE_LOSER_QUERY
        assert "_merged_into IS NOT NULL" in DELETE_LOSER_QUERY

    def test_transfer_skips_duplicate_relationships(self):
        from application.services.deduplication_service import TRANSFER_INCOMING_RELS_QUERY
        assert "NOT EXISTS" in TRANSFER_INCOMING_RELS_QUERY


class TestCrossTypeDetection:
    """Test cross-type duplicate detection logic."""

    @pytest.fixture
    def service_with_mock_driver(self):
        driver = AsyncMock()
        service = DeduplicationService(driver)
        return service, driver

    def _make_mock_session(self, driver, records):
        """Helper to set up a mock Neo4j session with async iteration."""
        async def mock_aiter(self_iter):
            for r in records:
                mock_record = MagicMock()
                mock_record.data.return_value = r
                yield mock_record

        mock_result = MagicMock()
        mock_result.__aiter__ = mock_aiter

        mock_session = AsyncMock()
        mock_session.run.return_value = mock_result

        # driver.session() must be a regular call returning an async context manager
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = False
        driver.session = MagicMock(return_value=mock_ctx)

    @pytest.mark.asyncio
    async def test_cross_type_group_detected(self, service_with_mock_driver):
        """Entities with same canonical name but different types are detected."""
        service, driver = service_with_mock_driver
        records = [
            {"id": "e1", "name": "corticosteroids", "type": "Drug", "rel_count": 3},
            {"id": "e2", "name": "Corticosteroids", "type": "Treatment", "rel_count": 1},
        ]
        self._make_mock_session(driver, records)

        groups = await service.detect_cross_type_duplicates()
        assert len(groups) == 1
        assert groups[0].canonical_form == "corticosteroids"
        assert groups[0].entity_count == 2
        types = {e["type"] for e in groups[0].entities}
        assert types == {"Drug", "Treatment"}

    @pytest.mark.asyncio
    async def test_same_type_excluded_from_cross_type(self, service_with_mock_driver):
        """Same-type duplicates are not reported as cross-type."""
        service, driver = service_with_mock_driver
        records = [
            {"id": "e1", "name": "Aspirin", "type": "Drug", "rel_count": 5},
            {"id": "e2", "name": "aspirin", "type": "Drug", "rel_count": 2},
        ]
        self._make_mock_session(driver, records)

        groups = await service.detect_cross_type_duplicates()
        assert len(groups) == 0

    def test_fetch_all_query_excludes_dismissed(self):
        from application.services.deduplication_service import FETCH_ALL_ENTITIES_QUERY
        assert "_dedup_skip" in FETCH_ALL_ENTITIES_QUERY
        assert "_merged_into" in FETCH_ALL_ENTITIES_QUERY
        assert "_is_structural" in FETCH_ALL_ENTITIES_QUERY


class TestDismissEntities:
    """Test dismiss/undismiss query structure."""

    def test_dismiss_query_sets_dedup_skip(self):
        from application.services.deduplication_service import DISMISS_ENTITIES_QUERY
        assert "_dedup_skip" in DISMISS_ENTITIES_QUERY
        assert "true" in DISMISS_ENTITIES_QUERY.lower()

    def test_undismiss_query_removes_dedup_skip(self):
        from application.services.deduplication_service import UNDISMISS_ENTITIES_QUERY
        assert "REMOVE" in UNDISMISS_ENTITIES_QUERY
        assert "_dedup_skip" in UNDISMISS_ENTITIES_QUERY
