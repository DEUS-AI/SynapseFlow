"""In‑memory implementation of the knowledge graph backend.

This backend stores nodes and edges in dictionaries.  It is primarily
intended for unit testing and local development where a real graph
database is unnecessary or unavailable.
"""

from typing import Any, Dict, List, Tuple

from domain.kg_backends import KnowledgeGraphBackend


class InMemoryGraphBackend(KnowledgeGraphBackend):
    """A simple graph backend that stores data in memory."""

    def __init__(self) -> None:
        # Each node is keyed by its ID and stores a properties dict
        self.nodes: Dict[str, Dict[str, Any]] = {}
        # Edges keyed by source ID; each entry is a list of tuples
        # (relationship_type, target_id, properties)
        self.edges: Dict[str, List[Tuple[str, str, Dict[str, Any]]]] = {}
        # History stack for rudimentary rollback support
        self._history: List[Tuple[str, Any]] = []

    async def add_entity(self, entity_id: str, properties: Dict[str, Any], labels: List[str] = None) -> None:
        # Overwrite existing properties if the entity already exists
        props = dict(properties)
        if labels:
            props["labels"] = labels
        self.nodes[entity_id] = props
        # Record history for rollback
        self._history.append(("entity", entity_id))

    async def add_relationship(
        self,
        source_id: str,
        relationship_type: str,
        target_id: str,
        properties: Dict[str, Any],
    ) -> None:
        self.edges.setdefault(source_id, []).append((relationship_type, target_id, dict(properties)))
        self._history.append(("edge", (source_id, target_id)))

    async def rollback(self) -> None:
        """Rollback the last entity or relationship addition."""
        if not self._history:
            return
        kind, info = self._history.pop()
        if kind == "entity":
            # Remove entity and any outgoing edges
            self.nodes.pop(info, None)
            self.edges.pop(info, None)
        elif kind == "edge":
            source_id, target_id = info
            if source_id in self.edges:
                # Remove the last edge that matches the target
                edges_list = self.edges[source_id]
                for i in range(len(edges_list) - 1, -1, -1):
                    _, tgt, _ = edges_list[i]
                    if tgt == target_id:
                        edges_list.pop(i)
                        break
                if not edges_list:
                    del self.edges[source_id]

    async def query(self, query: str) -> Dict[str, Any]:
        """Return a snapshot of the in‑memory graph.

        The query string is ignored; this backend returns its entire state.
        """
        # Return deep copies to prevent external mutation
        import copy

        return {
            "nodes": copy.deepcopy(self.nodes),
            "edges": {k: copy.deepcopy(v) for k, v in self.edges.items()},
        }

    async def list_relationships(
        self,
        source_id: str = None,
        target_id: str = None,
        relationship_type: str = None
    ) -> List[Dict[str, Any]]:
        """List relationships matching criteria."""
        results = []
        
        for src, edges in self.edges.items():
            if source_id and src != source_id:
                continue
                
            for rel_type, tgt, props in edges:
                if target_id and tgt != target_id:
                    continue
                
                if relationship_type and rel_type != relationship_type:
                    continue
                    
                results.append({
                    "source": src,
                    "target": tgt,
                    "type": rel_type,
                    "properties": props
                })
        
        return results
