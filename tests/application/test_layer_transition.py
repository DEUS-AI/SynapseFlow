"""Unit tests for Layer Transition Service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from application.services.layer_transition import (
    LayerTransitionService,
    LayerTransitionRequest,
    LayerTransitionRecord,
    Layer,
    TransitionStatus
)


class TestLayerEnum:
    """Test Layer enumeration."""

    def test_layer_values(self):
        """Test layer enum values."""
        assert Layer.PERCEPTION == "PERCEPTION"
        assert Layer.SEMANTIC == "SEMANTIC"
        assert Layer.REASONING == "REASONING"
        assert Layer.APPLICATION == "APPLICATION"


class TestTransitionStatusEnum:
    """Test TransitionStatus enumeration."""

    def test_status_values(self):
        """Test status enum values."""
        assert TransitionStatus.PENDING == "pending"
        assert TransitionStatus.APPROVED == "approved"
        assert TransitionStatus.REJECTED == "rejected"
        assert TransitionStatus.COMPLETED == "completed"
        assert TransitionStatus.FAILED == "failed"


class TestLayerTransitionRequest:
    """Test LayerTransitionRequest model."""

    def test_request_creation(self):
        """Test creating a transition request."""
        request = LayerTransitionRequest(
            entity_id="entity:123",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Entity has sufficient semantic properties"
        )

        assert request.entity_id == "entity:123"
        assert request.from_layer == Layer.PERCEPTION
        assert request.to_layer == Layer.SEMANTIC
        assert request.reason == "Entity has sufficient semantic properties"
        assert request.requested_by == "system"
        assert isinstance(request.requested_at, datetime)

    def test_request_with_metadata(self):
        """Test request with metadata."""
        request = LayerTransitionRequest(
            entity_id="entity:456",
            from_layer=Layer.SEMANTIC,
            to_layer=Layer.REASONING,
            reason="Ready for reasoning",
            requested_by="user_123",
            metadata={"entity_name": "Customer", "priority": "high"}
        )

        assert request.requested_by == "user_123"
        assert request.metadata["entity_name"] == "Customer"
        assert request.metadata["priority"] == "high"


class TestLayerTransitionRecord:
    """Test LayerTransitionRecord model."""

    def test_record_creation(self):
        """Test creating a transition record."""
        record = LayerTransitionRecord(
            transition_id="transition_000001",
            entity_id="entity:123",
            entity_name="Customer",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test transition",
            status=TransitionStatus.PENDING,
            requested_by="system",
            requested_at=datetime.now()
        )

        assert record.transition_id == "transition_000001"
        assert record.entity_id == "entity:123"
        assert record.status == TransitionStatus.PENDING
        assert record.completed_at is None
        assert record.approval_required is False

    def test_record_with_validation_results(self):
        """Test record with validation results."""
        record = LayerTransitionRecord(
            transition_id="transition_000002",
            entity_id="entity:456",
            entity_name="Product",
            from_layer=Layer.SEMANTIC,
            to_layer=Layer.REASONING,
            reason="Test",
            status=TransitionStatus.APPROVED,
            requested_by="user",
            requested_at=datetime.now(),
            validation_results={"is_valid": True, "errors": []}
        )

        assert record.validation_results["is_valid"] is True
        assert len(record.validation_results["errors"]) == 0


class TestLayerHierarchy:
    """Test layer hierarchy enforcement."""

    @pytest.fixture
    def service(self):
        """Create layer transition service."""
        backend = MagicMock()
        return LayerTransitionService(
            backend=backend,
            require_approval=False,
            auto_version=False
        )

    def test_hierarchy_definition(self, service):
        """Test layer hierarchy is correctly defined."""
        assert service.LAYER_HIERARCHY[Layer.PERCEPTION] == 0
        assert service.LAYER_HIERARCHY[Layer.SEMANTIC] == 1
        assert service.LAYER_HIERARCHY[Layer.REASONING] == 2
        assert service.LAYER_HIERARCHY[Layer.APPLICATION] == 3

    def test_layer_requirements(self, service):
        """Test layer requirements are defined."""
        assert "source" in service.LAYER_REQUIREMENTS[Layer.PERCEPTION]
        assert "description" in service.LAYER_REQUIREMENTS[Layer.SEMANTIC]
        assert "confidence" in service.LAYER_REQUIREMENTS[Layer.REASONING]
        assert "usage_context" in service.LAYER_REQUIREMENTS[Layer.APPLICATION]


class TestTransitionValidation:
    """Test transition validation logic."""

    @pytest.fixture
    def service(self):
        """Create layer transition service."""
        backend = MagicMock()
        return LayerTransitionService(backend=backend)

    def test_validate_upward_transition(self, service):
        """Test validating upward transition (allowed)."""
        entity_data = {
            "id": "entity:123",
            "properties": {
                "description": "Customer entity",
                "domain": "sales"
            }
        }

        is_valid, errors = service.validate_transition(
            entity_data,
            Layer.PERCEPTION,
            Layer.SEMANTIC
        )

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_backward_transition(self, service):
        """Test validating backward transition (not allowed)."""
        entity_data = {
            "id": "entity:123",
            "properties": {}
        }

        is_valid, errors = service.validate_transition(
            entity_data,
            Layer.SEMANTIC,
            Layer.PERCEPTION
        )

        assert is_valid is False
        assert any("backwards" in err.lower() for err in errors)

    def test_validate_missing_required_properties(self, service):
        """Test validation fails when required properties missing."""
        entity_data = {
            "id": "entity:123",
            "properties": {
                "description": "Has description but no domain"
            }
        }

        is_valid, errors = service.validate_transition(
            entity_data,
            Layer.PERCEPTION,
            Layer.SEMANTIC
        )

        assert is_valid is False
        assert any("domain" in err.lower() for err in errors)

    def test_validate_lateral_transition(self, service):
        """Test validating lateral transition (same level - allowed)."""
        entity_data = {
            "id": "entity:123",
            "properties": {
                "description": "Test",
                "domain": "test"
            }
        }

        is_valid, errors = service.validate_transition(
            entity_data,
            Layer.SEMANTIC,
            Layer.SEMANTIC
        )

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_reasoning_layer_confidence(self, service):
        """Test REASONING layer requires valid confidence score."""
        # Missing confidence
        entity_data = {
            "id": "entity:123",
            "properties": {
                "reasoning": "Test reasoning"
            }
        }

        is_valid, errors = service.validate_transition(
            entity_data,
            Layer.SEMANTIC,
            Layer.REASONING
        )

        assert is_valid is False
        assert any("confidence" in err.lower() for err in errors)

        # Invalid confidence range
        entity_data["properties"]["confidence"] = 1.5

        is_valid, errors = service.validate_transition(
            entity_data,
            Layer.SEMANTIC,
            Layer.REASONING
        )

        assert is_valid is False
        assert any("0.0 and 1.0" in err for err in errors)

        # Valid confidence
        entity_data["properties"]["confidence"] = 0.85

        is_valid, errors = service.validate_transition(
            entity_data,
            Layer.SEMANTIC,
            Layer.REASONING
        )

        assert is_valid is True

    def test_validate_semantic_layer_domain(self, service):
        """Test SEMANTIC layer requires domain classification."""
        entity_data = {
            "id": "entity:123",
            "properties": {
                "description": "Has description but no domain"
            }
        }

        is_valid, errors = service.validate_transition(
            entity_data,
            Layer.PERCEPTION,
            Layer.SEMANTIC
        )

        assert is_valid is False
        assert any("domain" in err.lower() for err in errors)


class TestRequestTransition:
    """Test requesting transitions."""

    @pytest.fixture
    def service(self):
        """Create service without approval requirement."""
        backend = MagicMock()
        return LayerTransitionService(
            backend=backend,
            require_approval=False
        )

    @pytest.fixture
    def approval_service(self):
        """Create service with approval requirement."""
        backend = MagicMock()
        return LayerTransitionService(
            backend=backend,
            require_approval=True
        )

    def test_request_auto_approved(self, service):
        """Test request is auto-approved when approval not required."""
        request = LayerTransitionRequest(
            entity_id="entity:123",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test",
            metadata={"entity_name": "Customer"}
        )

        record = service.request_transition(request)

        assert record.transition_id.startswith("transition_")
        assert record.entity_id == "entity:123"
        assert record.entity_name == "Customer"
        assert record.status == TransitionStatus.APPROVED
        assert record.approved_by == "system"
        assert len(service.transition_history) == 1

    def test_request_pending_approval(self, approval_service):
        """Test request is pending when approval required."""
        request = LayerTransitionRequest(
            entity_id="entity:456",
            from_layer=Layer.SEMANTIC,
            to_layer=Layer.REASONING,
            reason="Test"
        )

        record = approval_service.request_transition(request)

        assert record.status == TransitionStatus.PENDING
        assert record.approval_required is True
        assert record.transition_id in approval_service.pending_transitions
        assert len(approval_service.transition_history) == 1

    def test_multiple_requests_increment_counter(self, service):
        """Test multiple requests increment transition counter."""
        request1 = LayerTransitionRequest(
            entity_id="entity:1",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test 1"
        )

        request2 = LayerTransitionRequest(
            entity_id="entity:2",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test 2"
        )

        record1 = service.request_transition(request1)
        record2 = service.request_transition(request2)

        assert record1.transition_id == "transition_000001"
        assert record2.transition_id == "transition_000002"


class TestExecuteTransition:
    """Test executing transitions."""

    @pytest.fixture
    def service(self):
        """Create layer transition service."""
        backend = MagicMock()
        return LayerTransitionService(
            backend=backend,
            require_approval=False,
            auto_version=False
        )

    @pytest.mark.asyncio
    async def test_execute_valid_transition(self, service):
        """Test executing a valid transition."""
        # Create request
        request = LayerTransitionRequest(
            entity_id="entity:123",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Ready for semantic layer"
        )

        record = service.request_transition(request)

        # Entity data with required properties
        entity_data = {
            "id": "entity:123",
            "layer": "PERCEPTION",
            "properties": {
                "source": "test_dda",
                "origin": "metadata",
                "description": "Customer entity",
                "domain": "sales"
            }
        }

        # Execute transition
        updated_record = await service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert updated_record.status == TransitionStatus.COMPLETED
        assert updated_record.completed_at is not None
        assert updated_record.validation_results["is_valid"] is True
        assert len(updated_record.validation_results["errors"]) == 0

    @pytest.mark.asyncio
    async def test_execute_invalid_transition(self, service):
        """Test executing invalid transition gets rejected."""
        request = LayerTransitionRequest(
            entity_id="entity:456",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test"
        )

        record = service.request_transition(request)

        # Entity data missing required properties
        entity_data = {
            "id": "entity:456",
            "properties": {
                "source": "test"
                # Missing description and domain
            }
        }

        updated_record = await service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert updated_record.status == TransitionStatus.REJECTED
        assert updated_record.validation_results["is_valid"] is False
        assert len(updated_record.validation_results["errors"]) > 0

    @pytest.mark.asyncio
    async def test_execute_backward_transition(self, service):
        """Test backward transition is rejected."""
        request = LayerTransitionRequest(
            entity_id="entity:789",
            from_layer=Layer.REASONING,
            to_layer=Layer.PERCEPTION,
            reason="Test backward"
        )

        record = service.request_transition(request)

        entity_data = {
            "id": "entity:789",
            "properties": {}
        }

        updated_record = await service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert updated_record.status == TransitionStatus.REJECTED
        assert any("backwards" in err.lower() for err in updated_record.validation_results["errors"])

    @pytest.mark.asyncio
    async def test_execute_nonexistent_transition(self, service):
        """Test executing non-existent transition raises error."""
        entity_data = {"id": "entity:123", "properties": {}}

        with pytest.raises(ValueError, match="not found"):
            await service.execute_transition("transition_999999", entity_data)

    @pytest.mark.asyncio
    async def test_execute_completed_transition(self, service):
        """Test cannot execute already completed transition."""
        request = LayerTransitionRequest(
            entity_id="entity:123",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test"
        )

        record = service.request_transition(request)

        entity_data = {
            "id": "entity:123",
            "properties": {
                "source": "test",
                "origin": "test",
                "description": "Test",
                "domain": "test"
            }
        }

        # Execute once
        await service.execute_transition(record.transition_id, entity_data)

        # Try to execute again
        with pytest.raises(ValueError, match="not executable"):
            await service.execute_transition(record.transition_id, entity_data)


class TestApprovalWorkflow:
    """Test approval workflow."""

    @pytest.fixture
    def service(self):
        """Create service with approval requirement."""
        backend = MagicMock()
        return LayerTransitionService(
            backend=backend,
            require_approval=True
        )

    def test_approve_transition(self, service):
        """Test approving a pending transition."""
        request = LayerTransitionRequest(
            entity_id="entity:123",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test"
        )

        record = service.request_transition(request)
        assert record.status == TransitionStatus.PENDING

        # Approve
        approved = service.approve_transition(record.transition_id, "admin_user")

        assert approved is not None
        assert approved.status == TransitionStatus.APPROVED
        assert approved.approved_by == "admin_user"

    def test_reject_transition(self, service):
        """Test rejecting a pending transition."""
        request = LayerTransitionRequest(
            entity_id="entity:456",
            from_layer=Layer.SEMANTIC,
            to_layer=Layer.REASONING,
            reason="Test"
        )

        record = service.request_transition(request)
        assert record.transition_id in service.pending_transitions

        # Reject
        rejected = service.reject_transition(
            record.transition_id,
            "Insufficient confidence data"
        )

        assert rejected is not None
        assert rejected.status == TransitionStatus.REJECTED
        assert rejected.error_message == "Insufficient confidence data"
        assert rejected.completed_at is not None
        assert record.transition_id not in service.pending_transitions

    def test_approve_nonexistent_transition(self, service):
        """Test approving non-existent transition returns None."""
        result = service.approve_transition("transition_999999", "admin")
        assert result is None

    def test_reject_nonexistent_transition(self, service):
        """Test rejecting non-existent transition returns None."""
        result = service.reject_transition("transition_999999", "reason")
        assert result is None

    def test_get_pending_transitions(self, service):
        """Test getting all pending transitions."""
        # Create multiple requests
        for i in range(3):
            request = LayerTransitionRequest(
                entity_id=f"entity:{i}",
                from_layer=Layer.PERCEPTION,
                to_layer=Layer.SEMANTIC,
                reason=f"Test {i}"
            )
            service.request_transition(request)

        pending = service.get_pending_transitions()

        assert len(pending) == 3
        assert all(t.status == TransitionStatus.PENDING for t in pending)


class TestVersioning:
    """Test automatic versioning."""

    @pytest.fixture
    def service(self):
        """Create service with auto-versioning enabled."""
        backend = MagicMock()
        return LayerTransitionService(
            backend=backend,
            require_approval=False,
            auto_version=True
        )

    @pytest.mark.asyncio
    async def test_create_versioned_entity(self, service):
        """Test creating versioned entity."""
        entity_data = {
            "id": "entity:customer",
            "properties": {"name": "Customer"}
        }

        new_id = await service._create_versioned_entity(
            entity_data,
            Layer.SEMANTIC
        )

        assert new_id.startswith("entity:customer_v")
        assert "_v" in new_id

    @pytest.mark.asyncio
    async def test_execute_with_versioning(self, service):
        """Test execution creates new version when auto_version enabled."""
        request = LayerTransitionRequest(
            entity_id="entity:original",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test versioning"
        )

        record = service.request_transition(request)

        entity_data = {
            "id": "entity:original",
            "properties": {
                "source": "test",
                "origin": "test",
                "description": "Test",
                "domain": "test"
            }
        }

        updated_record = await service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert updated_record.status == TransitionStatus.COMPLETED
        assert "entity:original" in updated_record.lineage
        assert updated_record.entity_id != "entity:original"
        assert updated_record.entity_id.startswith("entity:original_v")


class TestLineageTracking:
    """Test lineage tracking."""

    @pytest.fixture
    def service(self):
        """Create service."""
        backend = MagicMock()
        return LayerTransitionService(backend=backend, auto_version=True)

    @pytest.mark.asyncio
    async def test_lineage_tracking(self, service):
        """Test lineage is tracked through transitions."""
        request = LayerTransitionRequest(
            entity_id="entity:base",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="First transition"
        )

        record = service.request_transition(request)

        entity_data = {
            "id": "entity:base",
            "properties": {
                "source": "test",
                "origin": "test",
                "description": "Test",
                "domain": "test"
            }
        }

        completed = await service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert len(completed.lineage) == 1
        assert "entity:base" in completed.lineage

    def test_get_entity_lineage(self, service):
        """Test getting entity lineage."""
        # Create multiple transitions for same entity
        request1 = LayerTransitionRequest(
            entity_id="entity:123",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="First"
        )

        request2 = LayerTransitionRequest(
            entity_id="entity:123",
            from_layer=Layer.SEMANTIC,
            to_layer=Layer.REASONING,
            reason="Second"
        )

        service.request_transition(request1)
        service.request_transition(request2)

        lineage = service.get_entity_lineage("entity:123")

        assert len(lineage) == 2
        assert lineage[0].to_layer == Layer.SEMANTIC
        assert lineage[1].to_layer == Layer.REASONING


class TestStatistics:
    """Test statistics and reporting."""

    @pytest.fixture
    def service(self):
        """Create service."""
        backend = MagicMock()
        return LayerTransitionService(backend=backend)

    @pytest.mark.asyncio
    async def test_get_layer_statistics(self, service):
        """Test getting layer statistics."""
        # Create and complete some transitions
        for i in range(3):
            request = LayerTransitionRequest(
                entity_id=f"entity:{i}",
                from_layer=Layer.PERCEPTION,
                to_layer=Layer.SEMANTIC,
                reason=f"Test {i}"
            )

            record = service.request_transition(request)

            entity_data = {
                "id": f"entity:{i}",
                "properties": {
                    "source": "test",
                    "origin": "test",
                    "description": "Test",
                    "domain": "test"
                }
            }

            await service.execute_transition(record.transition_id, entity_data)

        stats = service.get_layer_statistics()

        assert stats["total_transitions"] == 3
        assert stats["completed"] == 3
        assert stats["pending"] == 0
        assert "PERCEPTION → SEMANTIC" in stats["transition_counts"]
        assert stats["transition_counts"]["PERCEPTION → SEMANTIC"] == 3

    @pytest.mark.asyncio
    async def test_statistics_with_failures(self, service):
        """Test statistics include failed transitions."""
        # Create valid transition
        request1 = LayerTransitionRequest(
            entity_id="entity:valid",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Valid"
        )

        record1 = service.request_transition(request1)

        entity_data1 = {
            "id": "entity:valid",
            "properties": {
                "source": "test",
                "origin": "test",
                "description": "Test",
                "domain": "test"
            }
        }

        await service.execute_transition(record1.transition_id, entity_data1)

        # Create invalid transition
        request2 = LayerTransitionRequest(
            entity_id="entity:invalid",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Invalid"
        )

        record2 = service.request_transition(request2)

        entity_data2 = {
            "id": "entity:invalid",
            "properties": {}  # Missing required properties
        }

        await service.execute_transition(record2.transition_id, entity_data2)

        stats = service.get_layer_statistics()

        assert stats["total_transitions"] == 2
        assert stats["completed"] == 1
        assert stats["rejected"] == 1

    def test_statistics_average_time(self, service):
        """Test statistics calculate average transition time."""
        # Create transition with completed_at set
        now = datetime.now()

        record1 = LayerTransitionRecord(
            transition_id="transition_000001",
            entity_id="entity:1",
            entity_name="Test1",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test",
            status=TransitionStatus.COMPLETED,
            requested_by="system",
            requested_at=now - timedelta(seconds=10),
            completed_at=now
        )

        record2 = LayerTransitionRecord(
            transition_id="transition_000002",
            entity_id="entity:2",
            entity_name="Test2",
            from_layer=Layer.SEMANTIC,
            to_layer=Layer.REASONING,
            reason="Test",
            status=TransitionStatus.COMPLETED,
            requested_by="system",
            requested_at=now - timedelta(seconds=20),
            completed_at=now
        )

        service.transition_history.append(record1)
        service.transition_history.append(record2)

        stats = service.get_layer_statistics()

        assert stats["avg_transition_time_seconds"] == 15.0  # (10 + 20) / 2


class TestPropertyChanges:
    """Test property change tracking."""

    @pytest.fixture
    def service(self):
        """Create service."""
        backend = MagicMock()
        return LayerTransitionService(backend=backend)

    def test_compute_property_changes(self, service):
        """Test computing property changes for transition."""
        entity_data = {
            "id": "entity:123",
            "layer": "PERCEPTION",
            "properties": {
                "source": "test",
                "origin": "metadata",
                "description": "Customer entity",
                "domain": "sales"
            }
        }

        changes = service._compute_property_changes(
            entity_data,
            Layer.SEMANTIC
        )

        assert changes["layer"]["old"] == "PERCEPTION"
        assert changes["layer"]["new"] == "SEMANTIC"
        assert "description" in changes["added_properties"]
        assert "domain" in changes["added_properties"]

    @pytest.mark.asyncio
    async def test_execute_tracks_property_changes(self, service):
        """Test execution tracks property changes."""
        request = LayerTransitionRequest(
            entity_id="entity:123",
            from_layer=Layer.PERCEPTION,
            to_layer=Layer.SEMANTIC,
            reason="Test"
        )

        record = service.request_transition(request)

        entity_data = {
            "id": "entity:123",
            "layer": "PERCEPTION",
            "properties": {
                "source": "test",
                "origin": "test",
                "description": "Test entity",
                "domain": "test"
            }
        }

        updated_record = await service.execute_transition(
            record.transition_id,
            entity_data
        )

        assert "layer" in updated_record.properties_changed
        assert len(updated_record.properties_changed["added_properties"]) > 0
