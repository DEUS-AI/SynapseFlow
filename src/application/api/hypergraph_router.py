"""Hypergraph Analytics API Router.

REST API endpoints for hypergraph analytics, visualization data, and HIF export.
All endpoints return 503 if HyperNetX is not available.

Prefix: /api/hypergraph
"""

import logging
from dataclasses import asdict
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hypergraph", tags=["hypergraph"])

# Lazy singleton — set by dependency injection at startup
_analytics_service = None


def set_analytics_service(service):
    """Set the analytics service instance (called from dependencies.py)."""
    global _analytics_service
    _analytics_service = service


def get_analytics():
    """Dependency that provides the analytics service or raises 503."""
    if _analytics_service is None or not _analytics_service.is_available():
        raise HTTPException(
            status_code=503, detail="HyperNetX analytics not available"
        )
    return _analytics_service


@router.get("/summary")
async def get_summary(
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    layer: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    service=Depends(get_analytics),
):
    """Get topological summary of the hypergraph."""
    summary = await service.get_topological_summary(
        min_confidence=min_confidence, layer=layer, document_id=document_id
    )
    return asdict(summary)


@router.get("/centrality")
async def get_centrality(
    s: int = Query(1, ge=1),
    limit: Optional[int] = Query(None, ge=1),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    layer: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    service=Depends(get_analytics),
):
    """Get entity centrality rankings."""
    results = await service.compute_entity_centrality(
        s=s,
        limit=limit,
        min_confidence=min_confidence,
        layer=layer,
        document_id=document_id,
    )
    return [asdict(r) for r in results]


@router.get("/communities")
async def get_communities(
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    layer: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    service=Depends(get_analytics),
):
    """Detect knowledge communities."""
    result = await service.detect_knowledge_communities(
        min_confidence=min_confidence, layer=layer, document_id=document_id
    )
    return asdict(result)


@router.get("/connectivity")
async def get_connectivity(
    s_values: Optional[str] = Query(None, description="Comma-separated s values, e.g. 1,2,3"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    layer: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    service=Depends(get_analytics),
):
    """Analyze s-connected components."""
    parsed_s_values = None
    if s_values:
        parsed_s_values = [int(s.strip()) for s in s_values.split(",")]

    results = await service.analyze_connectivity(
        s_values=parsed_s_values,
        min_confidence=min_confidence,
        layer=layer,
        document_id=document_id,
    )
    return [asdict(r) for r in results]


@router.get("/entity/{entity_id}/distances")
async def get_entity_distances(
    entity_id: str,
    s: int = Query(1, ge=1),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    layer: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    service=Depends(get_analytics),
):
    """Get s-distances from a specific entity."""
    try:
        results = await service.compute_entity_distances(
            entity_id=entity_id,
            s=s,
            min_confidence=min_confidence,
            layer=layer,
            document_id=document_id,
        )
    except KeyError:
        raise HTTPException(
            status_code=404, detail="Entity not found in hypergraph"
        )
    return [asdict(r) for r in results]


@router.get("/visualization/euler")
async def get_euler_visualization(
    max_edges: Optional[int] = Query(None, ge=1, description="Limit to top N edges by confidence"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    layer: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    service=Depends(get_analytics),
):
    """Get D3-compatible JSON for Euler diagram visualization."""
    H, node_props, edge_props = await service.adapter.load_hypergraph(
        min_confidence=min_confidence, layer=layer, document_id=document_id
    )

    # Build nodes array
    nodes = []
    for node_id in H.nodes:
        nid = str(node_id)
        props = node_props.get(nid, {})
        nodes.append({
            "id": nid,
            "name": props.get("name", nid),
            "type": props.get("entity_type", "Unknown"),
            "layer": props.get("layer", "PERCEPTION"),
        })

    # Build sets (hyperedges) array, optionally limited
    edges_list = []
    for edge_id in H.edges:
        eid = str(edge_id)
        eprops = edge_props.get(eid, {})
        members = [str(m) for m in H.edges[edge_id]]
        edges_list.append({
            "id": eid,
            "members": members,
            "fact_type": eprops.get("fact_type", "unknown"),
            "confidence": eprops.get("confidence", 0.0),
        })

    # Sort by confidence and limit
    edges_list.sort(key=lambda e: e["confidence"], reverse=True)
    if max_edges:
        edges_list = edges_list[:max_edges]

    # Filter nodes to only those in visible edges
    visible_node_ids = set()
    for edge in edges_list:
        visible_node_ids.update(edge["members"])
    nodes = [n for n in nodes if n["id"] in visible_node_ids]

    return {"nodes": nodes, "sets": edges_list}


@router.get("/export/hif")
async def export_hif(
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    layer: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    service=Depends(get_analytics),
):
    """Export hypergraph in Hypergraph Interchange Format (HIF)."""
    H, node_props, edge_props = await service.adapter.load_hypergraph(
        min_confidence=min_confidence, layer=layer, document_id=document_id
    )

    # Build HIF format
    hif_nodes = []
    for node_id in H.nodes:
        nid = str(node_id)
        props = node_props.get(nid, {})
        hif_nodes.append({"node": nid, "attrs": props})

    hif_edges = []
    for edge_id in H.edges:
        eid = str(edge_id)
        eprops = edge_props.get(eid, {})
        members = [str(m) for m in H.edges[edge_id]]
        hif_edges.append({"edge": eid, "nodes": members, "attrs": eprops})

    hif_incidences = []
    for edge_id in H.edges:
        eid = str(edge_id)
        for member in H.edges[edge_id]:
            hif_incidences.append({"edge": eid, "node": str(member)})

    return {
        "network-type": "asc",
        "metadata": {"format": "HIF", "generator": "SynapseFlow"},
        "nodes": hif_nodes,
        "edges": hif_edges,
        "incidences": hif_incidences,
    }
