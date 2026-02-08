"""Extraction Pipeline Audit Service.

Phase 0 of the Orphan Nodes Remediation Plan.

This service performs a comprehensive audit of the knowledge extraction pipeline
to diagnose the root causes of orphan nodes. It executes diagnostic queries
against Neo4j and generates a detailed report.

Usage:
    from application.services.extraction_audit_service import ExtractionAuditService

    service = ExtractionAuditService(neo4j_backend)
    report = await service.run_full_audit()
    await service.save_report(report, "analysis/extraction_audit_report.md")
"""

import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class OrphanSeverity(str, Enum):
    """Severity levels for orphan node issues."""
    CRITICAL = "critical"    # >80% orphan rate
    HIGH = "high"            # 50-80% orphan rate
    MEDIUM = "medium"        # 20-50% orphan rate
    LOW = "low"              # <20% orphan rate


@dataclass
class OrphanDistribution:
    """Distribution of orphan nodes by type."""
    entity_type: str
    orphan_count: int
    connected_count: int
    orphan_rate: float


@dataclass
class RelationshipDistribution:
    """Distribution of relationships by type."""
    relationship_type: str
    count: int
    percentage: float


@dataclass
class DocumentOrphanStats:
    """Orphan statistics per document."""
    source_id: str
    orphan_count: int
    total_entities: int
    orphan_rate: float


@dataclass
class NodeDegreeStats:
    """Statistics about node connectivity."""
    name: str
    entity_type: str
    degree: int


@dataclass
class ExtractionAuditReport:
    """Complete extraction pipeline audit report."""

    # Metadata
    audit_id: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    processing_time_ms: int = 0

    # Graph Statistics
    total_entities: int = 0
    total_orphans: int = 0
    total_relationships: int = 0
    orphan_rate: float = 0.0
    severity: OrphanSeverity = OrphanSeverity.LOW

    # Distribution Analysis
    orphan_distribution_by_type: List[OrphanDistribution] = field(default_factory=list)
    connected_distribution_by_type: List[OrphanDistribution] = field(default_factory=list)
    relationship_distribution: List[RelationshipDistribution] = field(default_factory=list)
    unmapped_types: List[Dict[str, Any]] = field(default_factory=list)

    # Concentration Analysis
    top_connected_nodes: List[NodeDegreeStats] = field(default_factory=list)
    documents_with_most_orphans: List[DocumentOrphanStats] = field(default_factory=list)

    # Confidence Analysis
    confidence_distribution: Dict[str, int] = field(default_factory=dict)

    # Ontology Analysis
    ontology_coverage: float = 0.0
    entities_without_mapping: int = 0

    # Root Cause Diagnosis
    identified_causes: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Raw Query Results (for debugging)
    raw_results: Dict[str, Any] = field(default_factory=dict)

    def compute_severity(self) -> OrphanSeverity:
        """Compute severity based on orphan rate."""
        if self.orphan_rate >= 0.8:
            self.severity = OrphanSeverity.CRITICAL
        elif self.orphan_rate >= 0.5:
            self.severity = OrphanSeverity.HIGH
        elif self.orphan_rate >= 0.2:
            self.severity = OrphanSeverity.MEDIUM
        else:
            self.severity = OrphanSeverity.LOW
        return self.severity

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "audit_id": self.audit_id,
            "generated_at": self.generated_at.isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "total_entities": self.total_entities,
            "total_orphans": self.total_orphans,
            "total_relationships": self.total_relationships,
            "orphan_rate": round(self.orphan_rate, 4),
            "severity": self.severity.value,
            "ontology_coverage": round(self.ontology_coverage, 4),
            "entities_without_mapping": self.entities_without_mapping,
            "identified_causes": self.identified_causes,
            "recommendations": self.recommendations,
        }


