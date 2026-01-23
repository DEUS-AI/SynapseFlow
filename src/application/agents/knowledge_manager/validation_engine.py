"""Advanced validation engine for knowledge graph operations."""

from typing import Dict, Any, List, Optional
from domain.kg_backends import KnowledgeGraphBackend
from domain.event import KnowledgeEvent
from domain.roles import Role


class ValidationEngine:
    """Advanced validation for knowledge graph operations."""

    def __init__(self, backend: KnowledgeGraphBackend):
        self.backend = backend
        self._validation_rules = self._initialize_validation_rules()
        self.shacl_graph = self._load_shacl_shapes()

    def _load_shacl_shapes(self):
        """Load SHACL shapes from file."""
        try:
            from rdflib import Graph
            import os
            
            g = Graph()
            # Path to shapes file
            shapes_path = os.path.join(os.path.dirname(__file__), "../../../domain/shapes/odin_shapes.ttl")
            if os.path.exists(shapes_path):
                g.parse(shapes_path, format="turtle")
                return g
            else:
                print(f"Warning: SHACL shapes file not found at {shapes_path}")
                return None
        except ImportError:
            print("Warning: rdflib not installed, SHACL validation disabled")
            return None

    def _initialize_validation_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize validation rules for different operations."""
        return {
            "create_entity": [
                {
                    "name": "required_id",
                    "validator": self._validate_required_id,
                    "severity": "error"
                },
                {
                    "name": "id_format",
                    "validator": self._validate_id_format,
                    "severity": "warning"
                },
                {
                    "name": "properties_structure",
                    "validator": self._validate_properties_structure,
                    "severity": "warning"
                },
                {
                    "name": "role_permission",
                    "validator": self._validate_role_permission,
                    "severity": "error"
                },
                {
                    "name": "shacl_compliance",
                    "validator": self._validate_shacl,
                    "severity": "error"
                },
                {
                    "name": "layer_assignment",
                    "validator": self._validate_layer_assignment,
                    "severity": "error"
                },
                {
                    "name": "layer_properties",
                    "validator": self._validate_layer_properties,
                    "severity": "warning"
                }
            ],
            "create_relationship": [
                {
                    "name": "required_fields",
                    "validator": self._validate_required_relationship_fields,
                    "severity": "error"
                },
                {
                    "name": "relationship_type",
                    "validator": self._validate_relationship_type,
                    "severity": "warning"
                },
                {
                    "name": "role_permission",
                    "validator": self._validate_role_permission,
                    "severity": "error"
                },
                {
                    "name": "layer_hierarchy",
                    "validator": self._validate_relationship_layer_hierarchy,
                    "severity": "warning"
                }
            ]
        }

    async def validate_event(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """Validate a knowledge event using all applicable rules."""
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "validation_details": []
        }
        
        # Get rules for this action
        rules = self._validation_rules.get(event.action, [])
        
        for rule in rules:
            try:
                rule_result = await rule["validator"](event)
                
                if rule_result["is_valid"]:
                    if rule_result.get("warnings"):
                        validation_result["warnings"].extend(rule_result["warnings"])
                else:
                    validation_result["is_valid"] = False
                    if rule_result.get("errors"):
                        validation_result["errors"].extend(rule_result["errors"])
                
                # Add validation details
                validation_result["validation_details"].append({
                    "rule": rule["name"],
                    "severity": rule["severity"],
                    "passed": rule_result["is_valid"],
                    "warnings": rule_result.get("warnings", []),
                    "errors": rule_result.get("errors", [])
                })
                
            except Exception as e:
                # Rule validation failed
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Validation rule '{rule['name']}' failed: {str(e)}")
                validation_result["validation_details"].append({
                    "rule": rule["name"],
                    "severity": rule["severity"],
                    "passed": False,
                    "errors": [f"Rule execution failed: {str(e)}"]
                })
        
        return validation_result

    async def _validate_required_id(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """Validate that entity ID is provided."""
        entity_id = event.data.get("id")
        
        if not entity_id:
            return {
                "is_valid": False,
                "errors": ["Entity ID is required for create_entity operation"]
            }
        
        if not isinstance(entity_id, str):
            return {
                "is_valid": False,
                "errors": ["Entity ID must be a string"]
            }
        
        return {"is_valid": True}

    async def _validate_id_format(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """Validate entity ID format."""
        entity_id = event.data.get("id", "")
        warnings = []
        
        # Check for common ID format issues
        if len(entity_id) > 100:
            warnings.append("Entity ID is very long (>100 characters)")
        
        if " " in entity_id:
            warnings.append("Entity ID contains spaces - consider using underscores or hyphens")
        
        if entity_id.lower() in ["null", "none", "undefined", ""]:
            warnings.append("Entity ID appears to be empty or invalid")
        
        # Check for special characters that might cause issues
        special_chars = ['<', '>', '"', "'", '&', '|', ';', '(', ')', '[', ']', '{', '}']
        if any(char in entity_id for char in special_chars):
            warnings.append("Entity ID contains special characters that might cause issues")
        
        return {
            "is_valid": True,
            "warnings": warnings
        }

    async def _validate_properties_structure(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """Validate entity properties structure."""
        properties = event.data.get("properties", {})
        warnings = []
        
        if not isinstance(properties, dict):
            return {
                "is_valid": False,
                "errors": ["Properties must be a dictionary"]
            }
        
        # Check property keys
        for key, value in properties.items():
            if not isinstance(key, str):
                warnings.append(f"Property key '{key}' is not a string")
                continue
            
            if not key.strip():
                warnings.append("Empty property key found")
                continue
            
            # Check for reserved property names
            reserved_names = ["id", "_id", "type", "_type", "label", "_label"]
            if key.lower() in reserved_names:
                warnings.append(f"Property key '{key}' might conflict with system properties")
            
            # Check property values
            if value is None:
                warnings.append(f"Property '{key}' has null value")
            elif isinstance(value, (dict, list)) and len(str(value)) > 1000:
                warnings.append(f"Property '{key}' has very large value (>1000 characters)")
        
        return {
            "is_valid": True,
            "warnings": warnings
        }

    async def _validate_required_relationship_fields(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """Validate required fields for relationship creation."""
        required_fields = ["source", "target", "type"]
        missing_fields = []
        
        for field in required_fields:
            if not event.data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            return {
                "is_valid": False,
                "errors": [f"Missing required fields: {', '.join(missing_fields)}"]
            }
        
        return {"is_valid": True}

    async def _validate_relationship_type(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """Validate relationship type."""
        rel_type = event.data.get("type", "")
        warnings = []
        
        if not isinstance(rel_type, str):
            return {
                "is_valid": False,
                "errors": ["Relationship type must be a string"]
            }
        
        # Check relationship type format
        if len(rel_type) > 50:
            warnings.append("Relationship type is very long (>50 characters)")
        
        if " " in rel_type:
            warnings.append("Relationship type contains spaces - consider using underscores or hyphens")
        
        # Check for common relationship type patterns
        if rel_type.lower() in ["relates", "related", "connection", "link"]:
            warnings.append("Relationship type is very generic - consider using more specific types")
        
        return {
            "is_valid": True,
            "warnings": warnings
        }

    async def _validate_role_permission(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """Validate role permissions for the operation."""
        role = event.role
        action = event.action
        
        # Define role permissions
        role_permissions = {
            "create_entity": {
                Role.DATA_ARCHITECT: True,
                Role.DATA_ENGINEER: True,
                Role.KNOWLEDGE_MANAGER: True,
                Role.SYSTEM_ADMIN: True
            },
            "create_relationship": {
                Role.DATA_ARCHITECT: False,
                Role.DATA_ENGINEER: False,
                Role.KNOWLEDGE_MANAGER: True,
                Role.SYSTEM_ADMIN: True
            }
        }
        
        action_permissions = role_permissions.get(action, {})
        is_allowed = action_permissions.get(role, False)
        
        if not is_allowed:
            return {
                "is_valid": False,
                "errors": [f"Role '{role.value}' is not allowed to perform action '{action}'"]
            }
        
        return {"is_valid": True}

    async def validate_batch_operation(self, events: List[KnowledgeEvent]) -> Dict[str, Any]:
        """Validate a batch of knowledge events."""
        batch_result = {
            "is_valid": True,
            "total_events": len(events),
            "valid_events": 0,
            "invalid_events": 0,
            "event_results": []
        }
        
        for i, event in enumerate(events):
            event_result = await self.validate_event(event)
            batch_result["event_results"].append({
                "index": i,
                "event": event,
                "result": event_result
            })
            
            if event_result["is_valid"]:
                batch_result["valid_events"] += 1
            else:
                batch_result["invalid_events"] += 1
                batch_result["is_valid"] = False
        
        return batch_result

    async def _validate_shacl(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """Validate event data against SHACL shapes."""
        try:
            import pyshacl
            from rdflib import Graph, Literal, RDF, URIRef, Namespace
        except ImportError:
            return {"is_valid": True, "warnings": ["pyshacl not installed, skipping SHACL validation"]}

        # 1. Convert Event to RDF Graph
        data_graph = self._event_to_rdf(event)
        if not data_graph:
             return {"is_valid": True} # Nothing to validate

        # 2. Run Validation
        conforms, report_graph, report_text = pyshacl.validate(
            data_graph,
            shacl_graph=self.shacl_graph,
            inference='rdfs',
            abort_on_first=False,
            meta_shacl=False,
            debug=False
        )

        if conforms:
            return {"is_valid": True}
        else:
            return {
                "is_valid": False,
                "errors": [f"SHACL Violation: {report_text}"]
            }

    def _event_to_rdf(self, event: KnowledgeEvent):
        """Convert KnowledgeEvent data to RDFLib Graph."""
        from rdflib import Graph, Literal, RDF, URIRef, Namespace
        
        g = Graph()
        ODIN = Namespace("http://example.org/odin#")
        g.bind("odin", ODIN)
        
        data = event.data
        if event.action == "create_entity":
            entity_id = data.get("id", "temp_id")
            entity_uri = URIRef(f"http://example.org/data/{entity_id}")
            
            # Add Type
            # Map internal labels to ODIN types
            labels = data.get("labels", [])
            if "Table" in labels or "File" in labels:
                g.add((entity_uri, RDF.type, ODIN.DataEntity))
            elif "Report" in labels:
                g.add((entity_uri, RDF.type, ODIN.InformationAsset))
            elif "Concept" in labels:
                g.add((entity_uri, RDF.type, ODIN.BusinessConcept))
            
            # Add Properties
            props = data.get("properties", {})
            if "name" in props:
                g.add((entity_uri, ODIN.name, Literal(props["name"])))
            if "origin" in props:
                g.add((entity_uri, ODIN.origin, Literal(props["origin"])))
            if "description" in props:
                g.add((entity_uri, ODIN.description, Literal(props["description"])))
                
            return g
            
        elif event.action == "create_relationship":
            # For relationship validation, we might need the source/target nodes too.
            # This is harder without querying the backend.
            # For now, we skip SHACL for relationships in this MVP or mock the nodes.
            return None
            
        return None

    def add_custom_rule(self, action: str, rule: Dict[str, Any]) -> None:
        """Add a custom validation rule."""
        if action not in self._validation_rules:
            self._validation_rules[action] = []
        
        self._validation_rules[action].append(rule)

    def remove_rule(self, action: str, rule_name: str) -> bool:
        """Remove a validation rule by name."""
        if action in self._validation_rules:
            for i, rule in enumerate(self._validation_rules[action]):
                if rule.get("name") == rule_name:
                    del self._validation_rules[action][i]
                    return True
        return False

    async def _validate_layer_assignment(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """
        Validate that entities have proper layer assignment.

        All entities must have a 'layer' property set to one of:
        PERCEPTION, SEMANTIC, REASONING, or APPLICATION
        """
        from domain.knowledge_layers import KnowledgeLayer

        properties = event.data.get("properties", {})
        labels = event.data.get("labels", [])
        layer = properties.get("layer")

        errors = []

        # Check if layer is assigned
        if not layer:
            errors.append("Entity must have a 'layer' property assigned")
            return {"is_valid": False, "errors": errors}

        # Validate layer value
        valid_layers = [l.value for l in KnowledgeLayer]
        if layer not in valid_layers:
            errors.append(
                f"Invalid layer '{layer}'. Must be one of: {', '.join(valid_layers)}"
            )
            return {"is_valid": False, "errors": errors}

        # Validate layer assignment based on entity type
        layer_type_mapping = {
            "PERCEPTION": ["Table", "Column", "Schema", "Catalog", "File", "Chunk",
                           "TypeAssignment", "DataEntity"],
            "SEMANTIC": ["Domain", "BusinessConcept", "User", "DataType",
                         "InformationAsset", "Attribute"],
            "REASONING": ["DataQualityRule", "DataQualityScore", "Decision",
                          "Constraint", "Policy"],
            "APPLICATION": ["UsageStats", "View", "Query", "Report", "Dashboard"]
        }

        expected_layer = None
        for entity_type in labels:
            for layer_key, types in layer_type_mapping.items():
                if entity_type in types:
                    expected_layer = layer_key
                    break
            if expected_layer:
                break

        # Warn if layer doesn't match expected type
        warnings = []
        if expected_layer and layer != expected_layer:
            warnings.append(
                f"Entity type '{labels}' typically belongs to '{expected_layer}' layer, "
                f"but assigned to '{layer}' layer. This may be intentional but should be verified."
            )

        return {
            "is_valid": True,
            "warnings": warnings
        }

    async def _validate_layer_properties(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """
        Validate layer-specific property requirements.

        - REASONING layer entities must have confidence scores
        - All layers should have appropriate metadata
        """
        properties = event.data.get("properties", {})
        layer = properties.get("layer")
        warnings = []

        if not layer:
            return {"is_valid": True}  # Will be caught by layer_assignment validation

        # REASONING layer requirements
        if layer == "REASONING":
            confidence = properties.get("confidence")
            if confidence is None:
                warnings.append(
                    "Entities in REASONING layer should have a 'confidence' property"
                )
            elif not isinstance(confidence, (int, float)):
                warnings.append("Confidence property should be a numeric value")
            elif not (0.0 <= float(confidence) <= 1.0):
                warnings.append("Confidence score should be between 0.0 and 1.0")

            # Check for reasoning provenance
            if "reasoning" not in properties and "inferred_by" not in properties:
                warnings.append(
                    "Entities in REASONING layer should have provenance "
                    "(reasoning or inferred_by property)"
                )

        # SEMANTIC layer requirements
        elif layer == "SEMANTIC":
            if "description" not in properties and "definition" not in properties:
                warnings.append(
                    "Entities in SEMANTIC layer should have a description or definition"
                )

        # PERCEPTION layer requirements
        elif layer == "PERCEPTION":
            if "origin" not in properties and "source" not in properties:
                warnings.append(
                    "Entities in PERCEPTION layer should have an origin or source property"
                )

        # APPLICATION layer requirements
        elif layer == "APPLICATION":
            if "usage_count" not in properties and "last_accessed" not in properties:
                warnings.append(
                    "Entities in APPLICATION layer should track usage statistics"
                )

        return {
            "is_valid": True,
            "warnings": warnings
        }

    async def _validate_layer_relationship_hierarchy(
        self,
        source_layer: str,
        target_layer: str
    ) -> Dict[str, Any]:
        """
        Validate that relationships respect layer hierarchy.

        Relationships should generally flow from lower to higher layers:
        PERCEPTION -> SEMANTIC -> REASONING -> APPLICATION

        Reverse relationships (higher to lower) generate warnings.
        """
        from domain.knowledge_layers import KnowledgeLayer

        layer_order = {
            KnowledgeLayer.PERCEPTION.value: 1,
            KnowledgeLayer.SEMANTIC.value: 2,
            KnowledgeLayer.REASONING.value: 3,
            KnowledgeLayer.APPLICATION.value: 4
        }

        source_order = layer_order.get(source_layer, 0)
        target_order = layer_order.get(target_layer, 0)

        warnings = []

        # Check for reverse relationships (higher layer pointing to lower layer)
        if source_order > target_order and source_order > 0 and target_order > 0:
            # Allow certain reverse relationships
            allowed_reverse_types = [
                "derived_from",
                "based_on",
                "references",
                "uses",
                "reads_from"
            ]

            # This would need relationship type from event, which we don't have in this context
            # So we just issue a warning
            warnings.append(
                f"Relationship flows from higher layer ({source_layer}) to lower layer "
                f"({target_layer}). Verify this is intentional (e.g., derivation relationship)."
            )

        return {
            "is_valid": True,
            "warnings": warnings
        }

    async def _validate_relationship_layer_hierarchy(self, event: KnowledgeEvent) -> Dict[str, Any]:
        """
        Validate relationship layer hierarchy for create_relationship events.

        Fetches source and target entities to check their layers and validates
        the relationship follows proper layer hierarchy.

        Args:
            event: Knowledge event for creating relationship

        Returns:
            Validation result with warnings for hierarchy violations
        """
        source_id = event.data.get("source_id")
        target_id = event.data.get("target_id")

        if not source_id or not target_id:
            # Will be caught by required_fields validation
            return {"is_valid": True}

        try:
            # Query backend for source and target entity layers
            # Note: This requires async graph queries
            source_layer = await self._get_entity_layer(source_id)
            target_layer = await self._get_entity_layer(target_id)

            if source_layer and target_layer:
                # Use the existing hierarchy validation logic
                return await self._validate_layer_relationship_hierarchy(source_layer, target_layer)

        except Exception as e:
            # If we can't fetch layers, just warn
            return {
                "is_valid": True,
                "warnings": [f"Could not validate layer hierarchy: {str(e)}"]
            }

        return {"is_valid": True}

    async def _get_entity_layer(self, entity_id: str) -> Optional[str]:
        """
        Get the layer property of an entity from the graph.

        Args:
            entity_id: Entity identifier

        Returns:
            Layer value or None if not found
        """
        try:
            # Query the backend for entity properties
            # This is a simplified implementation - actual implementation depends on backend
            # For now, return None to avoid breaking existing code
            # TODO: Implement actual graph query when backend supports it
            return None
        except Exception:
            return None
