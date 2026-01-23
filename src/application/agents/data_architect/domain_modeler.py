from typing import Dict, Any, List
from domain.dda_models import DDADocument, DataEntity, Relationship
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from datetime import datetime
import json
import hashlib
from functools import lru_cache


class DomainModeler:
    """Creates and updates domain knowledge graphs from DDA documents using Graphiti."""
    
    def __init__(self, graph: Graphiti, llm: Graphiti):
        self.graph = graph
        self.llm = llm
        self._document_cache = {}  # Simple in-memory cache for parsed documents
        self._domain_cache = {}    # Cache for domain search results
    
    async def create_domain_graph(self, dda_document: DDADocument) -> Dict[str, Any]:
        """Create a new domain knowledge graph from DDA document using Graphiti."""
        
        # Check cache for existing parsed content
        cache_key = self._generate_cache_key(dda_document)
        if cache_key in self._document_cache:
            print(f"Using cached episode content for domain: {dda_document.domain}")
            episode_content = self._document_cache[cache_key]
        else:
            # Create a structured episode content from the DDA document
            episode_content = self._create_episode_content(dda_document)
            # Cache the content
            self._document_cache[cache_key] = episode_content
        
        # Create safe group ID
        safe_group_id = "dda_" + dda_document.domain.lower().replace(' ', '_').replace("'", '').replace('-', '_')
        
        # Add the episode to Graphiti
        episode_results = await self.graph.add_episode(
            name=f"DDA - {dda_document.domain}",
            episode_body=episode_content,
            source_description=f"Data Delivery Agreement for {dda_document.domain} domain",
            reference_time=dda_document.effective_date,
            source=EpisodeType.message,  # Using message as the episode type
            group_id=safe_group_id,
            update_communities=True
        )
        
        # Return summary of what was created
        return {
            "episode_uuid": episode_results.episode.uuid if episode_results.episode else None,
            "domain": dda_document.domain,
            "entities_count": len(dda_document.entities),
            "relationships_count": len(dda_document.relationships),
            "nodes_created": len(episode_results.nodes) if episode_results.nodes else 0,
            "edges_created": len(episode_results.edges) if episode_results.edges else 0,
            "group_id": safe_group_id,
            "cache_hit": cache_key in self._document_cache
        }
    
    async def batch_create_domain_graphs(self, dda_documents: List[DDADocument]) -> List[Dict[str, Any]]:
        """Create multiple domain graphs in batch for better performance."""
        
        results = []
        
        # Prepare batch episodes
        batch_episodes = []
        for dda_document in dda_documents:
            cache_key = self._generate_cache_key(dda_document)
            if cache_key in self._document_cache:
                episode_content = self._document_cache[cache_key]
            else:
                episode_content = self._create_episode_content(dda_document)
                self._document_cache[cache_key] = episode_content
            
            # Create RawEpisode for batch processing
            from graphiti_core.utils.bulk_utils import RawEpisode
            # Create safe group ID for batch
            batch_group_id = "dda_" + dda_document.domain.lower().replace(' ', '_').replace("'", '').replace('-', '_')
            batch_episode = RawEpisode(
                name=f"DDA - {dda_document.domain}",
                episode_body=episode_content,
                source_description=f"Data Delivery Agreement for {dda_document.domain} domain",
                reference_time=dda_document.effective_date,
                source=EpisodeType.message,
                group_id=batch_group_id
            )
            batch_episodes.append(batch_episode)
        
        # Process batch
        try:
            await self.graph.add_episode_bulk(
                bulk_episodes=batch_episodes,
                group_id="batch_dda_processing"
            )
            
            # Generate results (note: bulk processing doesn't return individual results)
            for dda_document in dda_documents:
                results.append({
                    "domain": dda_document.domain,
                    "entities_count": len(dda_document.entities),
                    "relationships_count": len(dda_document.relationships),
                    "nodes_created": "bulk_processed",
                    "edges_created": "bulk_processed",
                    "group_id": batch_group_id,
                    "batch_processed": True
                })
                
        except Exception as e:
            print(f"Batch processing failed: {e}")
            # Fallback to individual processing
            for dda_document in dda_documents:
                result = await self.create_domain_graph(dda_document)
                results.append(result)
        
        return results
    
    def _generate_cache_key(self, dda_document: DDADocument) -> str:
        """Generate a cache key for the DDA document."""
        # Create a hash based on domain and content
        content_string = f"{dda_document.domain}_{len(dda_document.entities)}_{len(dda_document.relationships)}"
        return hashlib.md5(content_string.encode()).hexdigest()
    
    def clear_cache(self) -> None:
        """Clear the document and domain caches."""
        self._document_cache.clear()
        self._domain_cache.clear()
        print("Domain modeler cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        return {
            "document_cache_size": len(self._document_cache),
            "domain_cache_size": len(self._domain_cache),
            "total_cache_entries": len(self._document_cache) + len(self._domain_cache)
        }
    
    async def update_domain_graph(self, dda_document: DDADocument) -> Dict[str, Any]:
        """Update existing domain knowledge graph with new DDA information."""
        
        # 1. Check if domain already exists
        existing_domain = await self._find_existing_domain(dda_document.domain)
        
        if existing_domain:
            # 2. Merge new entities with existing ones
            merged_entities = await self._merge_entities(dda_document.entities, existing_domain)
            
            # 3. Update relationships
            updated_relationships = await self._update_relationships(dda_document.relationships, existing_domain)
            
            # 4. Create update episode with merged content
            update_content = self._create_update_episode_content(
                dda_document, 
                merged_entities, 
                updated_relationships,
                existing_domain
            )
            
            # Add the update episode to Graphiti
            episode_results = await self.graph.add_episode(
                name=f"DDA Update - {dda_document.domain}",
                episode_body=update_content,
                source_description=f"Data Delivery Agreement Update for {dda_document.domain} domain",
                reference_time=dda_document.effective_date,
                source=EpisodeType.message,
                group_id=f"dda_{dda_document.domain.lower().replace(' ', '_')}",
                update_communities=True
            )
            
            return {
                "episode_uuid": episode_results.episode.uuid if episode_results.episode else None,
                "domain": dda_document.domain,
                "entities_count": len(merged_entities),
                "relationships_count": len(updated_relationships),
                "nodes_created": len(episode_results.nodes) if episode_results.nodes else 0,
                "edges_created": len(episode_results.edges) if episode_results.edges else 0,
                "group_id": f"dda_{dda_document.domain.lower().replace(' ', '_')}",
                "update_type": "merge",
                "existing_domain_found": True
            }
        else:
            # Domain doesn't exist, create new graph
            return await self.create_domain_graph(dda_document)
    
    async def _find_existing_domain(self, domain_name: str) -> Dict[str, Any] | None:
        """Find existing domain in the knowledge graph."""
        try:
            # Search for existing domain nodes
            search_results = await self.graph.search(
                query=f"domain {domain_name}",
                group_ids=[f"dda_{domain_name.lower().replace(' ', '_')}"],
                num_results=5
            )
            
            if search_results:
                # Check if any of the results are domain nodes
                for result in search_results:
                    if hasattr(result, 'attributes') and result.attributes:
                        if 'domain' in result.attributes.get('name', '').lower():
                            return {
                                "uuid": result.uuid,
                                "name": result.name,
                                "attributes": result.attributes
                            }
            
            return None
        except Exception as e:
            print(f"Warning: Could not search for existing domain: {e}")
            return None
    
    async def _merge_entities(self, new_entities: List[DataEntity], existing_domain: Dict[str, Any]) -> List[DataEntity]:
        """Merge new entities with existing ones, resolving conflicts."""
        merged_entities = []
        
        try:
            # Search for existing entities in the domain
            existing_entities = await self.graph.search(
                query="data entities",
                group_ids=[existing_domain.get("group_id", "")],
                num_results=20
            )
            
            existing_entity_names = set()
            if existing_entities:
                for entity in existing_entities:
                    if hasattr(entity, 'name'):
                        existing_entity_names.add(entity.name)
            
            # Merge logic: add new entities, update existing ones
            for new_entity in new_entities:
                if new_entity.name in existing_entity_names:
                    # Entity exists - merge attributes
                    merged_entity = await self._merge_entity_attributes(new_entity, existing_entities)
                    merged_entities.append(merged_entity)
                else:
                    # New entity - add as is
                    merged_entities.append(new_entity)
            
        except Exception as e:
            print(f"Warning: Could not merge entities: {e}")
            # Fallback: return new entities as is
            merged_entities = new_entities
        
        return merged_entities
    
    async def _merge_entity_attributes(self, new_entity: DataEntity, existing_entities: List) -> DataEntity:
        """Merge attributes of new entity with existing entity."""
        # Find the existing entity
        existing_entity = None
        for entity in existing_entities:
            if hasattr(entity, 'name') and entity.name == new_entity.name:
                existing_entity = entity
                break
        
        if not existing_entity:
            return new_entity
        
        # Merge attributes (simple union for now)
        merged_attributes = list(set(new_entity.attributes))
        if hasattr(existing_entity, 'attributes') and existing_entity.attributes:
            existing_attrs = existing_entity.attributes.get('attributes', [])
            if isinstance(existing_attrs, list):
                merged_attributes.extend(existing_attrs)
                merged_attributes = list(set(merged_attributes))  # Remove duplicates
        
        # Merge business rules
        merged_business_rules = list(set(new_entity.business_rules))
        if hasattr(existing_entity, 'attributes') and existing_entity.attributes:
            existing_rules = existing_entity.attributes.get('business_rules', [])
            if isinstance(existing_rules, list):
                merged_business_rules.extend(existing_rules)
                merged_business_rules = list(set(merged_business_rules))
        
        return DataEntity(
            name=new_entity.name,
            description=new_entity.description,
            attributes=merged_attributes,
            business_rules=merged_business_rules,
            primary_key=new_entity.primary_key,
            foreign_keys=new_entity.foreign_keys
        )
    
    async def _update_relationships(self, new_relationships: List[Relationship], existing_domain: Dict[str, Any]) -> List[Relationship]:
        """Update relationships, preserving existing ones and adding new ones."""
        updated_relationships = []
        
        try:
            # Search for existing relationships in the domain
            existing_relationships = await self.graph.search(
                query="relationships",
                group_ids=[existing_domain.get("group_id", "")],
                num_results=20
            )
            
            existing_rel_keys = set()
            if existing_relationships:
                for rel in existing_relationships:
                    if hasattr(rel, 'name'):
                        existing_rel_keys.add(rel.name)
            
            # Add new relationships, skip if they already exist
            for new_rel in new_relationships:
                rel_key = f"{new_rel.source_entity}_{new_rel.target_entity}_{new_rel.relationship_type}"
                if rel_key not in existing_rel_keys:
                    updated_relationships.append(new_rel)
                else:
                    # Relationship exists - could implement update logic here
                    print(f"Relationship already exists: {rel_key}")
            
        except Exception as e:
            print(f"Warning: Could not update relationships: {e}")
            # Fallback: return new relationships as is
            updated_relationships = new_relationships
        
        return updated_relationships
    
    def _create_update_episode_content(self, dda_document: DDADocument, merged_entities: List[DataEntity], 
                                     updated_relationships: List[Relationship], existing_domain: Dict[str, Any]) -> str:
        """Create structured episode content for graph updates."""
        
        content_parts = []
        
        # Update header
        content_parts.append(f"DOMAIN UPDATE: {dda_document.domain}")
        content_parts.append(f"Update Type: Merge with existing domain")
        content_parts.append(f"Existing Domain UUID: {existing_domain.get('uuid', 'Unknown')}")
        content_parts.append(f"Update Date: {dda_document.effective_date.strftime('%Y-%m-%d')}")
        
        # Domain information (if changed)
        content_parts.append(f"\nDomain Information:")
        content_parts.append(f"Business Context: {dda_document.business_context}")
        content_parts.append(f"Data Owner: {dda_document.data_owner}")
        content_parts.append(f"Stakeholders: {', '.join(dda_document.stakeholders)}")
        
        # Merged entities
        content_parts.append(f"\nMerged Data Entities ({len(merged_entities)} total):")
        for entity in merged_entities:
            content_parts.append(f"\nEntity: {entity.name}")
            content_parts.append(f"Description: {entity.description}")
            content_parts.append(f"Attributes: {', '.join(entity.attributes)}")
            if entity.primary_key:
                content_parts.append(f"Primary Key: {entity.primary_key}")
            if entity.foreign_keys:
                content_parts.append(f"Foreign Keys: {', '.join(entity.foreign_keys)}")
            content_parts.append(f"Business Rules: {', '.join(entity.business_rules)}")
        
        # Updated relationships
        content_parts.append(f"\nUpdated Relationships ({len(updated_relationships)} new):")
        for relationship in updated_relationships:
            content_parts.append(f"\nRelationship: {relationship.source_entity} -> {relationship.target_entity}")
            content_parts.append(f"Type: {relationship.relationship_type}")
            content_parts.append(f"Description: {relationship.description}")
            if relationship.constraints:
                content_parts.append(f"Constraints: {', '.join(relationship.constraints)}")
        
        # Data Quality Requirements
        if dda_document.data_quality_requirements:
            content_parts.append("\nData Quality Requirements:")
            content_parts.append(f"Completeness: {json.dumps(dda_document.data_quality_requirements.completeness)}")
            content_parts.append(f"Accuracy: {json.dumps(dda_document.data_quality_requirements.accuracy)}")
            content_parts.append(f"Timeliness: {json.dumps(dda_document.data_quality_requirements.timeliness)}")
        
        # Access Patterns
        if dda_document.access_patterns:
            content_parts.append("\nAccess Patterns:")
            content_parts.append(f"Common Queries: {', '.join(dda_document.access_patterns.common_queries)}")
            content_parts.append(f"Performance Requirements: {json.dumps(dda_document.access_patterns.performance_requirements)}")
        
        # Governance
        if dda_document.governance:
            content_parts.append("\nGovernance:")
            content_parts.append(f"Privacy: {json.dumps(dda_document.governance.privacy)}")
            content_parts.append(f"Security: {json.dumps(dda_document.governance.security)}")
            content_parts.append(f"Compliance: {json.dumps(dda_document.governance.compliance)}")
        
        return "\n".join(content_parts)
    
    def _create_episode_content(self, dda_document: DDADocument) -> str:
        """Create structured episode content from DDA document for Graphiti processing.
        
        This content is optimized for Graphiti's LLM to extract the correct entities.
        We emphasize DATA ENTITIES (Customer, Campaign, etc.) as the primary entities,
        not stakeholders or people mentioned in the document.
        """
        
        content_parts = []
        
        # Start with a clear statement about what this domain contains
        content_parts.append(f"DATA DOMAIN: {dda_document.domain}")
        content_parts.append(f"\nThis domain defines {len(dda_document.entities)} core data entities and their relationships.")
        content_parts.append(f"Business Context: {dda_document.business_context}")
        content_parts.append(f"Effective Date: {dda_document.effective_date.strftime('%Y-%m-%d')}")
        
        # Emphasize the data entities as the main subject
        content_parts.append(f"\n{'='*60}")
        content_parts.append("CORE DATA ENTITIES (Primary Subject)")
        content_parts.append(f"{'='*60}")
        content_parts.append(f"\nThe {dda_document.domain} domain contains the following data entities:\n")
        
        # Entities - with emphasis that these ARE the entities
        for i, entity in enumerate(dda_document.entities, 1):
            content_parts.append(f"\n{i}. DATA ENTITY: {entity.name}")
            content_parts.append(f"   Entity Type: {entity.name}")
            content_parts.append(f"   Purpose: {entity.description}")
            content_parts.append(f"   Data Attributes: {', '.join(entity.attributes)}")
            if entity.primary_key:
                content_parts.append(f"   Unique Identifier: {entity.primary_key}")
            if entity.foreign_keys:
                content_parts.append(f"   References to other entities: {', '.join(entity.foreign_keys)}")
            if entity.business_rules:
                content_parts.append(f"   Constraints: {'; '.join(entity.business_rules)}")
        
        # Relationships between data entities
        if dda_document.relationships:
            content_parts.append(f"\n{'='*60}")
            content_parts.append("RELATIONSHIPS BETWEEN DATA ENTITIES")
            content_parts.append(f"{'='*60}\n")
            
            for i, relationship in enumerate(dda_document.relationships, 1):
                content_parts.append(f"\n{i}. The {relationship.source_entity} entity {relationship.relationship_type} the {relationship.target_entity} entity")
                content_parts.append(f"   Cardinality: {relationship.relationship_type}")
                content_parts.append(f"   Description: {relationship.description}")
                if relationship.constraints:
                    content_parts.append(f"   Constraints: {', '.join(relationship.constraints)}")
        
        # Add metadata section (de-emphasized)
        content_parts.append(f"\n{'='*60}")
        content_parts.append("DOMAIN METADATA (Reference Information)")
        content_parts.append(f"{'='*60}")
        content_parts.append(f"\nData Owner: {dda_document.data_owner}")
        content_parts.append(f"Stakeholder Teams: {', '.join(dda_document.stakeholders)}")
        
        # Data Quality Requirements
        if dda_document.data_quality_requirements:
            content_parts.append("\nData Quality Requirements:")
            content_parts.append(f"Completeness: {json.dumps(dda_document.data_quality_requirements.completeness)}")
            content_parts.append(f"Accuracy: {json.dumps(dda_document.data_quality_requirements.accuracy)}")
            content_parts.append(f"Timeliness: {json.dumps(dda_document.data_quality_requirements.timeliness)}")
        
        # Access Patterns
        if dda_document.access_patterns:
            content_parts.append("\nAccess Patterns:")
            content_parts.append(f"Common Queries: {', '.join(dda_document.access_patterns.common_queries)}")
            content_parts.append(f"Performance Requirements: {json.dumps(dda_document.access_patterns.performance_requirements)}")
        
        # Governance
        if dda_document.governance:
            content_parts.append("\nGovernance:")
            content_parts.append(f"Privacy: {json.dumps(dda_document.governance.privacy)}")
            content_parts.append(f"Security: {json.dumps(dda_document.governance.security)}")
            content_parts.append(f"Compliance: {json.dumps(dda_document.governance.compliance)}")
        
        return "\n".join(content_parts)
    
    async def validate_graph(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the created knowledge graph."""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "statistics": {
                "episode_uuid": graph_data.get("episode_uuid"),
                "entities_count": graph_data.get("entities_count", 0),
                "relationships_count": graph_data.get("relationships_count", 0),
                "nodes_created": graph_data.get("nodes_created", 0),
                "edges_created": graph_data.get("edges_created", 0),
                "domain": graph_data.get("domain")
            }
        }
        
        # Basic validation checks
        if not graph_data.get("episode_uuid"):
            validation_result["errors"].append("No episode UUID found")
            validation_result["is_valid"] = False
        
        if graph_data.get("entities_count", 0) == 0:
            validation_result["errors"].append("No entities found")
            validation_result["is_valid"] = False
        
        if graph_data.get("nodes_created", 0) == 0:
            validation_result["warnings"].append("No nodes were created in the graph")
        
        if graph_data.get("edges_created", 0) == 0:
            validation_result["warnings"].append("No edges were created in the graph")
        
        return validation_result 