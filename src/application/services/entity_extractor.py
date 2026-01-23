"""Entity Extractor Service.

Uses LLM to extract entities and relationships from text chunks,
then links them to existing graph nodes.

Enhanced with semantic normalization for consistent terminology.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os
import json
import re
from application.services.semantic_normalizer import SemanticNormalizer


@dataclass
class ExtractedEntity:
    """Represents an entity extracted from text."""
    name: str
    entity_type: str
    context: str
    confidence: float
    source_chunk_id: str
    linked_node_id: Optional[str] = None


@dataclass
class ExtractedRelation:
    """Represents a relationship extracted from text."""
    source_entity: str
    relation_type: str
    target_entity: str
    context: str
    confidence: float


class EntityExtractor:
    """Extracts entities and relationships from text using LLM."""
    
    # Entity types relevant to data architecture domain
    ENTITY_TYPES = [
        "Table", "Column", "Database", "Schema",
        "BusinessConcept", "DataProduct", "Person",
        "Process", "System", "Policy", "Metric"
    ]
    
    def __init__(self, llm_client=None, domain: Optional[str] = None, enable_normalization: bool = True):
        """Initialize the entity extractor.

        Args:
            llm_client: Optional LLM client (uses OpenAI if not provided)
            domain: Optional domain for domain-specific normalization
            enable_normalization: Whether to enable semantic normalization
        """
        self.llm_client = llm_client
        self.enable_normalization = enable_normalization

        # Initialize semantic normalizer
        if enable_normalization:
            self.normalizer = SemanticNormalizer(domain=domain)
        else:
            self.normalizer = None
    
    async def extract_entities(
        self, 
        text: str, 
        chunk_id: str = "unknown"
    ) -> List[ExtractedEntity]:
        """Extract entities from a text chunk.
        
        Args:
            text: Text to extract entities from
            chunk_id: ID of the source chunk
            
        Returns:
            List of extracted entities
        """
        prompt = self._create_entity_extraction_prompt(text)
        response = await self._call_llm(prompt)
        
        entities = []
        if response and "entities" in response:
            for e in response["entities"]:
                original_name = e.get("name", "Unknown")

                # Normalize entity name if normalizer available
                if self.normalizer:
                    canonical_name = self.normalizer.normalize(original_name)
                else:
                    canonical_name = original_name

                entity = ExtractedEntity(
                    name=canonical_name,  # Use normalized name
                    entity_type=e.get("type", "Unknown"),
                    context=e.get("context", ""),
                    confidence=e.get("confidence", 0.5),
                    source_chunk_id=chunk_id
                )

                # Store original name if different (for traceability)
                if canonical_name != original_name and hasattr(entity, '__dict__'):
                    entity.__dict__['original_name'] = original_name
                    entity.__dict__['normalized'] = True

                entities.append(entity)

        return entities
    
    async def extract_relations(
        self, 
        text: str,
        entities: List[ExtractedEntity]
    ) -> List[ExtractedRelation]:
        """Extract relationships between entities from text.
        
        Args:
            text: Text to analyze
            entities: Previously extracted entities
            
        Returns:
            List of extracted relations
        """
        entity_names = [e.name for e in entities]
        prompt = self._create_relation_extraction_prompt(text, entity_names)
        response = await self._call_llm(prompt)
        
        relations = []
        if response and "relations" in response:
            for r in response["relations"]:
                relations.append(ExtractedRelation(
                    source_entity=r.get("source", ""),
                    relation_type=r.get("relation", "RELATED_TO"),
                    target_entity=r.get("target", ""),
                    context=r.get("context", ""),
                    confidence=r.get("confidence", 0.5)
                ))
        
        return relations
    
    async def link_to_graph(
        self, 
        entity: ExtractedEntity, 
        kg_backend
    ) -> Optional[str]:
        """Try to link an extracted entity to an existing graph node.
        
        Uses multiple matching strategies:
        1. Exact name match on BusinessConcept nodes
        2. Partial name match on any node
        3. Type-based matching (e.g., "Patient" entity to Patient concept)
        
        Args:
            entity: The extracted entity
            kg_backend: Knowledge graph backend
            
        Returns:
            ID of linked node, or None if no match found
        """
        entity_name_lower = entity.name.lower().strip()
        
        # Check if backend supports query_raw (Neo4j)
        use_raw = hasattr(kg_backend, 'query_raw')
        
        # Strategy 1: Look for BusinessConcept with matching name
        try:
            query = """
            MATCH (n:BusinessConcept)
            WHERE toLower(n.name) = $name
            RETURN n.id as id, n.name as name
            LIMIT 1
            """
            if use_raw:
                records = await kg_backend.query_raw(query, {"name": entity_name_lower})
                if records and records[0].get("id"):
                    return records[0]["id"]
            else:
                result = await kg_backend.query(query, {"name": entity_name_lower})
                if result and result.get("nodes"):
                    first_node = list(result["nodes"].values())[0]
                    node_id = first_node.get("properties", {}).get("id")
                    if node_id:
                        return node_id
        except Exception:
            pass
        
        # Strategy 2: Partial match on any Entity node
        try:
            query = """
            MATCH (n:Entity)
            WHERE toLower(n.name) CONTAINS $name 
               OR toLower(n.id) CONTAINS $name
            RETURN n.id as id, n.name as name
            LIMIT 3
            """
            if use_raw:
                records = await kg_backend.query_raw(query, {"name": entity_name_lower})
                if records and records[0].get("id"):
                    return records[0]["id"]
            else:
                result = await kg_backend.query(query, {"name": entity_name_lower})
                if result and result.get("nodes"):
                    first_node = list(result["nodes"].values())[0]
                    node_id = first_node.get("properties", {}).get("id")
                    if node_id:
                        return node_id
        except Exception:
            pass
        
        # Strategy 3: Match concept by extracting key term
        # e.g., "Disease Activity Assessment" -> look for "Assessment" concept
        try:
            words = entity_name_lower.split()
            for word in reversed(words):  # Try last word first (often the noun)
                if len(word) > 3:
                    query = """
                    MATCH (n)
                    WHERE (n:BusinessConcept OR n:Concept OR n:DataEntity)
                      AND toLower(n.name) CONTAINS $word
                    RETURN n.id as id, n.name as name
                    LIMIT 1
                    """
                    if use_raw:
                        records = await kg_backend.query_raw(query, {"word": word})
                        if records and records[0].get("id"):
                            return records[0]["id"]
                    else:
                        result = await kg_backend.query(query, {"word": word})
                        if result and result.get("nodes"):
                            first_node = list(result["nodes"].values())[0]
                            node_id = first_node.get("properties", {}).get("id")
                            if node_id:
                                return node_id
        except Exception:
            pass
        
        return None
    
    def _create_entity_extraction_prompt(self, text: str) -> str:
        """Create prompt for entity extraction."""
        return f"""Extract entities from the following text. Focus on data architecture concepts like:
- Tables, Columns, Databases, Schemas
- Business Concepts (Customer, Patient, Order, etc.)
- Data Products, Systems, Processes
- People (data owners, stakeholders)
- Policies, Metrics

Text:
{text}

Respond with JSON in this exact format:
{{
    "entities": [
        {{"name": "EntityName", "type": "EntityType", "context": "brief context", "confidence": 0.9}},
        ...
    ]
}}

Only include entities explicitly mentioned in the text."""

    def _create_relation_extraction_prompt(self, text: str, entity_names: List[str]) -> str:
        """Create prompt for relation extraction."""
        return f"""Given these entities: {', '.join(entity_names)}

Extract relationships between them from this text:
{text}

Respond with JSON in this exact format:
{{
    "relations": [
        {{"source": "Entity1", "relation": "RELATION_TYPE", "target": "Entity2", "context": "brief context", "confidence": 0.8}},
        ...
    ]
}}

Common relation types: CONTAINS, DERIVED_FROM, OWNED_BY, RELATED_TO, REFERENCES, USES"""

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call LLM for extraction."""
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            # Fallback to heuristic extraction
            return self._heuristic_extraction(prompt)
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a data architecture expert. Extract entities and relationships from text. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            
            return None
            
        except Exception as e:
            print(f"Warning: LLM extraction failed: {e}")
            return self._heuristic_extraction(prompt)
    
    def _heuristic_extraction(self, prompt: str) -> Dict[str, Any]:
        """Fallback heuristic entity extraction."""
        # Simple pattern matching for common entity types
        entities = []
        
        # Extract text from prompt
        text_match = re.search(r'Text:\n(.+?)(?:\n\nRespond|$)', prompt, re.DOTALL)
        if not text_match:
            return {"entities": []}
        
        text = text_match.group(1)
        
        # Pattern for capitalized terms (potential entities)
        words = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        
        seen = set()
        for word in words:
            if word.lower() not in seen and len(word) > 2:
                seen.add(word.lower())
                entity_type = self._guess_entity_type(word)
                entities.append({
                    "name": word,
                    "type": entity_type,
                    "context": f"Found in text",
                    "confidence": 0.5
                })
        
        return {"entities": entities[:10]}  # Limit to 10 entities
    
    def _guess_entity_type(self, name: str) -> str:
        """Guess entity type from name."""
        name_lower = name.lower()
        
        if any(x in name_lower for x in ["table", "entity", "record"]):
            return "Table"
        elif any(x in name_lower for x in ["column", "field", "attribute"]):
            return "Column"
        elif any(x in name_lower for x in ["patient", "customer", "user", "person"]):
            return "BusinessConcept"
        elif any(x in name_lower for x in ["system", "service", "api"]):
            return "System"
        elif any(x in name_lower for x in ["policy", "rule", "constraint"]):
            return "Policy"
        else:
            return "BusinessConcept"
