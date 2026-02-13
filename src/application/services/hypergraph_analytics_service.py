"""Hypergraph Analytics Service.

Provides hypergraph analytics over FactUnit data using HyperNetX.
Wraps the HyperNetXAdapter and exposes high-level analytical methods
for centrality, community detection, connectivity, distances, topology,
and hypergraph diffs.

Usage:
    service = HypergraphAnalyticsService(adapter)
    centrality = await service.compute_entity_centrality(s=1)
    communities = await service.detect_knowledge_communities()
"""

import logging
import math
from typing import Dict, List, Optional

from domain.hypergraph_models import (
    CentralityResult,
    CommunityDetectionResult,
    CommunityResult,
    ConnectivityComponent,
    ConnectivityResult,
    DistanceResult,
    HypergraphDiff,
    TopologicalSummary,
)

logger = logging.getLogger(__name__)

try:
    import hypernetx as hnx
    import hypernetx.algorithms as hnx_alg

    HNX_AVAILABLE = True
except ImportError:
    hnx = None
    hnx_alg = None
    HNX_AVAILABLE = False


class HypergraphAnalyticsService:
    """Application service for hypergraph analytics over FactUnit data."""

    def __init__(self, adapter):
        """Initialize with a HyperNetXAdapter.

        Args:
            adapter: HyperNetXAdapter instance for loading hypergraphs
        """
        self.adapter = adapter

    def is_available(self) -> bool:
        """Check if analytics are available."""
        return self.adapter.is_available()

    async def compute_entity_centrality(
        self,
        s: int = 1,
        limit: Optional[int] = None,
        min_confidence: Optional[float] = None,
        layer: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[CentralityResult]:
        """Compute s-betweenness centrality for entities.

        Args:
            s: Minimum overlap between hyperedges for connectivity
            limit: Max number of results to return
            min_confidence: Filter FactUnits by confidence
            layer: Filter by DIKW layer
            document_id: Filter by source document

        Returns:
            Ranked list of CentralityResult, descending by score
        """
        H, node_props, edge_props = await self.adapter.load_hypergraph(
            min_confidence=min_confidence, layer=layer, document_id=document_id
        )

        if len(H.nodes) == 0:
            return []

        # Compute node-level s-betweenness centrality
        centrality_scores = hnx_alg.s_betweenness_centrality(H, s=s, edges=False)

        results = []
        for entity_id, score in centrality_scores.items():
            entity_id_str = str(entity_id)
            props = node_props.get(entity_id_str, {})
            fact_count = H.degree(entity_id)
            results.append(
                CentralityResult(
                    entity_id=entity_id_str,
                    entity_name=props.get("name", entity_id_str),
                    entity_type=props.get("entity_type", "Unknown"),
                    centrality_score=round(score, 6),
                    participating_fact_count=fact_count,
                )
            )

        results.sort(key=lambda r: r.centrality_score, reverse=True)

        if limit:
            results = results[:limit]

        return results

    async def detect_knowledge_communities(
        self,
        min_confidence: Optional[float] = None,
        layer: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> CommunityDetectionResult:
        """Detect communities using Kumar's algorithm.

        Returns:
            CommunityDetectionResult with communities and modularity scores
        """
        H, node_props, edge_props = await self.adapter.load_hypergraph(
            min_confidence=min_confidence, layer=layer, document_id=document_id
        )

        if len(H.nodes) == 0:
            return CommunityDetectionResult(
                total_communities=0, overall_modularity=0.0, communities=[]
            )

        # Kumar's algorithm returns list of sets
        partitions = hnx_alg.kumar(H)
        overall_modularity = hnx_alg.modularity(H, partitions)

        communities = []
        for idx, member_set in enumerate(partitions):
            member_ids = [str(m) for m in member_set]

            # Determine dominant entity types
            type_counts: Dict[str, int] = {}
            for mid in member_ids:
                etype = node_props.get(mid, {}).get("entity_type", "Unknown")
                type_counts[etype] = type_counts.get(etype, 0) + 1

            dominant_types = sorted(type_counts, key=type_counts.get, reverse=True)[
                :3
            ]

            communities.append(
                CommunityResult(
                    community_id=idx,
                    member_entity_ids=member_ids,
                    member_count=len(member_ids),
                    dominant_types=dominant_types,
                    modularity_contribution=round(
                        overall_modularity / max(len(partitions), 1), 4
                    ),
                )
            )

        return CommunityDetectionResult(
            total_communities=len(communities),
            overall_modularity=round(overall_modularity, 6),
            communities=communities,
        )

    async def analyze_connectivity(
        self,
        s_values: Optional[List[int]] = None,
        min_confidence: Optional[float] = None,
        layer: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[ConnectivityResult]:
        """Analyze s-connected components at varying strictness levels.

        Args:
            s_values: List of s values to analyze (default [1, 2, 3])

        Returns:
            List of ConnectivityResult, one per s value
        """
        if s_values is None:
            s_values = [1, 2, 3]

        H, node_props, edge_props = await self.adapter.load_hypergraph(
            min_confidence=min_confidence, layer=layer, document_id=document_id
        )

        if len(H.nodes) == 0:
            return [
                ConnectivityResult(s_value=s, component_count=0, components=[])
                for s in s_values
            ]

        results = []
        for s in s_values:
            try:
                raw_components = list(H.s_connected_components(s=s))
            except Exception:
                raw_components = []

            components = []
            for idx, comp in enumerate(raw_components):
                entity_ids = [str(e) for e in comp]
                components.append(
                    ConnectivityComponent(
                        component_id=idx,
                        size=len(entity_ids),
                        entity_ids=entity_ids,
                        is_knowledge_island=len(entity_ids) < 3,
                    )
                )

            components.sort(key=lambda c: c.size, reverse=True)

            results.append(
                ConnectivityResult(
                    s_value=s,
                    component_count=len(components),
                    components=components,
                )
            )

        return results

    async def compute_entity_distances(
        self,
        entity_id: str,
        s: int = 1,
        min_confidence: Optional[float] = None,
        layer: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[DistanceResult]:
        """Compute s-distances from a source entity to all others.

        Args:
            entity_id: Source entity ID
            s: Minimum overlap for s-walks

        Returns:
            List of DistanceResult sorted by ascending distance

        Raises:
            KeyError: If entity_id is not in the hypergraph
        """
        H, node_props, edge_props = await self.adapter.load_hypergraph(
            min_confidence=min_confidence, layer=layer, document_id=document_id
        )

        if entity_id not in H.nodes:
            raise KeyError(f"Entity '{entity_id}' not found in hypergraph")

        results = []
        for target_id in H.nodes:
            target_str = str(target_id)
            if target_str == entity_id:
                continue

            props = node_props.get(target_str, {})
            try:
                dist = H.distance(entity_id, target_id, s=s)
                if dist == math.inf or dist is None:
                    results.append(
                        DistanceResult(
                            entity_id=target_str,
                            entity_name=props.get("name", target_str),
                            distance=float("inf"),
                            reachable=False,
                        )
                    )
                else:
                    results.append(
                        DistanceResult(
                            entity_id=target_str,
                            entity_name=props.get("name", target_str),
                            distance=float(dist),
                            reachable=True,
                        )
                    )
            except Exception:
                results.append(
                    DistanceResult(
                        entity_id=target_str,
                        entity_name=props.get("name", target_str),
                        distance=float("inf"),
                        reachable=False,
                    )
                )

        results.sort(key=lambda r: (not r.reachable, r.distance))
        return results

    async def get_topological_summary(
        self,
        min_confidence: Optional[float] = None,
        layer: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> TopologicalSummary:
        """Get topological summary of the hypergraph.

        Returns:
            TopologicalSummary with node/edge counts, density, degree stats
        """
        H, node_props, edge_props = await self.adapter.load_hypergraph(
            min_confidence=min_confidence, layer=layer, document_id=document_id
        )

        num_nodes = len(H.nodes)
        num_edges = len(H.edges)

        if num_edges == 0:
            return TopologicalSummary(
                node_count=num_nodes,
                edge_count=0,
                density=0.0,
                avg_edge_size=0.0,
                max_edge_size=0,
                avg_node_degree=0.0,
                diameter=None,
            )

        # Edge sizes
        edge_sizes = H.edge_size_dist()
        avg_edge_size = sum(edge_sizes) / len(edge_sizes) if edge_sizes else 0.0
        max_edge_size = max(edge_sizes) if edge_sizes else 0

        # Node degrees
        degrees = [H.degree(n) for n in H.nodes]
        avg_node_degree = sum(degrees) / len(degrees) if degrees else 0.0

        # Density: ratio of actual edges to possible hyperedges
        # For hypergraphs: |E| / (2^|V| - 1)
        # Simplified: |E| * avg_edge_size / (|V| * (|V|-1)/2) for practical use
        if num_nodes > 1:
            density = (2 * num_edges * avg_edge_size) / (num_nodes * (num_nodes - 1))
            density = min(density, 1.0)
        else:
            density = 0.0

        # Diameter
        diameter = None
        try:
            if H.is_connected(s=1):
                diameter = H.diameter(s=1)
        except Exception:
            pass

        return TopologicalSummary(
            node_count=num_nodes,
            edge_count=num_edges,
            density=round(density, 6),
            avg_edge_size=round(avg_edge_size, 2),
            max_edge_size=max_edge_size,
            avg_node_degree=round(avg_node_degree, 2),
            diameter=diameter,
        )

    async def compute_hypergraph_diff(
        self,
        before_filters: Optional[Dict] = None,
        after_filters: Optional[Dict] = None,
    ) -> HypergraphDiff:
        """Compute diff between two hypergraph snapshots.

        Args:
            before_filters: Filter params for the "before" snapshot
            after_filters: Filter params for the "after" snapshot

        Returns:
            HypergraphDiff with added/removed/modified edges and nodes
        """
        before_filters = before_filters or {}
        after_filters = after_filters or {}

        H_before, _, edge_props_before = await self.adapter.load_hypergraph(
            **before_filters
        )
        # Invalidate cache to force fresh load for "after"
        self.adapter.invalidate_cache()
        H_after, _, edge_props_after = await self.adapter.load_hypergraph(
            **after_filters
        )

        before_edges = set(H_before.edges)
        after_edges = set(H_after.edges)
        before_nodes = set(str(n) for n in H_before.nodes)
        after_nodes = set(str(n) for n in H_after.nodes)

        added_edges = list(after_edges - before_edges)
        removed_edges = list(before_edges - after_edges)
        added_nodes = list(after_nodes - before_nodes)
        removed_nodes = list(before_nodes - after_nodes)

        # Modified: edges present in both but with changed confidence
        modified_edges = []
        for edge_id in before_edges & after_edges:
            edge_str = str(edge_id)
            before_conf = edge_props_before.get(edge_str, {}).get("confidence", 0)
            after_conf = edge_props_after.get(edge_str, {}).get("confidence", 0)
            if before_conf != after_conf:
                modified_edges.append(edge_str)

        return HypergraphDiff(
            added_edges=[str(e) for e in added_edges],
            removed_edges=[str(e) for e in removed_edges],
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            modified_edges=modified_edges,
        )
