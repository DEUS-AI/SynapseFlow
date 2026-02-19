"""Tests for RemediationService with mocked Neo4j backend.

Covers task 6.3:
- dry_run() returns preview without modifying data
- execute() runs all queries and returns results
- rollback() removes remediation properties
- get_orphans() lists flagged entities
"""

import pytest
from unittest.mock import MagicMock

from application.services.remediation_service import (
    RemediationService,
    REMEDIATION_QUERIES,
    MARK_STRUCTURAL_QUERY,
    PRE_STATS_QUERY,
    UNMAPPED_TYPES_QUERY,
    _convert_to_count_query,
)


class MockResult:
    """Mock Neo4j result that supports both single() and async iteration."""

    def __init__(self, record=None, iter_records=None):
        self._record = record
        self._iter_records = iter_records or []

    async def single(self):
        return self._record

    def __aiter__(self):
        return self._async_iter()

    async def _async_iter(self):
        for r in self._iter_records:
            yield r


class MockSession:
    """Mock Neo4j async session supporting 'async with driver.session() as s'."""

    def __init__(self, records):
        self.records = records

    async def run(self, query, params=None):
        # Determine which kind of record to return based on query content
        if "would_update" in query:
            return MockResult(record={"would_update": self.records.get("would_update", 0)})
        elif "rolled_back" in query:
            return MockResult(record={"rolled_back": self.records.get("rolled_back", 5)})
        elif "knowledge_entities" in query or "as total" in query:
            return MockResult(record={
                "total": self.records.get("total", 100),
                "knowledge_entities": self.records.get("knowledge_entities", 50),
                "already_mapped": self.records.get("already_mapped", 10),
                "structural_entities": self.records.get("structural_entities", 30),
                "excluded_entities": self.records.get("excluded_entities", 20),
            })
        elif "_is_orphan" in query:
            return MockResult(iter_records=self.records.get("orphan_records", []))
        elif "n.type as type" in query:
            return MockResult(iter_records=self.records.get("type_records", []))
        else:
            return MockResult(record={"updated": self.records.get("updated", 3)})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def make_mock_driver(records=None):
    """Create a mock Neo4j async driver."""
    if records is None:
        records = {}

    driver = MagicMock()
    session = MockSession(records)
    driver.session.return_value = session
    return driver


class TestConvertToCountQuery:
    """Test the _convert_to_count_query helper."""

    def test_simple_query_conversion(self):
        query = """
        MATCH (n)
        WHERE n.type = 'Disease'
        SET n._ontology_mapped = true
        RETURN count(n) as updated
        """
        count_query = _convert_to_count_query(query)
        assert "RETURN count(n) as would_update" in count_query
        assert "SET" not in count_query
        assert "MATCH (n)" in count_query
        assert "WHERE n.type = 'Disease'" in count_query

    def test_all_remediation_queries_convert(self):
        """Every remediation query should convert to a valid count query."""
        for name, desc, query in REMEDIATION_QUERIES:
            count_query = _convert_to_count_query(query)
            assert "RETURN count(n) as would_update" in count_query, (
                f"Query {name} failed to convert"
            )
            assert "SET" not in count_query, (
                f"Query {name} still contains SET after conversion"
            )


class TestNewRemediationQueries:
    """Test cytokine_mapping and chemical_mapping queries exist and are well-formed."""

    def test_cytokine_mapping_exists(self):
        names = [name for name, _, _ in REMEDIATION_QUERIES]
        assert "cytokine_mapping" in names

    def test_chemical_mapping_exists(self):
        names = [name for name, _, _ in REMEDIATION_QUERIES]
        assert "chemical_mapping" in names

    def test_cytokine_mapping_targets_protein(self):
        for name, desc, query in REMEDIATION_QUERIES:
            if name == "cytokine_mapping":
                assert "'protein'" in query
                assert "_original_type" in query
                assert "NOT coalesce(n._ontology_mapped, false)" in query
                break

    def test_chemical_mapping_targets_drug(self):
        for name, desc, query in REMEDIATION_QUERIES:
            if name == "chemical_mapping":
                assert "'drug'" in query
                assert "_original_type" in query
                assert "NOT coalesce(n._ontology_mapped, false)" in query
                break

    def test_cytokine_mapping_skips_already_mapped(self):
        for name, _, query in REMEDIATION_QUERIES:
            if name == "cytokine_mapping":
                assert "NOT coalesce(n._ontology_mapped, false)" in query
                break

    def test_chemical_mapping_skips_already_mapped(self):
        for name, _, query in REMEDIATION_QUERIES:
            if name == "chemical_mapping":
                assert "NOT coalesce(n._ontology_mapped, false)" in query
                break


