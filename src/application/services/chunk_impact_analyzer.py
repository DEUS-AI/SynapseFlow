"""Chunk Impact Analyzer Service.

Analyzes the impact of chunk separation on SynapseFlow services.
Evaluates each separation option and provides decision criteria.

Options analyzed:
- Option A: Keep in Neo4j with indexes and labels
- Option B: Move chunks to PostgreSQL (dual-write)
- Option C: Separate Neo4j database for RAG

Usage:
    from application.services.chunk_impact_analyzer import ChunkImpactAnalyzer

    analyzer = ChunkImpactAnalyzer(neo4j_backend)
    report = await analyzer.analyze_impact()
    await analyzer.save_report(report, "analysis/chunk_impact_report.md")
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from domain.chunk_separation_models import (
    ChunkSeparationOption,
    ChunkSeparationRecommendation,
    ChunkImpactReport,
    ImpactSeverity,
    ServiceImpact,
)

logger = logging.getLogger(__name__)


@dataclass
class ChunkDependency:
    """A service dependency on chunk data."""
    service_name: str
    file_path: str
    line_range: Tuple[int, int]
    query_pattern: str
    access_type: str  # "read", "write", "both"
    description: str


# Known chunk dependencies in the codebase
CHUNK_DEPENDENCIES: List[ChunkDependency] = [
    ChunkDependency(
        service_name="RAGService",
        file_path="src/application/services/rag_service.py",
        line_range=(93, 98),
        query_pattern="MATCH (c:Chunk {id: $chunk_id})-[:MENTIONS]->(e:ExtractedEntity)",
        access_type="read",
        description="Retrieves entities mentioned by chunks for graph context enrichment",
    ),
    ChunkDependency(
        service_name="DocumentRouter",
        file_path="src/application/api/document_router.py",
        line_range=(383, 391),
        query_pattern="MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:ExtractedEntity)",
        access_type="read",
        description="Lists entities associated with a document via chunk path",
    ),
    ChunkDependency(
        service_name="Neo4jPDFIngestion",
        file_path="src/infrastructure/neo4j_pdf_ingestion.py",
        line_range=(282, 374),
        query_pattern="CREATE (c:Chunk {id: $id, text: $text})",
        access_type="write",
        description="Creates chunks during PDF ingestion with MENTIONS relationships",
    ),
    ChunkDependency(
        service_name="ExtractionAuditService",
        file_path="src/application/services/extraction_audit_service.py",
        line_range=(1, 50),
        query_pattern="MATCH (c:Chunk)",
        access_type="read",
        description="Audits chunk counts and relationships for quality metrics",
    ),
    ChunkDependency(
        service_name="ExtendedKGAuditService",
        file_path="src/application/services/extended_kg_audit_service.py",
        line_range=(67, 176),
        query_pattern="MATCH (c:Chunk)-[:MENTIONS]->(e)",
        access_type="read",
        description="Analyzes co-occurrence patterns and subgraph separation",
    ),
]


@dataclass
class OptionAnalysis:
    """Analysis of a specific separation option."""
    option: ChunkSeparationOption
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    implementation_effort_days: float = 0.0
    risk_level: str = "low"  # low, medium, high
    affected_services: List[str] = field(default_factory=list)
    required_changes: List[str] = field(default_factory=list)
    rollback_complexity: str = "low"
    weighted_score: float = 0.0


class ChunkImpactAnalyzer:
    """Analyzes impact of chunk separation on services."""

    # Decision matrix weights
    DECISION_WEIGHTS = {
        "implementation_effort": 0.15,
        "query_performance": 0.25,
        "data_consistency": 0.20,
        "scalability": 0.20,
        "operational_simplicity": 0.10,
        "rollback_safety": 0.10,
    }

    def __init__(self, neo4j_backend=None):
        """Initialize the analyzer.

        Args:
            neo4j_backend: Optional Neo4j backend for live metrics
        """
        self.backend = neo4j_backend

    async def analyze_impact(self) -> ChunkImpactReport:
        """Perform complete impact analysis.

        Returns:
            ChunkImpactReport with all findings
        """
        start_time = datetime.now()

        report = ChunkImpactReport(
            report_id=f"impact_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            generated_at=start_time,
        )

        # Analyze service impacts
        report.service_impacts = self._analyze_service_impacts()

        # Get live metrics if backend available
        if self.backend:
            await self._collect_live_metrics(report)

        # Analyze each option
        option_analyses = {
            ChunkSeparationOption.OPTION_A: self._analyze_option_a(report),
            ChunkSeparationOption.OPTION_B: self._analyze_option_b(report),
            ChunkSeparationOption.OPTION_C: self._analyze_option_c(report),
        }

        # Generate recommendation
        report.recommendation = self._generate_recommendation(option_analyses, report)

        # Calculate processing time
        end_time = datetime.now()
        report.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return report

    def _analyze_service_impacts(self) -> List[ServiceImpact]:
        """Analyze impact on each dependent service."""
        impacts = []

        for dep in CHUNK_DEPENDENCIES:
            # Determine severity based on access type and query complexity
            if dep.access_type == "write":
                severity = ImpactSeverity.CRITICAL
                refactoring = "Requires dual-write implementation or source abstraction"
                effort = 16.0  # 2 days
            elif "HAS_CHUNK" in dep.query_pattern and "MENTIONS" in dep.query_pattern:
                severity = ImpactSeverity.HIGH
                refactoring = "Requires cross-store join logic or denormalized cache"
                effort = 8.0  # 1 day
            elif "Chunk" in dep.query_pattern:
                severity = ImpactSeverity.MEDIUM
                refactoring = "Query needs to be rerouted to new chunk store"
                effort = 4.0  # Half day
            else:
                severity = ImpactSeverity.LOW
                refactoring = "Minor query updates"
                effort = 2.0

            impacts.append(ServiceImpact(
                service_name=dep.service_name,
                file_path=dep.file_path,
                impact_severity=severity,
                affected_queries=[dep.query_pattern],
                refactoring_required=refactoring,
                estimated_effort_hours=effort,
            ))

        return impacts

    async def _collect_live_metrics(self, report: ChunkImpactReport) -> None:
        """Collect live metrics from Neo4j."""
        try:
            # Get chunk count and size
            result = await self.backend.query_raw(
                """
                MATCH (c:Chunk)
                WHERE c.text IS NOT NULL
                RETURN
                    count(c) as chunk_count,
                    avg(size(c.text)) as avg_text_size,
                    sum(size(c.text)) as total_bytes
                """,
                {}
            )

            if result:
                row = result[0]
                chunk_count = row.get("chunk_count", 0)
                total_bytes = row.get("total_bytes", 0)
                report.data_volume_mb = total_bytes / (1024 * 1024) if total_bytes else 0

                # Estimate migration time (1 MB/s conservative)
                report.estimated_migration_time_hours = report.data_volume_mb / 3600

            # Get relationship counts for consistency estimation
            result = await self.backend.query_raw(
                """
                MATCH ()-[r:MENTIONS]->()
                RETURN count(r) as mentions_count
                """,
                {}
            )

            if result:
                mentions_count = result[0].get("mentions_count", 0)
                # High mentions = higher consistency risk if separated
                if mentions_count > 10000:
                    report.consistency_risk = "high"
                elif mentions_count > 5000:
                    report.consistency_risk = "medium"
                else:
                    report.consistency_risk = "low"

            # Determine cross-store join complexity
            result = await self.backend.query_raw(
                """
                MATCH (c:Chunk)-[:MENTIONS]->(e)-[:LINKS_TO]->(ke)
                WHERE NOT ke:ExtractedEntity
                RETURN count(*) as bridge_traversals
                """,
                {}
            )

            if result:
                bridge_count = result[0].get("bridge_traversals", 0)
                if bridge_count > 5000:
                    report.cross_store_join_complexity = "complex"
                elif bridge_count > 1000:
                    report.cross_store_join_complexity = "simple"
                else:
                    report.cross_store_join_complexity = "none"

        except Exception as e:
            logger.warning(f"Failed to collect live metrics: {e}")

    def _analyze_option_a(self, report: ChunkImpactReport) -> OptionAnalysis:
        """Analyze Option A: Keep in Neo4j with indexes."""
        analysis = OptionAnalysis(option=ChunkSeparationOption.OPTION_A)

        analysis.pros = [
            "No migration required",
            "No cross-store join complexity",
            "Maintains data consistency automatically",
            "All existing queries continue to work",
            "Zero downtime implementation",
        ]

        analysis.cons = [
            "Neo4j memory usage continues to grow",
            "Limited scalability for large chunk volumes",
            "Mixed workloads (RAG + reasoning) on same DB",
        ]

        analysis.implementation_effort_days = 1
        analysis.risk_level = "low"
        analysis.rollback_complexity = "none"

        analysis.required_changes = [
            "Add composite index: CREATE INDEX chunk_doc_idx FOR (c:Chunk) ON (c.document_id, c.id)",
            "Add secondary label: MATCH (c:Chunk) SET c:StructuralChunk",
            "Monitor query performance with EXPLAIN/PROFILE",
        ]

        analysis.affected_services = []  # No services affected

        # Calculate weighted score
        scores = {
            "implementation_effort": 9,
            "query_performance": 8,
            "data_consistency": 10,
            "scalability": 5,
            "operational_simplicity": 10,
            "rollback_safety": 10,
        }
        analysis.weighted_score = sum(
            scores[k] * v for k, v in self.DECISION_WEIGHTS.items()
        )

        return analysis

    def _analyze_option_b(self, report: ChunkImpactReport) -> OptionAnalysis:
        """Analyze Option B: Move to PostgreSQL."""
        analysis = OptionAnalysis(option=ChunkSeparationOption.OPTION_B)

        analysis.pros = [
            "Separates structural (RAG) from semantic (reasoning) workloads",
            "PostgreSQL excels at text search and full-text indexing",
            "Existing dual-write pattern can be extended",
            "Better cost optimization (PostgreSQL cheaper at scale)",
        ]

        analysis.cons = [
            "Cross-store joins for Document→Chunk→Entity paths",
            "Dual-write complexity and potential consistency issues",
            "Requires service layer changes for chunk access",
            "Migration downtime for existing data",
        ]

        analysis.implementation_effort_days = 10  # 2 weeks
        analysis.risk_level = "medium"
        analysis.rollback_complexity = "medium"

        analysis.required_changes = [
            "Create PostgreSQL chunks table with proper indexes",
            "Implement ChunkRepository abstraction layer",
            "Update RAGService to use repository pattern",
            "Implement dual-write in PDF ingestion",
            "Add migration script for existing chunks",
            "Update document_router API to use cross-store queries",
        ]

        analysis.affected_services = [
            dep.service_name for dep in CHUNK_DEPENDENCIES
        ]

        # Calculate weighted score
        scores = {
            "implementation_effort": 6,
            "query_performance": 6,
            "data_consistency": 6,
            "scalability": 8,
            "operational_simplicity": 7,
            "rollback_safety": 6,
        }
        analysis.weighted_score = sum(
            scores[k] * v for k, v in self.DECISION_WEIGHTS.items()
        )

        return analysis

    def _analyze_option_c(self, report: ChunkImpactReport) -> OptionAnalysis:
        """Analyze Option C: Separate Neo4j database."""
        analysis = OptionAnalysis(option=ChunkSeparationOption.OPTION_C)

        analysis.pros = [
            "Complete workload isolation",
            "Independent scaling of RAG and reasoning",
            "Clear separation of concerns",
            "Can optimize each database independently",
        ]

        analysis.cons = [
            "Operational complexity (2 Neo4j instances)",
            "Higher infrastructure costs",
            "Cross-database entity resolution required",
            "Complex deployment and monitoring",
        ]

        analysis.implementation_effort_days = 20  # 4 weeks
        analysis.risk_level = "high"
        analysis.rollback_complexity = "high"

        analysis.required_changes = [
            "Provision second Neo4j instance (synapseflow_rag)",
            "Implement multi-database connection manager",
            "Create entity resolution service for cross-DB references",
            "Update all chunk-related services with database routing",
            "Implement distributed transaction handling",
            "Set up cross-database monitoring and alerting",
        ]

        analysis.affected_services = [
            dep.service_name for dep in CHUNK_DEPENDENCIES
        ] + ["Infrastructure", "Monitoring", "Deployment"]

        # Calculate weighted score
        scores = {
            "implementation_effort": 3,
            "query_performance": 7,
            "data_consistency": 7,
            "scalability": 9,
            "operational_simplicity": 4,
            "rollback_safety": 3,
        }
        analysis.weighted_score = sum(
            scores[k] * v for k, v in self.DECISION_WEIGHTS.items()
        )

        return analysis

    def _generate_recommendation(
        self,
        analyses: Dict[ChunkSeparationOption, OptionAnalysis],
        report: ChunkImpactReport
    ) -> ChunkSeparationRecommendation:
        """Generate recommendation based on analysis."""

        # Find best option by weighted score
        best_option = max(analyses.keys(), key=lambda o: analyses[o].weighted_score)
        best_analysis = analyses[best_option]

        # Determine confidence based on score margin
        scores = sorted([a.weighted_score for a in analyses.values()], reverse=True)
        margin = scores[0] - scores[1] if len(scores) > 1 else scores[0]
        confidence = min(0.9, 0.5 + margin / 20)

        # Build rationale
        rationale = [
            f"Weighted score: {best_analysis.weighted_score:.2f} (highest among options)",
            f"Implementation effort: {best_analysis.implementation_effort_days} days",
            f"Risk level: {best_analysis.risk_level}",
            f"Rollback complexity: {best_analysis.rollback_complexity}",
        ]

        # Add context-specific rationale
        if report.data_volume_mb < 100:
            rationale.append(f"Data volume ({report.data_volume_mb:.1f} MB) is manageable for Option A")
        if report.cross_store_join_complexity == "complex":
            rationale.append("High bridge traversal count favors keeping data unified")

        # Decision criteria
        criteria = {
            "chunk_count_manageable": report.data_volume_mb < 100,
            "low_consistency_risk": report.consistency_risk in ["low", "medium"],
            "simple_joins": report.cross_store_join_complexity != "complex",
            "quick_implementation_needed": True,  # Usually true for MVP
        }

        # Next steps based on recommendation
        if best_option == ChunkSeparationOption.OPTION_A:
            next_steps = [
                "Run CREATE INDEX chunk_doc_idx FOR (c:Chunk) ON (c.document_id, c.id)",
                "Add :StructuralChunk label to existing chunks",
                "Set up monitoring for chunk-related query latencies",
                "Define trigger criteria for escalation to Option B",
                "Schedule monthly review of chunk growth metrics",
            ]
        elif best_option == ChunkSeparationOption.OPTION_B:
            next_steps = [
                "Design PostgreSQL schema for chunks table",
                "Create ChunkRepository abstraction interface",
                "Implement feature flag for dual-write testing",
                "Plan migration window with rollback procedure",
                "Update RAGService with repository pattern",
            ]
        else:
            next_steps = [
                "Evaluate infrastructure requirements for second Neo4j",
                "Design cross-database entity resolution protocol",
                "Create proof-of-concept with test data",
                "Plan phased migration strategy",
                "Set up comprehensive monitoring for both databases",
            ]

        return ChunkSeparationRecommendation(
            recommended_option=best_option,
            confidence=confidence,
            rationale=rationale,
            decision_criteria_met=criteria,
            next_steps=next_steps,
        )

    async def save_report(
        self,
        report: ChunkImpactReport,
        output_path: str
    ) -> str:
        """Save impact report as Markdown file.

        Args:
            report: The impact report to save
            output_path: Path for the output file

        Returns:
            Path to the saved file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        content = self._format_markdown_report(report)

        with open(path, "w") as f:
            f.write(content)

        logger.info(f"Impact report saved to {path}")
        return str(path)

    def _format_markdown_report(self, report: ChunkImpactReport) -> str:
        """Format report as Markdown."""
        lines = [
            "# Chunk Separation Impact Report",
            "",
            f"**Report ID:** {report.report_id}",
            f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Processing Time:** {report.processing_time_ms}ms",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
        ]

        if report.recommendation:
            rec = report.recommendation
            lines.extend([
                f"**Recommended Option:** {rec.recommended_option.value}",
                f"**Confidence:** {rec.confidence:.0%}",
                "",
                "### Rationale",
                "",
            ])
            for r in rec.rationale:
                lines.append(f"- {r}")
            lines.append("")

        # Data metrics
        lines.extend([
            "## Data Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Data Volume | {report.data_volume_mb:.1f} MB |",
            f"| Estimated Migration Time | {report.estimated_migration_time_hours:.1f} hours |",
            f"| Cross-Store Join Complexity | {report.cross_store_join_complexity} |",
            f"| Consistency Risk | {report.consistency_risk} |",
            "",
        ])

        # Service impacts
        lines.extend([
            "---",
            "",
            "## Service Impact Analysis",
            "",
            "| Service | Severity | Effort (hrs) | Refactoring Required |",
            "|---------|----------|--------------|---------------------|",
        ])

        for impact in report.service_impacts:
            lines.append(
                f"| {impact.service_name} | {impact.impact_severity.value.upper()} | "
                f"{impact.estimated_effort_hours:.0f} | {impact.refactoring_required[:50]}... |"
            )

        lines.extend([
            "",
            "### Total Effort Estimate",
            "",
        ])

        total_effort = sum(i.estimated_effort_hours for i in report.service_impacts)
        lines.append(f"**Total Refactoring Effort:** {total_effort:.0f} hours ({total_effort/8:.1f} days)")
        lines.append("")

        # Option comparison
        lines.extend([
            "---",
            "",
            "## Option Comparison",
            "",
            "### Option A: Keep in Neo4j with Indexes",
            "",
            "**Effort:** 1 day | **Risk:** Low | **Rollback:** None",
            "",
            "**Pros:**",
            "- No migration required",
            "- All queries continue to work unchanged",
            "- Zero downtime implementation",
            "",
            "**Cons:**",
            "- Neo4j memory continues to grow with chunks",
            "- Limited scalability for very large document sets",
            "",
            "### Option B: Move to PostgreSQL",
            "",
            "**Effort:** 10 days | **Risk:** Medium | **Rollback:** Medium",
            "",
            "**Pros:**",
            "- Separates structural from semantic workloads",
            "- Better text indexing capabilities",
            "- Existing dual-write pattern available",
            "",
            "**Cons:**",
            "- Cross-store joins for Document→Chunk→Entity",
            "- Consistency risk during dual-write",
            "",
            "### Option C: Separate Neo4j Database",
            "",
            "**Effort:** 20 days | **Risk:** High | **Rollback:** High",
            "",
            "**Pros:**",
            "- Complete workload isolation",
            "- Independent scaling",
            "",
            "**Cons:**",
            "- Operational complexity (2 databases)",
            "- Higher infrastructure costs",
            "- Cross-database entity resolution",
            "",
        ])

        # Decision criteria
        if report.recommendation:
            lines.extend([
                "---",
                "",
                "## Decision Criteria",
                "",
                "| Criterion | Status |",
                "|-----------|--------|",
            ])
            for criterion, met in report.recommendation.decision_criteria_met.items():
                status = "PASS" if met else "FAIL"
                lines.append(f"| {criterion.replace('_', ' ').title()} | {status} |")

            lines.extend([
                "",
                "## Recommended Next Steps",
                "",
            ])
            for i, step in enumerate(report.recommendation.next_steps, 1):
                lines.append(f"{i}. {step}")

        lines.extend([
            "",
            "---",
            "",
            "*Generated by ChunkImpactAnalyzer*",
        ])

        return "\n".join(lines)


