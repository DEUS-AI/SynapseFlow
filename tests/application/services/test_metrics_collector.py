"""Tests for MetricsCollector service."""

import pytest
from unittest.mock import MagicMock

from application.services.metrics_collector import MetricsCollector, AGENT_METRIC_DEFINITIONS
from domain.agent_metrics import AgentMetricSnapshot, AgentPerformanceProfile


class TestMetricsCollector:
    def setup_method(self):
        self.feedback = MagicMock()
        self.discovery = MagicMock()
        self.collector = MetricsCollector(
            feedback_integrator=self.feedback,
            discovery_service=self.discovery,
        )

    def test_collect_metric_returns_snapshot(self):
        self.feedback.get_operation_stats.return_value = {
            "total": 10, "successes": 8, "failures": 2, "avg_confidence": 0.85
        }
        snap = self.collector.collect_metric("knowledge_manager_1", "validation_accuracy")
        assert isinstance(snap, AgentMetricSnapshot)
        assert snap.agent_id == "knowledge_manager_1"
        assert snap.metric_name == "validation_accuracy"
        assert snap.value == pytest.approx(0.8)

    def test_collect_metric_no_feedback(self):
        collector = MetricsCollector()
        snap = collector.collect_metric("km", "validation_accuracy")
        assert snap.value == 0.0

    def test_collect_agent_metrics_profile(self):
        # get_operation_stats is called with and without args;
        # with arg returns flat stats, without returns dict-of-dicts
        single_stats = {"total": 10, "successes": 9, "failures": 1, "avg_confidence": 0.9}
        all_stats = {"entity_creation": single_stats, "conflict_resolution": single_stats}

        def mock_get_stats(op_type=None):
            if op_type:
                return dict(single_stats)
            return dict(all_stats)

        self.feedback.get_operation_stats = mock_get_stats
        self.feedback.generate_calibration_report.return_value = {"overall_calibration_error": 0.05}
        self.feedback.detect_drift.return_value = None

        profile = self.collector.collect_agent_metrics("knowledge_manager_1")
        assert isinstance(profile, AgentPerformanceProfile)
        assert profile.agent_id == "knowledge_manager_1"
        assert "validation_accuracy" in profile.metrics

    def test_update_and_get_baseline(self):
        self.collector.update_baseline("km", "accuracy", 0.85)
        assert self.collector.get_baseline("km", "accuracy") == pytest.approx(0.85)
        assert self.collector.get_baseline("km", "nonexistent") is None

    def test_drift_scores_computed(self):
        self.collector.update_baseline("knowledge_manager_1", "validation_accuracy", 0.9)
        single_stats = {"total": 10, "successes": 7, "failures": 3, "avg_confidence": 0.8}
        all_stats = {"entity_creation": single_stats}

        def mock_get_stats(op_type=None):
            if op_type:
                return dict(single_stats)
            return dict(all_stats)

        self.feedback.get_operation_stats = mock_get_stats
        self.feedback.generate_calibration_report.return_value = {"overall_calibration_error": 0.1}
        self.feedback.detect_drift.return_value = None

        profile = self.collector.collect_agent_metrics("knowledge_manager_1")
        assert "validation_accuracy" in profile.drift_scores

    def test_known_metrics_for_km(self):
        assert "knowledge_manager" in AGENT_METRIC_DEFINITIONS
        assert "validation_accuracy" in AGENT_METRIC_DEFINITIONS["knowledge_manager"]
