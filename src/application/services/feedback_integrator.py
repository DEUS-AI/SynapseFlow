"""Feedback Integration Service.

This service captures validation results and uses them to improve the neurosymbolic system:
- Tracks which operations succeed/fail
- Suggests new symbolic rules from successful neural patterns
- Detects model drift
- Generates calibration reports
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class ValidationFeedback:
    """Represents feedback from a validation operation."""
    operation_id: str
    operation_type: str  # entity_creation, relationship_inference, etc.
    predicted_confidence: float
    actual_outcome: bool  # True = success, False = failure
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)

    # What was predicted
    predicted_action: str = ""  # e.g., "create entity Customer"

    # Actual validation results
    validation_errors: List[str] = field(default_factory=list)
    symbolic_rules_matched: List[str] = field(default_factory=list)

    # Metadata for learning
    neural_features: Dict[str, Any] = field(default_factory=dict)
    graph_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleSuggestion:
    """Suggestion for a new symbolic rule based on patterns."""
    rule_type: str  # validation, inference, constraint
    rule_description: str
    confidence: float
    supporting_examples: List[str]
    pattern: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DriftDetection:
    """Model drift detection result."""
    drift_detected: bool
    drift_score: float  # 0.0-1.0, higher = more drift
    affected_operations: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    recommendations: List[str] = field(default_factory=list)


class FeedbackIntegrator:
    """
    Service for integrating validation feedback into the neurosymbolic system.

    Responsibilities:
    - Collect and store validation feedback
    - Detect patterns in successful operations
    - Suggest new symbolic rules from patterns
    - Detect model drift
    - Generate calibration reports
    """

    def __init__(
        self,
        drift_window_days: int = 7,
        pattern_min_support: int = 5,
        rule_confidence_threshold: float = 0.85
    ):
        """
        Initialize feedback integrator.

        Args:
            drift_window_days: Days to look back for drift detection
            pattern_min_support: Minimum occurrences to suggest a rule
            rule_confidence_threshold: Minimum confidence for rule suggestions
        """
        self.drift_window_days = drift_window_days
        self.pattern_min_support = pattern_min_support
        self.rule_confidence_threshold = rule_confidence_threshold

        # Storage
        self.feedback_history: List[ValidationFeedback] = []
        self.rule_suggestions: List[RuleSuggestion] = []
        self.drift_history: List[DriftDetection] = []

        # Statistics per operation type
        self.operation_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total": 0,
            "successes": 0,
            "failures": 0,
            "avg_confidence": 0.0,
            "last_updated": None
        })

    def record_feedback(self, feedback: ValidationFeedback) -> None:
        """
        Record validation feedback.

        Args:
            feedback: Validation feedback to record
        """
        self.feedback_history.append(feedback)

        # Update statistics
        stats = self.operation_stats[feedback.operation_type]
        stats["total"] += 1

        if feedback.actual_outcome:
            stats["successes"] += 1
        else:
            stats["failures"] += 1

        # Update average confidence
        total = stats["total"]
        prev_avg = stats["avg_confidence"]
        stats["avg_confidence"] = (prev_avg * (total - 1) + feedback.predicted_confidence) / total
        stats["last_updated"] = datetime.now()

        logger.info(
            f"Recorded feedback: {feedback.operation_type}, "
            f"confidence={feedback.predicted_confidence:.3f}, "
            f"outcome={'SUCCESS' if feedback.actual_outcome else 'FAILURE'}"
        )

        # Trigger pattern analysis periodically
        if stats["total"] % 10 == 0:
            self._analyze_patterns(feedback.operation_type)

    def get_operation_stats(self, operation_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for an operation type or all operations.

        Args:
            operation_type: Specific operation type or None for all

        Returns:
            Statistics dictionary
        """
        if operation_type:
            return dict(self.operation_stats.get(operation_type, {}))

        return {op_type: dict(stats) for op_type, stats in self.operation_stats.items()}

    def detect_drift(self, operation_type: Optional[str] = None) -> Optional[DriftDetection]:
        """
        Detect model drift for an operation type.

        Compares recent performance (last N days) with historical baseline.

        Args:
            operation_type: Operation type to check, or None for overall

        Returns:
            DriftDetection result or None if insufficient data
        """
        cutoff_date = datetime.now() - timedelta(days=self.drift_window_days)

        # Get recent and historical feedback
        recent_feedback = [
            f for f in self.feedback_history
            if f.timestamp >= cutoff_date
            and (operation_type is None or f.operation_type == operation_type)
        ]

        historical_feedback = [
            f for f in self.feedback_history
            if f.timestamp < cutoff_date
            and (operation_type is None or f.operation_type == operation_type)
        ]

        if len(recent_feedback) < 10 or len(historical_feedback) < 10:
            logger.warning("Insufficient data for drift detection")
            return None

        # Calculate success rates
        recent_success_rate = sum(1 for f in recent_feedback if f.actual_outcome) / len(recent_feedback)
        historical_success_rate = sum(1 for f in historical_feedback if f.actual_outcome) / len(historical_feedback)

        # Calculate confidence calibration (are high confidence predictions actually succeeding?)
        recent_high_conf = [f for f in recent_feedback if f.predicted_confidence > 0.8]
        recent_high_conf_success = sum(1 for f in recent_high_conf if f.actual_outcome) / max(len(recent_high_conf), 1)

        historical_high_conf = [f for f in historical_feedback if f.predicted_confidence > 0.8]
        historical_high_conf_success = sum(1 for f in historical_high_conf if f.actual_outcome) / max(len(historical_high_conf), 1)

        # Drift score: combination of success rate drop and calibration degradation
        success_rate_drift = max(0, historical_success_rate - recent_success_rate)
        calibration_drift = max(0, historical_high_conf_success - recent_high_conf_success)

        drift_score = (success_rate_drift * 0.6 + calibration_drift * 0.4)

        # Threshold for drift detection
        drift_detected = drift_score > 0.15

        recommendations = []
        if drift_detected:
            recommendations.append(f"Success rate dropped from {historical_success_rate:.2%} to {recent_success_rate:.2%}")
            recommendations.append(f"High-confidence calibration: {historical_high_conf_success:.2%} → {recent_high_conf_success:.2%}")

            if success_rate_drift > 0.1:
                recommendations.append("Consider retraining neural components")

            if calibration_drift > 0.1:
                recommendations.append("Recalibrate confidence thresholds")

        affected_ops = [operation_type] if operation_type else list(set(f.operation_type for f in recent_feedback))

        result = DriftDetection(
            drift_detected=drift_detected,
            drift_score=drift_score,
            affected_operations=affected_ops,
            recommendations=recommendations
        )

        self.drift_history.append(result)

        if drift_detected:
            logger.warning(
                f"Drift detected for {operation_type or 'all operations'}: "
                f"score={drift_score:.3f}"
            )

        return result

    def suggest_rules(
        self,
        operation_type: Optional[str] = None,
        min_confidence: Optional[float] = None
    ) -> List[RuleSuggestion]:
        """
        Get rule suggestions for an operation type.

        Args:
            operation_type: Filter by operation type
            min_confidence: Minimum confidence threshold

        Returns:
            List of rule suggestions
        """
        min_conf = min_confidence or self.rule_confidence_threshold

        suggestions = [
            s for s in self.rule_suggestions
            if (operation_type is None or operation_type in s.supporting_examples[0])
            and s.confidence >= min_conf
        ]

        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)

        return suggestions

    def _analyze_patterns(self, operation_type: str) -> None:
        """
        Analyze patterns in successful operations to suggest new rules.

        Args:
            operation_type: Operation type to analyze
        """
        # Get successful operations
        successes = [
            f for f in self.feedback_history
            if f.operation_type == operation_type
            and f.actual_outcome
            and f.predicted_confidence > self.rule_confidence_threshold
        ]

        if len(successes) < self.pattern_min_support:
            return

        # Group by predicted action patterns
        action_patterns = defaultdict(list)
        for feedback in successes:
            # Extract pattern from predicted action
            pattern_key = self._extract_pattern(feedback)
            if pattern_key:
                action_patterns[pattern_key].append(feedback)

        # Suggest rules for frequent patterns
        for pattern_key, examples in action_patterns.items():
            if len(examples) >= self.pattern_min_support:
                # Check if we already have this suggestion
                existing = any(
                    s.pattern.get("key") == pattern_key
                    for s in self.rule_suggestions
                )

                if not existing:
                    confidence = len(examples) / len(successes)

                    if confidence >= self.rule_confidence_threshold:
                        suggestion = RuleSuggestion(
                            rule_type="validation",
                            rule_description=f"Pattern '{pattern_key}' consistently succeeds",
                            confidence=confidence,
                            supporting_examples=[e.operation_id for e in examples[:5]],
                            pattern={"key": pattern_key, "operation_type": operation_type}
                        )

                        self.rule_suggestions.append(suggestion)

                        logger.info(
                            f"Suggested new rule: {suggestion.rule_description} "
                            f"(confidence={confidence:.2%}, support={len(examples)})"
                        )

    def _extract_pattern(self, feedback: ValidationFeedback) -> Optional[str]:
        """
        Extract a pattern from feedback for rule suggestion.

        Args:
            feedback: Validation feedback

        Returns:
            Pattern key or None
        """
        # Simple pattern extraction based on predicted action
        action = feedback.predicted_action.lower()

        # Extract entity type patterns
        if "create entity" in action:
            # Pattern: "create entity {type}"
            parts = action.split()
            if len(parts) >= 3:
                return f"create_entity_{parts[2]}"

        elif "infer relationship" in action:
            # Pattern: "infer relationship {type}"
            parts = action.split()
            if len(parts) >= 3:
                return f"infer_relationship_{parts[2]}"

        # Extract from context
        if "entity_type" in feedback.context:
            return f"{feedback.operation_type}_{feedback.context['entity_type']}"

        return None

    def generate_calibration_report(self) -> Dict[str, Any]:
        """
        Generate a confidence calibration report.

        Shows how well predicted confidences match actual outcomes.

        Returns:
            Calibration report dictionary
        """
        if not self.feedback_history:
            return {"error": "No feedback data available"}

        # Bin predictions by confidence ranges
        bins = {
            "0.0-0.2": [],
            "0.2-0.4": [],
            "0.4-0.6": [],
            "0.6-0.8": [],
            "0.8-1.0": []
        }

        for feedback in self.feedback_history:
            conf = feedback.predicted_confidence

            if conf < 0.2:
                bin_key = "0.0-0.2"
            elif conf < 0.4:
                bin_key = "0.2-0.4"
            elif conf < 0.6:
                bin_key = "0.4-0.6"
            elif conf < 0.8:
                bin_key = "0.6-0.8"
            else:
                bin_key = "0.8-1.0"

            bins[bin_key].append(feedback)

        # Calculate actual success rate for each bin
        calibration_data = {}
        for bin_key, feedbacks in bins.items():
            if not feedbacks:
                continue

            success_rate = sum(1 for f in feedbacks if f.actual_outcome) / len(feedbacks)
            avg_predicted_conf = sum(f.predicted_confidence for f in feedbacks) / len(feedbacks)

            calibration_data[bin_key] = {
                "count": len(feedbacks),
                "avg_predicted_confidence": avg_predicted_conf,
                "actual_success_rate": success_rate,
                "calibration_error": abs(avg_predicted_conf - success_rate)
            }

        # Overall calibration error (mean absolute error)
        total_error = sum(data["calibration_error"] * data["count"] for data in calibration_data.values())
        total_count = sum(data["count"] for data in calibration_data.values())
        overall_error = total_error / total_count if total_count > 0 else 0

        return {
            "total_predictions": len(self.feedback_history),
            "overall_success_rate": sum(1 for f in self.feedback_history if f.actual_outcome) / len(self.feedback_history),
            "overall_calibration_error": overall_error,
            "calibration_quality": "good" if overall_error < 0.1 else "needs_improvement" if overall_error < 0.2 else "poor",
            "bins": calibration_data,
            "generated_at": datetime.now().isoformat()
        }

    def export_data(self, filepath: str) -> None:
        """
        Export feedback data to file.

        Args:
            filepath: Path to export file
        """
        data = {
            "feedback_count": len(self.feedback_history),
            "operation_stats": {k: dict(v) for k, v in self.operation_stats.items()},
            "rule_suggestions_count": len(self.rule_suggestions),
            "drift_detections_count": len(self.drift_history),
            "exported_at": datetime.now().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Exported feedback data to {filepath}")

    def clear_old_feedback(self, days_to_keep: int = 30) -> int:
        """
        Clear feedback older than specified days.

        Args:
            days_to_keep: Number of days of feedback to retain

        Returns:
            Number of feedback items removed
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        original_count = len(self.feedback_history)
        self.feedback_history = [
            f for f in self.feedback_history
            if f.timestamp >= cutoff_date
        ]

        removed = original_count - len(self.feedback_history)

        if removed > 0:
            logger.info(f"Cleared {removed} old feedback items (kept last {days_to_keep} days)")

        return removed