async def run_impact_analysis(
    neo4j_uri: str = None,
    neo4j_user: str = None,
    neo4j_password: str = None,
    output_path: str = "analysis/chunk_impact_report.md",
) -> ChunkImpactReport:
    """Convenience function to run impact analysis.

    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        output_path: Path for the output report

    Returns:
        ChunkImpactReport with all findings
    """
    import os
    from infrastructure.neo4j_backend import Neo4jBackend

    uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
    password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")

    backend = Neo4jBackend(uri, user, password)

    try:
        analyzer = ChunkImpactAnalyzer(backend)
        report = await analyzer.analyze_impact()
        await analyzer.save_report(report, output_path)
        return report
    finally:
        await backend.close()


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze chunk separation impact on services"
    )
    parser.add_argument(
        "--output", "-o",
        default="analysis/chunk_impact_report.md",
        help="Output path for the report"
    )

    args = parser.parse_args()

    async def main():
        report = await run_impact_analysis(output_path=args.output)
        print(f"\n========== IMPACT ANALYSIS SUMMARY ==========")

        if report.recommendation:
            print(f"Recommended Option: {report.recommendation.recommended_option.value}")
            print(f"Confidence: {report.recommendation.confidence:.0%}")

        print(f"\nData Volume: {report.data_volume_mb:.1f} MB")
        print(f"Cross-Store Complexity: {report.cross_store_join_complexity}")
        print(f"Consistency Risk: {report.consistency_risk}")

        total_effort = sum(i.estimated_effort_hours for i in report.service_impacts)
        print(f"\nTotal Refactoring Effort: {total_effort:.0f} hours")

        print(f"\nReport saved to: {args.output}")

    asyncio.run(main())
