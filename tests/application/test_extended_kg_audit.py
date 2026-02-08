"""Tests for Extended KG Audit and Chunk Impact Analysis services.

These tests validate the audit services without requiring a live Neo4j connection
by using mock backends.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from domain.chunk_separation_models import (
    SubgraphType,
    SubgraphMetrics,
    BridgeNodeMetrics,
    CoOccurrencePattern,
    QueryPathAnalysis,
    ExtendedKGAuditReport,
    ChunkSeparationOption,
    ChunkSeparationRecommendation,
    ChunkImpactReport,
    ImpactSeverity,
    ServiceImpact,
)
from application.services.extended_kg_audit_service import ExtendedKGAuditService
from application.services.chunk_impact_analyzer import (
    ChunkImpactAnalyzer,
    ChunkDependency,
    CHUNK_DEPENDENCIES,
)


class TestDomainModels:
    """Test domain models for chunk separation."""

    def test_subgraph_metrics_creation(self):
        """Test SubgraphMetrics dataclass."""
        metrics = SubgraphMetrics(
            subgraph_type=SubgraphType.DOCUMENT_GRAPH,
            node_count=1000,
            relationship_count=2000,
            node_labels={"Chunk": 800, "Document": 200},
            avg_degree=2.0,
        )

        assert metrics.subgraph_type == SubgraphType.DOCUMENT_GRAPH
        assert metrics.node_count == 1000
        assert metrics.relationship_count == 2000

    def test_subgraph_metrics_to_dict(self):
        """Test SubgraphMetrics serialization."""
        metrics = SubgraphMetrics(
            subgraph_type=SubgraphType.KNOWLEDGE_GRAPH,
            node_count=500,
            relationship_count=1000,
            percentage_of_total=33.5,
        )

        data = metrics.to_dict()

        assert data["subgraph_type"] == "knowledge_graph"
        assert data["node_count"] == 500
        assert data["percentage_of_total"] == 33.5

    def test_bridge_node_metrics(self):
        """Test BridgeNodeMetrics dataclass."""
        bridge = BridgeNodeMetrics(
            bridge_node_count=50,
            bridge_relationship_count=200,
            bridge_node_types={"Disease": 30, "Drug": 20},
            top_bridge_nodes=[
                {"name": "Diabetes", "labels": ["Disease"], "incoming_links": 50}
            ],
        )

        data = bridge.to_dict()

        assert data["bridge_node_count"] == 50
        assert data["bridge_relationship_count"] == 200
        assert "Disease" in data["bridge_node_types"]

    def test_co_occurrence_pattern(self):
        """Test CoOccurrencePattern dataclass."""
        pattern = CoOccurrencePattern(
            type_pair=("Disease", "Drug"),
            co_occurrence_count=150,
            avg_confidence=0.85,
        )

        data = pattern.to_dict()

        assert data["type_pair"] == ["Disease", "Drug"]
        assert data["co_occurrence_count"] == 150
        assert data["avg_confidence"] == 0.85

    def test_extended_audit_report_separation_readiness(self):
        """Test separation readiness computation."""
        report = ExtendedKGAuditReport(
            total_entities=10000,
            bridge_metrics=BridgeNodeMetrics(
                bridge_node_count=500,  # 5% bridge ratio
                bridge_relationship_count=1000,
            ),
            document_graph=SubgraphMetrics(
                subgraph_type=SubgraphType.DOCUMENT_GRAPH,
                node_count=7500,  # 75% - dominates
            ),
            co_occurrence_patterns=[
                CoOccurrencePattern(type_pair=("A", "B"), co_occurrence_count=10)
                for _ in range(30)  # 30 patterns
            ],
        )

        readiness = report.compute_separation_readiness()

        # 75% document graph should add an issue
        assert any("Document Graph dominates" in issue for issue in report.identified_issues)
        assert readiness in ["ready", "needs_work", "not_ready"]

    def test_service_impact_model(self):
        """Test ServiceImpact dataclass."""
        impact = ServiceImpact(
            service_name="RAGService",
            file_path="src/application/services/rag_service.py",
            impact_severity=ImpactSeverity.HIGH,
            affected_queries=["MATCH (c:Chunk)-[:MENTIONS]->(e)"],
            refactoring_required="Cross-store join logic",
            estimated_effort_hours=8.0,
        )

        data = impact.to_dict()

        assert data["service_name"] == "RAGService"
        assert data["impact_severity"] == "high"
        assert data["estimated_effort_hours"] == 8.0

    def test_chunk_separation_recommendation(self):
        """Test ChunkSeparationRecommendation dataclass."""
        rec = ChunkSeparationRecommendation(
            recommended_option=ChunkSeparationOption.OPTION_A,
            confidence=0.85,
            rationale=["Low data volume", "Simple queries"],
            decision_criteria_met={"chunk_count_manageable": True},
            next_steps=["Add indexes", "Monitor performance"],
        )

        data = rec.to_dict()

        assert data["recommended_option"] == "keep_neo4j_with_indexes"
        assert data["confidence"] == 0.85
        assert len(data["rationale"]) == 2


class TestExtendedKGAuditService:
    """Test ExtendedKGAuditService."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock Neo4j backend."""
        backend = AsyncMock()
        backend.query_raw = AsyncMock()
        return backend

    @pytest.fixture
    def audit_service(self, mock_backend):
        """Create audit service with mock backend."""
        return ExtendedKGAuditService(mock_backend)

    @pytest.mark.asyncio
    async def test_run_extended_audit_basic(self, audit_service, mock_backend):
        """Test basic extended audit execution."""
        # Setup mock responses
        mock_backend.query_raw.side_effect = [
            # Base metrics - total entities
            [{"count": 15000}],
            # Base metrics - total relationships
            [{"count": 30000}],
            # Base metrics - orphans
            [{"count": 45}],
            # Subgraph node distribution
            [
                {"subgraph": "document_graph", "primary_label": "Chunk", "count": 10000},
                {"subgraph": "document_graph", "primary_label": "Document", "count": 500},
                {"subgraph": "knowledge_graph", "primary_label": "Disease", "count": 200},
            ],
            # Subgraph relationship distribution
            [
                {"subgraph": "document_graph", "rel_type": "HAS_CHUNK", "count": 10000},
                {"subgraph": "bridge", "rel_type": "LINKS_TO", "count": 5000},
            ],
            # Document graph stats
            [{"node_count": 10500, "avg_degree": 2.5, "isolated_count": 10}],
            # Knowledge graph stats
            [{"node_count": 4500, "avg_degree": 3.0, "isolated_count": 5}],
            # Bridge nodes
            [{"source_labels": ["ExtractedEntity"], "target_labels": ["Disease"], "bridge_count": 100}],
            # Top bridge nodes
            [{"name": "Diabetes", "labels": ["Disease"], "incoming_links": 50}],
            # Co-occurrence patterns
            [{"type1": "Disease", "type2": "Drug", "co_count": 150}],
            # Document chunk entity path
            [{"path_length": 3, "frequency": 5000}],
            # Entity links depth
            [{"depth": 1, "frequency": 3000}],
        ]

        report = await audit_service.run_extended_audit()

        assert report.audit_id is not None
        assert report.total_entities == 15000
        assert report.total_orphans == 45
        assert report.orphan_rate == pytest.approx(0.003, rel=0.01)
        assert report.document_graph is not None
        assert report.knowledge_graph is not None
        assert report.bridge_metrics is not None
        assert len(report.co_occurrence_patterns) >= 1
        assert report.processing_time_ms >= 0  # Can be 0 for fast execution

    @pytest.mark.asyncio
    async def test_audit_handles_empty_results(self, audit_service, mock_backend):
        """Test audit handles empty query results gracefully."""
        mock_backend.query_raw.return_value = []

        report = await audit_service.run_extended_audit()

        assert report.total_entities == 0
        assert report.total_relationships == 0
        assert report.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_audit_handles_query_errors(self, audit_service, mock_backend):
        """Test audit handles query errors gracefully."""
        mock_backend.query_raw.side_effect = Exception("Connection failed")

        report = await audit_service.run_extended_audit()

        # Should still return a report with error logged in issues
        assert report.audit_id is not None
        # Error is logged in identified_issues
        assert len(report.identified_issues) >= 1 or report.total_entities == 0

    def test_format_markdown_report(self, audit_service):
        """Test markdown report generation."""
        report = ExtendedKGAuditReport(
            audit_id="test123",
            total_entities=10000,
            total_relationships=20000,
            total_orphans=50,
            orphan_rate=0.005,
            document_graph=SubgraphMetrics(
                subgraph_type=SubgraphType.DOCUMENT_GRAPH,
                node_count=7000,
                relationship_count=14000,
                node_labels={"Chunk": 6000, "Document": 1000},
                percentage_of_total=70.0,
                avg_degree=2.0,
            ),
            knowledge_graph=SubgraphMetrics(
                subgraph_type=SubgraphType.KNOWLEDGE_GRAPH,
                node_count=3000,
                relationship_count=6000,
                node_labels={"Disease": 500, "Drug": 300},
                percentage_of_total=30.0,
                avg_degree=3.0,
            ),
            bridge_metrics=BridgeNodeMetrics(
                bridge_node_count=20,
                bridge_relationship_count=500,
                bridge_node_types={"Disease": 10, "Drug": 10},
            ),
            separation_readiness="ready",
            recommendations=["Use Option A"],
        )

        markdown = audit_service._format_markdown_report(report)

        assert "# Extended Knowledge Graph Audit Report" in markdown
        assert "test123" in markdown
        assert "10,000" in markdown or "10000" in markdown
        assert "Document Graph" in markdown
        assert "Knowledge Graph" in markdown
        assert "ready" in markdown.lower() or "READY" in markdown


