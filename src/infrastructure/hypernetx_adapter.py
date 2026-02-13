"""HyperNetX Adapter.

Loads FactUnit + PARTICIPATES_IN data from Neo4j into HyperNetX Hypergraph
objects for analytical operations. Neo4j remains the source of truth;
HyperNetX operates as an ephemeral in-memory analytical overlay.

Usage:
    adapter = HyperNetXAdapter(neo4j_backend)
    if adapter.is_available():
        H = await adapter.load_hypergraph(min_confidence=0.7)
"""

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Conditional import — graceful degradation when HyperNetX not installed
try:
    import hypernetx as hnx

    HNX_AVAILABLE = True
except ImportError:
    hnx = None
    HNX_AVAILABLE = False


class HyperNetXAdapter:
    """Adapter for loading Neo4j FactUnit data into HyperNetX Hypergraphs.

    Supports filtering by confidence, DIKW layer, document, and fact type.
    Caches loaded hypergraphs with a 5-minute TTL.
    """

    CACHE_TTL_SECONDS = 300  # 5 minutes

    LOAD_QUERY = """
        MATCH (e)-[p:PARTICIPATES_IN]->(f:FactUnit)
        WHERE 1=1
        {confidence_filter}
        {document_filter}
        {fact_type_filter}
        {layer_filter}
        RETURN
            f.id AS fact_id,
            f.fact_type AS fact_type,
            f.aggregate_confidence AS confidence,
            f.validated AS validated,
            f.validation_count AS validation_count,
            f.extraction_method AS extraction_method,
            f.source_document_id AS source_document_id,
            coalesce(e.id, e.name) AS entity_id,
            e.name AS entity_name,
            coalesce(e.type, labels(e)[0]) AS entity_type,
            coalesce(e.layer, 'PERCEPTION') AS entity_layer,
            coalesce(e.confidence, e.extraction_confidence, 0.7) AS entity_confidence,
            p.role AS participation_role
    """

    def __init__(self, neo4j_backend):
        """Initialize with a Neo4j backend.

        Args:
            neo4j_backend: KnowledgeGraphBackend instance for Neo4j queries
        """
        self.backend = neo4j_backend
        self._cache: Dict[str, Any] = {}  # cache_key -> (timestamp, hypergraph, node_props, edge_props)

    def is_available(self) -> bool:
        """Check if HyperNetX is installed and available."""
        return HNX_AVAILABLE

    async def load_hypergraph(
        self,
        min_confidence: Optional[float] = None,
        layer: Optional[str] = None,
        document_id: Optional[str] = None,
        fact_type: Optional[str] = None,
    ):
        """Load FactUnit data from Neo4j and construct a HyperNetX Hypergraph.

        Args:
            min_confidence: Minimum aggregate_confidence for FactUnits
            layer: DIKW layer filter (PERCEPTION, SEMANTIC, REASONING, APPLICATION)
            document_id: Filter by source document ID
            fact_type: Filter by fact type (treatment, causation, etc.)

        Returns:
            Tuple of (hnx.Hypergraph, node_properties dict, edge_properties dict)

        Raises:
            RuntimeError: If HyperNetX is not installed
        """
        if not HNX_AVAILABLE:
            raise RuntimeError(
                "HyperNetX is not installed. Install with: pip install hypernetx"
            )

        cache_key = self._make_cache_key(min_confidence, layer, document_id, fact_type)

        cached = self._cache.get(cache_key)
        if cached:
            ts, H, node_props, edge_props = cached
            if time.time() - ts < self.CACHE_TTL_SECONDS:
                logger.debug("HyperNetX cache hit for key %s", cache_key[:12])
                return H, node_props, edge_props

        # Build filtered query
        query = self._build_query(min_confidence, layer, document_id, fact_type)
        params = {}
        if min_confidence is not None:
            params["min_confidence"] = min_confidence
        if document_id is not None:
            params["document_id"] = document_id
        if fact_type is not None:
            params["fact_type"] = fact_type
        if layer is not None:
            params["layer"] = layer

        results = await self.backend.query_raw(query, params)

        # Build edge dict: fact_id -> set of entity_ids
        edge_dict: Dict[str, set] = {}
        node_props: Dict[str, Dict] = {}
        edge_props: Dict[str, Dict] = {}

        for row in results:
            fact_id = row["fact_id"]
            entity_id = row["entity_id"]

            if fact_id not in edge_dict:
                edge_dict[fact_id] = set()
                edge_props[fact_id] = {
                    "fact_type": row["fact_type"],
                    "confidence": row["confidence"],
                    "validated": row.get("validated", False),
                    "validation_count": row.get("validation_count", 0),
                    "extraction_method": row.get("extraction_method", "unknown"),
                    "source_document_id": row.get("source_document_id"),
                }

            edge_dict[fact_id].add(entity_id)

            if entity_id not in node_props:
                node_props[entity_id] = {
                    "name": row["entity_name"],
                    "entity_type": row["entity_type"],
                    "layer": row["entity_layer"],
                    "confidence": row["entity_confidence"],
                }

        # Construct HyperNetX Hypergraph
        if edge_dict:
            H = hnx.Hypergraph(edge_dict)
        else:
            H = hnx.Hypergraph({})

        # Cache the result
        self._cache[cache_key] = (time.time(), H, node_props, edge_props)

        logger.info(
            "Loaded HyperNetX hypergraph: %d edges, %d nodes",
            len(H.edges),
            len(H.nodes),
        )

        return H, node_props, edge_props

    def invalidate_cache(self):
        """Invalidate all cached hypergraphs."""
        self._cache.clear()
        logger.info("HyperNetX cache invalidated")

    def _build_query(
        self,
        min_confidence: Optional[float],
        layer: Optional[str],
        document_id: Optional[str],
        fact_type: Optional[str],
    ) -> str:
        """Build the Cypher query with appropriate filters."""
        confidence_filter = (
            "AND f.aggregate_confidence >= $min_confidence"
            if min_confidence is not None
            else ""
        )
        document_filter = (
            "AND f.source_document_id = $document_id"
            if document_id is not None
            else ""
        )
        fact_type_filter = (
            "AND f.fact_type = $fact_type" if fact_type is not None else ""
        )
        layer_filter = (
            "AND coalesce(e.layer, 'PERCEPTION') = $layer"
            if layer is not None
            else ""
        )

        return self.LOAD_QUERY.format(
            confidence_filter=confidence_filter,
            document_filter=document_filter,
            fact_type_filter=fact_type_filter,
            layer_filter=layer_filter,
        )

    def _make_cache_key(
        self,
        min_confidence: Optional[float],
        layer: Optional[str],
        document_id: Optional[str],
        fact_type: Optional[str],
    ) -> str:
        """Generate a cache key from filter parameters."""
        key_str = f"{min_confidence}:{layer}:{document_id}:{fact_type}"
        return hashlib.md5(key_str.encode()).hexdigest()
