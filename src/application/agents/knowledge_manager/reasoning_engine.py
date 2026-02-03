"""Reasoning engine for applying symbolic logic to knowledge graph operations."""

from typing import Dict, Any, List, Optional
from domain.kg_backends import KnowledgeGraphBackend
from domain.event import KnowledgeEvent
from domain.confidence_models import (
    Confidence,
    ConfidenceSource,
    symbolic_confidence,
    neural_confidence
)
from graphiti_core import Graphiti
from .ontology_mapper import OntologyMapper
import logging

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Applies symbolic reasoning and logic to knowledge graph operations.

    Enhanced with:
    - Confidence tracking for all inferences
    - Provenance tracking (which rules contributed)
    - Support for tentative vs certain inferences
    - Neural-symbolic collaboration patterns
    """

    def __init__(
        self,
        backend: KnowledgeGraphBackend,
        llm: Optional[Graphiti] = None,
        enable_confidence_tracking: bool = True
    ):
        self.backend = backend
        self.llm = llm
        self.ontology_mapper = OntologyMapper()  # Initialize Mapper
        self._reasoning_rules = self._initialize_reasoning_rules()
        self.enable_confidence_tracking = enable_confidence_tracking

        # Initialize LLM reasoner if LLM is provided
        self.llm_reasoner = None
        if llm:
            from .llm_reasoner import LLMReasoner
            self.llm_reasoner = LLMReasoner(llm)

        # Track reasoning provenance
        self._reasoning_provenance: Dict[str, List[Dict[str, Any]]] = {}

    def _initialize_reasoning_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize reasoning rules for different operations."""
        return {
            "create_entity": [
                {
                    "name": "ontology_mapping",
                    "reasoner": self._apply_ontology_mapping,
                    "priority": "high"
                },
                {
                    "name": "property_inference",
                    "reasoner": self._infer_properties,
                    "priority": "high"
                },
                {
                    "name": "entity_classification",
                    "reasoner": self._classify_entity,
                    "priority": "medium"
                },
                {
                    "name": "relationship_suggestion",
                    "reasoner": self._suggest_relationships,
                    "priority": "low"
                },
                {
                    "name": "llm_semantic_inference",
                    "reasoner": self._llm_semantic_inference,
                    "priority": "low"
                },
                {
                    "name": "semantic_linking",
                    "reasoner": self._infer_semantic_links,
                    "priority": "low"
                }
            ],
            "create_relationship": [
                {
                    "name": "relationship_validation",
                    "reasoner": self._validate_relationship_logic,
                    "priority": "high"
                },
                {
                    "name": "inverse_relationship",
                    "reasoner": self._suggest_inverse_relationship,
                    "priority": "medium"
                },
                {
                    "name": "transitive_closure",
                    "reasoner": self._apply_transitive_closure,
                    "priority": "low"
                }
            ],
            "chat_query": [
                # CRITICAL SAFETY RULES (NEW - Phase 2E)
                {
                    "name": "contraindication_check",
                    "reasoner": self._check_contraindications,
                    "priority": "critical"  # Highest priority for patient safety
                },
                # Existing rules
                {
                    "name": "medical_context_validation",
                    "reasoner": self._validate_medical_context,
                    "priority": "high"
                },
                {
                    "name": "cross_graph_inference",
                    "reasoner": self._infer_cross_graph_relationships,
                    "priority": "high"
                },
                {
                    "name": "treatment_recommendation_check",
                    "reasoner": self._check_treatment_recommendations,
                    "priority": "medium"
                },
                # PATIENT-SPECIFIC ANALYSIS (NEW - Phase 2E)
                {
                    "name": "treatment_history_analysis",
                    "reasoner": self._analyze_treatment_history,
                    "priority": "high"
                },
                {
                    "name": "symptom_tracking",
                    "reasoner": self._track_symptoms_over_time,
                    "priority": "medium"
                },
                {
                    "name": "medication_adherence",
                    "reasoner": self._check_medication_adherence,
                    "priority": "low"
                },
                # General rules
                {
                    "name": "data_availability_assessment",
                    "reasoner": self._assess_data_availability,
                    "priority": "medium"
                },
                {
                    "name": "confidence_scoring",
                    "reasoner": self._score_answer_confidence,
                    "priority": "low"
                }
            ]
        }

    async def apply_reasoning(
        self,
        event: KnowledgeEvent,
        strategy: str = "collaborative"
    ) -> Dict[str, Any]:
        """
        Apply reasoning to a knowledge event.

        Args:
            event: Knowledge event to reason about
            strategy: Reasoning strategy - "neural_first", "symbolic_first", or "collaborative"

        Returns:
            Reasoning results with confidence tracking
        """
        reasoning_result = {
            "applied_rules": [],
            "inferences": [],
            "suggestions": [],
            "warnings": [],
            "reasoning_time": "0ms",
            "confidence_scores": {},  # NEW: Track confidence per inference
            "provenance": [],  # NEW: Track which rules contributed
            "strategy": strategy  # NEW: Record strategy used
        }

        import time
        start_time = time.time()

        # Apply reasoning based on strategy
        if strategy == "neural_first":
            reasoning_result = await self._neural_first_reasoning(event, reasoning_result)
        elif strategy == "symbolic_first":
            reasoning_result = await self._symbolic_first_reasoning(event, reasoning_result)
        else:  # collaborative
            reasoning_result = await self._collaborative_reasoning(event, reasoning_result)

        # Calculate reasoning time
        reasoning_time = (time.time() - start_time) * 1000
        reasoning_result["reasoning_time"] = f"{reasoning_time:.2f}ms"

        # Store provenance
        if self.enable_confidence_tracking:
            entity_id = event.data.get("id", "unknown")
            self._reasoning_provenance[entity_id] = reasoning_result.get("provenance", [])

        return reasoning_result

    async def _neural_first_reasoning(
        self,
        event: KnowledgeEvent,
        reasoning_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Neural-first strategy: LLM generates hypotheses → symbolic validation.

        Args:
            event: Knowledge event
            reasoning_result: Result dictionary to populate

        Returns:
            Updated reasoning result
        """
        # Step 1: Generate neural hypotheses
        if self.llm_reasoner:
            try:
                neural_result = await self._llm_semantic_inference(event)
                if neural_result and neural_result.get("inferences"):
                    # Mark as tentative
                    for inference in neural_result["inferences"]:
                        inference["certainty"] = "tentative"
                        inference["source"] = "neural_model"

                        # Create confidence object
                        if self.enable_confidence_tracking:
                            conf = neural_confidence(
                                inference.get("confidence", 0.7),
                                "llm_reasoner"
                            )
                            inference["confidence_obj"] = conf

                    reasoning_result["inferences"].extend(neural_result["inferences"])
                    reasoning_result["applied_rules"].append("llm_semantic_inference")

                    # Add provenance
                    reasoning_result["provenance"].append({
                        "rule": "llm_semantic_inference",
                        "type": "neural",
                        "contribution": len(neural_result["inferences"])
                    })
            except Exception as e:
                reasoning_result["warnings"].append(f"Neural reasoning failed: {str(e)}")

        # Step 2: Validate with symbolic rules
        rules = self._reasoning_rules.get(event.action, [])
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_rules = sorted(rules, key=lambda r: priority_order.get(r["priority"], 3))

        for rule in sorted_rules:
            if rule["name"] == "llm_semantic_inference":
                continue  # Already applied

            try:
                rule_result = await rule["reasoner"](event)

                if rule_result:
                    reasoning_result["applied_rules"].append(rule["name"])

                    # Validate neural inferences
                    if rule_result.get("inferences"):
                        for inference in rule_result["inferences"]:
                            inference["certainty"] = "certain"
                            inference["source"] = "symbolic_rule"

                            # Create confidence object
                            if self.enable_confidence_tracking:
                                conf = symbolic_confidence(
                                    1.0,
                                    rule["name"]
                                )
                                inference["confidence_obj"] = conf

                        reasoning_result["inferences"].extend(rule_result["inferences"])

                    if rule_result.get("suggestions"):
                        reasoning_result["suggestions"].extend(rule_result["suggestions"])

                    if rule_result.get("warnings"):
                        reasoning_result["warnings"].extend(rule_result["warnings"])

                    # Add provenance
                    reasoning_result["provenance"].append({
                        "rule": rule["name"],
                        "type": "symbolic",
                        "contribution": len(rule_result.get("inferences", []))
                    })

            except Exception as e:
                reasoning_result["warnings"].append(
                    f"Reasoning rule '{rule['name']}' failed: {str(e)}"
                )

        return reasoning_result

    async def _symbolic_first_reasoning(
        self,
        event: KnowledgeEvent,
        reasoning_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Symbolic-first strategy: Apply rules first → LLM fills gaps.

        Args:
            event: Knowledge event
            reasoning_result: Result dictionary to populate

        Returns:
            Updated reasoning result
        """
        # Step 1: Apply symbolic rules
        rules = self._reasoning_rules.get(event.action, [])
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_rules = sorted(rules, key=lambda r: priority_order.get(r["priority"], 3))

        for rule in sorted_rules:
            if rule["name"] == "llm_semantic_inference":
                continue  # Apply later

            try:
                rule_result = await rule["reasoner"](event)

                if rule_result:
                    reasoning_result["applied_rules"].append(rule["name"])

                    if rule_result.get("inferences"):
                        for inference in rule_result["inferences"]:
                            inference["certainty"] = "certain"
                            inference["source"] = "symbolic_rule"

                            if self.enable_confidence_tracking:
                                conf = symbolic_confidence(1.0, rule["name"])
                                inference["confidence_obj"] = conf

                        reasoning_result["inferences"].extend(rule_result["inferences"])

                    if rule_result.get("suggestions"):
                        reasoning_result["suggestions"].extend(rule_result["suggestions"])

                    if rule_result.get("warnings"):
                        reasoning_result["warnings"].extend(rule_result["warnings"])

                    # Add provenance
                    reasoning_result["provenance"].append({
                        "rule": rule["name"],
                        "type": "symbolic",
                        "contribution": len(rule_result.get("inferences", []))
                    })

            except Exception as e:
                reasoning_result["warnings"].append(
                    f"Reasoning rule '{rule['name']}' failed: {str(e)}"
                )

        # Step 2: LLM fills gaps (only if symbolic rules didn't produce enough)
        if len(reasoning_result["inferences"]) < 2 and self.llm_reasoner:
            try:
                neural_result = await self._llm_semantic_inference(event)
                if neural_result and neural_result.get("inferences"):
                    for inference in neural_result["inferences"]:
                        inference["certainty"] = "tentative"
                        inference["source"] = "neural_model"

                        if self.enable_confidence_tracking:
                            conf = neural_confidence(
                                inference.get("confidence", 0.7),
                                "llm_reasoner"
                            )
                            inference["confidence_obj"] = conf

                    reasoning_result["inferences"].extend(neural_result["inferences"])
                    reasoning_result["applied_rules"].append("llm_semantic_inference")

                    reasoning_result["provenance"].append({
                        "rule": "llm_semantic_inference",
                        "type": "neural",
                        "contribution": len(neural_result["inferences"])
                    })
            except Exception as e:
                reasoning_result["warnings"].append(f"Neural gap-filling failed: {str(e)}")

        return reasoning_result

    async def _collaborative_reasoning(
        self,
        event: KnowledgeEvent,
        reasoning_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Collaborative strategy: Run both in parallel → confidence weighting.

        Args:
            event: Knowledge event
            reasoning_result: Result dictionary to populate

        Returns:
            Updated reasoning result
        """
        # Get rules for this action
        rules = self._reasoning_rules.get(event.action, [])

        # Sort rules by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_rules = sorted(rules, key=lambda r: priority_order.get(r["priority"], 3))

        for rule in sorted_rules:
            try:
                rule_result = await rule["reasoner"](event)

                if rule_result:
                    reasoning_result["applied_rules"].append(rule["name"])

                    if rule_result.get("inferences"):
                        # Determine source type
                        is_neural = rule["name"] in ["llm_semantic_inference", "semantic_linking"]

                        for inference in rule_result["inferences"]:
                            # Set certainty based on source
                            inference["certainty"] = "tentative" if is_neural else "certain"
                            inference["source"] = "neural_model" if is_neural else "symbolic_rule"

                            # Create confidence object
                            if self.enable_confidence_tracking:
                                if is_neural:
                                    conf = neural_confidence(
                                        inference.get("confidence", 0.7),
                                        rule["name"]
                                    )
                                else:
                                    conf = symbolic_confidence(
                                        1.0,
                                        rule["name"]
                                    )
                                inference["confidence_obj"] = conf

                        reasoning_result["inferences"].extend(rule_result["inferences"])

                    if rule_result.get("suggestions"):
                        reasoning_result["suggestions"].extend(rule_result["suggestions"])

                    if rule_result.get("warnings"):
                        reasoning_result["warnings"].extend(rule_result["warnings"])

                    # Add provenance
                    reasoning_result["provenance"].append({
                        "rule": rule["name"],
                        "type": "neural" if is_neural else "symbolic",
                        "contribution": len(rule_result.get("inferences", []))
                    })

            except Exception as e:
                reasoning_result["warnings"].append(
                    f"Reasoning rule '{rule['name']}' failed: {str(e)}"
                )

        return reasoning_result

    def get_inference_provenance(self, entity_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get provenance information for an entity's inferences.

        Args:
            entity_id: Entity identifier

        Returns:
            List of provenance records or None
        """
        return self._reasoning_provenance.get(entity_id)

    async def _infer_properties(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Infer additional properties for an entity based on existing data."""
        entity_id = event.data.get("id", "")
        properties = event.data.get("properties", {})
        inferences = []
        
        # Infer entity type based on ID patterns
        if entity_id:
            if entity_id.lower().endswith(("_id", "id")):
                inferences.append({
                    "property": "entity_type",
                    "value": "identifier",
                    "confidence": 0.8,
                    "reason": "ID pattern suggests identifier entity"
                })
            
            if any(keyword in entity_id.lower() for keyword in ["user", "customer", "person"]):
                inferences.append({
                    "property": "entity_type",
                    "value": "person",
                    "confidence": 0.7,
                    "reason": "ID contains person-related keywords"
                })
            
            if any(keyword in entity_id.lower() for keyword in ["order", "transaction", "purchase"]):
                inferences.append({
                    "property": "entity_type",
                    "value": "transaction",
                    "confidence": 0.7,
                    "reason": "ID contains transaction-related keywords"
                })
        
        # Infer properties based on existing properties
        if "email" in properties:
            inferences.append({
                "property": "has_contact_info",
                "value": True,
                "confidence": 0.9,
                "reason": "Entity has email property"
            })
        
        if "created_date" in properties:
            inferences.append({
                "property": "is_temporal",
                "value": True,
                "confidence": 0.8,
                "reason": "Entity has temporal properties"
            })
        
        return {"inferences": inferences} if inferences else None

    async def _classify_entity(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Classify entity based on properties and patterns."""
        properties = event.data.get("properties", {})
        suggestions = []
        
        # Classify based on property patterns
        if "name" in properties and "email" in properties:
            suggestions.append({
                "classification": "person",
                "confidence": 0.8,
                "reason": "Has name and email properties"
            })
        
        if "amount" in properties or "price" in properties:
            suggestions.append({
                "classification": "financial",
                "confidence": 0.7,
                "reason": "Has financial properties"
            })
        
        if "status" in properties and "created_date" in properties:
            suggestions.append({
                "classification": "process",
                "confidence": 0.6,
                "reason": "Has status and temporal properties"
            })
        
        return {"suggestions": suggestions} if suggestions else None

    async def _suggest_relationships(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Suggest potential relationships for the entity."""
        entity_id = event.data.get("id", "")
        properties = event.data.get("properties", {})
        suggestions = []
        
        # Suggest relationships based on entity type
        if "email" in properties:
            suggestions.append({
                "relationship_type": "HAS_EMAIL",
                "target_pattern": "email_*",
                "confidence": 0.7,
                "reason": "Entity has email property"
            })
        
        if "created_date" in properties:
            suggestions.append({
                "relationship_type": "CREATED_ON",
                "target_pattern": "date_*",
                "confidence": 0.6,
                "reason": "Entity has creation date"
            })
        
        return {"suggestions": suggestions} if suggestions else None

    async def _validate_relationship_logic(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Validate the logical consistency of a relationship."""
        source = event.data.get("source", "")
        target = event.data.get("target", "")
        rel_type = event.data.get("type", "")
        warnings = []
        
        # Check for logical inconsistencies
        if source == target and rel_type.lower() in ["is_a", "instance_of", "subclass_of"]:
            warnings.append({
                "type": "logical_inconsistency",
                "message": "Entity cannot be a subclass or instance of itself",
                "severity": "high"
            })
        
        # Check for relationship type patterns
        if rel_type.lower() in ["is_a", "instance_of"] and not rel_type[0].isupper():
            warnings.append({
                "type": "naming_convention",
                "message": "Taxonomic relationships should use PascalCase",
                "severity": "low"
            })
        
        return {"warnings": warnings} if warnings else None

    async def _suggest_inverse_relationship(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Suggest inverse relationships."""
        rel_type = event.data.get("type", "")
        suggestions = []
        
        # Common inverse relationship patterns
        inverse_patterns = {
            "is_a": "has_instance",
            "has_part": "part_of",
            "owns": "owned_by",
            "manages": "managed_by",
            "reports_to": "has_subordinate"
        }
        
        if rel_type in inverse_patterns:
            suggestions.append({
                "inverse_type": inverse_patterns[rel_type],
                "confidence": 0.8,
                "reason": f"Standard inverse of '{rel_type}' relationship"
            })
        
        return {"suggestions": suggestions} if suggestions else None

    async def _apply_transitive_closure(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Apply transitive closure for hierarchical relationships."""
        rel_type = event.data.get("type", "")
        source = event.data.get("source", "")
        target = event.data.get("target", "")
        suggestions = []
        
        # Transitive relationships
        transitive_types = ["is_a", "subclass_of", "part_of", "contains"]
        
        if rel_type in transitive_types:
            # 1. Forward Transitivity: If A -> B and B -> C, then A -> C
            # Find relationships where source is the current target (B -> C)
            outgoing_rels = await self.backend.list_relationships(source_id=target, relationship_type=rel_type)
            for rel in outgoing_rels:
                suggestions.append({
                    "relationship_type": rel_type,
                    "source": source,
                    "target": rel["target"],
                    "confidence": 0.9,
                    "reason": f"Transitive closure: {source} -> {target} -> {rel['target']}"
                })
                
            # 2. Backward Transitivity: If X -> A and A -> B, then X -> B
            # Find relationships where target is the current source (X -> A)
            incoming_rels = await self.backend.list_relationships(target_id=source, relationship_type=rel_type)
            for rel in incoming_rels:
                suggestions.append({
                    "relationship_type": rel_type,
                    "source": rel["source"],
                    "target": target,
                    "confidence": 0.9,
                    "reason": f"Transitive closure: {rel['source']} -> {source} -> {target}"
                })
        
        return {"suggestions": suggestions} if suggestions else None

    async def apply_advanced_reasoning(self, events: List[KnowledgeEvent]) -> Dict[str, Any]:
        """Apply advanced reasoning across multiple events."""
        advanced_result = {
            "cross_event_inferences": [],
            "consistency_checks": [],
            "optimization_suggestions": []
        }
        
        # Cross-event consistency checks
        entity_ids = set()
        relationship_types = set()
        
        for event in events:
            if event.action == "create_entity":
                entity_id = event.data.get("id")
                if entity_id:
                    entity_ids.add(entity_id)
            
            elif event.action == "create_relationship":
                rel_type = event.data.get("type")
                if rel_type:
                    relationship_types.add(rel_type)
        
        # Check for orphaned relationships
        for event in events:
            if event.action == "create_relationship":
                source = event.data.get("source")
                target = event.data.get("target")
                
                if source and source not in entity_ids:
                    advanced_result["consistency_checks"].append({
                        "type": "orphaned_relationship",
                        "message": f"Relationship source '{source}' has no corresponding entity",
                        "severity": "high"
                    })
                
                if target and target not in entity_ids:
                    advanced_result["consistency_checks"].append({
                        "type": "orphaned_relationship",
                        "message": f"Relationship target '{target}' has no corresponding entity",
                        "severity": "high"
                    })
        
        # Suggest relationship optimizations
        if len(relationship_types) > 10:
            advanced_result["optimization_suggestions"].append({
                "type": "relationship_consolidation",
                "message": "Consider consolidating similar relationship types",
                "severity": "medium"
            })
        
        return advanced_result

    def add_custom_reasoning_rule(self, action: str, rule: Dict[str, Any]) -> None:
        """Add a custom reasoning rule."""
        if action not in self._reasoning_rules:
            self._reasoning_rules[action] = []
        
        self._reasoning_rules[action].append(rule)

    def remove_reasoning_rule(self, action: str, rule_name: str) -> bool:
        """Remove a reasoning rule by name."""
        if action in self._reasoning_rules:
            for i, rule in enumerate(self._reasoning_rules[action]):
                if rule.get("name") == rule_name:
                    del self._reasoning_rules[action][i]
                    return True
        return False

    async def _llm_semantic_inference(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Use LLM to infer semantic relationships."""
        if not self.llm_reasoner:
            return None
            
        suggestions = await self.llm_reasoner.suggest_semantic_relationships(event)
        
        if suggestions:
            return {"suggestions": suggestions}
        return None

    async def _infer_semantic_links(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Infer semantic links to business concepts."""
        if not self.llm_reasoner:
            return None
            
        # Only apply to Tables for now
        # Check if it's a table based on ID or properties
        entity_id = event.data.get("id", "")
        if "table:" not in entity_id and "Table" not in event.data.get("labels", []):
             return None

        suggestions = await self.llm_reasoner.suggest_business_concepts(event)
        if suggestions:
            return {"suggestions": suggestions}
        return None

    async def _apply_ontology_mapping(self, event: KnowledgeEvent) -> Optional[Dict[str, Any]]:
        """Apply Hybrid Ontology mapping to the entity."""
        # Get current labels and properties
        labels = event.data.get("labels", [])
        properties = event.data.get("properties", {})

        # Use the first label as the primary type if available, otherwise guess
        primary_type = labels[0] if labels else "Entity"

        # Call mapper
        new_labels, new_props = self.ontology_mapper.map_entity(primary_type, properties)

        # Merge labels (avoid duplicates)
        final_labels = list(set(labels + new_labels))

        # Return as inference/modification
        # Note: ReasoningEngine usually returns suggestions/inferences.
        # Ideally, this should modify the event or return a "modification" action.
        # For now, we'll return it as an inference that the KnowledgeManager can act on.
        return {
            "inferences": [
                {
                    "type": "ontology_enrichment",
                    "labels": final_labels,
                    "properties": new_props,
                    "reason": "Applied Hybrid DIKW Ontology mapping"
                }
            ]
        }

    # ========================================
    # Chat Query Reasoning Rules (Phase 1)
    # ========================================

    async def _validate_medical_context(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """
        Validate medical entities in chat context.

        Checks confidence of medical entities extracted from the question
        and flags low-confidence entities that may need verification.

        Args:
            event: KnowledgeEvent with medical_entities in data

        Returns:
            Validation results with high/low confidence entities
        """
        entities = event.data.get("medical_entities", [])

        if not entities:
            return None

        inferences = []
        warnings = []
        high_confidence_entities = []
        low_confidence_entities = []

        for entity in entities:
            entity_name = entity.get("name", "")
            entity_type = entity.get("type", "unknown")
            confidence = entity.get("confidence", 0.0)

            if confidence >= 0.8:
                high_confidence_entities.append(entity)
                inferences.append({
                    "type": "validated_medical_entity",
                    "entity": entity_name,
                    "entity_type": entity_type,
                    "confidence": 0.9,
                    "source": entity.get("source_document", "knowledge_graph"),
                    "reason": f"High-confidence medical entity: {entity_name} ({entity_type})"
                })
            elif confidence < 0.6:
                low_confidence_entities.append(entity)
                warnings.append(
                    f"Low confidence entity: {entity_name} ({confidence:.2f}) - may need verification"
                )

        result = {
            "inferences": inferences,
            "warnings": warnings
        }

        return result if inferences or warnings else None

    async def _infer_cross_graph_relationships(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """
        Infer implicit relationships between medical and data entities.

        Analyzes medical entities and data catalog entities to find potential
        semantic connections (e.g., disease name in table/column names).

        Args:
            event: KnowledgeEvent with medical and data entities

        Returns:
            Inferred cross-graph relationships
        """
        medical_entities = event.data.get("medical_entities", [])
        data_tables = event.data.get("data_tables", [])
        data_columns = event.data.get("data_columns", [])

        if not medical_entities:
            return None

        inferences = []
        potential_connections = []

        for med_entity in medical_entities:
            med_name = med_entity.get("name", "").lower()

            if not med_name:
                continue

            # Check if medical entity name appears in data entity names
            for table in data_tables:
                table_name = table.get("name", "").lower()

                # Check for name containment (both directions)
                if med_name in table_name or table_name in med_name:
                    potential_connections.append({
                        "medical": med_entity.get("name"),
                        "data": table.get("name"),
                        "type": "table",
                        "confidence": 0.75
                    })

            for column in data_columns:
                col_name = column.get("name", "").lower()

                if med_name in col_name or col_name in med_name:
                    potential_connections.append({
                        "medical": med_entity.get("name"),
                        "data": column.get("name"),
                        "type": "column",
                        "confidence": 0.70
                    })

        if potential_connections:
            for conn in potential_connections:
                inferences.append({
                    "type": "inferred_cross_graph_link",
                    "medical_entity": conn["medical"],
                    "data_entity": conn["data"],
                    "data_type": conn["type"],
                    "confidence": conn["confidence"],
                    "reason": f"Medical entity '{conn['medical']}' matches data {conn['type']} '{conn['data']}'"
                })

        return {"inferences": inferences} if inferences else None

    async def _check_treatment_recommendations(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """
        Check if question involves treatment recommendations (sensitive).

        Detects when users ask for medical advice or treatment recommendations
        and flags these queries for disclaimer requirements.

        Args:
            event: KnowledgeEvent with question text

        Returns:
            Warning if treatment recommendation detected
        """
        question = event.data.get("question", "").lower()

        if not question:
            return None

        # Treatment recommendation keywords
        treatment_keywords = [
            "should i take",
            "should i use",
            "recommend",
            "prescribe",
            "best treatment",
            "what medication",
            "which drug",
            "how to treat",
            "cure for"
        ]

        if any(keyword in question for keyword in treatment_keywords):
            return {
                "warnings": [
                    "Question involves treatment recommendations - provide educational info only"
                ],
                "inferences": [
                    {
                        "type": "treatment_recommendation_detected",
                        "disclaimer_required": True,
                        "confidence": 0.95,
                        "reason": "Detected treatment recommendation query - medical disclaimer required"
                    }
                ]
            }

        return None

    async def _assess_data_availability(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """
        Assess data availability for answering the question.

        Calculates a score based on available context (medical entities,
        relationships, data tables) to determine answer quality potential.

        Args:
            event: KnowledgeEvent with context information

        Returns:
            Data availability assessment with score
        """
        medical_entities = event.data.get("medical_entities", [])
        relationships = event.data.get("medical_relationships", [])
        data_tables = event.data.get("data_tables", [])
        data_columns = event.data.get("data_columns", [])

        # Base availability score
        availability_score = 0.5

        # Boost for medical entities (up to +0.3)
        if medical_entities:
            entity_boost = 0.1 * min(len(medical_entities), 3)
            availability_score += entity_boost

        # Boost for relationships (up to +0.2)
        if relationships:
            rel_boost = 0.1 * min(len(relationships), 2)
            availability_score += rel_boost

        # Boost for data catalog context (up to +0.2)
        if data_tables:
            table_boost = 0.1 * min(len(data_tables), 2)
            availability_score += table_boost

        if data_columns:
            col_boost = 0.05
            availability_score += col_boost

        # Cap at 1.0
        availability_score = min(1.0, availability_score)

        # Determine quality level
        if availability_score >= 0.8:
            quality_assessment = "Strong data availability - high-confidence answer possible"
        elif availability_score >= 0.6:
            quality_assessment = "Moderate data availability - answer with caveats"
        else:
            quality_assessment = "Limited data availability - answer may be incomplete"

        return {
            "inferences": [
                {
                    "type": "data_availability_assessment",
                    "score": availability_score,
                    "confidence": 0.85,
                    "quality_level": "high" if availability_score >= 0.8 else "medium" if availability_score >= 0.6 else "low",
                    "reason": quality_assessment,
                    "context_summary": {
                        "medical_entities": len(medical_entities),
                        "relationships": len(relationships),
                        "data_tables": len(data_tables),
                        "data_columns": len(data_columns)
                    }
                }
            ]
        }

    async def _score_answer_confidence(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate overall confidence score for the answer.

        Combines multiple signals (validated entities, cross-graph links,
        data availability) to produce final confidence score.

        Args:
            event: KnowledgeEvent with all reasoning results

        Returns:
            Confidence score calculation
        """
        # Start with base confidence
        base_confidence = 0.5

        # Get entities for confidence boost
        medical_entities = event.data.get("medical_entities", [])
        validated_count = sum(1 for e in medical_entities if e.get("confidence", 0) >= 0.8)

        # Boost for validated entities (up to +0.3)
        if validated_count > 0:
            entity_boost = 0.1 * min(validated_count, 3)
            base_confidence += entity_boost

        # Boost for relationships (up to +0.1)
        relationships = event.data.get("medical_relationships", [])
        if relationships:
            rel_boost = 0.05 * min(len(relationships), 2)
            base_confidence += rel_boost

        # Boost for cross-graph context (up to +0.1)
        data_tables = event.data.get("data_tables", [])
        data_columns = event.data.get("data_columns", [])
        if data_tables or data_columns:
            cross_boost = 0.1
            base_confidence += cross_boost

        # Penalize for warnings
        warnings = event.data.get("warnings", [])
        if warnings:
            base_confidence *= 0.95

        # Cap at 1.0
        final_confidence = min(1.0, base_confidence)

        return {
            "inferences": [
                {
                    "type": "confidence_score",
                    "score": final_confidence,
                    "confidence": 1.0,  # We're confident about our confidence calculation
                    "reason": f"Calculated confidence: {final_confidence:.2f} based on context quality",
                    "factors": {
                        "validated_entities": validated_count,
                        "relationships": len(relationships),
                        "cross_graph_context": bool(data_tables or data_columns),
                        "warnings": len(warnings)
                    }
                }
            ]
        }

    # ========================================
    # Cross-Layer Reasoning Rules (Phase 3)
    # ========================================

    async def apply_cross_layer_reasoning(
        self,
        entity_data: Dict[str, Any],
        current_layer: str
    ) -> Dict[str, Any]:
        """
        Apply cross-layer reasoning rules based on current entity layer.

        Enables reasoning across layer boundaries following DIKW hierarchy:
        - PERCEPTION → SEMANTIC: Infer business concepts from data attributes
        - SEMANTIC → REASONING: Derive quality rules from concept constraints
        - REASONING → APPLICATION: Suggest query patterns from usage stats
        - APPLICATION → PERCEPTION: Request new data based on query patterns

        Args:
            entity_data: Entity data including properties and relationships
            current_layer: Current knowledge layer (PERCEPTION/SEMANTIC/REASONING/APPLICATION)

        Returns:
            Dictionary with cross-layer inferences and suggestions
        """
        result = {
            "inferences": [],
            "suggestions": [],
            "cross_layer_rules_applied": []
        }

        # Apply layer-specific cross-layer rules
        if current_layer == "PERCEPTION":
            perception_result = await self._perception_to_semantic_reasoning(entity_data)
            if perception_result:
                result["inferences"].extend(perception_result.get("inferences", []))
                result["suggestions"].extend(perception_result.get("suggestions", []))
                result["cross_layer_rules_applied"].append("perception_to_semantic")

        elif current_layer == "SEMANTIC":
            semantic_result = await self._semantic_to_reasoning_reasoning(entity_data)
            if semantic_result:
                result["inferences"].extend(semantic_result.get("inferences", []))
                result["suggestions"].extend(semantic_result.get("suggestions", []))
                result["cross_layer_rules_applied"].append("semantic_to_reasoning")

        elif current_layer == "REASONING":
            reasoning_result = await self._reasoning_to_application_reasoning(entity_data)
            if reasoning_result:
                result["inferences"].extend(reasoning_result.get("inferences", []))
                result["suggestions"].extend(reasoning_result.get("suggestions", []))
                result["cross_layer_rules_applied"].append("reasoning_to_application")

        elif current_layer == "APPLICATION":
            application_result = await self._application_to_perception_reasoning(entity_data)
            if application_result:
                result["inferences"].extend(application_result.get("inferences", []))
                result["suggestions"].extend(application_result.get("suggestions", []))
                result["cross_layer_rules_applied"].append("application_to_perception")

        return result

    async def _perception_to_semantic_reasoning(
        self,
        entity_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        PERCEPTION → SEMANTIC: Infer business concepts from table/column attributes.

        Analyzes data structure (tables, columns, constraints) to infer semantic
        business concepts and their relationships.

        Args:
            entity_data: Entity data from PERCEPTION layer

        Returns:
            Semantic-layer inferences
        """
        inferences = []
        suggestions = []

        entity_type = entity_data.get("type", "")
        properties = entity_data.get("properties", {})

        # Infer business concepts from table structure
        if entity_type == "Table" or "table:" in entity_data.get("id", ""):
            table_name = properties.get("name", "")
            columns = properties.get("columns", [])

            # Common business concept patterns
            concept_patterns = {
                "customer": ["customer_id", "customer_name", "email", "phone"],
                "order": ["order_id", "order_date", "order_total", "order_status"],
                "product": ["product_id", "product_name", "price", "sku"],
                "employee": ["employee_id", "first_name", "last_name", "hire_date"],
                "transaction": ["transaction_id", "transaction_date", "amount"],
                "address": ["address_id", "street", "city", "state", "zip_code"],
                "payment": ["payment_id", "payment_method", "payment_date", "amount"]
            }

            # Match column patterns to business concepts
            if isinstance(columns, list):
                column_names_lower = [str(col).lower() for col in columns]

                for concept, pattern_cols in concept_patterns.items():
                    # Calculate match score
                    matches = sum(1 for col in pattern_cols if any(col in name for name in column_names_lower))
                    match_score = matches / len(pattern_cols)

                    if match_score >= 0.4:  # At least 40% match
                        inferences.append({
                            "type": "business_concept_inference",
                            "concept": concept.capitalize(),
                            "confidence": min(0.6 + (match_score * 0.4), 1.0),
                            "reason": f"Table '{table_name}' matches {int(match_score*100)}% of {concept} pattern",
                            "matched_columns": [col for col in pattern_cols if any(col in name for name in column_names_lower)],
                            "target_layer": "SEMANTIC"
                        })

            # Suggest semantic enrichment
            if inferences:
                suggestions.append({
                    "action": "promote_to_semantic",
                    "reason": "Table structure suggests business concepts",
                    "confidence": 0.8
                })

        # Infer domain from column names
        if entity_type == "Column":
            column_name = properties.get("name", "").lower()
            data_type = properties.get("data_type", "")

            domain_keywords = {
                "financial": ["amount", "price", "cost", "balance", "payment", "revenue"],
                "temporal": ["date", "time", "timestamp", "created_at", "updated_at"],
                "identity": ["id", "key", "uuid", "identifier"],
                "contact": ["email", "phone", "address", "contact"],
                "analytics": ["count", "sum", "avg", "total", "score", "metric"]
            }

            for domain, keywords in domain_keywords.items():
                if any(kw in column_name for kw in keywords):
                    inferences.append({
                        "type": "domain_classification",
                        "domain": domain,
                        "confidence": 0.75,
                        "reason": f"Column name '{column_name}' suggests {domain} domain",
                        "target_layer": "SEMANTIC"
                    })
                    break

        return {"inferences": inferences, "suggestions": suggestions} if inferences or suggestions else None

    async def _semantic_to_reasoning_reasoning(
        self,
        entity_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        SEMANTIC → REASONING: Derive quality rules from business concept constraints.

        Analyzes business concepts and their relationships to infer data quality
        rules, validation constraints, and reasoning logic.

        Args:
            entity_data: Entity data from SEMANTIC layer

        Returns:
            Reasoning-layer inferences
        """
        inferences = []
        suggestions = []

        properties = entity_data.get("properties", {})
        concept_type = properties.get("concept_type", "")

        # Infer quality rules from business concepts
        quality_rules = {
            "Customer": [
                {"rule": "email_required", "reason": "Customers must have valid contact info"},
                {"rule": "unique_email", "reason": "Email must be unique per customer"},
                {"rule": "phone_format", "reason": "Phone numbers should match standard format"}
            ],
            "Order": [
                {"rule": "order_date_not_future", "reason": "Order date cannot be in the future"},
                {"rule": "total_positive", "reason": "Order total must be positive"},
                {"rule": "status_valid", "reason": "Order status must be from valid set"}
            ],
            "Product": [
                {"rule": "price_positive", "reason": "Product price must be positive"},
                {"rule": "sku_unique", "reason": "SKU must be unique across products"},
                {"rule": "category_required", "reason": "Product must belong to a category"}
            ],
            "Transaction": [
                {"rule": "amount_non_zero", "reason": "Transaction amount cannot be zero"},
                {"rule": "timestamp_required", "reason": "All transactions must be timestamped"},
                {"rule": "balance_consistency", "reason": "Transaction should maintain balance consistency"}
            ]
        }

        # Generate quality rules for concept
        if concept_type in quality_rules:
            for rule in quality_rules[concept_type]:
                inferences.append({
                    "type": "quality_rule",
                    "rule_name": rule["rule"],
                    "reason": rule["reason"],
                    "concept": concept_type,
                    "confidence": 0.85,
                    "target_layer": "REASONING"
                })

        # Infer validation constraints from relationships
        relationships = entity_data.get("relationships", [])
        if relationships:
            for rel in relationships:
                rel_type = rel.get("type", "")

                if rel_type == "HAS_FK":
                    inferences.append({
                        "type": "referential_integrity_rule",
                        "rule_name": "foreign_key_constraint",
                        "reason": "Foreign key relationship requires referential integrity",
                        "confidence": 0.95,
                        "target_layer": "REASONING"
                    })

                elif rel_type == "IS_PART_OF":
                    inferences.append({
                        "type": "composition_rule",
                        "rule_name": "parent_child_consistency",
                        "reason": "Part-of relationship requires parent existence",
                        "confidence": 0.9,
                        "target_layer": "REASONING"
                    })

        # Suggest reasoning layer promotion
        if inferences:
            suggestions.append({
                "action": "promote_to_reasoning",
                "reason": "Business concept has derived quality rules",
                "confidence": 0.8
            })

        return {"inferences": inferences, "suggestions": suggestions} if inferences or suggestions else None

    async def _reasoning_to_application_reasoning(
        self,
        entity_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        REASONING → APPLICATION: Suggest query patterns from usage statistics.

        Analyzes reasoning rules and validation patterns to suggest practical
        application-layer queries, views, and access patterns.

        Args:
            entity_data: Entity data from REASONING layer

        Returns:
            Application-layer inferences
        """
        inferences = []
        suggestions = []

        properties = entity_data.get("properties", {})
        reasoning_type = properties.get("reasoning_type", "")

        # Suggest queries based on reasoning rules
        if reasoning_type == "quality_rule":
            rule_name = properties.get("rule_name", "")

            if "unique" in rule_name:
                inferences.append({
                    "type": "query_pattern",
                    "pattern": "duplicate_detection_query",
                    "reason": "Uniqueness rule suggests duplicate detection queries",
                    "confidence": 0.8,
                    "target_layer": "APPLICATION"
                })

            elif "date" in rule_name or "timestamp" in rule_name:
                inferences.append({
                    "type": "query_pattern",
                    "pattern": "temporal_analysis_query",
                    "reason": "Temporal rules suggest time-series analysis",
                    "confidence": 0.75,
                    "target_layer": "APPLICATION"
                })

            elif "total" in rule_name or "amount" in rule_name or "balance" in rule_name:
                inferences.append({
                    "type": "query_pattern",
                    "pattern": "aggregation_query",
                    "reason": "Numeric rules suggest aggregation patterns",
                    "confidence": 0.8,
                    "target_layer": "APPLICATION"
                })

        # Suggest materialized views for frequently validated rules
        confidence = properties.get("confidence", 0.0)
        if confidence > 0.9:
            suggestions.append({
                "action": "create_materialized_view",
                "reason": "High-confidence rule benefits from materialized view",
                "confidence": 0.7
            })

        # Suggest indexes for performance
        if "foreign_key" in str(properties.get("rule_name", "")).lower():
            inferences.append({
                "type": "optimization_suggestion",
                "suggestion": "create_index_on_foreign_key",
                "reason": "Foreign key constraint benefits from index",
                "confidence": 0.9,
                "target_layer": "APPLICATION"
            })

        return {"inferences": inferences, "suggestions": suggestions} if inferences or suggestions else None

    async def _application_to_perception_reasoning(
        self,
        entity_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        APPLICATION → PERCEPTION: Request new data based on query patterns.

        Analyzes application usage patterns to identify missing data sources
        or suggest new data collection strategies.

        Args:
            entity_data: Entity data from APPLICATION layer

        Returns:
            Perception-layer suggestions
        """
        inferences = []
        suggestions = []

        properties = entity_data.get("properties", {})
        usage_pattern = properties.get("usage_pattern", "")
        access_count = properties.get("access_count", 0)

        # Suggest new data sources based on query patterns
        if usage_pattern == "temporal_analysis":
            suggestions.append({
                "action": "collect_temporal_data",
                "reason": "Frequent temporal queries suggest need for timestamp columns",
                "recommended_columns": ["created_at", "updated_at", "deleted_at"],
                "confidence": 0.75,
                "target_layer": "PERCEPTION"
            })

        elif usage_pattern == "aggregation":
            suggestions.append({
                "action": "collect_aggregate_metadata",
                "reason": "Aggregation queries benefit from pre-computed summaries",
                "recommended_tables": ["summary_stats", "daily_aggregates"],
                "confidence": 0.7,
                "target_layer": "PERCEPTION"
            })

        # High-frequency queries suggest missing indexes or tables
        if access_count > 100:
            inferences.append({
                "type": "data_gap_detection",
                "gap": "missing_optimized_structure",
                "reason": f"Query accessed {access_count} times suggests need for optimized data structure",
                "confidence": 0.8,
                "target_layer": "PERCEPTION"
            })

        # Suggest new data collection based on failed queries
        query_errors = properties.get("query_errors", 0)
        if query_errors > 10:
            suggestions.append({
                "action": "review_data_sources",
                "reason": f"{query_errors} query errors suggest missing or incomplete data",
                "confidence": 0.85,
                "target_layer": "PERCEPTION"
            })

        return {"inferences": inferences, "suggestions": suggestions} if inferences or suggestions else None

    # ========================================
    # PATIENT SAFETY REASONING RULES (Phase 2E)
    # ========================================

    async def _check_contraindications(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """
        Check for drug allergies and medication interactions (CRITICAL SAFETY).

        This is the highest priority reasoning rule for patient safety.
        """
        patient_context = event.data.get("patient_context")

        if not patient_context:
            return None

        # Extract medications mentioned in question
        question = event.data.get("question", "").lower()
        medical_entities = event.data.get("medical_entities", [])

        warnings = []
        inferences = []

        # Check 1: Allergy contraindications
        allergies = patient_context.allergies
        for entity in medical_entities:
            entity_name = entity.get("name", "").lower()

            for allergy in allergies:
                if allergy.lower() in entity_name or entity_name in allergy.lower():
                    warnings.append(
                        f"⚠️ CRITICAL: Patient is allergic to {allergy}. "
                        f"Mentioned drug {entity['name']} may be contraindicated."
                    )
                    inferences.append({
                        "type": "contraindication_detected",
                        "severity": "critical",
                        "substance": entity["name"],
                        "allergy": allergy,
                        "confidence": 0.95,
                        "reason": "Patient has documented allergy to similar substance"
                    })

        # Check 2: Current medication interactions (simplified - would use drug database in production)
        current_meds = [med["name"].lower() for med in patient_context.medications]

        # Known interaction pairs (simplified for demo - production would use drug interaction API)
        known_interactions = {
            ("warfarin", "aspirin"): "Increased bleeding risk",
            ("methotrexate", "nsaid"): "Increased toxicity risk",
            ("warfarin", "ibuprofen"): "Increased bleeding risk",
            ("methotrexate", "ibuprofen"): "Increased methotrexate toxicity",
            ("prednisone", "nsaid"): "Increased risk of GI bleeding",
        }

        for entity in medical_entities:
            entity_name = entity.get("name", "").lower()

            for current_med in current_meds:
                # Check both orderings
                interaction_key = tuple(sorted([entity_name, current_med]))

                if interaction_key in known_interactions:
                    warnings.append(
                        f"⚠️ WARNING: Potential interaction between {entity['name']} "
                        f"and current medication {current_med}: "
                        f"{known_interactions[interaction_key]}"
                    )
                    inferences.append({
                        "type": "drug_interaction_detected",
                        "severity": "high",
                        "drug1": entity["name"],
                        "drug2": current_med,
                        "interaction": known_interactions[interaction_key],
                        "confidence": 0.85,
                        "reason": "Known drug-drug interaction"
                    })

        if not warnings and not inferences:
            # No contraindications found - positive signal
            inferences.append({
                "type": "no_contraindications",
                "confidence": 0.90,
                "reason": "No contraindications detected based on patient allergies and current medications"
            })

        return {
            "warnings": warnings,
            "inferences": inferences
        }

    async def _analyze_treatment_history(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """Analyze patient's treatment history for patterns."""
        patient_context = event.data.get("patient_context")

        if not patient_context or not patient_context.medications:
            return None

        inferences = []

        # Analyze medication patterns
        active_meds = [med for med in patient_context.medications if med.get("status") == "active"]

        if active_meds:
            med_classes = []
            for med in active_meds:
                # Classify medication (simplified - would use drug database in production)
                name_lower = med["name"].lower()
                if any(bio in name_lower for bio in ["humira", "remicade", "adalimumab", "infliximab", "enbrel"]):
                    med_classes.append("biologic")
                elif any(immuno in name_lower for immuno in ["azathioprine", "methotrexate", "6-mp"]):
                    med_classes.append("immunosuppressant")
                elif any(steroid in name_lower for steroid in ["prednisone", "budesonide", "cortisone"]):
                    med_classes.append("corticosteroid")
                # Add more classifications

            if "biologic" in med_classes:
                inferences.append({
                    "type": "treatment_pattern",
                    "pattern": "on_biologic_therapy",
                    "confidence": 0.90,
                    "reason": f"Patient is currently on biologic therapy: {[m['name'] for m in active_meds]}",
                    "implications": "Patient has moderate to severe condition requiring advanced therapy"
                })

            if "corticosteroid" in med_classes and len(active_meds) > 2:
                inferences.append({
                    "type": "treatment_complexity",
                    "pattern": "multi_drug_regimen",
                    "confidence": 0.85,
                    "reason": f"Patient on {len(active_meds)} medications including steroids",
                    "implications": "Complex treatment requiring careful monitoring"
                })

        # Check for long-term conditions
        diagnoses = patient_context.diagnoses
        if diagnoses:
            chronic_conditions = []
            for dx in diagnoses:
                # Check if chronic condition (simplified)
                condition_lower = dx["condition"].lower()
                if any(chronic in condition_lower for chronic in ["crohn", "colitis", "lupus", "arthritis", "diabetes", "hypertension"]):
                    chronic_conditions.append(dx["condition"])

            if chronic_conditions:
                inferences.append({
                    "type": "chronic_condition_management",
                    "conditions": chronic_conditions,
                    "confidence": 0.95,
                    "reason": f"Patient managing chronic conditions: {', '.join(chronic_conditions)}",
                    "implications": "Requires ongoing monitoring and long-term treatment strategy"
                })

        return {"inferences": inferences} if inferences else None

    async def _track_symptoms_over_time(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """Track symptom mentions across conversations."""
        patient_context = event.data.get("patient_context")

        if not patient_context:
            return None

        # Analyze recent symptoms from Mem0 memory
        recent_symptoms = patient_context.recent_symptoms

        if not recent_symptoms:
            return None

        inferences = []

        # Group symptoms by frequency
        symptom_counts = {}
        for symptom_data in recent_symptoms:
            symptom_text = symptom_data["text"].lower()

            # Extract symptom keywords (simplified - would use NER in production)
            symptom_keywords = [
                "pain", "headache", "nausea", "fatigue", "fever", "bleeding",
                "diarrhea", "cramping", "bloating", "vomiting", "dizzy"
            ]

            for keyword in symptom_keywords:
                if keyword in symptom_text:
                    symptom_counts[keyword] = symptom_counts.get(keyword, 0) + 1

        # Identify recurring symptoms
        for symptom, count in symptom_counts.items():
            if count >= 2:  # Mentioned 2+ times
                inferences.append({
                    "type": "recurring_symptom",
                    "symptom": symptom,
                    "frequency": count,
                    "confidence": 0.85,
                    "reason": f"Patient mentioned '{symptom}' {count} times in recent conversations",
                    "recommendation": f"Consider monitoring {symptom} closely or discussing with healthcare provider"
                })

        # Check for symptom escalation
        if symptom_counts:
            total_symptom_mentions = sum(symptom_counts.values())
            if total_symptom_mentions >= 5:
                inferences.append({
                    "type": "symptom_escalation",
                    "total_mentions": total_symptom_mentions,
                    "confidence": 0.80,
                    "reason": f"Patient mentioned symptoms {total_symptom_mentions} times recently",
                    "recommendation": "May indicate disease flare or medication ineffectiveness"
                })

        return {"inferences": inferences} if inferences else None

    async def _check_medication_adherence(
        self,
        event: KnowledgeEvent
    ) -> Optional[Dict[str, Any]]:
        """Monitor medication adherence mentions."""
        patient_context = event.data.get("patient_context")
        question = event.data.get("question", "").lower()

        if not patient_context or not patient_context.medications:
            return None

        inferences = []

        # Check if patient mentions taking medication
        adherence_keywords = {
            "positive": ["took", "taking", "started", "using", "on schedule"],
            "negative": ["missed", "forgot", "skip", "stopped", "discontinued", "ran out"]
        }

        has_positive = any(keyword in question for keyword in adherence_keywords["positive"])
        has_negative = any(keyword in question for keyword in adherence_keywords["negative"])

        if has_negative:
            inferences.append({
                "type": "adherence_concern",
                "confidence": 0.80,
                "reason": "Patient mentioned missing or stopping medication",
                "recommendation": "Gently remind about importance of medication adherence. Ask about barriers to adherence.",
                "follow_up": "Consider discussing with healthcare provider if pattern continues"
            })
        elif has_positive:
            inferences.append({
                "type": "adherence_positive",
                "confidence": 0.75,
                "reason": "Patient mentioned taking medication as prescribed",
                "recommendation": "Acknowledge positive adherence behavior"
            })

        # Check for side effect mentions (potential adherence risk)
        side_effect_keywords = ["side effect", "reaction", "feeling worse", "nausea from", "tired from"]
        if any(keyword in question for keyword in side_effect_keywords):
            inferences.append({
                "type": "side_effect_concern",
                "confidence": 0.85,
                "reason": "Patient mentioned medication side effects",
                "recommendation": "Suggest discussing side effects with healthcare provider. May impact adherence.",
                "risk": "Side effects are a common reason for non-adherence"
            })

        return {"inferences": inferences} if inferences else None
