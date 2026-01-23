"""Neo4j implementation of the knowledge graph backend.

This backend provides persistent storage using Neo4j database.
It implements the KnowledgeGraphBackend interface and supports
all CRUD operations for entities and relationships.
"""

import asyncio
from typing import Any, Dict, List, Tuple, Optional
from neo4j import AsyncGraphDatabase
from domain.kg_backends import KnowledgeGraphBackend


class Neo4jBackend(KnowledgeGraphBackend):
    """Neo4j backend for persistent knowledge graph storage."""

    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """Initialize Neo4j backend.
        
        Args:
            uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            username: Neo4j username
            password: Neo4j password
            database: Neo4j database name (default: "neo4j")
        """
        self.uri = uri
        
        self.username = username
        self.password = password
        self.database = database
        self._driver = None

    async def _get_driver(self):
        """Get or create Neo4j driver."""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
        return self._driver

    async def _close_driver(self):
        """Close Neo4j driver."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def add_entity(self, entity_id: str, properties: Dict[str, Any], labels: List[str] = None) -> None:
        """Add or update an entity in Neo4j.
        
        Args:
            entity_id: Unique identifier for the entity
            properties: Entity properties as key-value pairs
            labels: Optional list of node labels (e.g., ["BusinessConcept", "Concept"])
        """
        driver = await self._get_driver()
        
        # Build label string (e.g., ":Entity:BusinessConcept:Concept")
        if labels:
            label_str = ":Entity:" + ":".join(labels)
        else:
            label_str = ":Entity"
        
        # Create Cypher query to merge entity with dynamic labels
        # We need to use APOC or a two-step query because labels can't be parameterized
        query = f"""
        MERGE (n{label_str} {{id: $entity_id}})
        SET n += $properties
        RETURN n
        """
        
        async with driver.session(database=self.database) as session:
            await session.run(query, entity_id=entity_id, properties=properties)

    async def add_relationship(
        self,
        source_id: str,
        relationship_type: str,
        target_id: str,
        properties: Dict[str, Any],
    ) -> None:
        """Add a relationship between two entities.
        
        Creates source/target nodes if they don't exist.
        
        Args:
            source_id: Source entity ID
            relationship_type: Type of relationship
            target_id: Target entity ID
            properties: Relationship properties
        """
        driver = await self._get_driver()
        
        # Sanitize relationship type (replace special chars)
        safe_rel_type = relationship_type.replace(":", "_").replace(" ", "_").upper()
        
        # Use MERGE for nodes to ensure they exist, then create relationship
        query = f"""
        MERGE (source:Entity {{id: $source_id}})
        MERGE (target:Entity {{id: $target_id}})
        MERGE (source)-[r:`{safe_rel_type}`]->(target)
        SET r += $properties
        RETURN r
        """
        
        async with driver.session(database=self.database) as session:
            await session.run(query, 
                            source_id=source_id, 
                            target_id=target_id, 
                            properties=properties)

    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            Entity properties or None if not found
        """
        driver = await self._get_driver()
        
        query = """
        MATCH (n:Entity {id: $entity_id})
        RETURN n
        """
        
        async with driver.session(database=self.database) as session:
            result = await session.run(query, entity_id=entity_id)
            record = await result.single()
            
            if record:
                node = record["n"]
                return {
                    "id": node["id"],
                    "properties": dict(node),
                    "labels": list(node.labels)
                }
            return None

    async def list_entities(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List entities with pagination.
        
        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip
            
        Returns:
            List of entity dictionaries
        """
        driver = await self._get_driver()
        
        query = """
        MATCH (n:Entity)
        RETURN n
        SKIP $offset
        LIMIT $limit
        """
        
        entities = []
        async with driver.session(database=self.database) as session:
            result = await session.run(query, limit=limit, offset=offset)
            
            async for record in result:
                node = record["n"]
                entities.append({
                    "id": node["id"],
                    "properties": dict(node),
                    "labels": list(node.labels)
                })
        
        return entities

    async def list_relationships(
        self, 
        source_id: Optional[str] = None, 
        target_id: Optional[str] = None,
        relationship_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List relationships with optional filtering.
        
        Args:
            source_id: Filter by source entity ID
            target_id: Filter by target entity ID
            relationship_type: Filter by relationship type
            limit: Maximum number of relationships to return
            
        Returns:
            List of relationship dictionaries
        """
        driver = await self._get_driver()
        
        # Build dynamic query based on filters
        where_clauses = []
        params = {"limit": limit}
        
        if source_id:
            where_clauses.append("source.id = $source_id")
            params["source_id"] = source_id
            
        if target_id:
            where_clauses.append("target.id = $target_id")
            params["target_id"] = target_id
            
        if relationship_type:
            where_clauses.append("type(r) = $relationship_type")
            params["relationship_type"] = relationship_type
        
        where_clause = " AND ".join(where_clauses) if where_clauses else ""
        where_part = f"WHERE {where_clause}" if where_clause else ""
        
        query = f"""
        MATCH (source:Entity)-[r]->(target:Entity)
        {where_part}
        RETURN source.id as source_id, type(r) as type, target.id as target_id, r as properties
        LIMIT $limit
        """
        
        relationships = []
        async with driver.session(database=self.database) as session:
            result = await session.run(query, **params)
            
            async for record in result:
                relationships.append({
                    "source": record["source_id"],
                    "target": record["target_id"],
                    "type": record["type"],
                    "properties": dict(record["properties"])
                })
        
        return relationships

    async def query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a Cypher query.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            Query results in a standardized format
        """
        driver = await self._get_driver()
        parameters = parameters or {}
        
        async with driver.session(database=self.database) as session:
            result = await session.run(query, **parameters)
            
            # Convert result to standardized format
            nodes = {}
            edges = {}
            
            async for record in result:
                # Extract nodes
                for key, value in record.items():
                    if hasattr(value, 'labels'):  # It's a node
                        node_id = value.get('id', str(hash(str(value))))
                        nodes[node_id] = {
                            "properties": dict(value),
                            "labels": list(value.labels)
                        }
                    elif hasattr(value, 'type'):  # It's a relationship
                        edge_id = f"{value.start_node.get('id')}_{value.type}_{value.end_node.get('id')}"
                        edges[edge_id] = {
                            "source": value.start_node.get('id'),
                            "target": value.end_node.get('id'),
                            "type": value.type,
                            "properties": dict(value)
                        }
            
            return {
                "nodes": nodes,
                "edges": edges,
                "query": query,
                "parameters": parameters
            }

    async def query_raw(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return raw records.
        
        Use this for queries that return scalar values (e.g., n.id, n.name).
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of record dictionaries
        """
        driver = await self._get_driver()
        parameters = parameters or {}
        
        records = []
        async with driver.session(database=self.database) as session:
            result = await session.run(query, **parameters)
            
            async for record in result:
                records.append(dict(record))
        
        return records

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relationships.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            True if deleted, False if not found
        """
        driver = await self._get_driver()
        
        query = """
        MATCH (n:Entity {id: $entity_id})
        DETACH DELETE n
        RETURN count(n) as deleted
        """
        
        async with driver.session(database=self.database) as session:
            result = await session.run(query, entity_id=entity_id)
            record = await result.single()
            
            return record["deleted"] > 0 if record else False

    async def delete_relationship(
        self, 
        source_id: str, 
        relationship_type: str, 
        target_id: str
    ) -> bool:
        """Delete a specific relationship.
        
        Args:
            source_id: Source entity ID
            relationship_type: Relationship type
            target_id: Target entity ID
            
        Returns:
            True if deleted, False if not found
        """
        driver = await self._get_driver()
        
        query = """
        MATCH (source:Entity {id: $source_id})-[r:`%s`]->(target:Entity {id: $target_id})
        DELETE r
        RETURN count(r) as deleted
        """ % relationship_type
        
        async with driver.session(database=self.database) as session:
            result = await session.run(query, 
                                    source_id=source_id, 
                                    target_id=target_id)
            record = await result.single()
            
            return record["deleted"] > 0 if record else False

    async def rollback(self) -> None:
        """Rollback is not supported in Neo4j.
        
        Neo4j transactions are ACID compliant and don't support
        application-level rollback. Use database transactions instead.
        """
        # Neo4j doesn't support application-level rollback
        # Transactions are handled at the database level
        pass

    async def close(self):
        """Close the Neo4j connection."""
        await self._close_driver()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Factory function for easy backend creation
async def create_neo4j_backend(
    uri: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    database: str = "neo4j"
) -> Neo4jBackend:
    """Create a Neo4j backend with environment variable fallbacks.
    
    Args:
        uri: Neo4j URI (defaults to NEO4J_URI env var)
        username: Neo4j username (defaults to NEO4J_USERNAME env var)
        password: Neo4j password (defaults to NEO4J_PASSWORD env var)
        database: Neo4j database name
        
    Returns:
        Configured Neo4jBackend instance
    """
    import os
    
    uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    username = username or os.environ.get("NEO4J_USERNAME", "neo4j")
    password = password or os.environ.get("NEO4J_PASSWORD", "password")
    
    return Neo4jBackend(uri, username, password, database)