class TestRemediationServiceDryRun:
    """Test RemediationService.dry_run()."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_preview(self):
        driver = make_mock_driver({"would_update": 5, "total": 100, "knowledge_entities": 50})
        service = RemediationService(driver)

        results = await service.dry_run()

        assert "pre_stats" in results
        assert "unmapped_types" in results
        assert "remediation_preview" in results
        assert "total_would_update" in results

    @pytest.mark.asyncio
    async def test_dry_run_preview_has_all_queries(self):
        driver = make_mock_driver({"would_update": 2})
        service = RemediationService(driver)

        results = await service.dry_run()

        assert len(results["remediation_preview"]) == len(REMEDIATION_QUERIES)

    @pytest.mark.asyncio
    async def test_dry_run_sums_updates(self):
        driver = make_mock_driver({"would_update": 3})
        service = RemediationService(driver)

        results = await service.dry_run()

        expected = 3 * len(REMEDIATION_QUERIES)
        assert results["total_would_update"] == expected


class TestRemediationServiceExecute:
    """Test RemediationService.execute()."""

    @pytest.mark.asyncio
    async def test_execute_returns_batch_id(self):
        driver = make_mock_driver({"updated": 2})
        service = RemediationService(driver)

        results = await service.execute()

        assert "batch_id" in results
        assert "started_at" in results
        assert "completed_at" in results

    @pytest.mark.asyncio
    async def test_execute_runs_all_steps(self):
        driver = make_mock_driver({"updated": 1})
        service = RemediationService(driver)

        results = await service.execute()

        assert len(results["steps"]) == len(REMEDIATION_QUERIES)

    @pytest.mark.asyncio
    async def test_execute_calculates_coverage(self):
        driver = make_mock_driver({
            "updated": 5,
            "total": 100,
            "knowledge_entities": 50,
            "already_mapped": 10,
        })
        service = RemediationService(driver)

        results = await service.execute()

        assert "coverage_before" in results
        assert "coverage_after" in results

    @pytest.mark.asyncio
    async def test_execute_marks_structural(self):
        driver = make_mock_driver({"updated": 10})
        service = RemediationService(driver)

        results = await service.execute(mark_structural=True)

        assert "structural_marked" in results

    @pytest.mark.asyncio
    async def test_execute_skip_structural(self):
        driver = make_mock_driver({"updated": 10})
        service = RemediationService(driver)

        results = await service.execute(mark_structural=False, mark_noise=False)

        assert "structural_marked" not in results
        assert "noise_marked" not in results


class TestRemediationServiceRollback:
    """Test RemediationService.rollback()."""

    @pytest.mark.asyncio
    async def test_rollback_returns_count(self):
        driver = make_mock_driver({"rolled_back": 15})
        service = RemediationService(driver)

        results = await service.rollback("20260212_120000")

        assert results["batch_id"] == "20260212_120000"
        assert results["rolled_back"] == 15


class TestRemediationServiceOrphans:
    """Test RemediationService.get_orphans()."""

    @pytest.mark.asyncio
    async def test_get_orphans_returns_list(self):
        mock_records = [
            {
                "id": "ent-1",
                "name": "Orphan Entity",
                "type": "Disease",
                "labels": ["Disease", "Entity"],
                "canonical_type": "disease",
                "layer": "SEMANTIC",
            }
        ]
        driver = make_mock_driver({"orphan_records": mock_records})
        service = RemediationService(driver)

        orphans = await service.get_orphans(limit=10)

        assert len(orphans) == 1
        assert orphans[0]["id"] == "ent-1"
        assert orphans[0]["name"] == "Orphan Entity"


class TestConversationNodeReclassification:
    """Tests for reclassifying ConversationSession/Message as structural."""

    def test_no_conversation_mapping_in_remediation_queries(self):
        """conversation_mapping query should not exist in REMEDIATION_QUERIES."""
        query_names = [name for name, _, _ in REMEDIATION_QUERIES]
        assert "conversation_mapping" not in query_names

    def test_no_conversation_usage_mapping(self):
        """No query should map ConversationSession/Message to usage."""
        for name, desc, query in REMEDIATION_QUERIES:
            if "ConversationSession" in query or "Message" in query:
                assert "_canonical_type = 'usage'" not in query, (
                    f"Query {name} maps conversation nodes to usage"
                )

    def test_mark_structural_includes_conversation_labels(self):
        """MARK_STRUCTURAL_QUERY should include ConversationSession and Message."""
        assert "ConversationSession" in MARK_STRUCTURAL_QUERY
        assert "Message" in MARK_STRUCTURAL_QUERY

    def test_pre_stats_includes_conversation_labels(self):
        """PRE_STATS_QUERY should detect ConversationSession/Message as structural."""
        assert "ConversationSession" in PRE_STATS_QUERY
        assert "Message" in PRE_STATS_QUERY

    def test_unmapped_types_excludes_conversation_labels(self):
        """UNMAPPED_TYPES_QUERY should exclude ConversationSession/Message."""
        assert "ConversationSession" in UNMAPPED_TYPES_QUERY
        assert "Message" in UNMAPPED_TYPES_QUERY

    def test_migration_query_exists(self):
        """A migration query for conversation nodes should exist."""
        query_names = [name for name, _, _ in REMEDIATION_QUERIES]
        assert "conversation_structural_migration" in query_names

    def test_migration_query_is_first(self):
        """Migration query should run before type-mapping queries."""
        first_name = REMEDIATION_QUERIES[0][0]
        assert first_name == "conversation_structural_migration"

    def test_migration_query_is_idempotent(self):
        """Migration query should be guarded by NOT _is_structural."""
        _, _, query = REMEDIATION_QUERIES[0]
        assert "NOT coalesce(n._is_structural, false)" in query

    def test_migration_query_removes_ontology_mapping(self):
        """Migration query should REMOVE _ontology_mapped and _canonical_type."""
        _, _, query = REMEDIATION_QUERIES[0]
        assert "REMOVE" in query
        assert "_ontology_mapped" in query
        assert "_canonical_type" in query

    def test_migration_query_sets_structural(self):
        """Migration query should SET _is_structural and _exclude_from_ontology."""
        _, _, query = REMEDIATION_QUERIES[0]
        assert "_is_structural = true" in query
        assert "_exclude_from_ontology = true" in query
