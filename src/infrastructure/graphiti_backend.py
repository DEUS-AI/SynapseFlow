"""Graphiti backend implementation.

This backend integrates with the Graphiti knowledge graph platform.
It maps the generic KnowledgeGraphBackend interface to Graphiti's
specific data structures (EntityNode, EntityEdge) and API.
"""

from typing import Any, Dict, Optional
from datetime import datetime
import json

from domain.kg_backends import KnowledgeGraphBackend
from graphiti_core import Graphiti
from graphiti_core.nodes import EntityNode
from graphiti_core.edges import EntityEdge


class GraphitiBackend(KnowledgeGraphBackend):
    """Graphiti implementation of the knowledge graph backend."""

    def __init__(self, graphiti_client: Graphiti, group_id: str = "default"):
        """Initialize Graphiti backend.
        
        Args:
            graphiti_client: Configured Graphiti client instance
            group_id: Default group ID for nodes and edges
        """
        self.client = graphiti_client
        self.group_id = group_id

    async def add_entity(self, entity_id: str, properties: Dict[str, Any]) -> None:
        """Add or update an entity in Graphiti.
        
        Since Graphiti is edge-centric, we use the driver to directly MERGE the node
        to ensure it exists with the correct properties, adhering to Graphiti's schema.
        """
        # Prepare properties
        props = properties.copy()
        name = props.pop("name", entity_id)
        
        # Serialize complex types
        serialized_props = {}
        for k, v in props.items():
            if isinstance(v, (dict, list)):
                serialized_props[k] = json.dumps(v)
            else:
                serialized_props[k] = v

        # Graphiti uses 'Entity' label by default for its index
        # We map entity_id to uuid
        query = """
        MERGE (n:Entity {uuid: $uuid})
        SET n.name = $name,
            n.group_id = $group_id,
            n.attributes = $attributes,
            n.updated_at = datetime()
        """
        
        await self.client.driver.execute_query(
            query, 
            {
                "uuid": entity_id,
                "name": name,
                "group_id": self.group_id,
                "attributes": json.dumps(serialized_props) # Graphiti stores attributes as JSON string often, or we can set individual props
            }
        )
        # Note: Graphiti's EntityNode puts attributes in a dict. 
        # In Neo4j, Graphiti often stores them as properties or a JSON blob.
        # Let's check EntityNode schema again? 
        # It has `attributes: dict`.
        # For now, we'll try to set them as node properties for easier querying, 
        # but also keep Graphiti happy if it expects specific fields.
        
        # Refined query to set properties directly on the node for better compatibility with other tools
        query_props = """
        MERGE (n:Entity {uuid: $uuid})
        SET n += $props,
            n.name = $name,
            n.group_id = $group_id
        """
        await self.client.driver.execute_query(
            query_props,
            {
                "uuid": entity_id,
                "name": name,
                "group_id": self.group_id,
                "props": serialized_props
            }
        )

    async def add_relationship(
        self,
        source_id: str,
        relationship_type: str,
        target_id: str,
        properties: Dict[str, Any],
    ) -> None:
        """Add a relationship using Graphiti's add_triplet."""
        # Create source and target nodes (wrappers)
        # We assume they exist or will be created/merged by add_triplet
        source_node = EntityNode(
            uuid=source_id,
            name=source_id, # Placeholder if not known, but uuid matches
            group_id=self.group_id,
            labels=["Entity"]
        )
        
        target_node = EntityNode(
            uuid=target_id,
            name=target_id,
            group_id=self.group_id,
            labels=["Entity"]
        )
        
        # Create edge
        edge = EntityEdge(
            group_id=self.group_id,
            source_node_uuid=source_id,
            target_node_uuid=target_id,
            created_at=datetime.now(),
            name=relationship_type,
            fact=properties.get("fact", f"{source_id} {relationship_type} {target_id}"),
            attributes=properties
        )
        
        await self.client.add_triplet(source_node, edge, target_node)

    async def rollback(self) -> None:
        """Rollback not supported."""
        pass

    async def query(self, query: str) -> Any:
        """Execute raw Cypher query via Graphiti driver."""
        return await self.client.driver.execute_query(query)

