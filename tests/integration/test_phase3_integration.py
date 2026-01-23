"""Integration tests for Phase 3: Layer Enforcement & Cross-Layer Integration.

Tests the complete workflow of:
1. Layer transition service
2. Cross-layer reasoning rules
3. Layer validation
4. End-to-end entity promotion through all layers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from application.services.layer_transition import (
    LayerTransitionService,
    LayerTransitionRequest,
    Layer,
    TransitionStatus
)
from domain.event import KnowledgeEvent
from domain.roles import Role

# Mock graphiti_core to avoid import errors
sys.modules['graphiti_core'] = MagicMock()

from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
from application.agents.knowledge_manager.validation_engine import ValidationEngine


class TestLayerTransitionWorkflow:
    """Test complete layer transition workflows."""

    @pytest.fixture
    def backend(self):
        """Create mock backend."""
        return MagicMock()

    @pytest.fixture
    def transition_service(self, backend):
        """Create layer transition service."""
        return LayerTransitionService(
            backend=backend,
            require_approval=False,
            auto_version=True
        )

    @pytest.fixture
    def reasoning_engine(self, backend):
        """Create reasoning engine."""
        return ReasoningEngine(backend=backend)

    @pytest.fixture
    def validation_engine(self, backend):
        """Create validation engine."""
        return ValidationEngine(backend=backend)

    @pytest.mark.asyncio
    async def test_perception_to_semantic_transition(
        self,
        transition_service,
        reasoning_engine,
        validation_engine
    ):
        """Test transitioning entity from PERCEPTION to SEMANTIC layer."""
        # Step 1: Create entity in PERCEPTION layer
        entity_data = {
            "id": "table:customers",
            "type": "Table",
            "layer": "PERCEPTION",
            "properties": {
                "name": "customers",
                "source": "sales_db",
                "origin": "production_database",
                "columns": ["customer_id", "customer_name", "email", "phone"],
                "description": "Customer master table",
                "domain": "sales"
            }
        }

        # Step 2: Apply cross-layer reasoning to suggest semantic concepts
        reasoning_result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data,
            "PERCEPTION"
        )

        # Should infer business concept
        assert len(reasoning_result["inferences"]) > 0
        assert any(
            inf["type"] == "business_concept_inference"
            for inf in reasoning_result["inferences"]
        )

        # Step 3: Request transition to SEMANTIC layer
        request = LayerTransitionRequest(
            entity_id="table:customers",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Business concept inferred from table structure",
            metadata={"entity_name": "customers"}
        )

        record = transition_service.request_transition(request)

        assert record.status == TransitionStatus.APPROVED
        assert record.from_layer == Layer.PERCEPTION
        assert record.to_layer == Layer.SEMANTIC

        # Step 4: Execute transition
        updated_record = await transition_service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert updated_record.status == TransitionStatus.COMPLETED
        assert updated_record.validation_results["is_valid"] is True

    @pytest.mark.asyncio
    async def test_semantic_to_reasoning_transition(
        self,
        transition_service,
        reasoning_engine
    ):
        """Test transitioning from SEMANTIC to REASONING layer."""
        # Step 1: Entity in SEMANTIC layer
        entity_data = {
            "id": "concept:customer",
            "type": "BusinessConcept",
            "layer": "SEMANTIC",
            "properties": {
                "concept_type": "Customer",
                "description": "Individual or organization that purchases products",
                "domain": "sales",
                "confidence": 0.9,
                "reasoning": "Inferred from customer table structure"
            }
        }

        # Step 2: Apply cross-layer reasoning
        reasoning_result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data,
            "SEMANTIC"
        )

        # Should derive quality rules
        assert len(reasoning_result["inferences"]) > 0
        assert any(
            inf["type"] == "quality_rule"
            for inf in reasoning_result["inferences"]
        )

        # Quality rules should be specific to Customer concept
        quality_rules = [
            inf for inf in reasoning_result["inferences"]
            if inf["type"] == "quality_rule"
        ]
        assert any("email" in rule["rule_name"] for rule in quality_rules)

        # Step 3: Request transition
        request = LayerTransitionRequest(
            entity_id="concept:customer",
            from_layer=Layer.SEMANTIC,
            to_layer=Layer.REASONING,
            reason="Quality rules derived from concept constraints"
        )

        record = transition_service.request_transition(request)

        # Step 4: Execute transition
        updated_record = await transition_service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert updated_record.status == TransitionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_reasoning_to_application_transition(
        self,
        transition_service,
        reasoning_engine
    ):
        """Test transitioning from REASONING to APPLICATION layer."""
        # Step 1: Entity in REASONING layer
        entity_data = {
            "id": "rule:customer_email_unique",
            "type": "DataQualityRule",
            "layer": "REASONING",
            "properties": {
                "reasoning_type": "quality_rule",
                "rule_name": "unique_email",
                "confidence": 0.95,
                "reasoning": "Email uniqueness constraint ensures data integrity",
                "usage_context": "data_validation",
                "access_pattern": "batch_validation"
            }
        }

        # Step 2: Apply cross-layer reasoning
        reasoning_result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data,
            "REASONING"
        )

        # Should suggest query patterns
        assert len(reasoning_result["inferences"]) > 0
        assert any(
            inf["type"] == "query_pattern" or inf["type"] == "optimization_suggestion"
            for inf in reasoning_result["inferences"]
        )

        # Step 3: Request transition
        request = LayerTransitionRequest(
            entity_id="rule:customer_email_unique",
            from_layer=Layer.REASONING,
            to_layer=Layer.APPLICATION,
            reason="Query patterns identified for practical application"
        )

        record = transition_service.request_transition(request)

        # Step 4: Execute transition
        updated_record = await transition_service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert updated_record.status == TransitionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_application_to_perception_feedback(
        self,
        reasoning_engine
    ):
        """Test feedback loop from APPLICATION to PERCEPTION layer."""
        # Application layer entity with usage statistics
        entity_data = {
            "id": "query:customer_temporal_analysis",
            "type": "Query",
            "layer": "APPLICATION",
            "properties": {
                "usage_pattern": "temporal_analysis",
                "access_count": 150,
                "query_errors": 5
            }
        }

        # Apply cross-layer reasoning
        reasoning_result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data,
            "APPLICATION"
        )

        # Should suggest new data sources
        assert len(reasoning_result["suggestions"]) > 0
        suggestions = reasoning_result["suggestions"]

        # Should recommend temporal data collection
        temporal_suggestions = [
            s for s in suggestions
            if s.get("action") == "collect_temporal_data"
        ]
        assert len(temporal_suggestions) > 0
        assert "timestamp" in str(temporal_suggestions[0]).lower()

    @pytest.mark.asyncio
    async def test_complete_layer_progression(
        self,
        transition_service,
        reasoning_engine
    ):
        """Test complete entity progression through all layers."""
        # Start with PERCEPTION layer
        entity_data = {
            "id": "table:orders",
            "type": "Table",
            "layer": "PERCEPTION",
            "properties": {
                "name": "orders",
                "source": "sales_db",
                "origin": "production",
                "columns": ["order_id", "order_date", "order_total", "order_status"],
                "description": "Order transactions table",
                "domain": "sales"
            }
        }

        # Track entity through all transitions
        transitions = []

        # PERCEPTION → SEMANTIC
        reasoning1 = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "PERCEPTION"
        )
        # Should have some inferences or suggestions
        assert len(reasoning1.get("inferences", [])) > 0 or len(reasoning1.get("suggestions", [])) > 0

        request1 = LayerTransitionRequest(
            entity_id="table:orders",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Business concept inferred"
        )
        record1 = transition_service.request_transition(request1)
        completed1 = await transition_service.execute_transition(
            record1.transition_id, entity_data
        )
        transitions.append(completed1)

        # Update entity data for next layer
        entity_data["layer"] = "SEMANTIC"
        entity_data["properties"]["concept_type"] = "Order"
        entity_data["properties"]["confidence"] = 0.88
        entity_data["properties"]["reasoning"] = "Inferred from table structure"

        # SEMANTIC → REASONING
        reasoning2 = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "SEMANTIC"
        )
        assert len(reasoning2.get("inferences", [])) > 0 or len(reasoning2.get("suggestions", [])) > 0

        request2 = LayerTransitionRequest(
            entity_id="table:orders",
            from_layer=Layer.SEMANTIC,
            to_layer=Layer.REASONING,
            reason="Quality rules derived"
        )
        record2 = transition_service.request_transition(request2)
        completed2 = await transition_service.execute_transition(
            record2.transition_id, entity_data
        )
        transitions.append(completed2)

        # Update entity data for next layer
        entity_data["layer"] = "REASONING"
        entity_data["properties"]["reasoning_type"] = "quality_rule"
        entity_data["properties"]["usage_context"] = "validation"
        entity_data["properties"]["access_pattern"] = "real_time"

        # REASONING → APPLICATION
        reasoning3 = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "REASONING"
        )
        # Cross-layer reasoning executed (may or may not have results depending on entity properties)
        assert reasoning3 is not None

        request3 = LayerTransitionRequest(
            entity_id="table:orders",
            from_layer=Layer.REASONING,
            to_layer=Layer.APPLICATION,
            reason="Query patterns identified"
        )
        record3 = transition_service.request_transition(request3)
        completed3 = await transition_service.execute_transition(
            record3.transition_id, entity_data
        )
        transitions.append(completed3)

        # Verify all transitions completed successfully
        assert len(transitions) == 3
        assert all(t.status == TransitionStatus.COMPLETED for t in transitions)

        # Verify layer progression
        assert transitions[0].to_layer == Layer.SEMANTIC
        assert transitions[1].to_layer == Layer.REASONING
        assert transitions[2].to_layer == Layer.APPLICATION


class TestLayerValidationIntegration:
    """Test layer validation integration."""

    @pytest.fixture
    def backend(self):
        """Create mock backend."""
        return MagicMock()

    @pytest.fixture
    def validation_engine(self, backend):
        """Create validation engine."""
        return ValidationEngine(backend=backend)

    @pytest.mark.asyncio
    async def test_validate_perception_layer_entity(self, validation_engine):
        """Test validating PERCEPTION layer entity."""
        event = KnowledgeEvent(
            action="create_entity",
            role=Role.DATA_ARCHITECT,
            data={
                "id": "table:test",
                "labels": ["Table"],
                "properties": {
                    "layer": "PERCEPTION",
                    "source": "test_db",
                    "origin": "production"
                }
            }
        )

        result = await validation_engine.validate_event(event)

        assert result["is_valid"] is True
        # Should not have warnings about missing source/origin
        layer_warnings = [
            w for w in result["warnings"]
            if "origin" in w.lower() or "source" in w.lower()
        ]
        assert len(layer_warnings) == 0

    @pytest.mark.asyncio
    async def test_validate_semantic_layer_entity(self, validation_engine):
        """Test validating SEMANTIC layer entity."""
        event = KnowledgeEvent(
            action="create_entity",
            role=Role.DATA_ARCHITECT,
            data={
                "id": "concept:customer",
                "labels": ["BusinessConcept"],
                "properties": {
                    "layer": "SEMANTIC",
                    "description": "Customer entity",
                    "domain": "sales"
                }
            }
        )

        result = await validation_engine.validate_event(event)

        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_reasoning_layer_requires_confidence(self, validation_engine):
        """Test REASONING layer requires confidence score."""
        # Missing confidence
        event = KnowledgeEvent(
            action="create_entity",
            role=Role.DATA_ARCHITECT,
            data={
                "id": "rule:test",
                "labels": ["DataQualityRule"],
                "properties": {
                    "layer": "REASONING"
                }
            }
        )

        result = await validation_engine.validate_event(event)

        # Should warn about missing confidence
        assert any("confidence" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_validate_application_layer_tracks_usage(self, validation_engine):
        """Test APPLICATION layer should track usage."""
        event = KnowledgeEvent(
            action="create_entity",
            role=Role.DATA_ARCHITECT,
            data={
                "id": "query:test",
                "labels": ["Query"],
                "properties": {
                    "layer": "APPLICATION"
                }
            }
        )

        result = await validation_engine.validate_event(event)

        # Should warn about missing usage tracking
        assert any("usage" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_validate_invalid_layer_assignment(self, validation_engine):
        """Test validation fails for invalid layer."""
        event = KnowledgeEvent(
            action="create_entity",
            role=Role.DATA_ARCHITECT,
            data={
                "id": "entity:test",
                "labels": ["Entity"],
                "properties": {
                    "layer": "INVALID_LAYER"
                }
            }
        )

        result = await validation_engine.validate_event(event)

        assert result["is_valid"] is False
        assert any("invalid layer" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_missing_layer_assignment(self, validation_engine):
        """Test validation fails when layer is missing."""
        event = KnowledgeEvent(
            action="create_entity",
            role=Role.DATA_ARCHITECT,
            data={
                "id": "entity:test",
                "labels": ["Entity"],
                "properties": {}
            }
        )

        result = await validation_engine.validate_event(event)

        assert result["is_valid"] is False
        assert any("must have a 'layer' property" in e.lower() for e in result["errors"])


class TestCrossLayerReasoningIntegration:
    """Test cross-layer reasoning integration."""

    @pytest.fixture
    def backend(self):
        """Create mock backend."""
        return MagicMock()

    @pytest.fixture
    def reasoning_engine(self, backend):
        """Create reasoning engine."""
        return ReasoningEngine(backend=backend)

    @pytest.mark.asyncio
    async def test_perception_infers_customer_concept(self, reasoning_engine):
        """Test PERCEPTION layer infers Customer business concept."""
        entity_data = {
            "id": "table:customer_master",
            "type": "Table",
            "properties": {
                "name": "customer_master",
                "columns": ["customer_id", "customer_name", "email", "phone", "address"]
            }
        }

        result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "PERCEPTION"
        )

        # Should infer Customer concept
        customer_inferences = [
            inf for inf in result["inferences"]
            if inf.get("concept", "").lower() == "customer"
        ]
        assert len(customer_inferences) > 0
        assert customer_inferences[0]["confidence"] > 0.6

    @pytest.mark.asyncio
    async def test_perception_classifies_domains(self, reasoning_engine):
        """Test PERCEPTION layer classifies column domains."""
        entity_data = {
            "id": "column:order_date",
            "type": "Column",
            "properties": {
                "name": "order_date",
                "data_type": "DATE"
            }
        }

        result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "PERCEPTION"
        )

        # Should classify as temporal domain
        domain_inferences = [
            inf for inf in result["inferences"]
            if inf["type"] == "domain_classification"
        ]
        assert len(domain_inferences) > 0
        assert domain_inferences[0]["domain"] == "temporal"

    @pytest.mark.asyncio
    async def test_semantic_derives_quality_rules(self, reasoning_engine):
        """Test SEMANTIC layer derives quality rules."""
        entity_data = {
            "id": "concept:product",
            "type": "BusinessConcept",
            "properties": {
                "concept_type": "Product"
            }
        }

        result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "SEMANTIC"
        )

        # Should derive Product quality rules
        quality_rules = [
            inf for inf in result["inferences"]
            if inf["type"] == "quality_rule"
        ]
        assert len(quality_rules) > 0
        assert any("price_positive" in rule["rule_name"] for rule in quality_rules)
        assert any("sku_unique" in rule["rule_name"] for rule in quality_rules)

    @pytest.mark.asyncio
    async def test_semantic_infers_referential_integrity(self, reasoning_engine):
        """Test SEMANTIC layer infers referential integrity rules."""
        entity_data = {
            "id": "concept:order_line",
            "type": "BusinessConcept",
            "properties": {
                "concept_type": "OrderLine"
            },
            "relationships": [
                {"type": "HAS_FK", "target": "concept:order"}
            ]
        }

        result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "SEMANTIC"
        )

        # Should infer referential integrity rule
        integrity_rules = [
            inf for inf in result["inferences"]
            if inf["type"] == "referential_integrity_rule"
        ]
        assert len(integrity_rules) > 0

    @pytest.mark.asyncio
    async def test_reasoning_suggests_query_patterns(self, reasoning_engine):
        """Test REASONING layer suggests query patterns."""
        entity_data = {
            "id": "rule:unique_check",
            "type": "DataQualityRule",
            "properties": {
                "reasoning_type": "quality_rule",
                "rule_name": "unique_customer_email",
                "confidence": 0.95
            }
        }

        result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "REASONING"
        )

        # Should suggest duplicate detection query
        query_patterns = [
            inf for inf in result["inferences"]
            if inf["type"] == "query_pattern"
        ]
        assert len(query_patterns) > 0
        assert query_patterns[0]["pattern"] == "duplicate_detection_query"

    @pytest.mark.asyncio
    async def test_reasoning_suggests_indexes(self, reasoning_engine):
        """Test REASONING layer suggests index optimization."""
        entity_data = {
            "id": "rule:fk_constraint",
            "type": "DataQualityRule",
            "properties": {
                "reasoning_type": "quality_rule",
                "rule_name": "foreign_key_order_customer"
            }
        }

        result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "REASONING"
        )

        # Should suggest index on foreign key
        optimizations = [
            inf for inf in result["inferences"]
            if inf["type"] == "optimization_suggestion"
        ]
        assert len(optimizations) > 0
        assert "index" in optimizations[0]["suggestion"].lower()

    @pytest.mark.asyncio
    async def test_application_identifies_data_gaps(self, reasoning_engine):
        """Test APPLICATION layer identifies data gaps."""
        entity_data = {
            "id": "query:high_frequency",
            "type": "Query",
            "properties": {
                "usage_pattern": "aggregation",
                "access_count": 250
            }
        }

        result = await reasoning_engine.apply_cross_layer_reasoning(
            entity_data, "APPLICATION"
        )

        # Should identify data gap
        data_gaps = [
            inf for inf in result["inferences"]
            if inf["type"] == "data_gap_detection"
        ]
        assert len(data_gaps) > 0
        assert data_gaps[0]["gap"] == "missing_optimized_structure"


class TestEndToEndLayerTransitions:
    """Test end-to-end layer transition scenarios."""

    @pytest.fixture
    def backend(self):
        """Create mock backend."""
        return MagicMock()

    @pytest.fixture
    def transition_service(self, backend):
        """Create transition service."""
        return LayerTransitionService(backend=backend, auto_version=True)

    @pytest.fixture
    def reasoning_engine(self, backend):
        """Create reasoning engine."""
        return ReasoningEngine(backend=backend)

    @pytest.mark.asyncio
    async def test_lineage_tracking_across_layers(
        self,
        transition_service,
        reasoning_engine
    ):
        """Test lineage is properly tracked across layer transitions."""
        entity_id = "entity:test_lineage"

        # Create multiple transitions
        layers = [
            (Layer.PERCEPTION, Layer.SEMANTIC),
            (Layer.SEMANTIC, Layer.REASONING),
            (Layer.REASONING, Layer.APPLICATION)
        ]

        for from_layer, to_layer in layers:
            entity_data = {
                "id": entity_id,
                "properties": {
                    "source": "test",
                    "origin": "test",
                    "description": "Test",
                    "domain": "test",
                    "confidence": 0.9,
                    "reasoning": "Test reasoning",
                    "usage_context": "test",
                    "access_pattern": "test"
                }
            }

            request = LayerTransitionRequest(
                entity_id=entity_id,
                from_layer=from_layer,
                to_layer=to_layer,
                reason="Test transition"
            )

            record = transition_service.request_transition(request)
            await transition_service.execute_transition(record.transition_id, entity_data)

        # Get complete lineage
        lineage = transition_service.get_entity_lineage(entity_id)

        assert len(lineage) == 3
        assert lineage[0].to_layer == Layer.SEMANTIC
        assert lineage[1].to_layer == Layer.REASONING
        assert lineage[2].to_layer == Layer.APPLICATION

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, transition_service):
        """Test statistics are tracked across transitions."""
        # Create multiple transitions
        for i in range(5):
            entity_data = {
                "id": f"entity:{i}",
                "properties": {
                    "source": "test",
                    "origin": "test",
                    "description": "Test",
                    "domain": "test"
                }
            }

            request = LayerTransitionRequest(
                entity_id=f"entity:{i}",
                from_layer=Layer.PERCEPTION,
                to_layer=Layer.SEMANTIC,
                reason="Test"
            )

            record = transition_service.request_transition(request)
            await transition_service.execute_transition(record.transition_id, entity_data)

        stats = transition_service.get_layer_statistics()

        assert stats["total_transitions"] == 5
        assert stats["completed"] == 5
        assert "PERCEPTION → SEMANTIC" in stats["transition_counts"]
        assert stats["transition_counts"]["PERCEPTION → SEMANTIC"] == 5

    @pytest.mark.asyncio
    async def test_backward_transition_prevented(self, transition_service):
        """Test backward transitions are prevented."""
        entity_data = {
            "id": "entity:backward_test",
            "properties": {}
        }

        request = LayerTransitionRequest(
            entity_id="entity:backward_test",
            from_layer=Layer.REASONING,
            to_layer=Layer.PERCEPTION,
            reason="Attempt backward transition"
        )

        record = transition_service.request_transition(request)
        result = await transition_service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert result.status == TransitionStatus.REJECTED
        assert any("backwards" in err.lower() for err in result.validation_results["errors"])
