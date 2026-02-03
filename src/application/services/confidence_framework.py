"""Confidence Framework Service.

This service provides practical confidence management for the neurosymbolic system:
- Tracks confidence through workflows
- Combines neural and symbolic confidences
- Manages confidence decay and propagation
- Learns confidence parameters from feedback
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

from domain.confidence_models import (
    Confidence,
    ConfidenceSource,
    ConfidenceCombination,
    AggregationStrategy,
    ConfidencePropagation,
    ConfidenceTracker,
    neural_confidence,
    symbolic_confidence
)

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceConfig:
    """Configuration for confidence framework."""
    # Neural-symbolic combination weight (0.0 = all symbolic, 1.0 = all neural)
    alpha: float = 0.6

    # Decay factor for reasoning chains
    decay_factor: float = 0.95

    # Minimum confidence threshold
    min_threshold: float = 0.1

    # High confidence threshold
    high_confidence_threshold: float = 0.85

    # Default aggregation strategy
    default_aggregation: AggregationStrategy = AggregationStrategy.WEIGHTED_AVERAGE

    # Learning rate for alpha adjustment
    learning_rate: float = 0.01


@dataclass
class WorkflowStep:
    """Represents a step in a confidence workflow."""
    step_name: str
    confidence: Confidence
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ConfidenceFrameworkService:
    """
    Service for managing confidence throughout the neurosymbolic workflow.

    Provides:
    - Confidence tracking across workflow steps
    - Neural-symbolic confidence combination
    - Confidence-based decision making
    - Adaptive learning from feedback
    """

    def __init__(self, config: Optional[ConfidenceConfig] = None):
        """
        Initialize the confidence framework.

        Args:
            config: Optional configuration (uses defaults if not provided)
        """
        self.config = config or ConfidenceConfig()
        self.propagator = ConfidencePropagation(
            decay_factor=self.config.decay_factor,
            min_threshold=self.config.min_threshold
        )

        # Track workflows
        self.workflows: Dict[str, List[WorkflowStep]] = {}

        # Track alpha values per operation type (for adaptive learning)
        self.alpha_values: Dict[str, float] = {}

        # Track validation feedback
        self.feedback_history: List[Dict[str, Any]] = []

    def start_workflow(self, workflow_id: str) -> None:
        """
        Start a new confidence tracking workflow.

        Args:
            workflow_id: Unique identifier for the workflow
        """
        if workflow_id in self.workflows:
            logger.warning(f"Workflow {workflow_id} already exists, resetting")

        self.workflows[workflow_id] = []
        logger.info(f"Started confidence workflow: {workflow_id}")

    def add_step(
        self,
        workflow_id: str,
        step_name: str,
        confidence: Confidence,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a step to a workflow.

        Args:
            workflow_id: Workflow identifier
            step_name: Name of this step
            confidence: Confidence at this step
            inputs: Optional input data
            outputs: Optional output data
        """
        if workflow_id not in self.workflows:
            logger.warning(f"Workflow {workflow_id} not found, creating")
            self.start_workflow(workflow_id)

        step = WorkflowStep(
            step_name=step_name,
            confidence=confidence,
            inputs=inputs or {},
            outputs=outputs or {}
        )

        self.workflows[workflow_id].append(step)
        logger.debug(f"Added step '{step_name}' to workflow {workflow_id} (confidence: {confidence.score:.3f})")

    def get_workflow_confidence(self, workflow_id: str) -> Optional[Confidence]:
        """
        Get the final confidence for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Final confidence or None if workflow not found
        """
        if workflow_id not in self.workflows:
            return None

        steps = self.workflows[workflow_id]
        if not steps:
            return None

        return steps[-1].confidence

    def combine_neural_symbolic(
        self,
        neural_conf: Confidence,
        symbolic_certainty: float,
        operation_type: str = "default",
        adaptive: bool = True
    ) -> Confidence:
        """
        Combine neural and symbolic confidence.

        Args:
            neural_conf: Neural model confidence
            symbolic_certainty: Symbolic rule certainty (0.0 or 1.0)
            operation_type: Type of operation (for adaptive alpha)
            adaptive: Whether to use adaptive alpha learning

        Returns:
            Combined hybrid confidence
        """
        # Get alpha for this operation type
        if adaptive and operation_type in self.alpha_values:
            alpha = self.alpha_values[operation_type]
            logger.debug(f"Using adaptive alpha={alpha:.3f} for {operation_type}")
        else:
            alpha = self.config.alpha

        # Combine using propagator
        combined = self.propagator.combine_with_rule(
            neural_conf,
            symbolic_certainty,
            alpha=alpha
        )

        # Add metadata about combination
        combined.properties.update({
            "operation_type": operation_type,
            "alpha": alpha,
            "adaptive": adaptive,
            "neural_score": neural_conf.score,
            "symbolic_certainty": symbolic_certainty
        })

        return combined

    def propagate_confidence(
        self,
        initial_confidence: Confidence,
        num_steps: int
    ) -> Confidence:
        """
        Propagate confidence through a reasoning chain.

        Args:
            initial_confidence: Starting confidence
            num_steps: Number of reasoning steps

        Returns:
            Propagated confidence
        """
        return self.propagator.propagate(initial_confidence, num_steps)

    def combine_multiple(
        self,
        confidences: List[Confidence],
        strategy: Optional[AggregationStrategy] = None,
        weights: Optional[List[float]] = None
    ) -> Confidence:
        """
        Combine multiple confidence scores.

        Args:
            confidences: List of confidence scores
            strategy: Aggregation strategy (uses default if not provided)
            weights: Optional weights for weighted average

        Returns:
            Combined confidence
        """
        if not confidences:
            raise ValueError("Cannot combine empty confidence list")

        strategy = strategy or self.config.default_aggregation

        combination = ConfidenceCombination.combine(
            confidences,
            strategy=strategy,
            weights=weights
        )

        # Create result confidence
        result = Confidence(
            score=combination.combined_score,
            source=ConfidenceSource.HYBRID,
            generated_by="confidence_framework",
            evidence=[f"Combined {len(confidences)} confidences using {strategy.value}"],
            reasoning=f"Aggregated using {strategy.value} strategy"
        )

        return result

    def should_proceed(
        self,
        confidence: Confidence,
        threshold: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Determine if an operation should proceed based on confidence.

        Args:
            confidence: Confidence to evaluate
            threshold: Optional threshold (uses high_confidence_threshold if not provided)

        Returns:
            Tuple of (should_proceed, reason)
        """
        threshold = threshold or self.config.high_confidence_threshold

        if confidence.score >= threshold:
            return True, f"Confidence {confidence.score:.3f} >= threshold {threshold:.3f}"
        else:
            return False, f"Confidence {confidence.score:.3f} < threshold {threshold:.3f}"

    def record_feedback(
        self,
        operation_type: str,
        predicted_confidence: float,
        actual_outcome: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record validation feedback for adaptive learning.

        Args:
            operation_type: Type of operation
            predicted_confidence: Confidence that was predicted
            actual_outcome: Whether operation succeeded (True) or failed (False)
            metadata: Optional additional metadata
        """
        feedback = {
            "operation_type": operation_type,
            "predicted_confidence": predicted_confidence,
            "actual_outcome": actual_outcome,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        self.feedback_history.append(feedback)
        logger.info(
            f"Recorded feedback: {operation_type}, confidence={predicted_confidence:.3f}, "
            f"outcome={'SUCCESS' if actual_outcome else 'FAILURE'}"
        )

        # Update alpha if we have enough feedback
        self._update_alpha(operation_type)

    def _update_alpha(self, operation_type: str) -> None:
        """
        Update alpha value based on feedback history.

        Simple adaptive algorithm:
        - If predictions are overconfident (high confidence but failures), decrease alpha (trust symbolic more)
        - If predictions are underconfident (low confidence but successes), increase alpha (trust neural more)
        """
        # Get recent feedback for this operation type
        recent_feedback = [
            f for f in self.feedback_history[-100:]  # Last 100 feedback items
            if f["operation_type"] == operation_type
        ]

        if len(recent_feedback) < 10:
            return  # Need at least 10 samples

        # Calculate metrics
        successes = [f for f in recent_feedback if f["actual_outcome"]]
        failures = [f for f in recent_feedback if not f["actual_outcome"]]

        if not failures:
            # All successes, slightly increase alpha
            current_alpha = self.alpha_values.get(operation_type, self.config.alpha)
            new_alpha = min(1.0, current_alpha + self.config.learning_rate)
            self.alpha_values[operation_type] = new_alpha
            logger.debug(f"Increased alpha for {operation_type}: {current_alpha:.3f} → {new_alpha:.3f}")

        elif not successes:
            # All failures, slightly decrease alpha
            current_alpha = self.alpha_values.get(operation_type, self.config.alpha)
            new_alpha = max(0.0, current_alpha - self.config.learning_rate)
            self.alpha_values[operation_type] = new_alpha
            logger.debug(f"Decreased alpha for {operation_type}: {current_alpha:.3f} → {new_alpha:.3f}")

        else:
            # Mixed results, check if overconfident or underconfident
            avg_success_conf = sum(f["predicted_confidence"] for f in successes) / len(successes)
            avg_failure_conf = sum(f["predicted_confidence"] for f in failures) / len(failures)

            current_alpha = self.alpha_values.get(operation_type, self.config.alpha)

            if avg_failure_conf > avg_success_conf:
                # Overconfident - decrease alpha
                new_alpha = max(0.0, current_alpha - self.config.learning_rate)
            else:
                # Underconfident - increase alpha
                new_alpha = min(1.0, current_alpha + self.config.learning_rate)

            self.alpha_values[operation_type] = new_alpha
            logger.debug(f"Adjusted alpha for {operation_type}: {current_alpha:.3f} → {new_alpha:.3f}")

    def get_workflow_summary(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of a workflow's confidence evolution.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Summary dictionary or None if workflow not found
        """
        if workflow_id not in self.workflows:
            return None

        steps = self.workflows[workflow_id]
        if not steps:
            return None

        confidences = [step.confidence.score for step in steps]

        return {
            "workflow_id": workflow_id,
            "num_steps": len(steps),
            "initial_confidence": confidences[0],
            "final_confidence": confidences[-1],
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
            "avg_confidence": sum(confidences) / len(confidences),
            "trend": "increasing" if confidences[-1] > confidences[0] else "decreasing",
            "steps": [
                {
                    "name": step.step_name,
                    "confidence": step.confidence.score,
                    "source": step.confidence.source.value
                }
                for step in steps
            ]
        }

    def export_config(self) -> Dict[str, Any]:
        """Export configuration and learned parameters."""
        return {
            "config": {
                "alpha": self.config.alpha,
                "decay_factor": self.config.decay_factor,
                "min_threshold": self.config.min_threshold,
                "high_confidence_threshold": self.config.high_confidence_threshold,
                "learning_rate": self.config.learning_rate
            },
            "learned_alphas": self.alpha_values.copy(),
            "feedback_count": len(self.feedback_history)
        }

    def import_config(self, config_data: Dict[str, Any]) -> None:
        """Import configuration and learned parameters."""
        if "learned_alphas" in config_data:
            self.alpha_values.update(config_data["learned_alphas"])
            logger.info(f"Imported {len(self.alpha_values)} learned alpha values")

    def save_to_file(self, filepath: str) -> None:
        """Save configuration to file."""
        with open(filepath, 'w') as f:
            json.dump(self.export_config(), f, indent=2)
        logger.info(f"Saved confidence framework config to {filepath}")

    def load_from_file(self, filepath: str) -> None:
        """Load configuration from file."""
        with open(filepath, 'r') as f:
            config_data = json.load(f)
        self.import_config(config_data)
        logger.info(f"Loaded confidence framework config from {filepath}")