class ExtractionAuditService:
    """Service for auditing the extraction pipeline.

    Implements Phase 0 of the Orphan Nodes Remediation Plan by:
    1. Running diagnostic Cypher queries against Neo4j
    2. Analyzing entity and relationship distributions
    3. Identifying root causes of orphan nodes
    4. Generating recommendations for remediation
    """

    # Diagnostic Cypher Queries
    QUERIES = {
        "total_entities": """
            MATCH (n)
            WHERE n.name IS NOT NULL OR n.id IS NOT NULL
            RETURN count(n) AS count
        """,

        "total_orphans": """
            MATCH (n)
            WHERE NOT (n)--()
              AND (n.name IS NOT NULL OR n.id IS NOT NULL)
            RETURN count(n) AS count
        """,

        "total_relationships": """
            MATCH ()-[r]->()
            RETURN count(r) AS count
        """,

        "orphan_distribution_by_type": """
            MATCH (n)
            WHERE NOT (n)--()
              AND (n.name IS NOT NULL OR n.id IS NOT NULL)
            RETURN coalesce(n.type, n.entity_type, labels(n)[0], 'Unknown') AS type,
                   count(n) AS orphan_count
            ORDER BY orphan_count DESC
            LIMIT 30
        """,

        "connected_distribution_by_type": """
            MATCH (n)
            WHERE (n)--()
              AND (n.name IS NOT NULL OR n.id IS NOT NULL)
            RETURN coalesce(n.type, n.entity_type, labels(n)[0], 'Unknown') AS type,
                   count(n) AS connected_count
            ORDER BY connected_count DESC
            LIMIT 30
        """,

        "unmapped_types": """
            MATCH (n)
            WHERE (n.ontology_code IS NULL OR n.ontology_code = '')
              AND (n.name IS NOT NULL OR n.id IS NOT NULL)
            RETURN coalesce(n.type, n.entity_type, labels(n)[0], 'Unknown') AS type,
                   count(n) AS count
            ORDER BY count DESC
            LIMIT 20
        """,

        "relationship_distribution": """
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(r) AS count
            ORDER BY count DESC
            LIMIT 30
        """,

        "top_connected_nodes": """
            MATCH (n)
            WHERE (n.name IS NOT NULL OR n.id IS NOT NULL)
            WITH n, size([(n)-[]-() | 1]) AS degree
            WHERE degree > 0
            RETURN coalesce(n.name, n.id) AS name,
                   coalesce(n.type, n.entity_type, labels(n)[0]) AS entity_type,
                   degree
            ORDER BY degree DESC
            LIMIT 50
        """,

        "documents_with_most_orphans": """
            MATCH (n)
            WHERE NOT (n)--()
              AND n.source_document IS NOT NULL
            RETURN n.source_document AS source_id, count(n) AS orphan_count
            ORDER BY orphan_count DESC
            LIMIT 20
        """,

        "confidence_distribution": """
            MATCH ()-[r]->()
            WHERE r.confidence IS NOT NULL
            RETURN
              CASE
                WHEN r.confidence >= 0.9 THEN 'high (>=0.9)'
                WHEN r.confidence >= 0.7 THEN 'medium (0.7-0.9)'
                WHEN r.confidence >= 0.5 THEN 'low (0.5-0.7)'
                ELSE 'very_low (<0.5)'
              END AS confidence_band,
              count(r) AS count
            ORDER BY count DESC
        """,

        "entities_by_layer": """
            MATCH (n)
            WHERE n.layer IS NOT NULL
            RETURN n.layer AS layer, count(n) AS count
            ORDER BY count DESC
        """,

        "orphans_by_layer": """
            MATCH (n)
            WHERE NOT (n)--() AND n.layer IS NOT NULL
            RETURN n.layer AS layer, count(n) AS count
            ORDER BY count DESC
        """,

        "entities_per_document": """
            MATCH (n)
            WHERE n.source_document IS NOT NULL
            WITH n.source_document AS doc, count(n) AS entity_count
            OPTIONAL MATCH (orphan)
            WHERE NOT (orphan)--()
              AND orphan.source_document = doc
            WITH doc, entity_count, count(orphan) AS orphan_count
            RETURN doc AS source_id,
                   entity_count AS total_entities,
                   orphan_count,
                   CASE WHEN entity_count > 0
                        THEN toFloat(orphan_count) / entity_count
                        ELSE 0 END AS orphan_rate
            ORDER BY orphan_rate DESC
            LIMIT 20
        """,

        "relationship_endpoint_validation": """
            MATCH (n)
            WHERE n.name IS NOT NULL
            WITH collect(n.name) AS valid_names
            MATCH ()-[r]->()
            WHERE r.source_name IS NOT NULL
              AND NOT r.source_name IN valid_names
            RETURN r.source_name AS invalid_source, count(r) AS count
            LIMIT 20
        """,
    }

    def __init__(self, neo4j_backend):
        """Initialize the audit service.

        Args:
            neo4j_backend: Neo4j backend instance for queries
        """
        self.backend = neo4j_backend

    async def run_full_audit(self) -> ExtractionAuditReport:
        """Execute complete extraction pipeline audit.

        Returns:
            ExtractionAuditReport with all diagnostic results
        """
        import uuid
        start_time = datetime.now()

        report = ExtractionAuditReport(
            audit_id=str(uuid.uuid4())[:8],
            generated_at=start_time,
        )

        try:
            # Run all diagnostic queries
            logger.info("Starting extraction pipeline audit...")

            # Basic counts
            report.total_entities = await self._run_count_query("total_entities")
            report.total_orphans = await self._run_count_query("total_orphans")
            report.total_relationships = await self._run_count_query("total_relationships")

            # Calculate orphan rate
            if report.total_entities > 0:
                report.orphan_rate = report.total_orphans / report.total_entities
            report.compute_severity()

            logger.info(
                f"Basic stats: {report.total_entities} entities, "
                f"{report.total_orphans} orphans ({report.orphan_rate:.1%}), "
                f"{report.total_relationships} relationships"
            )

            # Distribution analysis
            report.orphan_distribution_by_type = await self._run_distribution_query(
                "orphan_distribution_by_type", "orphan"
            )
            report.connected_distribution_by_type = await self._run_distribution_query(
                "connected_distribution_by_type", "connected"
            )
            report.relationship_distribution = await self._run_relationship_distribution()
            report.unmapped_types = await self._run_unmapped_types_query()

            # Concentration analysis
            report.top_connected_nodes = await self._run_node_degree_query()
            report.documents_with_most_orphans = await self._run_document_orphan_query()

            # Confidence analysis
            report.confidence_distribution = await self._run_confidence_distribution()

            # Ontology coverage
            if report.unmapped_types:
                report.entities_without_mapping = sum(
                    t.get("count", 0) for t in report.unmapped_types
                )
                report.ontology_coverage = 1 - (
                    report.entities_without_mapping / max(report.total_entities, 1)
                )

            # Diagnose root causes
            report.identified_causes = self._diagnose_root_causes(report)
            report.recommendations = self._generate_recommendations(report)

        except Exception as e:
            logger.error(f"Audit failed: {e}")
            report.identified_causes.append(f"Audit error: {str(e)}")

        # Calculate processing time
        end_time = datetime.now()
        report.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        logger.info(f"Audit completed in {report.processing_time_ms}ms")

        return report

    async def _run_count_query(self, query_name: str) -> int:
        """Run a count query and return the result."""
        try:
            query = self.QUERIES[query_name]
            results = await self.backend.query_raw(query, {})
            if results and len(results) > 0:
                return results[0].get("count", 0)
            return 0
        except Exception as e:
            logger.warning(f"Count query {query_name} failed: {e}")
            return 0

    async def _run_distribution_query(
        self, query_name: str, dist_type: str
    ) -> List[OrphanDistribution]:
        """Run a distribution query."""
        try:
            query = self.QUERIES[query_name]
            results = await self.backend.query_raw(query, {})

            distributions = []
            for row in results:
                entity_type = row.get("type", "Unknown")
                count = row.get("orphan_count", 0) if dist_type == "orphan" else row.get("connected_count", 0)

                distributions.append(OrphanDistribution(
                    entity_type=entity_type,
                    orphan_count=count if dist_type == "orphan" else 0,
                    connected_count=count if dist_type == "connected" else 0,
                    orphan_rate=0.0,  # Calculated later if needed
                ))

            return distributions
        except Exception as e:
            logger.warning(f"Distribution query {query_name} failed: {e}")
            return []

    async def _run_relationship_distribution(self) -> List[RelationshipDistribution]:
        """Run relationship distribution query."""
        try:
            query = self.QUERIES["relationship_distribution"]
            results = await self.backend.query_raw(query, {})

            total = sum(r.get("count", 0) for r in results)
            distributions = []

            for row in results:
                rel_type = row.get("rel_type", "UNKNOWN")
                count = row.get("count", 0)

                distributions.append(RelationshipDistribution(
                    relationship_type=rel_type,
                    count=count,
                    percentage=round(count / max(total, 1) * 100, 2),
                ))

            return distributions
        except Exception as e:
            logger.warning(f"Relationship distribution query failed: {e}")
            return []

    async def _run_unmapped_types_query(self) -> List[Dict[str, Any]]:
        """Run unmapped types query."""
        try:
            query = self.QUERIES["unmapped_types"]
            results = await self.backend.query_raw(query, {})
            return [dict(r) for r in results]
        except Exception as e:
            logger.warning(f"Unmapped types query failed: {e}")
            return []

    async def _run_node_degree_query(self) -> List[NodeDegreeStats]:
        """Run top connected nodes query."""
        try:
            query = self.QUERIES["top_connected_nodes"]
            results = await self.backend.query_raw(query, {})

            return [
                NodeDegreeStats(
                    name=r.get("name", "Unknown"),
                    entity_type=r.get("entity_type", "Unknown"),
                    degree=r.get("degree", 0),
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Node degree query failed: {e}")
            return []

    async def _run_document_orphan_query(self) -> List[DocumentOrphanStats]:
        """Run documents with most orphans query."""
        try:
            query = self.QUERIES["entities_per_document"]
            results = await self.backend.query_raw(query, {})

            return [
                DocumentOrphanStats(
                    source_id=r.get("source_id", "Unknown"),
                    orphan_count=r.get("orphan_count", 0),
                    total_entities=r.get("total_entities", 0),
                    orphan_rate=r.get("orphan_rate", 0.0),
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Document orphan query failed: {e}")
            return []

    async def _run_confidence_distribution(self) -> Dict[str, int]:
        """Run confidence distribution query."""
        try:
            query = self.QUERIES["confidence_distribution"]
            results = await self.backend.query_raw(query, {})
            return {r.get("confidence_band", "unknown"): r.get("count", 0) for r in results}
        except Exception as e:
            logger.warning(f"Confidence distribution query failed: {e}")
            return {}

    def _diagnose_root_causes(self, report: ExtractionAuditReport) -> List[str]:
        """Analyze report data to identify root causes of orphan nodes."""
        causes = []

        # Critical orphan rate
        if report.orphan_rate >= 0.9:
            causes.append(
                f"CRITICAL: {report.orphan_rate:.1%} of entities are orphans. "
                "This suggests extraction is not producing relationships at all, "
                "or relationship write logic is failing."
            )
        elif report.orphan_rate >= 0.5:
            causes.append(
                f"HIGH: {report.orphan_rate:.1%} orphan rate indicates systematic "
                "relationship extraction or writing failure."
            )

        # Relationship concentration
        if report.top_connected_nodes:
            max_degree = report.top_connected_nodes[0].degree if report.top_connected_nodes else 0
            if max_degree > 100 and report.total_relationships > 1000:
                causes.append(
                    f"Relationship concentration: Top node has {max_degree} connections. "
                    "Relationships may be concentrated in a small subset of nodes."
                )

        # Ontology coverage
        if report.ontology_coverage < 0.5:
            causes.append(
                f"Low ontology coverage ({report.ontology_coverage:.1%}): "
                f"{report.entities_without_mapping} entities lack type mapping. "
                "These cannot participate in hierarchical (IS_A) relationships."
            )

        # Unmapped types analysis
        if report.unmapped_types:
            top_unmapped = [t["type"] for t in report.unmapped_types[:5]]
            causes.append(
                f"Unmapped entity types: {', '.join(top_unmapped)}. "
                "These types are not in the ontology registry."
            )

        # Document-level analysis
        high_orphan_docs = [
            d for d in report.documents_with_most_orphans
            if d.orphan_rate > 0.8
        ]
        if high_orphan_docs:
            causes.append(
                f"{len(high_orphan_docs)} documents have >80% orphan rate. "
                "Extraction may be failing for specific document types."
            )

        # Code analysis insight (based on our earlier investigation)
        if report.orphan_rate > 0.5:
            causes.append(
                "CODE ANALYSIS: neo4j_pdf_ingestion.py uses separate loops for "
                "entities (lines 283-321) and relationships (lines 339-374). "
                "Relationships are SKIPPED if entity name lookup fails, creating orphans."
            )
            causes.append(
                "CODE ANALYSIS: Entity names are normalized with .title() but "
                "relationship lookup may use original names, causing mismatches."
            )

        return causes

    def _generate_recommendations(self, report: ExtractionAuditReport) -> List[str]:
        """Generate prioritized recommendations based on audit findings."""
        recommendations = []

        # Critical severity
        if report.severity == OrphanSeverity.CRITICAL:
            recommendations.append(
                "IMMEDIATE: Implement atomic entity+relationship transactions. "
                "Use a single transaction per fact to prevent orphans."
            )
            recommendations.append(
                "IMMEDIATE: Add write-time validation that blocks orphan creation. "
                "If relationship fails, rollback entity creation."
            )

        # Ontology issues
        if report.ontology_coverage < 0.8:
            recommendations.append(
                f"Phase 1: Extend ontology with missing types. "
                f"Current coverage: {report.ontology_coverage:.1%}. "
                f"Target: >80%."
            )

        # Extraction redesign
        if report.orphan_rate > 0.3:
            recommendations.append(
                "Phase 2: Redesign extraction to use fact-first approach. "
                "Extract (entity + relationship) bundles, not entities alone."
            )

        # Orphan remediation
        if report.total_orphans > 1000:
            recommendations.append(
                f"Phase 3: Run OrphanLinker to reconnect {report.total_orphans} "
                "existing orphans using type-based, embedding-based, and "
                "re-extraction strategies."
            )

        # Quality monitoring
        recommendations.append(
            "Phase 4: Implement per-document quality monitoring. "
            "Alert when document orphan rate exceeds 30%."
        )

        # Document-specific issues
        if report.documents_with_most_orphans:
            worst_doc = report.documents_with_most_orphans[0]
            if worst_doc.orphan_rate > 0.9:
                recommendations.append(
                    f"INVESTIGATE: Document '{worst_doc.source_id}' has "
                    f"{worst_doc.orphan_rate:.1%} orphan rate. "
                    "Check extraction logs for this document."
                )

        return recommendations

    async def save_report(
        self, report: ExtractionAuditReport, output_path: str
    ) -> str:
        """Save audit report as Markdown file.

        Args:
            report: The audit report to save
            output_path: Path for the output file

        Returns:
            Path to the saved file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        content = self._format_markdown_report(report)

        with open(path, "w") as f:
            f.write(content)

        logger.info(f"Audit report saved to {path}")
        return str(path)

    def _format_markdown_report(self, report: ExtractionAuditReport) -> str:
        """Format report as Markdown."""
        severity_emoji = {
            OrphanSeverity.CRITICAL: "🔴",
            OrphanSeverity.HIGH: "🟠",
            OrphanSeverity.MEDIUM: "🟡",
            OrphanSeverity.LOW: "🟢",
        }

        lines = [
            "# Extraction Pipeline Audit Report",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Processing Time:** {report.processing_time_ms}ms",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"| Metric | Value | Status |",
            f"|--------|-------|--------|",
            f"| Total Entities | {report.total_entities:,} | — |",
            f"| Total Orphans | {report.total_orphans:,} | {severity_emoji[report.severity]} {report.severity.value.upper()} |",
            f"| Orphan Rate | {report.orphan_rate:.1%} | — |",
            f"| Total Relationships | {report.total_relationships:,} | — |",
            f"| Ontology Coverage | {report.ontology_coverage:.1%} | {'🟢' if report.ontology_coverage > 0.8 else '🔴'} |",
            f"| Entities Without Mapping | {report.entities_without_mapping:,} | — |",
            "",
            "---",
            "",
            "## Root Cause Analysis",
            "",
        ]

        for i, cause in enumerate(report.identified_causes, 1):
            lines.append(f"{i}. {cause}")
        lines.append("")

        lines.extend([
            "---",
            "",
            "## Recommendations",
            "",
        ])

        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

        lines.extend([
            "---",
            "",
            "## Orphan Distribution by Type",
            "",
            "| Entity Type | Orphan Count |",
            "|-------------|--------------|",
        ])

        for dist in report.orphan_distribution_by_type[:15]:
            lines.append(f"| {dist.entity_type} | {dist.orphan_count:,} |")
        lines.append("")

        lines.extend([
            "---",
            "",
            "## Relationship Distribution",
            "",
            "| Relationship Type | Count | Percentage |",
            "|-------------------|-------|------------|",
        ])

        for dist in report.relationship_distribution[:15]:
            lines.append(f"| {dist.relationship_type} | {dist.count:,} | {dist.percentage:.1f}% |")
        lines.append("")

        lines.extend([
            "---",
            "",
            "## Top Connected Nodes",
            "",
            "| Name | Type | Connections |",
            "|------|------|-------------|",
        ])

        for node in report.top_connected_nodes[:20]:
            lines.append(f"| {node.name[:50]} | {node.entity_type} | {node.degree:,} |")
        lines.append("")

        lines.extend([
            "---",
            "",
            "## Documents with Highest Orphan Rates",
            "",
            "| Document | Orphans | Total | Rate |",
            "|----------|---------|-------|------|",
        ])

        for doc in report.documents_with_most_orphans[:10]:
            lines.append(
                f"| {doc.source_id[:40]} | {doc.orphan_count:,} | "
                f"{doc.total_entities:,} | {doc.orphan_rate:.1%} |"
            )
        lines.append("")

        if report.unmapped_types:
            lines.extend([
                "---",
                "",
                "## Unmapped Entity Types",
                "",
                "| Type | Count |",
                "|------|-------|",
            ])

            for t in report.unmapped_types[:15]:
                lines.append(f"| {t.get('type', 'Unknown')} | {t.get('count', 0):,} |")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Confidence Distribution (Relationships)",
            "",
            "| Confidence Band | Count |",
            "|-----------------|-------|",
        ])

        for band, count in report.confidence_distribution.items():
            lines.append(f"| {band} | {count:,} |")
        lines.append("")

        lines.extend([
            "---",
            "",
            "*Generated by ExtractionAuditService - Phase 0 of Orphan Nodes Remediation Plan*",
        ])

        return "\n".join(lines)


async def run_extraction_audit(
    neo4j_uri: str = None,
    neo4j_user: str = None,
    neo4j_password: str = None,
    output_path: str = "analysis/extraction_audit_report.md",
) -> ExtractionAuditReport:
    """Convenience function to run a full extraction audit.

    Args:
        neo4j_uri: Neo4j connection URI (uses env var if not provided)
        neo4j_user: Neo4j username (uses env var if not provided)
        neo4j_password: Neo4j password (uses env var if not provided)
        output_path: Path for the output report

    Returns:
        ExtractionAuditReport with all findings
    """
    import os
    from infrastructure.neo4j_backend import Neo4jBackend

    uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
    password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")

    backend = Neo4jBackend(uri, user, password)

    try:
        service = ExtractionAuditService(backend)
        report = await service.run_full_audit()
        await service.save_report(report, output_path)
        return report
    finally:
        await backend.close()


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run extraction pipeline audit (Phase 0)"
    )
    parser.add_argument(
        "--output", "-o",
        default="analysis/extraction_audit_report.md",
        help="Output path for the report"
    )
    parser.add_argument(
        "--neo4j-uri",
        help="Neo4j connection URI"
    )

    args = parser.parse_args()

    async def main():
        report = await run_extraction_audit(
            neo4j_uri=args.neo4j_uri,
            output_path=args.output,
        )
        print(f"\nAudit Summary:")
        print(f"  Severity: {report.severity.value.upper()}")
        print(f"  Entities: {report.total_entities:,}")
        print(f"  Orphans: {report.total_orphans:,} ({report.orphan_rate:.1%})")
        print(f"  Relationships: {report.total_relationships:,}")
        print(f"  Ontology Coverage: {report.ontology_coverage:.1%}")
        print(f"\nReport saved to: {args.output}")

    asyncio.run(main())
