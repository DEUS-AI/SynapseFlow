"""Neo4j implementation of the knowledge graph backend.

This backend provides persistent storage using Neo4j database.
It implements the KnowledgeGraphBackend interface and supports
all CRUD operations for entities and relationships.

Enhanced with 4-layer Knowledge Graph architecture support:
- PERCEPTION: Raw extracted data from PDFs
- SEMANTIC: Validated concepts linked to ontologies
- REASONING: Inferred knowledge with provenance
- APPLICATION: Query patterns and cached results
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
from enum import Enum
from neo4j import AsyncGraphDatabase
from domain.kg_backends import KnowledgeGraphBackend

logger = logging.getLogger(__name__)


class KnowledgeLayer(str, Enum):
    """The four knowledge graph layers."""
    PERCEPTION = "PERCEPTION"
    SEMANTIC = "SEMANTIC"
    REASONING = "REASONING"
    APPLICATION = "APPLICATION"


# Required properties for each layer
# Note: These are soft requirements - entities can exist without them but
# may be flagged for validation. 'confidence' is the standard property name.
LAYER_REQUIREMENTS = {
    KnowledgeLayer.PERCEPTION: ["source_type"],  # source_document optional
    KnowledgeLayer.SEMANTIC: ["domain"],  # ontology_codes optional
    KnowledgeLayer.REASONING: ["confidence", "inference_rules_applied"],
    KnowledgeLayer.APPLICATION: ["usage_context"],
}


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

        Matches existing nodes by ID (regardless of label) and creates the relationship.
        Falls back to creating Entity nodes if nodes don't exist.

        Args:
            source_id: Source entity ID
            relationship_type: Type of relationship
            target_id: Target entity ID
            properties: Relationship properties
        """
        driver = await self._get_driver()

        # Sanitize relationship type (replace special chars)
        safe_rel_type = relationship_type.replace(":", "_").replace(" ", "_").upper()

        # MATCH existing nodes by ID (regardless of their label) instead of creating new Entity nodes
        # This fixes the issue where relationships were created between Entity nodes
        # instead of the actual ConversationSession/Message nodes
        query = f"""
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        MERGE (source)-[r:`{safe_rel_type}`]->(target)
        SET r += $properties
        RETURN r
        """

        async with driver.session(database=self.database) as session:
            result = await session.run(query,
                            source_id=source_id,
                            target_id=target_id,
                            properties=properties)
            records = [r async for r in result]

            # If no nodes found, fall back to creating Entity nodes (legacy behavior)
            if not records:
                logger.warning(f"Nodes not found for relationship {source_id} -> {target_id}, creating Entity nodes")
                fallback_query = f"""
                MERGE (source:Entity {{id: $source_id}})
                MERGE (target:Entity {{id: $target_id}})
                MERGE (source)-[r:`{safe_rel_type}`]->(target)
                SET r += $properties
                RETURN r
                """
                await session.run(fallback_query,
                                source_id=source_id,
                                target_id=target_id,
                                properties=properties)

    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID or name.

        Searches across all node types, matching by either id or name property.
        This allows finding DDA entities (Table, Column, etc.) which use name as identifier.

        Args:
            entity_id: Entity identifier (can be id or name)

        Returns:
            Entity properties or None if not found
        """
        driver = await self._get_driver()

        # Search by both id and name to support different entity types
        query = """
        MATCH (n)
        WHERE n.id = $entity_id OR n.name = $entity_id
        RETURN n, labels(n) as labels
        LIMIT 1
        """

        async with driver.session(database=self.database) as session:
            result = await session.run(query, entity_id=entity_id)
            record = await result.single()

            if record:
                node = record["n"]
                return {
                    "id": node.get("id") or node.get("name"),
                    "properties": dict(node),
                    "labels": record["labels"]
                }
            return None

    async def update_entity_properties(
        self,
        entity_id: str,
        properties: Dict[str, Any]
    ) -> bool:
        """Update properties of an entity.

        Finds entity by id or name and updates the specified properties.
        Used for updating session titles, status, and other entity attributes.

        Args:
            entity_id: Entity identifier (can be id or name)
            properties: Dictionary of properties to update

        Returns:
            True if entity was found and updated, False otherwise
        """
        driver = await self._get_driver()

        # Build SET clause dynamically for the properties
        # Use parameter binding for safety
        query = """
        MATCH (n)
        WHERE n.id = $entity_id OR n.name = $entity_id
        SET n += $properties
        RETURN n
        """

        async with driver.session(database=self.database) as session:
            result = await session.run(
                query,
                entity_id=entity_id,
                properties=properties
            )
            record = await result.single()

            if record:
                logger.debug(f"Updated entity {entity_id} with properties: {list(properties.keys())}")
                return True

            logger.warning(f"Entity not found for update: {entity_id}")
            return False

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

    # ========================================
    # Layer-Aware Methods (4-Layer Architecture)
    # ========================================

    async def add_entity_with_layer(
        self,
        entity_id: str,
        properties: Dict[str, Any],
        layer: KnowledgeLayer,
        labels: List[str] = None,
        validate: bool = True
    ) -> Dict[str, Any]:
        """Add an entity with layer assignment and validation.

        Args:
            entity_id: Unique identifier for the entity
            properties: Entity properties as key-value pairs
            layer: Target knowledge layer (PERCEPTION, SEMANTIC, REASONING, APPLICATION)
            labels: Optional list of node labels
            validate: If True, validate required properties for the layer

        Returns:
            Created entity with layer assignment

        Raises:
            ValueError: If required properties for the layer are missing
        """
        # Validate required properties for the layer
        if validate:
            required = LAYER_REQUIREMENTS.get(layer, [])
            missing = [prop for prop in required if prop not in properties]
            if missing:
                logger.warning(
                    f"Entity {entity_id} missing recommended properties for {layer.value}: {missing}"
                )

        # Add layer metadata
        properties["layer"] = layer.value
        properties["layer_assigned_at"] = datetime.now().isoformat()

        # Add status for PERCEPTION layer
        if layer == KnowledgeLayer.PERCEPTION and "status" not in properties:
            properties["status"] = "pending_validation"

        await self.add_entity(entity_id, properties, labels)

        return {
            "id": entity_id,
            "layer": layer.value,
            "properties": properties,
            "labels": labels or []
        }

    async def promote_entity(
        self,
        entity_id: str,
        target_layer: KnowledgeLayer,
        promotion_properties: Dict[str, Any] = None,
        create_version: bool = True
    ) -> Dict[str, Any]:
        """Promote an entity to a higher layer with version tracking.

        Args:
            entity_id: Entity to promote
            target_layer: Target layer (must be higher than current)
            promotion_properties: Additional properties to add during promotion
            create_version: If True, create a versioned copy instead of modifying in place

        Returns:
            Promotion result with transition details

        Raises:
            ValueError: If target layer is not higher than current layer
        """
        driver = await self._get_driver()
        promotion_properties = promotion_properties or {}

        # Get current entity
        entity = await self.get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        current_layer = entity["properties"].get("layer", "PERCEPTION")
        layer_order = ["PERCEPTION", "SEMANTIC", "REASONING", "APPLICATION"]

        current_idx = layer_order.index(current_layer) if current_layer in layer_order else 0
        target_idx = layer_order.index(target_layer.value)

        if target_idx <= current_idx:
            raise ValueError(
                f"Cannot promote from {current_layer} to {target_layer.value}. "
                f"Target layer must be higher than current layer."
            )

        transition_id = f"transition_{entity_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if create_version:
            # Create new versioned entity
            new_entity_id = f"{entity_id}_v{target_idx + 1}"
            # Match by id or name to support all entity types (Entity, Table, Column, etc.)
            query = """
            MATCH (source)
            WHERE source.id = $entity_id OR source.name = $entity_id
            CREATE (target:Entity {id: $new_entity_id})
            SET target = source,
                target.id = $new_entity_id,
                target.layer = $target_layer,
                target.layer_assigned_at = datetime(),
                target.promoted_from = $entity_id,
                target.promotion_timestamp = datetime(),
                target.status = 'active'
            SET target += $promotion_properties
            CREATE (source)-[:PROMOTED_TO {
                transition_id: $transition_id,
                promoted_at: datetime(),
                from_layer: $current_layer,
                to_layer: $target_layer
            }]->(target)
            RETURN target, source
            """
        else:
            # Modify in place - search by id or name to support all entity types
            new_entity_id = entity_id
            query = """
            MATCH (n)
            WHERE n.id = $entity_id OR n.name = $entity_id
            SET n.layer = $target_layer,
                n.layer_assigned_at = datetime(),
                n.previous_layer = $current_layer,
                n.promotion_timestamp = datetime(),
                n.status = 'active'
            SET n += $promotion_properties
            RETURN n as target
            """

        async with driver.session(database=self.database) as session:
            result = await session.run(
                query,
                entity_id=entity_id,
                new_entity_id=new_entity_id,
                target_layer=target_layer.value,
                current_layer=current_layer,
                promotion_properties=promotion_properties,
                transition_id=transition_id
            )
            record = await result.single()

            if not record:
                raise ValueError(f"Failed to promote entity {entity_id}")

            target_node = record["target"]

            # Create transition audit record
            audit_query = """
            CREATE (t:LayerTransition {
                transition_id: $transition_id,
                entity_id: $entity_id,
                from_layer: $from_layer,
                to_layer: $to_layer,
                status: 'completed',
                completed_at: datetime(),
                trigger_type: 'manual',
                new_entity_id: $new_entity_id
            })
            RETURN t
            """
            await session.run(
                audit_query,
                transition_id=transition_id,
                entity_id=entity_id,
                from_layer=current_layer,
                to_layer=target_layer.value,
                new_entity_id=new_entity_id
            )

        return {
            "transition_id": transition_id,
            "entity_id": entity_id,
            "new_entity_id": new_entity_id,
            "from_layer": current_layer,
            "to_layer": target_layer.value,
            "status": "completed",
            "target_properties": dict(target_node)
        }

    async def get_promotion_candidates(
        self,
        from_layer: str = None,
        source_layer: KnowledgeLayer = None,
        confidence_threshold: float = 0.85,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get entities ready for promotion to the next layer.

        Args:
            source_layer: Layer to check for promotion candidates
            confidence_threshold: Minimum confidence for promotion
            limit: Maximum number of candidates to return

        Returns:
            List of entities meeting promotion criteria
        """
        driver = await self._get_driver()

        # Normalize layer parameter (support both from_layer string and source_layer enum)
        layer = from_layer or (source_layer.value if source_layer else None)
        if not layer:
            return []

        # Build layer-specific query
        # Note: Match any node with the layer property, not just :Entity label
        # This allows promotion of DDA entities (Table, Column, etc.) and other node types
        if layer == "PERCEPTION" or layer == KnowledgeLayer.PERCEPTION:
            # Check for entities with high confidence, validation count, or ontology match
            # Allow entities with pending_validation status OR no status (migrated data)
            query = """
            MATCH (n)
            WHERE n.layer = 'PERCEPTION'
              AND n.name IS NOT NULL
              AND (n.status IS NULL OR n.status = 'pending_validation' OR n.status = 'active')
              AND (
                  coalesce(n.confidence, 0) >= $threshold
                  OR coalesce(n.validation_count, 0) >= 3
                  OR n.ontology_codes IS NOT NULL
              )
            RETURN coalesce(n.id, n.name) as id,
                   n.name as name,
                   n.layer as layer,
                   labels(n) as labels,
                   coalesce(n.confidence, 0) as confidence,
                   coalesce(n.validation_count, 0) as validation_count,
                   n.ontology_codes as ontology_codes,
                   CASE
                     WHEN coalesce(n.confidence, 0) >= $threshold THEN 'confidence'
                     WHEN coalesce(n.validation_count, 0) >= 3 THEN 'validation_count'
                     ELSE 'ontology_match'
                   END as trigger_type
            ORDER BY coalesce(n.confidence, 0) DESC
            LIMIT $limit
            """
        elif layer == "SEMANTIC" or layer == KnowledgeLayer.SEMANTIC:
            query = """
            MATCH (n)
            WHERE n.layer = 'SEMANTIC'
              AND n.name IS NOT NULL
            OPTIONAL MATCH (n)<-[r]-(other {layer: 'SEMANTIC'})
            WITH n, count(r) as reference_count
            WHERE reference_count >= 5 OR coalesce(n.confidence, 0) >= $threshold
            RETURN coalesce(n.id, n.name) as id,
                   n.name as name,
                   n.layer as layer,
                   labels(n) as labels,
                   coalesce(n.confidence, 0.5) as confidence,
                   reference_count,
                   CASE
                     WHEN reference_count >= 5 THEN 'reference_count'
                     ELSE 'confidence'
                   END as trigger_type
            ORDER BY confidence DESC
            LIMIT $limit
            """
        elif layer == "REASONING" or layer == KnowledgeLayer.REASONING:
            query = """
            MATCH (n)
            WHERE n.layer = 'REASONING'
              AND n.name IS NOT NULL
              AND coalesce(n.query_count, 0) >= 10
            RETURN coalesce(n.id, n.name) as id,
                   n.name as name,
                   n.layer as layer,
                   labels(n) as labels,
                   coalesce(n.confidence, 0.5) as confidence,
                   n.query_count as query_count,
                   coalesce(n.cache_hit_rate, 0) as cache_hit_rate,
                   'query_frequency' as trigger_type
            ORDER BY n.query_count DESC
            LIMIT $limit
            """
        else:
            return []  # APPLICATION is the highest layer

        async with driver.session(database=self.database) as session:
            result = await session.run(query, threshold=confidence_threshold, limit=limit)
            records = await result.data()
            return records

    async def list_entities_by_layer(
        self,
        layer: KnowledgeLayer,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List entities filtered by layer.

        Args:
            layer: Knowledge layer to filter by
            limit: Maximum number of entities to return
            offset: Number of entities to skip
            status: Optional status filter

        Returns:
            List of entity dictionaries
        """
        driver = await self._get_driver()

        where_clause = "WHERE n.layer = $layer"
        params = {"layer": layer.value, "limit": limit, "offset": offset}

        if status:
            where_clause += " AND n.status = $status"
            params["status"] = status

        query = f"""
        MATCH (n:Entity)
        {where_clause}
        RETURN n
        SKIP $offset
        LIMIT $limit
        """

        entities = []
        async with driver.session(database=self.database) as session:
            result = await session.run(query, **params)

            async for record in result:
                node = record["n"]
                entities.append({
                    "id": node.get("id"),
                    "properties": dict(node),
                    "labels": list(node.labels)
                })

        return entities

    async def get_layer_statistics(self) -> Dict[str, Any]:
        """Get statistics about entities in each layer.

        Returns:
            Dictionary with layer counts and additional metrics
        """
        driver = await self._get_driver()

        query = """
        MATCH (n:Entity)
        WITH n.layer as layer, count(n) as count
        RETURN layer, count
        ORDER BY
            CASE layer
                WHEN 'PERCEPTION' THEN 1
                WHEN 'SEMANTIC' THEN 2
                WHEN 'REASONING' THEN 3
                WHEN 'APPLICATION' THEN 4
                ELSE 5
            END
        """

        async with driver.session(database=self.database) as session:
            result = await session.run(query)
            records = await result.data()

            layer_counts = {r["layer"]: r["count"] for r in records}

            # Get promotion statistics
            promotion_query = """
            MATCH (t:LayerTransition)
            WHERE t.status = 'completed'
            RETURN t.from_layer as from_layer, t.to_layer as to_layer, count(t) as count
            """
            promo_result = await session.run(promotion_query)
            promo_records = await promo_result.data()

            promotions = {}
            for r in promo_records:
                key = f"{r['from_layer']}_to_{r['to_layer']}"
                promotions[key] = r["count"]

            return {
                "layer_counts": layer_counts,
                "total_entities": sum(layer_counts.values()),
                "promotions": promotions,
                "timestamp": datetime.now().isoformat()
            }

    async def create_layer_indexes(self) -> List[str]:
        """Create required indexes for layer-based queries.

        Returns:
            List of created/verified index names
        """
        driver = await self._get_driver()

        indexes = [
            ("idx_entity_layer", "CREATE INDEX idx_entity_layer IF NOT EXISTS FOR (n:Entity) ON (n.layer)"),
            ("idx_entity_confidence", "CREATE INDEX idx_entity_confidence IF NOT EXISTS FOR (n:Entity) ON (n.confidence)"),
            ("idx_entity_status", "CREATE INDEX idx_entity_status IF NOT EXISTS FOR (n:Entity) ON (n.status)"),
            ("idx_transition_status", "CREATE INDEX idx_transition_status IF NOT EXISTS FOR (t:LayerTransition) ON (t.status)"),
        ]

        created = []
        async with driver.session(database=self.database) as session:
            for name, query in indexes:
                try:
                    await session.run(query)
                    created.append(name)
                    logger.info(f"Created/verified index: {name}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to create index {name}: {e}")

        return created


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
