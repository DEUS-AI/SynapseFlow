"""Knowledge Enricher Service.

This service uses LLMs (via Graphiti) to enrich the Knowledge Graph with
semantic relationships, business concepts, and verifiable knowledge.

Enhanced with entity resolution to prevent duplicate concept creation.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from graphiti_core import Graphiti
from domain.event import KnowledgeEvent
from domain.ontologies.odin import ODIN
from domain.knowledge_layers import KnowledgeLayer
from application.services.entity_resolver import EntityResolver, ResolutionStrategy

class KnowledgeEnricher:
    """Enriches metadata with semantic knowledge using LLMs."""

    def __init__(self, llm_client: Graphiti, backend: Optional[Any] = None, enable_resolution: bool = True):
        self.llm = llm_client
        self.backend = backend
        self.enable_resolution = enable_resolution

        # Initialize entity resolver if backend provided
        self.entity_resolver = None
        if backend and enable_resolution:
            self.entity_resolver = EntityResolver(
                backend=backend,
                semantic_threshold=0.90  # High threshold for concept matching
            )

    async def enrich_entity(self, entity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Enriches a single entity with inferred relationships and concepts.
        
        Args:
            entity_data: Dictionary containing entity details (name, columns, etc.)
            
        Returns:
            List of inferred relationships/nodes as dictionaries.
        """
        entity_name = entity_data.get("name")
        entity_type = entity_data.get("type", "Table")
        attributes = entity_data.get("attributes", [])
        
        # 1. Construct Prompt
        prompt = f"""
        Analyze this Data Entity and infer its semantic meaning.
        
        Entity: {entity_name} ({entity_type})
        Attributes: {', '.join(attributes)}
        
        Task:
        1. Identify the high-level Business Concept this entity represents (e.g., 'Customer', 'SalesOrder').
        2. Suggest a relationship between the Entity and the Concept.
        3. Provide a confidence score (0.0-1.0).
        
        Output Format (JSON):
        {{
            "concept": "ConceptName",
            "relationship": "represents",
            "confidence": 0.9,
            "reason": "Explanation..."
        }}
        """
        
        # 2. Call LLM (using Graphiti's add_episode to simulate/record the reasoning)
        # In a real scenario, we might use a direct completion call if we just want the JSON,
        # but add_episode allows us to store this reasoning event in the graph itself.
        
        # For this implementation, we assume we can get the structured response.
        # Since Graphiti is primarily for graph memory, we might need a helper to extract the JSON.
        # For now, we will simulate the extraction or assume a method exists.
        
        # We'll use a mockable interface for the actual LLM call if Graphiti doesn't expose one directly for this.
        # But let's try to use add_episode and assume we can parse the result or that Graphiti
        # extracts the nodes for us.
        
        # Actually, for "Verifiable Knowledge", we want to explicitly create the nodes ourselves
        # based on the LLM's output.
        
        # Let's assume we have a method `_call_llm` that wraps the LLM generation.
        response = await self._call_llm(prompt)
        
        inferences = []
        if response:
            concept_name = response.get("concept")
            if concept_name:
                # Try to resolve entity if resolver available
                if self.entity_resolver:
                    resolution = await self.entity_resolver.resolve_entity(
                        entity_name=concept_name,
                        entity_type="BusinessConcept",
                        properties={"domain": entity_data.get("domain", "general")},
                        strategy=ResolutionStrategy.HYBRID
                    )

                    if resolution.is_duplicate and resolution.recommended_action in ["merge", "link"]:
                        # Link to existing concept instead of creating new
                        print(f"✓ Found existing concept: {resolution.canonical_entity_id} (confidence: {resolution.confidence:.2f})")
                        inferences.append({
                            "type": "relationship",
                            "source_id": entity_data.get("id"),
                            "target_id": resolution.canonical_entity_id,
                            "rel_type": ODIN.REPRESENTS,
                            "properties": {
                                "confidence": response.get("confidence", 0.5),
                                "reason": response.get("reason"),
                                "resolution_strategy": "entity_resolver",
                                "resolution_confidence": resolution.confidence
                            }
                        })
                        return inferences

                # No duplicate found or resolver disabled - create new concept
                concept_id = f"concept:{concept_name.lower().replace(' ', '_')}"
                inferences.append({
                    "type": "node",
                    "labels": [ODIN.BUSINESS_CONCEPT, "Concept"],
                    "properties": {
                        "name": concept_name,
                        ODIN.STATUS: "hypothetical",
                        ODIN.CONFIDENCE_SCORE: response.get("confidence", 0.5),
                        "layer": KnowledgeLayer.SEMANTIC.value  # Add layer assignment
                    }
                })

                # Create Relationship
                inferences.append({
                    "type": "relationship",
                    "source_id": entity_data.get("id"),
                    "target_id": concept_id,
                    "rel_type": ODIN.REPRESENTS,
                    "properties": {
                        "confidence": response.get("confidence", 0.5),
                        "reason": response.get("reason")
                    }
                })

        return inferences

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Performs the LLM call using OpenAI API.
        Falls back to heuristic inference if API key is not available.
        """
        import os
        import json
        import re
        
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            # Fallback to heuristic
            return self._heuristic_inference(prompt)
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a data modeling expert. Analyze data entities and infer business concepts. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return None
            
        except Exception as e:
            print(f"⚠️ LLM call failed: {e}. Using heuristic fallback.")
            return self._heuristic_inference(prompt)
    
    def _heuristic_inference(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Heuristic-based concept inference when LLM is not available.
        """
        import re
        
        # Extract entity name from prompt
        match = re.search(r'Entity:\s*(\w+)', prompt)
        if not match:
            return None
        
        entity_name = match.group(1).lower()
        
        # Common mappings
        concept_map = {
            "patient": ("Patient", 0.95),
            "customer": ("Customer", 0.95),
            "user": ("User", 0.90),
            "order": ("SalesOrder", 0.90),
            "product": ("Product", 0.90),
            "invoice": ("Invoice", 0.85),
            "diagnosis": ("MedicalDiagnosis", 0.90),
            "treatment": ("Treatment", 0.85),
            "medication": ("Medication", 0.90),
            "therapy": ("Therapy", 0.85),
            "appointment": ("Appointment", 0.80),
            "lab": ("LaboratoryResult", 0.85),
            "assessment": ("Assessment", 0.80),
            "provider": ("HealthcareProvider", 0.85),
        }
        
        for key, (concept, confidence) in concept_map.items():
            if key in entity_name:
                return {
                    "concept": concept,
                    "relationship": "represents",
                    "confidence": confidence,
                    "reason": f"Heuristic: Entity name '{entity_name}' contains '{key}'"
                }
        
        # Default: Use PascalCase of entity name
        concept = ''.join(word.title() for word in entity_name.split('_'))
        return {
            "concept": concept,
            "relationship": "represents",
            "confidence": 0.6,
            "reason": f"Heuristic: Derived from entity name '{entity_name}'"
        }
