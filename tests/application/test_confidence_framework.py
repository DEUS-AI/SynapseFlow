"""Unit tests for ConfidenceFrameworkService."""

import pytest
from datetime import datetime
from application.services.confidence_framework import (
    ConfidenceFrameworkService,
    ConfidenceConfig,
    WorkflowStep
)
from domain.confidence_models import (
    Confidence,
    ConfidenceSource,
    AggregationStrategy,
    neural_confidence,
    symbolic_confidence
)


@pytest.fixture
def framework():
    """Create a ConfidenceFrameworkService instance."""
    return ConfidenceFrameworkService()


@pytest.fixture
def custom_config():
    """Create a custom configuration."""
    return ConfidenceConfig(
        alpha=0.7,
        decay_factor=0.90,
        min_threshold=0.2,
        high_confidence_threshold=0.90,
        learning_rate=0.05
    )


class TestConfidenceConfig:
    """Test ConfidenceConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ConfidenceConfig()

        assert config.alpha == 0.6
        assert config.decay_factor == 0.95
        assert config.min_threshold == 0.1
        assert config.high_confidence_threshold == 0.85
        assert config.learning_rate == 0.01

    def test_custom_config(self, custom_config):
        """Test custom configuration."""
        assert custom_config.alpha == 0.7
        assert custom_config.decay_factor == 0.90
        assert custom_config.min_threshold == 0.2
        assert custom_config.high_confidence_threshold == 0.90
        assert custom_config.learning_rate == 0.05


class TestWorkflowManagement:
    """Test workflow creation and management."""

    def test_start_workflow(self, framework):
        """Test starting a new workflow."""
        framework.start_workflow("workflow_001")

        assert "workflow_001" in framework.workflows
        assert len(framework.workflows["workflow_001"]) == 0

    def test_start_existing_workflow_resets(self, framework):
        """Test starting existing workflow resets it."""
        framework.start_workflow("workflow_001")
        framework.add_step("workflow_001", "step1", neural_confidence(0.8, "test"))

        # Start again
        framework.start_workflow("workflow_001")

        assert len(framework.workflows["workflow_001"]) == 0

    def test_add_step(self, framework):
        """Test adding a step to workflow."""
        framework.start_workflow("workflow_001")
        conf = neural_confidence(0.85, "llm_extractor")

        framework.add_step(
            "workflow_001",
            "extraction",
            conf,
            inputs={"text": "sample"},
            outputs={"entities": 5}
        )

        assert len(framework.workflows["workflow_001"]) == 1
        step = framework.workflows["workflow_001"][0]
        assert step.step_name == "extraction"
        assert step.confidence.score == 0.85
        assert step.inputs["text"] == "sample"
        assert step.outputs["entities"] == 5

    def test_add_step_creates_workflow(self, framework):
        """Test adding step creates workflow if not exists."""
        conf = neural_confidence(0.85, "test")

        framework.add_step("workflow_002", "step1", conf)

        assert "workflow_002" in framework.workflows
        assert len(framework.workflows["workflow_002"]) == 1

    def test_get_workflow_confidence(self, framework):
        """Test getting final workflow confidence."""
        framework.start_workflow("workflow_001")

        conf1 = neural_confidence(0.8, "step1")
        conf2 = symbolic_confidence(1.0, "step2")

        framework.add_step("workflow_001", "step1", conf1)
        framework.add_step("workflow_001", "step2", conf2)

        final = framework.get_workflow_confidence("workflow_001")

        assert final is not None
        assert final.score == 1.0  # Last step

    def test_get_workflow_confidence_not_found(self, framework):
        """Test getting confidence for non-existent workflow."""
        conf = framework.get_workflow_confidence("nonexistent")
        assert conf is None

    def test_get_workflow_confidence_empty(self, framework):
        """Test getting confidence for empty workflow."""
        framework.start_workflow("workflow_001")
        conf = framework.get_workflow_confidence("workflow_001")
        assert conf is None


class TestNeuralSymbolicCombination:
    """Test neural-symbolic confidence combination."""

    def test_combine_neural_symbolic_default(self, framework):
        """Test combining with default alpha."""
        neural = neural_confidence(0.8, "llm")
        symbolic = 1.0  # Rule certainty

        combined = framework.combine_neural_symbolic(
            neural,
            symbolic,
            operation_type="entity_creation"
        )

        # α=0.6: 0.6*0.8 + 0.4*1.0 = 0.48 + 0.4 = 0.88
        assert abs(combined.score - 0.88) < 0.01
        assert combined.source == ConfidenceSource.HYBRID
        assert combined.properties["operation_type"] == "entity_creation"
        assert combined.properties["alpha"] == 0.6

    def test_combine_neural_symbolic_custom_alpha(self):
        """Test combining with custom alpha."""
        config = ConfidenceConfig(alpha=0.7)
        framework = ConfidenceFrameworkService(config)

        neural = neural_confidence(0.8, "llm")
        symbolic = 1.0

        combined = framework.combine_neural_symbolic(neural, symbolic)

        # α=0.7: 0.7*0.8 + 0.3*1.0 = 0.56 + 0.3 = 0.86
        assert abs(combined.score - 0.86) < 0.01

    def test_combine_neural_symbolic_adaptive(self, framework):
        """Test adaptive alpha usage."""
        # Set learned alpha for specific operation
        framework.alpha_values["entity_creation"] = 0.75

        neural = neural_confidence(0.8, "llm")
        symbolic = 1.0

        combined = framework.combine_neural_symbolic(
            neural,
            symbolic,
            operation_type="entity_creation",
            adaptive=True
        )

        # Should use learned alpha=0.75
        # 0.75*0.8 + 0.25*1.0 = 0.6 + 0.25 = 0.85
        assert abs(combined.score - 0.85) < 0.01
        assert combined.properties["alpha"] == 0.75

    def test_combine_neural_symbolic_no_adaptive(self, framework):
        """Test non-adaptive uses default alpha."""
        framework.alpha_values["entity_creation"] = 0.75

        neural = neural_confidence(0.8, "llm")
        symbolic = 1.0

        combined = framework.combine_neural_symbolic(
            neural,
            symbolic,
            operation_type="entity_creation",
            adaptive=False
        )

        # Should use default alpha=0.6
        assert abs(combined.score - 0.88) < 0.01
        assert combined.properties["alpha"] == 0.6


class TestConfidencePropagation:
    """Test confidence propagation through reasoning chains."""

    def test_propagate_confidence(self, framework):
        """Test propagating confidence over steps."""
        initial = neural_confidence(0.9, "llm")

        propagated = framework.propagate_confidence(initial, num_steps=3)

        # With decay=0.95: 0.9 * 0.95^3 = 0.9 * 0.857375 ≈ 0.772
        assert 0.77 < propagated.score < 0.78
        # Source is preserved from initial confidence
        assert propagated.source == ConfidenceSource.NEURAL_MODEL

    def test_propagate_confidence_custom_decay(self):
        """Test propagation with custom decay factor."""
        config = ConfidenceConfig(decay_factor=0.90)
        framework = ConfidenceFrameworkService(config)

        initial = neural_confidence(0.9, "llm")
        propagated = framework.propagate_confidence(initial, num_steps=2)

        # 0.9 * 0.90^2 = 0.9 * 0.81 = 0.729
        assert abs(propagated.score - 0.729) < 0.01


class TestMultipleConfidenceCombination:
    """Test combining multiple confidence scores."""

    def test_combine_multiple_average(self, framework):
        """Test combining with average strategy."""
        confidences = [
            neural_confidence(0.8, "llm1"),
            neural_confidence(0.9, "llm2"),
            symbolic_confidence(1.0, "rule")
        ]

        combined = framework.combine_multiple(
            confidences,
            strategy=AggregationStrategy.AVERAGE
        )

        # (0.8 + 0.9 + 1.0) / 3 = 0.9
        assert abs(combined.score - 0.9) < 0.01

    def test_combine_multiple_min(self, framework):
        """Test combining with min strategy."""
        confidences = [
            neural_confidence(0.8, "llm1"),
            neural_confidence(0.9, "llm2"),
            symbolic_confidence(1.0, "rule")
        ]

        combined = framework.combine_multiple(
            confidences,
            strategy=AggregationStrategy.MIN
        )

        assert combined.score == 0.8

    def test_combine_multiple_max(self, framework):
        """Test combining with max strategy."""
        confidences = [
            neural_confidence(0.8, "llm1"),
            neural_confidence(0.9, "llm2"),
            symbolic_confidence(1.0, "rule")
        ]

        combined = framework.combine_multiple(
            confidences,
            strategy=AggregationStrategy.MAX
        )

        assert combined.score == 1.0

    def test_combine_multiple_weighted(self, framework):
        """Test combining with weighted average."""
        confidences = [
            neural_confidence(0.8, "llm1"),
            neural_confidence(0.9, "llm2"),
            symbolic_confidence(1.0, "rule")
        ]
        weights = [0.3, 0.3, 0.4]

        combined = framework.combine_multiple(
            confidences,
            strategy=AggregationStrategy.WEIGHTED_AVERAGE,
            weights=weights
        )

        # 0.8*0.3 + 0.9*0.3 + 1.0*0.4 = 0.24 + 0.27 + 0.4 = 0.91
        assert abs(combined.score - 0.91) < 0.01

    def test_combine_multiple_empty_raises(self, framework):
        """Test combining empty list raises error."""
        with pytest.raises(ValueError):
            framework.combine_multiple([])


class TestDecisionMaking:
    """Test confidence-based decision making."""

    def test_should_proceed_above_threshold(self, framework):
        """Test should proceed when above threshold."""
        conf = neural_confidence(0.90, "llm")

        should_proceed, reason = framework.should_proceed(conf)

        assert should_proceed is True
        assert "0.900" in reason
        assert "0.850" in reason

    def test_should_proceed_below_threshold(self, framework):
        """Test should not proceed when below threshold."""
        conf = neural_confidence(0.70, "llm")

        should_proceed, reason = framework.should_proceed(conf)

        assert should_proceed is False
        assert "0.700" in reason
        assert "0.850" in reason

    def test_should_proceed_custom_threshold(self, framework):
        """Test should proceed with custom threshold."""
        conf = neural_confidence(0.75, "llm")

        should_proceed, reason = framework.should_proceed(conf, threshold=0.70)

        assert should_proceed is True
        assert "0.750" in reason
        assert "0.700" in reason


class TestFeedbackRecording:
    """Test feedback recording and adaptive learning."""

    def test_record_feedback(self, framework):
        """Test recording validation feedback."""
        framework.record_feedback(
            operation_type="entity_creation",
            predicted_confidence=0.85,
            actual_outcome=True,
            metadata={"entity_id": "concept:customer"}
        )

        assert len(framework.feedback_history) == 1
        feedback = framework.feedback_history[0]

        assert feedback["operation_type"] == "entity_creation"
        assert feedback["predicted_confidence"] == 0.85
        assert feedback["actual_outcome"] is True
        assert feedback["metadata"]["entity_id"] == "concept:customer"

    def test_update_alpha_all_successes(self, framework):
        """Test alpha update with all successes."""
        # Record 10 successes
        for i in range(10):
            framework.record_feedback("test_op", 0.85, True)

        # Alpha should increase slightly
        assert "test_op" in framework.alpha_values
        assert framework.alpha_values["test_op"] > framework.config.alpha

    def test_update_alpha_all_failures(self, framework):
        """Test alpha update with all failures."""
        # Record 10 failures
        for i in range(10):
            framework.record_feedback("test_op", 0.85, False)

        # Alpha should decrease
        assert "test_op" in framework.alpha_values
        assert framework.alpha_values["test_op"] < framework.config.alpha

    def test_update_alpha_insufficient_samples(self, framework):
        """Test alpha not updated with insufficient samples."""
        # Record only 5 feedbacks (need 10)
        for i in range(5):
            framework.record_feedback("test_op", 0.85, True)

        # Alpha should not be set yet
        assert "test_op" not in framework.alpha_values

    def test_update_alpha_overconfident(self, framework):
        """Test alpha decreases when overconfident."""
        # Overconfident: higher confidence on failures than successes
        for i in range(10):
            if i < 5:
                # Failures with high confidence (overconfident)
                framework.record_feedback("test_op", 0.95, False)
            else:
                # Successes with lower confidence
                framework.record_feedback("test_op", 0.75, True)

        # Should decrease alpha (trust symbolic more)
        # avg_failure_conf (0.95) > avg_success_conf (0.75) → decrease alpha
        assert framework.alpha_values["test_op"] < framework.config.alpha


class TestWorkflowSummary:
    """Test workflow summary generation."""

    def test_get_workflow_summary(self, framework):
        """Test getting workflow summary."""
        framework.start_workflow("workflow_001")

        framework.add_step("workflow_001", "extraction", neural_confidence(0.75, "llm"))
        framework.add_step("workflow_001", "validation", symbolic_confidence(0.95, "shacl"))
        framework.add_step("workflow_001", "enrichment", neural_confidence(0.85, "llm"))

        summary = framework.get_workflow_summary("workflow_001")

        assert summary is not None
        assert summary["workflow_id"] == "workflow_001"
        assert summary["num_steps"] == 3
        assert summary["initial_confidence"] == 0.75
        assert summary["final_confidence"] == 0.85
        assert summary["min_confidence"] == 0.75
        assert summary["max_confidence"] == 0.95
        assert abs(summary["avg_confidence"] - 0.85) < 0.01
        assert summary["trend"] == "increasing"

    def test_get_workflow_summary_decreasing(self, framework):
        """Test workflow summary with decreasing trend."""
        framework.start_workflow("workflow_001")

        framework.add_step("workflow_001", "step1", neural_confidence(0.9, "llm"))
        framework.add_step("workflow_001", "step2", neural_confidence(0.7, "llm"))

        summary = framework.get_workflow_summary("workflow_001")

        assert summary["trend"] == "decreasing"

    def test_get_workflow_summary_not_found(self, framework):
        """Test summary for non-existent workflow."""
        summary = framework.get_workflow_summary("nonexistent")
        assert summary is None

    def test_get_workflow_summary_empty(self, framework):
        """Test summary for empty workflow."""
        framework.start_workflow("workflow_001")
        summary = framework.get_workflow_summary("workflow_001")
        assert summary is None


class TestConfigExportImport:
    """Test configuration export and import."""

    def test_export_config(self, framework):
        """Test exporting configuration."""
        # Add some learned alphas and feedback
        framework.alpha_values["op1"] = 0.65
        framework.alpha_values["op2"] = 0.70
        framework.record_feedback("op1", 0.85, True)

        config_data = framework.export_config()

        assert config_data["config"]["alpha"] == 0.6
        assert config_data["config"]["decay_factor"] == 0.95
        assert config_data["learned_alphas"]["op1"] == 0.65
        assert config_data["learned_alphas"]["op2"] == 0.70
        assert config_data["feedback_count"] == 1

    def test_import_config(self, framework):
        """Test importing configuration."""
        config_data = {
            "learned_alphas": {
                "op1": 0.75,
                "op2": 0.80
            },
            "feedback_count": 100
        }

        framework.import_config(config_data)

        assert framework.alpha_values["op1"] == 0.75
        assert framework.alpha_values["op2"] == 0.80

    def test_save_load_file(self, framework, tmp_path):
        """Test saving and loading from file."""
        # Setup framework with some data
        framework.alpha_values["op1"] = 0.65
        framework.record_feedback("op1", 0.85, True)

        # Save to file
        filepath = tmp_path / "config.json"
        framework.save_to_file(str(filepath))

        # Create new framework and load
        new_framework = ConfidenceFrameworkService()
        new_framework.load_from_file(str(filepath))

        assert new_framework.alpha_values["op1"] == 0.65


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_complete_workflow(self, framework):
        """Test complete workflow with multiple steps."""
        workflow_id = "dda_processing_001"

        # Start workflow
        framework.start_workflow(workflow_id)

        # Step 1: Entity extraction (neural)
        extraction_conf = neural_confidence(0.82, "llm_extractor")
        framework.add_step(
            workflow_id,
            "extraction",
            extraction_conf,
            outputs={"entities": 15}
        )

        # Step 2: SHACL validation (symbolic)
        validation_conf = symbolic_confidence(1.0, "shacl_validator")
        framework.add_step(
            workflow_id,
            "validation",
            validation_conf,
            outputs={"valid": True}
        )

        # Step 3: Combine for entity creation decision
        combined = framework.combine_neural_symbolic(
            extraction_conf,
            1.0,
            operation_type="entity_creation"
        )
        framework.add_step(workflow_id, "decision", combined)

        # Check if should proceed
        should_proceed, _ = framework.should_proceed(combined)
        assert should_proceed is True

        # Get summary
        summary = framework.get_workflow_summary(workflow_id)
        assert summary["num_steps"] == 3
        assert summary["trend"] == "increasing"

    def test_adaptive_learning_scenario(self, framework):
        """Test adaptive learning over multiple operations."""
        operation = "concept_inference"

        # Simulate 15 operations with feedback
        for i in range(15):
            # Predict with current alpha
            neural = neural_confidence(0.80, "llm")
            symbolic = 1.0

            combined = framework.combine_neural_symbolic(
                neural,
                symbolic,
                operation_type=operation,
                adaptive=True
            )

            # Simulate outcome (90% success rate)
            success = i < 13

            framework.record_feedback(
                operation,
                combined.score,
                success
            )

        # Alpha should have been adjusted
        assert operation in framework.alpha_values
        # With high success rate, alpha should increase
        assert framework.alpha_values[operation] >= framework.config.alpha
