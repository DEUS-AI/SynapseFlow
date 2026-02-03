"""Type inference service using Graphiti LLM for intelligent data type detection."""

from typing import Dict, Any, Optional
from graphiti_core import Graphiti
from domain.odin_models import DataType, DataTypeEntity
import json
import re


class TypeInferenceService:
    """Service for inferring SQL data types from attribute names and context using Graphiti LLM."""
    
    def __init__(self, llm: Graphiti):
        """Initialize the type inference service with a Graphiti LLM instance.
        
        Args:
            llm: Graphiti instance configured for LLM processing
        """
        self.llm = llm
        self._type_cache: Dict[str, DataType] = {}
    
    async def infer_data_type(
        self, 
        attribute_name: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> DataTypeEntity:
        """Infer the most appropriate SQL data type for an attribute.
        
        Uses heuristic-based inference for reliability and speed.
        
        Args:
            attribute_name: Name of the attribute (e.g., "Customer ID", "Email Address")
            context: Optional context information (e.g., entity name, business rules)
        
        Returns:
            DataTypeEntity with inferred type and base_type
        """
        # Check cache first
        cache_key = self._generate_cache_key(attribute_name, context)
        if cache_key in self._type_cache:
            data_type = self._type_cache[cache_key]
            return DataTypeEntity(name=data_type, base_type=self._get_base_type(data_type))
        
        # Use heuristic inference (fast and reliable)
        inferred_type = self._heuristic_type_inference(attribute_name)
        
        # Cache the result
        self._type_cache[cache_key] = inferred_type
        
        # Convert enum to string value
        data_type_name = inferred_type.value if hasattr(inferred_type, 'value') else str(inferred_type)
        
        return DataTypeEntity(
            name=data_type_name,
            base_type=self._get_base_type(inferred_type)
        )
    
    async def infer_precision(
        self,
        attribute_name: str,
        data_type: DataTypeEntity,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """Infer precision for a data type (e.g., VARCHAR length, DECIMAL precision).
        
        Uses heuristic-based inference for reliability and speed.
        
        Args:
            attribute_name: Name of the attribute
            data_type: The inferred data type
            context: Optional context information
        
        Returns:
            Precision value or None if not applicable
        """
        if data_type.name not in [DataType.VARCHAR, DataType.DECIMAL]:
            return None
        
        # Use heuristic inference directly
        return self._heuristic_precision_inference(attribute_name, data_type)
    
    async def infer_scale(
        self,
        attribute_name: str,
        data_type: DataTypeEntity
    ) -> Optional[int]:
        """Infer scale for DECIMAL data types.
        
        Args:
            attribute_name: Name of the attribute
            data_type: The inferred data type (should be DECIMAL)
        
        Returns:
            Scale value or None if not applicable
        """
        if data_type.name != DataType.DECIMAL:
            return None
        
        # For DECIMAL types, default scale is typically 2 (for currency/amounts)
        # Can be enhanced with Graphiti if needed
        if any(keyword in attribute_name.lower() for keyword in ['amount', 'price', 'cost', 'revenue', 'budget']):
            return 2
        elif any(keyword in attribute_name.lower() for keyword in ['percentage', 'rate', 'ratio']):
            return 4
        else:
            return 2  # Default scale
    
    def _create_type_inference_prompt(
        self,
        attribute_name: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Create a prompt for Graphiti to infer data type."""
        prompt_parts = [
            "Given the following attribute name and context, infer the most appropriate SQL data type.",
            "",
            f"Attribute Name: {attribute_name}",
        ]
        
        if context:
            if "entity_name" in context:
                prompt_parts.append(f"Entity: {context['entity_name']}")
            if "business_rules" in context and context["business_rules"]:
                prompt_parts.append(f"Business Rules: {', '.join(context['business_rules'])}")
            if "description" in context:
                prompt_parts.append(f"Description: {context['description']}")
        
        prompt_parts.extend([
            "",
            "Available SQL data types: VARCHAR, INTEGER, BIGINT, DECIMAL, DATE, TIMESTAMP, BOOLEAN, JSON, ARRAY",
            "",
            "Respond with only the data type name (e.g., VARCHAR, INTEGER, DATE)."
        ])
        
        return "\n".join(prompt_parts)
    
    def _create_precision_inference_prompt(
        self,
        attribute_name: str,
        data_type: DataTypeEntity,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Create a prompt for Graphiti to infer precision."""
        prompt_parts = [
            f"Given attribute '{attribute_name}' with data type {data_type.name}, infer the appropriate precision/length.",
        ]
        
        if data_type.name == DataType.VARCHAR:
            prompt_parts.append("For VARCHAR, provide the maximum character length (e.g., 50, 255).")
        elif data_type.name == DataType.DECIMAL:
            prompt_parts.append("For DECIMAL, provide the total number of digits (e.g., 10, 19).")
        
        if context:
            if "business_rules" in context:
                prompt_parts.append(f"Business Rules: {', '.join(context.get('business_rules', []))}")
        
        prompt_parts.append("Respond with only the numeric precision value.")
        
        return "\n".join(prompt_parts)
    
    def _extract_type_from_graph_document(
        self,
        graph_document: Any,
        attribute_name: str
    ) -> Optional[DataType]:
        """Extract inferred data type from Graphiti graph document."""
        try:
            # Graphiti returns a graph document with nodes and relationships
            # Look for nodes that might contain the type information
            if hasattr(graph_document, 'nodes') and graph_document.nodes:
                for node in graph_document.nodes:
                    # Check if node properties contain type information
                    if hasattr(node, 'properties'):
                        props = node.properties if isinstance(node.properties, dict) else {}
                        # Look for type-related properties
                        if 'type' in props:
                            type_str = str(props['type']).upper()
                            try:
                                return DataType(type_str)
                            except ValueError:
                                pass
                        if 'data_type' in props:
                            type_str = str(props['data_type']).upper()
                            try:
                                return DataType(type_str)
                            except ValueError:
                                pass
            
            # Try to extract from node names or relationships
            if hasattr(graph_document, 'nodes') and graph_document.nodes:
                for node in graph_document.nodes:
                    if hasattr(node, 'name'):
                        node_name = str(node.name).upper()
                        for dt in DataType:
                            if dt.value in node_name:
                                return dt
            
            # Try to parse from relationships
            if hasattr(graph_document, 'relationships') and graph_document.relationships:
                for rel in graph_document.relationships:
                    if hasattr(rel, 'properties'):
                        props = rel.properties if isinstance(rel.properties, dict) else {}
                        if 'type' in props:
                            type_str = str(props['type']).upper()
                            try:
                                return DataType(type_str)
                            except ValueError:
                                pass
            
            return None
            
        except Exception as e:
            print(f"Warning: Failed to extract type from graph document: {e}")
            return None
    
    def _extract_precision_from_graph_document(
        self,
        graph_document: Any,
        attribute_name: str
    ) -> Optional[int]:
        """Extract precision value from Graphiti graph document."""
        try:
            if hasattr(graph_document, 'nodes') and graph_document.nodes:
                for node in graph_document.nodes:
                    if hasattr(node, 'properties'):
                        props = node.properties if isinstance(node.properties, dict) else {}
                        if 'precision' in props:
                            try:
                                return int(props['precision'])
                            except (ValueError, TypeError):
                                pass
                        if 'length' in props:
                            try:
                                return int(props['length'])
                            except (ValueError, TypeError):
                                pass
            
            # Try to extract numeric values from node names
            if hasattr(graph_document, 'nodes') and graph_document.nodes:
                for node in graph_document.nodes:
                    if hasattr(node, 'name'):
                        # Look for numbers in node names (e.g., "VARCHAR_50")
                        match = re.search(r'(\d+)', str(node.name))
                        if match:
                            return int(match.group(1))
            
            return None
            
        except Exception as e:
            print(f"Warning: Failed to extract precision from graph document: {e}")
            return None
    
    def _heuristic_type_inference(self, attribute_name: str) -> DataType:
        """Fallback heuristic for type inference based on attribute name patterns."""
        attr_lower = attribute_name.lower()
        
        # ID and key patterns
        if any(x in attr_lower for x in ['_id', ' id', 'id', 'key']):
            return DataType.BIGINT
        
        # Date and time patterns
        if any(x in attr_lower for x in ['timestamp', 'created_at', 'updated_at']):
            return DataType.TIMESTAMP
        if any(x in attr_lower for x in ['date', 'time']):
            return DataType.DATE
        
        # Email patterns
        if 'email' in attr_lower:
            return DataType.VARCHAR
        
        # Amount, price, cost patterns
        if any(x in attr_lower for x in ['amount', 'price', 'cost', 'revenue', 'budget', 'value', 'total']):
            return DataType.DECIMAL
        
        # Count, number, quantity patterns
        if any(x in attr_lower for x in ['count', 'number', 'quantity', 'num_', 'qty']):
            return DataType.INTEGER
        
        # Boolean patterns
        if any(x in attr_lower for x in ['is_', 'has_', 'can_', 'should_', 'active', 'enabled', 'status']):
            if 'status' in attr_lower and 'code' not in attr_lower:
                # Status might be VARCHAR if it's a code
                return DataType.BOOLEAN
            return DataType.BOOLEAN
        
        # Name, description, text patterns
        if any(x in attr_lower for x in ['name', 'description', 'title', 'label', 'text', 'comment', 'note']):
            return DataType.VARCHAR
        
        # Default to VARCHAR
        return DataType.VARCHAR
    
    def _heuristic_precision_inference(
        self,
        attribute_name: str,
        data_type: DataTypeEntity
    ) -> Optional[int]:
        """Fallback heuristic for precision inference."""
        attr_lower = attribute_name.lower()
        
        if data_type.name == DataType.VARCHAR:
            # ID fields
            if any(x in attr_lower for x in ['_id', ' id', 'id']):
                return 50
            # Email fields
            if 'email' in attr_lower:
                return 255
            # Name fields
            if 'name' in attr_lower:
                return 100
            # Description fields
            if 'description' in attr_lower or 'text' in attr_lower:
                return 500
            # Default VARCHAR length
            return 100
        
        elif data_type.name == DataType.DECIMAL:
            # Default DECIMAL precision
            return 10
        
        return None
    
    def _get_base_type(self, data_type: DataType) -> str:
        """Get the base type category for a data type."""
        base_types = {
            DataType.VARCHAR: "STRING",
            DataType.INTEGER: "NUMERIC",
            DataType.BIGINT: "NUMERIC",
            DataType.DECIMAL: "NUMERIC",
            DataType.DATE: "TEMPORAL",
            DataType.TIMESTAMP: "TEMPORAL",
            DataType.BOOLEAN: "BOOLEAN",
            DataType.JSON: "JSON",
            DataType.ARRAY: "ARRAY",
        }
        return base_types.get(data_type, "STRING")
    
    def _generate_cache_key(self, attribute_name: str, context: Optional[Dict[str, Any]]) -> str:
        """Generate a cache key for type inference."""
        context_str = ""
        if context:
            # Include relevant context fields
            context_parts = []
            if "entity_name" in context:
                context_parts.append(f"entity:{context['entity_name']}")
            if "description" in context:
                context_parts.append(f"desc:{context['description'][:50]}")
            context_str = "_".join(context_parts)
        
        return f"{attribute_name.lower()}_{context_str}"
    
    def clear_cache(self) -> None:
        """Clear the type inference cache."""
        self._type_cache.clear()

