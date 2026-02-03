"""FalkorDB backend implementation.

This backend connects to a FalkorDB instance to store knowledge graph data.
"""

from typing import Any, Dict, List, Optional
from falkordb import FalkorDB

from domain.kg_backends import KnowledgeGraphBackend


class FalkorBackend(KnowledgeGraphBackend):
    """FalkorDB implementation of the knowledge graph backend."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        graph_name: str = "knowledge_graph"
    ) -> None:
        """Initialize FalkorDB backend.
        
        Args:
            host: FalkorDB host
            port: FalkorDB port
            password: Redis password (if any)
            graph_name: Name of the graph key in Redis
        """
        self.host = host
        self.port = port
        self.password = password
        self.graph_name = graph_name
        
        # Initialize client
        self.client = FalkorDB(host=host, port=port, password=password)
        self.graph = self.client.select_graph(graph_name)
        
        # History for rollback (stores inverse operations)
        self._history: List[Dict[str, Any]] = []

    async def add_entity(self, entity_id: str, properties: Dict[str, Any]) -> None:
        """Add or update an entity (node) in the graph."""
        import json
        import asyncio
        
        # In FalkorDB/Cypher, we typically use labels. 
        # We'll assume the entity_id format "label:id" or just use a generic Entity label if not specified.
        
        label = "Entity"
        real_id = entity_id
        
        if ":" in entity_id:
            parts = entity_id.split(":", 1)
            label = parts[0]
            real_id = parts[1]
            
        # Prepare properties - flatten and convert complex types
        props = {}
        props["id"] = real_id
        props["_full_id"] = entity_id
        
        # Flatten properties dict and convert complex types to JSON strings
        # Special handling: if 'properties' key exists and is a dict, flatten it into the main props
        # This is to handle Pydantic models that have a 'properties' field (like ODIN models)
        
        flat_properties = properties.copy()
        if "properties" in flat_properties and isinstance(flat_properties["properties"], dict):
            nested_props = flat_properties.pop("properties")
            flat_properties.update(nested_props)
            
        for key, value in flat_properties.items():
            if value is None:
                continue
            elif isinstance(value, (dict, list)):
                # Convert complex types to JSON strings
                props[key] = json.dumps(value)
            elif hasattr(value, 'value'): # Handle Enum
                props[key] = str(value.value)
            elif isinstance(value, (str, int, float, bool)):
                props[key] = value
            else:
                # Convert other types to strings
                props[key] = str(value)
        
        # Construct MERGE query
        query = f"""
        MERGE (n:{label} {{id: $id}})
        SET n += $props
        """
        
        params = {"id": real_id, "props": props}
        
        # Run synchronous query in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.graph.query(query, params))
        
        # Record for rollback
        self._history.append({
            "type": "entity",
            "id": real_id,
            "label": label
        })

    async def add_relationship(
        self,
        source_id: str,
        relationship_type: str,
        target_id: str,
        properties: Dict[str, Any],
    ) -> None:
        """Add a relationship between two entities."""
        import json
        import asyncio
        
        source_label = "Entity"
        source_real_id = source_id
        if ":" in source_id:
            parts = source_id.split(":", 1)
            source_label = parts[0]
            source_real_id = parts[1]
            
        target_label = "Entity"
        target_real_id = target_id
        if ":" in target_id:
            parts = target_id.split(":", 1)
            target_label = parts[0]
            target_real_id = parts[1]
        
        # Flatten properties and convert complex types
        props = {}
        for key, value in properties.items():
            if value is None:
                continue
            elif isinstance(value, (dict, list)):
                props[key] = json.dumps(value)
            elif hasattr(value, 'value'): # Handle Enum
                props[key] = str(value.value)
            elif isinstance(value, (str, int, float, bool)):
                props[key] = value
            else:
                props[key] = str(value)
            
        query = f"""
        MATCH (s:{source_label} {{id: $source_id}})
        MATCH (t:{target_label} {{id: $target_id}})
        MERGE (s)-[r:{relationship_type}]->(t)
        SET r += $props
        """
        
        params = {
            "source_id": source_real_id,
            "target_id": target_real_id,
            "props": props
        }
        
        # Run synchronous query in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.graph.query(query, params))
        
        # Record for rollback
        self._history.append({
            "type": "relationship",
            "source": source_real_id,
            "source_label": source_label,
            "target": target_real_id,
            "target_label": target_label,
            "rel_type": relationship_type
        })

    async def rollback(self) -> None:
        """Rollback the last operation."""
        import asyncio
        if not self._history:
            return
            
        op = self._history.pop()
        loop = asyncio.get_event_loop()
        
        if op["type"] == "entity":
            # Delete the node
            query = f"MATCH (n:{op['label']} {{id: $id}}) DETACH DELETE n"
            await loop.run_in_executor(None, lambda: self.graph.query(query, {"id": op["id"]}))
            
        elif op["type"] == "relationship":
            # Delete the relationship
            query = f"""
            MATCH (s:{op['source_label']} {{id: $source_id}})-[r:{op['rel_type']}]->(t:{op['target_label']} {{id: $target_id}})
            DELETE r
            """
            params = {
                "source_id": op["source"],
                "target_id": op["target"]
            }
            await loop.run_in_executor(None, lambda: self.graph.query(query, params))

    async def query(self, query: str) -> Any:
        """Execute a raw Cypher query.
        
        Returns a dict with 'nodes' key for MATCH queries that return nodes.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        
        # Run synchronous query in executor
        result = await loop.run_in_executor(None, lambda: self.graph.query(query))
        
        # If this is a MATCH query returning nodes, parse result_set into node dicts
        if result.result_set and query.strip().upper().startswith("MATCH"):
            nodes = []
            for row in result.result_set:
                # Each row should contain a node
                if row and len(row) > 0:
                    node_data = row[0]
                    # FalkorDB returns a Node object, extract its properties
                    if hasattr(node_data, 'properties'):
                        node_dict = {
                            "id": node_data.properties.get("id", ""),
                            "properties": dict(node_data.properties)
                        }
                        nodes.append(node_dict)
            return {"nodes": nodes}
        
        # For other queries, return raw result
        return result.result_set
