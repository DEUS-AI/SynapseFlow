"""Metadata generation workflow for creating ODIN metadata graphs."""

from typing import Dict, Any, Optional
from application.commands.metadata_command import GenerateMetadataCommand
from application.agents.data_architect.dda_parser import DDAParserFactory
from application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
from application.services.knowledge_enricher import KnowledgeEnricher
from domain.kg_backends import KnowledgeGraphBackend
from graphiti_core import Graphiti


class MetadataGenerationWorkflow:
    """Orchestrates the complete metadata generation workflow."""
    
    def __init__(
        self,
        parser_factory: DDAParserFactory,
        metadata_builder: MetadataGraphBuilder,
        graph: Graphiti,
        kg_backend: KnowledgeGraphBackend
    ):
        """Initialize the metadata generation workflow.
        
        Args:
            parser_factory: Factory for creating DDA parsers
            metadata_builder: Builder for creating metadata graphs
            graph: Graphiti instance for reading architecture graphs
            kg_backend: Knowledge graph backend for storing metadata
        """
        self.parser_factory = parser_factory
        self.metadata_builder = metadata_builder
        self.graph = graph
        self.kg_backend = kg_backend
        self.enricher = KnowledgeEnricher(graph) # Initialize Enricher
    
    async def execute(self, command: GenerateMetadataCommand) -> Dict[str, Any]:
        """Execute the metadata generation workflow.
        
        Args:
            command: The GenerateMetadataCommand to execute
        
        Returns:
            Dictionary with success status, metadata graph results, and warnings
        """
        try:
            # 1. Parse DDA document
            parser = self.parser_factory.get_parser(command.dda_path)
            dda_document = await parser.parse(command.dda_path)
            
            # 2. (Optional) Read architecture graph from Graphiti if reference provided
            architecture_graph = None
            if command.architecture_graph_ref:
                architecture_graph = await self._read_architecture_graph(
                    command.architecture_graph_ref
                )
            
            # 3. (Optional) Validate DDA against architecture graph
            validation_result = {"is_valid": True, "errors": [], "warnings": []}
            if command.validate_against_architecture and architecture_graph:
                validation_result = await self._validate_against_architecture(
                    dda_document,
                    architecture_graph
                )
                if not validation_result["is_valid"]:
                    return {
                        "success": False,
                        "errors": validation_result["errors"],
                        "warnings": validation_result["warnings"],
                        "domain": command.domain
                    }
            
            # 4. Generate metadata graph
            metadata_result = await self.metadata_builder.build_metadata_graph(
                dda_document
            )
            
            # 5. Enrich metadata with LLM (Verifiable Knowledge)
            enrichment_results = []
            if self.enricher:
                print("🧠 Enriching metadata with LLM...")
                for entity in dda_document.entities:
                    # Convert entity to dict for enricher
                    entity_data = {
                        "id": f"table:{command.domain.lower()}.{entity.name.lower()}", # Heuristic ID
                        "name": entity.name,
                        "type": "Table",
                        "attributes": entity.attributes
                    }
                    inferences = await self.enricher.enrich_entity(entity_data)
                    
                    if inferences:
                        enrichment_results.extend(inferences)
                        # Apply inferences to backend
                        for inference in inferences:
                            if inference["type"] == "node":
                                await self.kg_backend.add_entity(
                                    f"concept:{inference['properties']['name']}",
                                    inference['properties'],
                                    inference['labels']
                                )
                            elif inference["type"] == "relationship":
                                await self.kg_backend.add_relationship(
                                    inference["source_id"],
                                    inference["rel_type"],
                                    inference["target_id"],
                                    inference["properties"]
                                )
            
            return {
                "success": True,
                "metadata_graph": metadata_result,
                "enrichment_results": enrichment_results,
                "domain": command.domain,
                "warnings": validation_result.get("warnings", [])
            }
            
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Metadata generation workflow failed: {str(e)}"],
                "warnings": [],
                "domain": command.domain
            }
    
    async def _read_architecture_graph(self, graph_ref: str) -> Optional[Dict[str, Any]]:
        """Read architecture graph from Graphiti.
        
        Args:
            graph_ref: Reference to architecture graph (group_id or episode_uuid)
        
        Returns:
            Dictionary with architecture graph nodes and edges, or None if not found
        """
        try:
            # Try to search for nodes in the architecture graph
            # graph_ref could be a group_id like "dda_customer_analytics"
            search_results = await self.graph.search(
                query=f"domain architecture entities relationships",
                group_ids=[graph_ref],
                num_results=50
            )
            
            if search_results:
                # Convert search results to a structured format
                nodes = []
                for result in search_results:
                    node_data = {
                        "uuid": result.uuid if hasattr(result, 'uuid') else None,
                        "name": result.name if hasattr(result, 'name') else None,
                        "attributes": result.attributes if hasattr(result, 'attributes') else {}
                    }
                    nodes.append(node_data)
                
                return {
                    "group_id": graph_ref,
                    "nodes": nodes,
                    "node_count": len(nodes)
                }
            
            return None
            
        except Exception as e:
            print(f"Warning: Could not read architecture graph {graph_ref}: {e}")
            return None
    
    async def _validate_against_architecture(
        self,
        dda_document,
        architecture_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate DDA document against existing architecture graph.
        
        Args:
            dda_document: The parsed DDA document
            architecture_graph: The architecture graph data
        
        Returns:
            Validation result with is_valid flag, errors, and warnings
        """
        errors = []
        warnings = []
        
        # Basic validation: check if entities in DDA match entities in architecture graph
        if architecture_graph and "nodes" in architecture_graph:
            dda_entity_names = {entity.name.lower() for entity in dda_document.entities}
            arch_entity_names = set()
            
            # Extract entity names from architecture graph nodes
            for node in architecture_graph["nodes"]:
                if "name" in node and node["name"]:
                    # Try to extract entity name from node name or attributes
                    node_name = str(node["name"]).lower()
                    if "entity" in node_name or "dataentity" in node_name:
                        # Extract entity name (simplified)
                        arch_entity_names.add(node_name)
            
            # Check for entities in DDA that don't exist in architecture
            if arch_entity_names:
                missing_in_arch = dda_entity_names - arch_entity_names
                if missing_in_arch:
                    warnings.append(
                        f"Entities in DDA not found in architecture graph: {', '.join(missing_in_arch)}"
                    )
        
        # Additional validation can be added here
        # e.g., check relationships, check attribute consistency, etc.
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