class TestChunkImpactAnalyzer:
    """Test ChunkImpactAnalyzer."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock Neo4j backend."""
        backend = AsyncMock()
        backend.query_raw = AsyncMock()
        return backend

    @pytest.fixture
    def analyzer(self, mock_backend):
        """Create analyzer with mock backend."""
        return ChunkImpactAnalyzer(mock_backend)

    def test_known_chunk_dependencies(self):
        """Test that chunk dependencies are defined."""
        assert len(CHUNK_DEPENDENCIES) >= 3

        service_names = [d.service_name for d in CHUNK_DEPENDENCIES]
        assert "RAGService" in service_names
        assert "DocumentRouter" in service_names

    def test_analyze_service_impacts(self, analyzer):
        """Test service impact analysis."""
        impacts = analyzer._analyze_service_impacts()

        assert len(impacts) >= 3

        # Check RAGService impact
        rag_impact = next(i for i in impacts if i.service_name == "RAGService")
        assert rag_impact.impact_severity in [ImpactSeverity.MEDIUM, ImpactSeverity.HIGH]
        assert rag_impact.estimated_effort_hours > 0

        # Check write service has CRITICAL severity
        write_impacts = [i for i in impacts if i.impact_severity == ImpactSeverity.CRITICAL]
        assert len(write_impacts) >= 1

    @pytest.mark.asyncio
    async def test_analyze_impact_with_backend(self, analyzer, mock_backend):
        """Test full impact analysis with mock backend."""
        # Setup mock responses
        mock_backend.query_raw.side_effect = [
            # Chunk count and size
            [{"chunk_count": 10000, "avg_text_size": 1500, "total_bytes": 15000000}],
            # Mentions count
            [{"mentions_count": 8000}],
            # Bridge traversals
            [{"bridge_traversals": 3000}],
        ]

        report = await analyzer.analyze_impact()

        assert report.report_id is not None
        assert len(report.service_impacts) >= 3
        assert report.data_volume_mb > 0
        assert report.recommendation is not None
        assert report.recommendation.recommended_option in ChunkSeparationOption

    @pytest.mark.asyncio
    async def test_analyze_impact_without_backend(self):
        """Test impact analysis without backend."""
        analyzer = ChunkImpactAnalyzer(None)

        report = await analyzer.analyze_impact()

        # Should still work, just without live metrics
        assert report.report_id is not None
        assert len(report.service_impacts) >= 3
        assert report.recommendation is not None

    def test_option_a_analysis(self, analyzer):
        """Test Option A analysis."""
        report = ChunkImpactReport()
        analysis = analyzer._analyze_option_a(report)

        assert analysis.option == ChunkSeparationOption.OPTION_A
        assert analysis.implementation_effort_days == 1
        assert analysis.risk_level == "low"
        assert analysis.rollback_complexity == "none"
        assert len(analysis.pros) >= 3
        assert len(analysis.required_changes) >= 2
        assert analysis.weighted_score > 0

    def test_option_b_analysis(self, analyzer):
        """Test Option B analysis."""
        report = ChunkImpactReport()
        analysis = analyzer._analyze_option_b(report)

        assert analysis.option == ChunkSeparationOption.OPTION_B
        assert analysis.implementation_effort_days == 10
        assert analysis.risk_level == "medium"
        assert len(analysis.affected_services) >= 3
        assert analysis.weighted_score > 0

    def test_option_c_analysis(self, analyzer):
        """Test Option C analysis."""
        report = ChunkImpactReport()
        analysis = analyzer._analyze_option_c(report)

        assert analysis.option == ChunkSeparationOption.OPTION_C
        assert analysis.implementation_effort_days == 20
        assert analysis.risk_level == "high"
        assert "Infrastructure" in analysis.affected_services
        assert analysis.weighted_score > 0

    def test_recommendation_generation(self, analyzer):
        """Test recommendation generation logic."""
        report = ChunkImpactReport(
            data_volume_mb=50.0,
            cross_store_join_complexity="simple",
            consistency_risk="low",
        )

        option_analyses = {
            ChunkSeparationOption.OPTION_A: analyzer._analyze_option_a(report),
            ChunkSeparationOption.OPTION_B: analyzer._analyze_option_b(report),
            ChunkSeparationOption.OPTION_C: analyzer._analyze_option_c(report),
        }

        rec = analyzer._generate_recommendation(option_analyses, report)

        assert rec.recommended_option is not None
        assert 0 < rec.confidence <= 1.0
        assert len(rec.rationale) >= 2
        assert len(rec.next_steps) >= 3
        assert isinstance(rec.decision_criteria_met, dict)

    def test_format_markdown_report(self, analyzer):
        """Test markdown report formatting."""
        report = ChunkImpactReport(
            report_id="impact_test",
            data_volume_mb=50.0,
            estimated_migration_time_hours=0.5,
            cross_store_join_complexity="simple",
            consistency_risk="low",
            service_impacts=[
                ServiceImpact(
                    service_name="RAGService",
                    file_path="src/rag.py",
                    impact_severity=ImpactSeverity.HIGH,
                    estimated_effort_hours=8.0,
                    refactoring_required="Cross-store queries",
                )
            ],
            recommendation=ChunkSeparationRecommendation(
                recommended_option=ChunkSeparationOption.OPTION_A,
                confidence=0.85,
                rationale=["Low volume", "Simple queries"],
                decision_criteria_met={"manageable": True},
                next_steps=["Add indexes"],
            ),
        )

        markdown = analyzer._format_markdown_report(report)

        assert "# Chunk Separation Impact Report" in markdown
        assert "impact_test" in markdown
        assert "RAGService" in markdown
        assert "Option A" in markdown or "keep_neo4j_with_indexes" in markdown
        assert "85%" in markdown


