"""Direct Neo4j writer for DDA architecture graphs.

This module bypasses Graphiti's LLM-based entity extraction and directly creates
a structured graph from the parsed DDA document.
"""

from typing import Dict, Any, List
from neo4j import GraphDatabase
from domain.dda_models import DDADocument, DataEntity, Relationship


class ArchitectureGraphWriter:
    """Writes DDA architecture graphs directly to Neo4j without LLM inference."""
    
    def __init__(self, uri: str, user: str, password: str):
        """Initialize the Neo4j writer.
        
        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()
    
    def create_architecture_graph(self, dda_document: DDADocument) -> Dict[str, Any]:
        """Create architecture graph from DDA document.
        
        Args:
            dda_document: Parsed DDA document
            
        Returns:
            Summary of created graph
        """
        with self.driver.session() as session:
            # Create domain node
            domain_id = self._create_domain_node(session, dda_document)
            
            # Create entity nodes
            entity_ids = {}
            for entity in dda_document.entities:
                entity_id = self._create_entity_node(session, entity, dda_document.domain)
                entity_ids[entity.name] = entity_id
                
                # Link entity to domain
                self._create_relationship(
                    session,
                    domain_id,
                    entity_id,
                    "CONTAINS_ENTITY",
                    {"description": f"Domain contains {entity.name} entity"}
                )
                
                # Create attribute nodes
                self._create_attribute_nodes(session, entity, entity_id)
            
            # Create relationship edges between entities
            for relationship in dda_document.relationships:
                if relationship.source_entity in entity_ids and relationship.target_entity in entity_ids:
                    self._create_entity_relationship(
                        session,
                        entity_ids[relationship.source_entity],
                        entity_ids[relationship.target_entity],
                        relationship
                    )
            
            # Get statistics
            stats = self._get_graph_stats(session, dda_document.domain)
            
            return {
                "domain": dda_document.domain,
                "domain_id": domain_id,
                "entities_count": len(dda_document.entities),
                "relationships_count": len(dda_document.relationships),
                "nodes_created": stats["nodes"],
                "edges_created": stats["edges"],
                "success": True
            }
    
    def _create_domain_node(self, session, dda_document: DDADocument) -> str:
        """Create domain node."""
        domain_id = f"domain:{dda_document.domain.lower().replace(' ', '_')}"
        
        query = """
        MERGE (d:Domain {id: $id})
        SET d.name = $name,
            d.description = $description,
            d.business_context = $business_context,
            d.data_owner = $data_owner,
            d.stakeholders = $stakeholders,
            d.effective_date = $effective_date
        RETURN d.id as id
        """
        
        result = session.run(query, {
            "id": domain_id,
            "name": dda_document.domain,
            "description": dda_document.business_context,
            "business_context": dda_document.business_context,
            "data_owner": dda_document.data_owner,
            "stakeholders": dda_document.stakeholders,
            "effective_date": dda_document.effective_date.isoformat()
        })
        
        return result.single()["id"]
    
    def _create_entity_node(self, session, entity: DataEntity, domain: str) -> str:
        """Create data entity node."""
        entity_id = f"entity:{domain.lower().replace(' ', '_')}:{entity.name.lower().replace(' ', '_')}"
        
        query = """
        MERGE (e:DataEntity {id: $id})
        SET e.name = $name,
            e.description = $description,
            e.domain = $domain,
            e.primary_key = $primary_key,
            e.foreign_keys = $foreign_keys,
            e.business_rules = $business_rules
        RETURN e.id as id
        """
        
        result = session.run(query, {
            "id": entity_id,
            "name": entity.name,
            "description": entity.description,
            "domain": domain,
            "primary_key": entity.primary_key,
            "foreign_keys": entity.foreign_keys,
            "business_rules": entity.business_rules
        })
        
        return result.single()["id"]
    
    def _create_attribute_nodes(self, session, entity: DataEntity, entity_id: str):
        """Create attribute nodes for an entity."""
        for attribute in entity.attributes:
            attr_id = f"{entity_id}:attr:{attribute.lower().replace(' ', '_')}"
            
            query = """
            MERGE (a:Attribute {id: $id})
            SET a.name = $name,
                a.entity_name = $entity_name
            WITH a
            MATCH (e:DataEntity {id: $entity_id})
            MERGE (e)-[:HAS_ATTRIBUTE]->(a)
            """
            
            session.run(query, {
                "id": attr_id,
                "name": attribute,
                "entity_name": entity.name,
                "entity_id": entity_id
            })
    
    def _create_entity_relationship(
        self,
        session,
        source_id: str,
        target_id: str,
        relationship: Relationship
    ):
        """Create relationship between entities."""
        # Map relationship type to Neo4j relationship type
        rel_type = self._map_relationship_type(relationship.relationship_type)
        
        query = f"""
        MATCH (source:DataEntity {{id: $source_id}})
        MATCH (target:DataEntity {{id: $target_id}})
        MERGE (source)-[r:{rel_type}]->(target)
        SET r.cardinality = $cardinality,
            r.description = $description,
            r.constraints = $constraints
        """
        
        session.run(query, {
            "source_id": source_id,
            "target_id": target_id,
            "cardinality": relationship.relationship_type,
            "description": relationship.description,
            "constraints": relationship.constraints
        })
    
    def _create_relationship(
        self,
        session,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: Dict[str, Any]
    ):
        """Create a generic relationship."""
        query = f"""
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        MERGE (source)-[r:{rel_type}]->(target)
        SET r += $properties
        """
        
        session.run(query, {
            "source_id": source_id,
            "target_id": target_id,
            "properties": properties
        })
    
    def _map_relationship_type(self, dda_rel_type: str) -> str:
        """Map DDA relationship type to Neo4j relationship type."""
        # Map common patterns
        mapping = {
            "1:1": "ONE_TO_ONE",
            "1:N": "ONE_TO_MANY",
            "N:1": "MANY_TO_ONE",
            "M:N": "MANY_TO_MANY",
            "N:M": "MANY_TO_MANY"
        }
        
        return mapping.get(dda_rel_type, "RELATES_TO")
    
    def _get_graph_stats(self, session, domain: str) -> Dict[str, int]:
        """Get statistics about the created graph."""
        # Count nodes
        node_result = session.run("""
            MATCH (n)
            WHERE n.domain = $domain OR n.name = $domain
            RETURN count(n) as count
        """, {"domain": domain})
        
        node_count = node_result.single()["count"]
        
        # Count relationships
        edge_result = session.run("""
            MATCH (n)-[r]->(m)
            WHERE n.domain = $domain OR n.name = $domain
            RETURN count(r) as count
        """, {"domain": domain})
        
        edge_count = edge_result.single()["count"]
        
        return {"nodes": node_count, "edges": edge_count}
