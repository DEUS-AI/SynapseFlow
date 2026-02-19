from typing import Dict, Any, List
from domain.commands import Command
from application.commands.base import CommandHandler
from graphiti_core import Graphiti


class BuildKGCommand(Command):
    """Command to build knowledge graph from domain models."""
    
    def __init__(self, domain: str, source_data: Dict[str, Any]):
        self.domain = domain
        self.source_data = source_data


class BuildKGCommandHandler(CommandHandler):
    """Handles BuildKGCommand execution with access to Data Architect's domain models."""
    
    def __init__(self, graph: Graphiti):
        self.graph = graph
    
    async def handle(self, command: BuildKGCommand) -> Dict[str, Any]:
        """Execute the knowledge graph building process with domain model integration."""
        try:
            # 1. Access existing domain models from Data Architect
            domain_models = await self._get_domain_models(command.domain)
            
            # 2. Build knowledge graph using domain models as context
            kg_result = await self._build_knowledge_graph(command.source_data, domain_models)
            
            # 3. Validate against domain models
            validation_result = await self._validate_against_domain_models(kg_result, domain_models)
            
            return {
                "success": True,
                "domain": command.domain,
                "kg_nodes_created": kg_result.get("nodes_created", 0),
                "kg_edges_created": kg_result.get("edges_created", 0),
                "domain_models_used": len(domain_models),
                "validation_passed": validation_result.get("is_valid", False),
                "validation_warnings": validation_result.get("warnings", [])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Knowledge graph building failed: {str(e)}"
            }
    
    async def _get_domain_models(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve domain models created by Data Architect."""
        try:
            # Search for domain models in the knowledge graph
            search_results = await self.graph.search(
                query=f"domain {domain} data entities relationships",
                group_ids=[f"dda_{domain.lower().replace(' ', '_')}"],
                num_results=20
            )
            
            domain_models = []
            if search_results:
                for result in search_results:
                    if hasattr(result, 'attributes') and result.attributes:
                        model_info = {
                            "uuid": result.uuid,
                            "name": result.name,
                            "type": "entity" if "entity" in result.name.lower() else "relationship",
                            "attributes": result.attributes
                        }
                        domain_models.append(model_info)
            
            print(f"Found {len(domain_models)} domain models for {domain}")
            return domain_models
            
        except Exception as e:
            print(f"Warning: Could not retrieve domain models: {e}")
            return []
    
    async def _build_knowledge_graph(self, source_data: Dict[str, Any], domain_models: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build knowledge graph using domain models as context."""
        
        # Create episode content that incorporates domain model context
        episode_content = self._create_contextual_episode_content(source_data, domain_models)
        
        # Add the episode to Graphiti
        episode_results = await self.graph.add_episode(
            name=f"KG Build - {source_data.get('domain', 'Unknown')}",
            episode_body=episode_content,
            source_description="Knowledge Graph built using domain models",
            reference_time=source_data.get('timestamp', '2024-01-01'),
            source="message",
            group_id=f"kg_{source_data.get('domain', 'unknown').lower().replace(' ', '_')}",
            update_communities=True
        )
        
        return {
            "episode_uuid": episode_results.episode.uuid if episode_results.episode else None,
            "nodes_created": len(episode_results.nodes) if episode_results.nodes else 0,
            "edges_created": len(episode_results.edges) if episode_results.edges else 0,
            "domain_models_referenced": len(domain_models)
        }
    
    def _create_contextual_episode_content(self, source_data: Dict[str, Any], domain_models: List[Dict[str, Any]]) -> str:
        """Create episode content that incorporates domain model context."""
        
        content_parts = []
        
        # Header with domain model context
        content_parts.append("KNOWLEDGE GRAPH BUILD")
        content_parts.append(f"Domain: {source_data.get('domain', 'Unknown')}")
        content_parts.append(f"Source Data Type: {source_data.get('type', 'Unknown')}")
        content_parts.append(f"Domain Models Available: {len(domain_models)}")
        
        # Domain model context
        if domain_models:
            content_parts.append("\nDOMAIN MODEL CONTEXT:")
            content_parts.append("The following domain models should be used as reference:")
            
            entities = [m for m in domain_models if m.get('type') == 'entity']
            relationships = [m for m in domain_models if m.get('type') == 'relationship']
            
            if entities:
                content_parts.append(f"\nReference Entities ({len(entities)}):")
                for entity in entities:
                    content_parts.append(f"- {entity.get('name', 'Unknown')}: {entity.get('attributes', {}).get('description', 'No description')}")
            
            if relationships:
                content_parts.append(f"\nReference Relationships ({len(relationships)}):")
                for rel in relationships:
                    content_parts.append(f"- {rel.get('name', 'Unknown')}: {rel.get('attributes', {}).get('description', 'No description')}")
        
        # Source data content
        content_parts.append("\nSOURCE DATA:")
        content_parts.append(f"Content: {source_data.get('content', 'No content provided')}")
        
        if source_data.get('metadata'):
            content_parts.append(f"Metadata: {source_data.get('metadata')}")
        
        # Instructions for graph building
        content_parts.append("\nBUILDING INSTRUCTIONS:")
        content_parts.append("1. Use the domain models above as reference for entity and relationship structure")
        content_parts.append("2. Extract entities and relationships from the source data")
        content_parts.append("3. Ensure consistency with existing domain model patterns")
        content_parts.append("4. Create nodes and edges that align with the domain architecture")
        
        return "\n".join(content_parts)
    
    async def _validate_against_domain_models(self, kg_result: Dict[str, Any], domain_models: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate the built knowledge graph against domain models."""
        
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Basic validation
        if kg_result.get("nodes_created", 0) == 0:
            validation_result["warnings"].append("No nodes were created in the knowledge graph")
        
        if kg_result.get("edges_created", 0) == 0:
            validation_result["warnings"].append("No edges were created in the knowledge graph")
        
        if len(domain_models) == 0:
            validation_result["warnings"].append("No domain models were available for reference")
        
        # Check if the built graph references domain models
        if kg_result.get("domain_models_referenced", 0) == 0 and len(domain_models) > 0:
            validation_result["warnings"].append("Built graph does not reference available domain models")
        
        return validation_result 