class TestIntegration:
    """Integration tests for audit services."""

    @pytest.mark.asyncio
    async def test_audit_report_serialization(self):
        """Test that audit reports can be fully serialized."""
        report = ExtendedKGAuditReport(
            audit_id="int_test",
            total_entities=1000,
            document_graph=SubgraphMetrics(
                subgraph_type=SubgraphType.DOCUMENT_GRAPH,
                node_count=700,
            ),
            knowledge_graph=SubgraphMetrics(
                subgraph_type=SubgraphType.KNOWLEDGE_GRAPH,
                node_count=300,
            ),
            bridge_metrics=BridgeNodeMetrics(bridge_node_count=10),
            co_occurrence_patterns=[
                CoOccurrencePattern(type_pair=("A", "B"), co_occurrence_count=5)
            ],
            query_paths=[
                QueryPathAnalysis(
                    path_pattern="A->B",
                    frequency=100,
                    avg_traversal_depth=2,
                    services_using=["Svc1"],
                )
            ],
        )

        data = report.to_dict()

        assert data["audit_id"] == "int_test"
        assert data["document_graph"]["subgraph_type"] == "document_graph"
        assert data["knowledge_graph"]["subgraph_type"] == "knowledge_graph"
        assert len(data["co_occurrence_patterns"]) == 1
        assert len(data["query_paths"]) == 1

    @pytest.mark.asyncio
    async def test_impact_report_serialization(self):
        """Test that impact reports can be fully serialized."""
        report = ChunkImpactReport(
            report_id="imp_test",
            data_volume_mb=100.0,
            service_impacts=[
                ServiceImpact(
                    service_name="Svc1",
                    file_path="path.py",
                    impact_severity=ImpactSeverity.HIGH,
                    estimated_effort_hours=8,
                )
            ],
            recommendation=ChunkSeparationRecommendation(
                recommended_option=ChunkSeparationOption.OPTION_A,
                confidence=0.9,
                rationale=["Test"],
            ),
        )

        data = report.to_dict()

        assert data["report_id"] == "imp_test"
        assert data["data_volume_mb"] == 100.0
        assert len(data["service_impacts"]) == 1
        assert data["recommendation"]["recommended_option"] == "keep_neo4j_with_indexes"
