"""LLM-based reasoner for semantic inference."""

from typing import Dict, Any, List, Optional
from graphiti_core import Graphiti
from domain.event import KnowledgeEvent

class LLMReasoner:
    """Uses LLM to infer semantic relationships and properties."""
    
    def __init__(self, llm: Graphiti):
        self.llm = llm
        
    async def suggest_semantic_relationships(self, event: KnowledgeEvent) -> List[Dict[str, Any]]:
        """Suggest semantic relationships for an entity using LLM."""
        if event.action != "create_entity":
            return []
            
        entity_data = event.data
        entity_id = entity_data.get("id", "")
        properties = event.data.get("properties", {})
        
        # Create prompt
        prompt = self._create_relationship_prompt(entity_id, properties)
        
        try:
            # Use Graphiti's add_episode to process the prompt
            # This will use the LLM to extract entities and relationships
            from datetime import datetime
            
            episode_result = await self.llm.add_episode(
                name=f"reasoning_{entity_id}",
                episode_body=prompt,
                source_description="LLM Reasoning Engine",
                reference_time=datetime.now()
            )
            
            suggestions = []
            
            # Extract relationships from the episode result
            # Graphiti returns edges (relationships) in the episode
            if hasattr(episode_result, 'edges') and episode_result.edges:
                for edge in episode_result.edges:
                    # Extract relationship information
                    source = str(edge.source_node_uuid) if hasattr(edge, 'source_node_uuid') else "unknown"
                    target = str(edge.target_node_uuid) if hasattr(edge, 'target_node_uuid') else "unknown"
                    rel_type = str(edge.name) if hasattr(edge, 'name') else "related_to"
                    
                    suggestions.append({
                        "type": "semantic_inference",
                        "relationship": rel_type,
                        "target": target,
                        "source": source,
                        "confidence": 0.7, # LLM inference is probabilistic
                        "reason": f"LLM suggested '{rel_type}' relationship"
                    })
            
            return suggestions
            
        except Exception as e:
            print(f"LLM reasoning failed: {e}")
            return []

    def _create_relationship_prompt(self, entity_id: str, properties: Dict[str, Any]) -> str:
        """Create prompt for relationship inference."""
        prop_str = ", ".join([f"{k}: {v}" for k, v in properties.items() if isinstance(v, (str, int, float, bool))])
        
        return f"""
        Analyze the following entity and suggest semantic relationships to other likely concepts in a business domain.
        
        Entity ID: {entity_id}
        Properties: {prop_str}
        
        Suggest relationships like 'belongs_to', 'has_part', 'related_to', 'is_a'.
        Focus on business concepts (e.g., Customer, Order, Product, Department).
        """

    async def suggest_business_concepts(self, event: KnowledgeEvent) -> List[Dict[str, Any]]:
        """Suggest linking entity to high-level business concepts."""
        if event.action != "create_entity":
            return []
            
        entity_data = event.data
        entity_id = entity_data.get("id", "")
        properties = event.data.get("properties", {})
        
        # Create prompt specifically for Business Concepts
        prop_str = ", ".join([f"{k}: {v}" for k, v in properties.items() if isinstance(v, (str, int, float, bool))])
        prompt = f"""
        Identify the high-level Business Concepts that this entity represents or is related to.
        
        Entity ID: {entity_id}
        Properties: {prop_str}
        
        Return a list of Business Concepts (e.g., 'Customer', 'Sales', 'Inventory').
        For each concept, suggest a relationship (e.g., 'represents', 'related_to').
        """
        
        try:
            from datetime import datetime
            
            # Use Graphiti to process
            episode_result = await self.llm.add_episode(
                name=f"concept_linking_{entity_id}",
                episode_body=prompt,
                source_description="LLM Concept Linker",
                reference_time=datetime.now()
            )
            
            suggestions = []
            if hasattr(episode_result, 'edges') and episode_result.edges:
                for edge in episode_result.edges:
                    target = str(edge.target_node_uuid) if hasattr(edge, 'target_node_uuid') else "unknown"
                    rel_type = str(edge.name) if hasattr(edge, 'name') else "related_to"
                    
                    suggestions.append({
                        "type": "semantic_linking",
                        "relationship": rel_type,
                        "target_concept": target,
                        "confidence": 0.8,
                        "reason": f"LLM identified '{target}' as a related Business Concept"
                    })
            
            return suggestions
            
        except Exception as e:
            print(f"LLM concept linking failed: {e}")
            return []
