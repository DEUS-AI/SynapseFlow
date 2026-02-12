"""Extended Knowledge Graph Audit Service.

Extends the Phase 0 extraction audit with deep subgraph analysis:
- Document Graph vs Knowledge Graph separation metrics
- Relationship distribution per subgraph
- Entity co-occurrence patterns within chunks
- Query path analysis for RAG/Quality services
- Bridge node identification

Usage:
    from application.services.extended_kg_audit_service import ExtendedKGAuditService

    service = ExtendedKGAuditService(neo4j_backend)
    report = await service.run_extended_audit()
    await service.save_report(report, "analysis/extended_kg_audit_report.md")
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from domain.chunk_separation_models import (
    SubgraphType,
    SubgraphMetrics,
    BridgeNodeMetrics,
    CoOccurrencePattern,
    QueryPathAnalysis,
    ExtendedKGAuditReport,
)

logger = logging.getLogger(__name__)


class ExtendedKGAuditService:
    """Extended KG audit service with subgraph separation analysis.

    Analyzes the knowledge graph to understand:
    1. How Document Graph (structural) and Knowledge Graph (semantic) are separated
    2. Bridge nodes connecting the two subgraphs
    3. Co-occurrence patterns within chunks
    4. Query traversal patterns
    """

    # Document Graph node labels
    DOCUMENT_GRAPH_LABELS = {
        "Document", "Chunk", "ExtractedEntity", "DocumentQuality"
    }

    # Known relationship types for each subgraph
    DOCUMENT_GRAPH_RELATIONSHIPS = {
        "HAS_CHUNK", "MENTIONS", "HAS_QUALITY"
    }

    KNOWLEDGE_GRAPH_RELATIONSHIPS = {
        "TREATS", "CAUSES", "INDICATES", "ASSOCIATED_WITH",
        "INTERACTS_WITH", "RELATED_TO", "REPRESENTS"
    }

    BRIDGE_RELATIONSHIPS = {
        "LINKS_TO"  # Connects ExtractedEntity to Knowledge entities
    }

    # Cypher queries for extended analysis
    EXTENDED_QUERIES = {
        "subgraph_node_distribution": """
            MATCH (n)
            WHERE n.name IS NOT NULL OR n.id IS NOT NULL
            WITH n,
                 CASE
                   WHEN any(label IN labels(n) WHERE label IN ['Document', 'Chunk', 'ExtractedEntity', 'DocumentQuality'])
                   THEN 'document_graph'
                   ELSE 'knowledge_graph'
                 END as subgraph
            RETURN subgraph, labels(n)[0] as primary_label, count(n) as count
            ORDER BY subgraph, count DESC
        """,

        "subgraph_relationship_distribution": """
            MATCH (a)-[r]->(b)
            WITH a, r, b,
                 CASE
                   WHEN type(r) IN ['HAS_CHUNK', 'MENTIONS', 'HAS_QUALITY'] THEN 'document_graph'
                   WHEN type(r) = 'LINKS_TO' THEN 'bridge'
                   ELSE 'knowledge_graph'
                 END as subgraph
            RETURN subgraph, type(r) as rel_type, count(r) as count
            ORDER BY subgraph, count DESC
        """,

        "bridge_nodes": """
            MATCH (ee)-[:LINKS_TO]->(ke)
            WHERE any(label IN labels(ee) WHERE label IN ['ExtractedEntity', 'Chunk'])
              AND NOT any(label IN labels(ke) WHERE label IN ['Document', 'Chunk', 'ExtractedEntity'])
            RETURN
                labels(ee) as source_labels,
                labels(ke) as target_labels,
                count(*) as bridge_count
            ORDER BY bridge_count DESC
            LIMIT 30
        """,

        "top_bridge_nodes": """
            MATCH (ee)-[r:LINKS_TO]->(ke)
            WHERE any(label IN labels(ee) WHERE label IN ['ExtractedEntity', 'Chunk'])
            WITH ke, count(r) as incoming_links
            ORDER BY incoming_links DESC
            LIMIT 20
            RETURN
                coalesce(ke.name, ke.id) as name,
                labels(ke) as labels,
                incoming_links
        """,

        "co_occurrence_patterns": """
            MATCH (c:Chunk)-[:MENTIONS]->(e1)
            MATCH (c)-[:MENTIONS]->(e2)
            WHERE id(e1) < id(e2)
            WITH labels(e1)[0] as type1, labels(e2)[0] as type2, count(*) as co_count
            WHERE co_count > 5
            RETURN type1, type2, co_count
            ORDER BY co_count DESC
            LIMIT 50
        """,

        "document_chunk_entity_path": """
            MATCH path = (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e)
            WITH length(path) as path_length, count(*) as frequency
            RETURN path_length, frequency
            ORDER BY path_length
        """,

        "entity_links_depth": """
            MATCH path = (ee:ExtractedEntity)-[:LINKS_TO*1..3]->(ke)
            WHERE NOT ke:ExtractedEntity AND NOT ke:Document AND NOT ke:Chunk
            WITH length(path) as depth, count(*) as frequency
            RETURN depth, frequency
            ORDER BY depth
        """,

        "document_graph_stats": """
            MATCH (n)
            WHERE any(label IN labels(n) WHERE label IN ['Document', 'Chunk', 'ExtractedEntity'])
            WITH n
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) as degree
            RETURN
                count(n) as node_count,
                avg(degree) as avg_degree,
                sum(CASE WHEN degree = 0 THEN 1 ELSE 0 END) as isolated_count
        """,

        "knowledge_graph_stats": """
            MATCH (n)
            WHERE NOT any(label IN labels(n) WHERE label IN ['Document', 'Chunk', 'ExtractedEntity', 'DocumentQuality'])
              AND (n.name IS NOT NULL OR n.id IS NOT NULL)
            WITH n
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) as degree
            RETURN
                count(n) as node_count,
                avg(degree) as avg_degree,
                sum(CASE WHEN degree = 0 THEN 1 ELSE 0 END) as isolated_count
        """,

        "chunk_text_size": """
            MATCH (c:Chunk)
            WHERE c.text IS NOT NULL
            RETURN
                count(c) as chunk_count,
                avg(size(c.text)) as avg_text_size,
                sum(size(c.text)) as total_text_bytes
        """,
    }

    def __init__(self, neo4j_backend):
        """Initialize the extended audit service.

        Args:
            neo4j_backend: Neo4j backend instance for queries
        """
        self.backend = neo4j_backend

    async def run_extended_audit(
        self,
        include_base_metrics: bool = True
    ) -> ExtendedKGAuditReport:
        """Execute complete extended KG audit.

        Args:
            include_base_metrics: Include Phase 0 base metrics

        Returns:
            ExtendedKGAuditReport with all analysis results
        """
        start_time = datetime.now()

        report = ExtendedKGAuditReport(
            audit_id=str(uuid.uuid4())[:8],
            generated_at=start_time,
        )

        try:
            logger.info("Starting extended KG audit...")

            # Run base metrics if requested
            if include_base_metrics:
                await self._collect_base_metrics(report)

            # Run subgraph analysis
            await self._analyze_subgraphs(report)

            # Analyze bridge nodes
            await self._analyze_bridge_nodes(report)

            # Analyze co-occurrence patterns
            await self._analyze_co_occurrence(report)

            # Analyze query paths
            await self._analyze_query_paths(report)

            # Compute separation readiness
            report.compute_separation_readiness()

            # Generate recommendations
            self._generate_recommendations(report)

        except Exception as e:
            logger.error(f"Extended audit failed: {e}")
            report.identified_issues.append(f"Audit error: {str(e)}")

        # Calculate processing time
        end_time = datetime.now()
        report.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        logger.info(f"Extended audit completed in {report.processing_time_ms}ms")

        return report

    async def _collect_base_metrics(self, report: ExtendedKGAuditReport) -> None:
        """Collect base metrics from Phase 0 audit."""
        try:
            # Total entities
            result = await self.backend.query_raw(
                "MATCH (n) WHERE n.name IS NOT NULL OR n.id IS NOT NULL RETURN count(n) as count",
                {}
            )
            report.total_entities = result[0]["count"] if result else 0

            # Total relationships
            result = await self.backend.query_raw(
                "MATCH ()-[r]->() RETURN count(r) as count",
                {}
            )
            report.total_relationships = result[0]["count"] if result else 0

            # Orphans
            result = await self.backend.query_raw(
                "MATCH (n) WHERE NOT (n)--() AND (n.name IS NOT NULL OR n.id IS NOT NULL) RETURN count(n) as count",
                {}
            )
            report.total_orphans = result[0]["count"] if result else 0

            if report.total_entities > 0:
                report.orphan_rate = report.total_orphans / report.total_entities

            logger.info(
                f"Base metrics: {report.total_entities} entities, "
                f"{report.total_orphans} orphans ({report.orphan_rate:.1%})"
            )

        except Exception as e:
            logger.warning(f"Failed to collect base metrics: {e}")

    async def _analyze_subgraphs(self, report: ExtendedKGAuditReport) -> None:
        """Analyze Document Graph and Knowledge Graph separately."""
        try:
            # Get node distribution by subgraph
            node_dist = await self.backend.query_raw(
                self.EXTENDED_QUERIES["subgraph_node_distribution"],
                {}
            )

            # Get relationship distribution by subgraph
            rel_dist = await self.backend.query_raw(
                self.EXTENDED_QUERIES["subgraph_relationship_distribution"],
                {}
            )

            # Get Document Graph stats
            doc_stats = await self.backend.query_raw(
                self.EXTENDED_QUERIES["document_graph_stats"],
                {}
            )

            # Get Knowledge Graph stats
            kg_stats = await self.backend.query_raw(
                self.EXTENDED_QUERIES["knowledge_graph_stats"],
                {}
            )

            # Build Document Graph metrics
            doc_labels = {}
            doc_node_count = 0
            for row in node_dist:
                if row.get("subgraph") == "document_graph":
                    label = row.get("primary_label", "Unknown")
                    count = row.get("count", 0)
                    doc_labels[label] = count
                    doc_node_count += count

            doc_rels = {}
            doc_rel_count = 0
            for row in rel_dist:
                if row.get("subgraph") == "document_graph":
                    rel_type = row.get("rel_type", "Unknown")
                    count = row.get("count", 0)
                    doc_rels[rel_type] = count
                    doc_rel_count += count

            report.document_graph = SubgraphMetrics(
                subgraph_type=SubgraphType.DOCUMENT_GRAPH,
                node_count=doc_node_count,
                relationship_count=doc_rel_count,
                node_labels=doc_labels,
                relationship_types=doc_rels,
                avg_degree=doc_stats[0].get("avg_degree", 0) if doc_stats else 0,
                isolated_nodes=doc_stats[0].get("isolated_count", 0) if doc_stats else 0,
                percentage_of_total=doc_node_count / max(report.total_entities, 1) * 100,
            )

            # Build Knowledge Graph metrics
            kg_labels = {}
            kg_node_count = 0
            for row in node_dist:
                if row.get("subgraph") == "knowledge_graph":
                    label = row.get("primary_label", "Unknown")
                    count = row.get("count", 0)
                    kg_labels[label] = count
                    kg_node_count += count

            kg_rels = {}
            kg_rel_count = 0
            for row in rel_dist:
                if row.get("subgraph") == "knowledge_graph":
                    rel_type = row.get("rel_type", "Unknown")
                    count = row.get("count", 0)
                    kg_rels[rel_type] = count
                    kg_rel_count += count

            report.knowledge_graph = SubgraphMetrics(
                subgraph_type=SubgraphType.KNOWLEDGE_GRAPH,
                node_count=kg_node_count,
                relationship_count=kg_rel_count,
                node_labels=kg_labels,
                relationship_types=kg_rels,
                avg_degree=kg_stats[0].get("avg_degree", 0) if kg_stats else 0,
                isolated_nodes=kg_stats[0].get("isolated_count", 0) if kg_stats else 0,
                percentage_of_total=kg_node_count / max(report.total_entities, 1) * 100,
            )

            # Store bridge relationship count
            bridge_rels = {}
            bridge_rel_count = 0
            for row in rel_dist:
                if row.get("subgraph") == "bridge":
                    rel_type = row.get("rel_type", "Unknown")
                    count = row.get("count", 0)
                    bridge_rels[rel_type] = count
                    bridge_rel_count += count

            report.relationships_by_subgraph = {
                "document_graph": doc_rels,
                "knowledge_graph": kg_rels,
                "bridge": bridge_rels,
            }

            logger.info(
                f"Subgraph analysis: Document Graph {doc_node_count} nodes, "
                f"Knowledge Graph {kg_node_count} nodes"
            )

        except Exception as e:
            logger.warning(f"Failed to analyze subgraphs: {e}")

    async def _analyze_bridge_nodes(self, report: ExtendedKGAuditReport) -> None:
        """Analyze nodes that bridge Document and Knowledge graphs."""
        try:
            # Get bridge node patterns
            bridge_patterns = await self.backend.query_raw(
                self.EXTENDED_QUERIES["bridge_nodes"],
                {}
            )

            # Get top bridge nodes
            top_bridges = await self.backend.query_raw(
                self.EXTENDED_QUERIES["top_bridge_nodes"],
                {}
            )

            bridge_node_types = {}
            bridge_rel_count = 0

            for row in bridge_patterns:
                target_labels = row.get("target_labels", [])
                count = row.get("bridge_count", 0)
                bridge_rel_count += count

                for label in target_labels:
                    if label not in ["Entity"]:  # Skip generic label
                        bridge_node_types[label] = bridge_node_types.get(label, 0) + count

            top_bridge_list = [
                {
                    "name": row.get("name", "Unknown"),
                    "labels": row.get("labels", []),
                    "incoming_links": row.get("incoming_links", 0),
                }
                for row in top_bridges
            ]

            report.bridge_metrics = BridgeNodeMetrics(
                bridge_node_count=len(bridge_node_types),
                bridge_relationship_count=bridge_rel_count,
                bridge_node_types=bridge_node_types,
                bridge_relationship_types={"LINKS_TO": bridge_rel_count},
                top_bridge_nodes=top_bridge_list,
            )

            logger.info(
                f"Bridge analysis: {bridge_rel_count} bridge relationships, "
                f"{len(bridge_node_types)} target types"
            )

        except Exception as e:
            logger.warning(f"Failed to analyze bridge nodes: {e}")

    async def _analyze_co_occurrence(self, report: ExtendedKGAuditReport) -> None:
        """Analyze entity type co-occurrence within chunks."""
        try:
            co_occur = await self.backend.query_raw(
                self.EXTENDED_QUERIES["co_occurrence_patterns"],
                {}
            )

            patterns = []
            for row in co_occur:
                type1 = row.get("type1", "Unknown")
                type2 = row.get("type2", "Unknown")
                count = row.get("co_count", 0)

                patterns.append(CoOccurrencePattern(
                    type_pair=(type1, type2),
                    co_occurrence_count=count,
                ))

            report.co_occurrence_patterns = patterns

            logger.info(f"Co-occurrence analysis: {len(patterns)} patterns found")

        except Exception as e:
            logger.warning(f"Failed to analyze co-occurrence: {e}")

    async def _analyze_query_paths(self, report: ExtendedKGAuditReport) -> None:
        """Analyze common query traversal paths."""
        try:
            # Document → Chunk → Entity path
            doc_chunk_entity = await self.backend.query_raw(
                self.EXTENDED_QUERIES["document_chunk_entity_path"],
                {}
            )

            total_traversals = sum(r.get("frequency", 0) for r in doc_chunk_entity)

            if doc_chunk_entity:
                report.query_paths.append(QueryPathAnalysis(
                    path_pattern="Document → HAS_CHUNK → Chunk → MENTIONS → Entity",
                    frequency=total_traversals,
                    avg_traversal_depth=3,
                    services_using=["RAGService", "DocumentService", "DocumentRouter API"],
                ))

            # Entity → LINKS_TO depth
            entity_links = await self.backend.query_raw(
                self.EXTENDED_QUERIES["entity_links_depth"],
                {}
            )

            link_traversals = sum(r.get("frequency", 0) for r in entity_links)

            if entity_links:
                avg_depth = sum(
                    r.get("depth", 0) * r.get("frequency", 0)
                    for r in entity_links
                ) / max(link_traversals, 1)

                report.query_paths.append(QueryPathAnalysis(
                    path_pattern="ExtractedEntity → LINKS_TO → KnowledgeEntity",
                    frequency=link_traversals,
                    avg_traversal_depth=int(avg_depth),
                    services_using=["RAGService"],
                ))

            logger.info(f"Query path analysis: {len(report.query_paths)} paths analyzed")

        except Exception as e:
            logger.warning(f"Failed to analyze query paths: {e}")

    def _generate_recommendations(self, report: ExtendedKGAuditReport) -> None:
        """Generate recommendations based on audit findings."""
        recommendations = []

        # Check Document Graph dominance
        if report.document_graph:
            doc_pct = report.document_graph.percentage_of_total
            if doc_pct > 60:
                recommendations.append(
                    f"Document Graph represents {doc_pct:.1f}% of total entities. "
                    "Consider Option A (indexes) or Option B (PostgreSQL) for chunk separation."
                )

        # Check bridge complexity
        if report.bridge_metrics:
            bridge_count = report.bridge_metrics.bridge_relationship_count
            if bridge_count > 5000:
                recommendations.append(
                    f"High bridge relationship count ({bridge_count:,}). "
                    "Cross-store queries would be frequent if chunks are separated."
                )

        # Check co-occurrence complexity
        if len(report.co_occurrence_patterns) > 30:
            recommendations.append(
                f"Complex co-occurrence patterns ({len(report.co_occurrence_patterns)} types). "
                "Consider maintaining chunk-entity relationships even after separation."
            )

        # Separation readiness
        if report.separation_readiness == "ready":
            recommendations.append(
                "Graph structure is ready for chunk separation. "
                "Recommend starting with Option A (Neo4j indexes + labels)."
            )
        elif report.separation_readiness == "needs_work":
            recommendations.append(
                "Graph needs optimization before separation. "
                "Address identified issues first."
            )
        else:
            recommendations.append(
                "Graph is not ready for separation. "
                "Focus on reducing bridge complexity and standardizing entity types."
            )

        report.recommendations = recommendations

    async def save_report(
        self,
        report: ExtendedKGAuditReport,
        output_path: str
    ) -> str:
        """Save extended audit report as Markdown file.

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

        logger.info(f"Extended audit report saved to {path}")
        return str(path)

    def _format_markdown_report(self, report: ExtendedKGAuditReport) -> str:
        """Format report as Markdown."""
        lines = [
            "# Extended Knowledge Graph Audit Report",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Processing Time:** {report.processing_time_ms}ms",
            f"**Separation Readiness:** {report.separation_readiness.upper()}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Entities | {report.total_entities:,} |",
            f"| Total Relationships | {report.total_relationships:,} |",
            f"| Total Orphans | {report.total_orphans:,} ({report.orphan_rate:.1%}) |",
            f"| Ontology Coverage | {report.ontology_coverage:.1%} |",
            "",
        ]

        # Subgraph Summary
        if report.document_graph and report.knowledge_graph:
            lines.extend([
                "---",
                "",
                "## Subgraph Analysis",
                "",
                "| Subgraph | Nodes | % of Total | Relationships | Avg Degree |",
                "|----------|-------|------------|---------------|------------|",
                f"| Document Graph | {report.document_graph.node_count:,} | {report.document_graph.percentage_of_total:.1f}% | {report.document_graph.relationship_count:,} | {report.document_graph.avg_degree:.1f} |",
                f"| Knowledge Graph | {report.knowledge_graph.node_count:,} | {report.knowledge_graph.percentage_of_total:.1f}% | {report.knowledge_graph.relationship_count:,} | {report.knowledge_graph.avg_degree:.1f} |",
                "",
            ])

        # Document Graph Labels
        if report.document_graph and report.document_graph.node_labels:
            lines.extend([
                "### Document Graph Node Types",
                "",
                "| Label | Count |",
                "|-------|-------|",
            ])
            for label, count in sorted(
                report.document_graph.node_labels.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:
                lines.append(f"| {label} | {count:,} |")
            lines.append("")

        # Knowledge Graph Labels
        if report.knowledge_graph and report.knowledge_graph.node_labels:
            lines.extend([
                "### Knowledge Graph Node Types",
                "",
                "| Label | Count |",
                "|-------|-------|",
            ])
            for label, count in sorted(
                report.knowledge_graph.node_labels.items(),
                key=lambda x: x[1],
                reverse=True
            )[:15]:
                lines.append(f"| {label} | {count:,} |")
            lines.append("")

        # Bridge Analysis
        if report.bridge_metrics:
            lines.extend([
                "---",
                "",
                "## Bridge Analysis",
                "",
                f"**Bridge Relationships:** {report.bridge_metrics.bridge_relationship_count:,}",
                "",
                "### Top Bridge Target Types",
                "",
                "| Target Type | Count |",
                "|-------------|-------|",
            ])
            for label, count in sorted(
                report.bridge_metrics.bridge_node_types.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:
                lines.append(f"| {label} | {count:,} |")
            lines.append("")

            if report.bridge_metrics.top_bridge_nodes:
                lines.extend([
                    "### Top Bridge Nodes (Most Linked)",
                    "",
                    "| Name | Labels | Incoming Links |",
                    "|------|--------|----------------|",
                ])
                for node in report.bridge_metrics.top_bridge_nodes[:10]:
                    name = str(node.get("name", "Unknown"))[:40]
                    labels = ", ".join(node.get("labels", [])[:2])
                    links = node.get("incoming_links", 0)
                    lines.append(f"| {name} | {labels} | {links:,} |")
                lines.append("")

        # Co-occurrence Patterns
        if report.co_occurrence_patterns:
            lines.extend([
                "---",
                "",
                "## Co-occurrence Patterns",
                "",
                "Entity types that frequently appear together in chunks:",
                "",
                "| Type 1 | Type 2 | Co-occurrences |",
                "|--------|--------|----------------|",
            ])
            for pattern in report.co_occurrence_patterns[:15]:
                t1, t2 = pattern.type_pair
                lines.append(f"| {t1} | {t2} | {pattern.co_occurrence_count:,} |")
            lines.append("")

        # Query Paths
        if report.query_paths:
            lines.extend([
                "---",
                "",
                "## Query Path Analysis",
                "",
                "| Path Pattern | Frequency | Services Using |",
                "|--------------|-----------|----------------|",
            ])
            for path in report.query_paths:
                services = ", ".join(path.services_using[:3])
                lines.append(f"| {path.path_pattern} | {path.frequency:,} | {services} |")
            lines.append("")

        # Issues and Recommendations
        lines.extend([
            "---",
            "",
            "## Issues Identified",
            "",
        ])
        if report.identified_issues:
            for issue in report.identified_issues:
                lines.append(f"- {issue}")
        else:
            lines.append("No critical issues identified.")
        lines.append("")

        lines.extend([
            "## Recommendations",
            "",
        ])
        for rec in report.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

        lines.extend([
            "---",
            "",
            "*Generated by ExtendedKGAuditService*",
        ])

        return "\n".join(lines)


async def run_extended_audit(
    neo4j_uri: str = None,
    neo4j_user: str = None,
    neo4j_password: str = None,
    output_path: str = "analysis/extended_kg_audit_report.md",
) -> ExtendedKGAuditReport:
    """Convenience function to run extended KG audit.

    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        output_path: Path for the output report

    Returns:
        ExtendedKGAuditReport with all findings
    """
    import os
    from infrastructure.neo4j_backend import Neo4jBackend

    uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
    password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")

    backend = Neo4jBackend(uri, user, password)

    try:
        service = ExtendedKGAuditService(backend)
        report = await service.run_extended_audit()
        await service.save_report(report, output_path)
        return report
    finally:
        await backend.close()


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run extended KG audit with subgraph analysis"
    )
    parser.add_argument(
        "--output", "-o",
        default="analysis/extended_kg_audit_report.md",
        help="Output path for the report"
    )

    args = parser.parse_args()

    async def main():
        report = await run_extended_audit(output_path=args.output)
        print(f"\n========== EXTENDED AUDIT SUMMARY ==========")
        print(f"Separation Readiness: {report.separation_readiness.upper()}")
        print(f"Total Entities: {report.total_entities:,}")

        if report.document_graph:
            print(f"Document Graph: {report.document_graph.node_count:,} nodes ({report.document_graph.percentage_of_total:.1f}%)")

        if report.knowledge_graph:
            print(f"Knowledge Graph: {report.knowledge_graph.node_count:,} nodes ({report.knowledge_graph.percentage_of_total:.1f}%)")

        if report.bridge_metrics:
            print(f"Bridge Relationships: {report.bridge_metrics.bridge_relationship_count:,}")

        print(f"\nReport saved to: {args.output}")

    asyncio.run(main())
