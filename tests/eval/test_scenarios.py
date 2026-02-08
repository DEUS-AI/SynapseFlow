"""
Scenario-based evaluation tests.

These tests execute YAML scenarios against the API and collect results
for report generation. Run with:

    uv run pytest tests/eval/test_scenarios.py -v --eval-report

Note: These tests require the API to be running and EVAL_API_KEY to be set.
For unit tests that don't require the API, see tests/eval/runner/
"""

import pytest
from tests.eval.runner import Scenario, EvalResult


# ========================================
# Dynamic Scenario Tests
# ========================================

@pytest.mark.eval_integration
class TestEvalScenarios:
    """
    Dynamic test class that runs all loaded YAML scenarios.

    The `eval_scenario` fixture is populated by pytest_generate_tests
    in pytest_plugin.py based on the YAML files in tests/eval/scenarios/.

    Filter scenarios with:
        --eval-severity=critical
        --eval-category=regression
        --eval-tag=medication
    """

    def test_scenario(self, run_eval_scenario, eval_scenario: Scenario, request):
        """
        Run a single evaluation scenario.

        This test is parametrized dynamically from YAML scenarios.
        Results are collected for report generation.
        """
        result: EvalResult = run_eval_scenario(eval_scenario)

        # Build detailed failure message if needed
        if not result.passed:
            failures = []
            for turn in result.turns:
                for assertion in turn.failed_assertions:
                    failures.append(
                        f"  Turn {turn.turn_number}: [{assertion.assertion_type}] "
                        f"{assertion.reason}"
                    )

            failure_msg = "\n".join(failures) if failures else result.error or "Unknown error"
            pytest.fail(
                f"Scenario '{result.scenario_id}' ({result.severity}) failed:\n{failure_msg}"
            )


# ========================================
# Category-Specific Tests
# ========================================

@pytest.mark.eval_critical
@pytest.mark.eval_integration
class TestCriticalScenarios:
    """Tests for critical-severity scenarios only."""

    @pytest.fixture(autouse=True)
    def skip_non_critical(self, eval_scenario: Scenario):
        """Skip non-critical scenarios in this class."""
        if eval_scenario.severity != "critical":
            pytest.skip(f"Skipping non-critical scenario: {eval_scenario.id}")

    def test_critical_scenario(self, run_eval_scenario, eval_scenario: Scenario):
        """Critical scenarios must never fail."""
        result = run_eval_scenario(eval_scenario)
        assert result.passed, f"CRITICAL scenario failed: {eval_scenario.id}"


@pytest.mark.eval_regression
@pytest.mark.eval_integration
class TestRegressionScenarios:
    """Tests for regression scenarios (from previous bugs)."""

    @pytest.fixture(autouse=True)
    def skip_non_regression(self, eval_scenario: Scenario):
        """Skip non-regression scenarios in this class."""
        if eval_scenario.category != "regression":
            pytest.skip(f"Skipping non-regression scenario: {eval_scenario.id}")

    def test_regression_scenario(self, run_eval_scenario, eval_scenario: Scenario):
        """Regression scenarios verify bug fixes remain fixed."""
        result = run_eval_scenario(eval_scenario)
        assert result.passed, f"REGRESSION detected: {eval_scenario.id} - Bug may have returned!"
