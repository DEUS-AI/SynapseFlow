"""Tests for DeduplicationService.

Covers:
- Duplicate detection (case-insensitive, same-type, exclude merged/structural)
- Merge plan creation (winner selection by relationships, confidence)
- Merge execution (relationship transfer, audit trail)
"""

import pytest
from application.services.deduplication_service import (
    DeduplicationService,
    DuplicatePair,
    MergePlan,
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
