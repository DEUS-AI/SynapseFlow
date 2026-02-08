"""
Pytest Plugin for Scenario-Based Evaluation Tests.

This module provides pytest hooks and fixtures to automatically discover
and run YAML-based evaluation scenarios as pytest tests.

Usage:
    # In conftest.py
    pytest_plugins = ["tests.eval.pytest_plugin"]

    # Run all evaluation tests
    pytest tests/eval/scenarios/ -v

    # Run only critical scenarios
    pytest tests/eval/scenarios/ -v --eval-severity=critical

    # Run with reports
    pytest tests/eval/scenarios/ -v --eval-report
"""

import asyncio
import os
import pytest
from pathlib import Path
from typing import List, Optional

from tests.eval.runner import (
    ScenarioLoader,
    ScenarioOrchestrator,
    MemoryInspector,
    Scenario,
    EvalResult,
)
from tests.eval.runner.evaluators import create_mock_judge, LLMJudgeEvaluator
from tests.eval.runner.reporting import ReportManager, SuiteReport


# ========================================
# Pytest Configuration
# ========================================

def pytest_addoption(parser):
    """Add command-line options for evaluation tests."""
    group = parser.getgroup("eval", "Evaluation Framework Options")

    group.addoption(
        "--eval-api-url",
        action="store",
        default=os.getenv("EVAL_API_URL", "http://localhost:8000"),
        help="Base URL for the evaluation API",
    )

    group.addoption(
        "--eval-api-key",
        action="store",
        default=os.getenv("EVAL_API_KEY", ""),
        help="API key for the evaluation API",
    )

    group.addoption(
        "--eval-scenarios-dir",
        action="store",
        default=None,
        help="Directory containing scenario YAML files",
    )

    group.addoption(
        "--eval-category",
        action="store",
        default=None,
        help="Filter scenarios by category",
    )

    group.addoption(
        "--eval-severity",
        action="store",
        default=None,
        help="Filter scenarios by severity (critical, high, medium, low)",
    )

    group.addoption(
        "--eval-tag",
        action="store",
        default=None,
        help="Filter scenarios by tag",
    )

    group.addoption(
        "--eval-report",
        action="store_true",
        default=False,
        help="Generate HTML and JSON reports after test run",
    )

    group.addoption(
        "--eval-report-dir",
        action="store",
        default="eval_reports",
        help="Directory for evaluation reports",
    )

    group.addoption(
        "--eval-use-mock-judge",
        action="store_true",
        default=True,
        help="Use mock LLM judge (default: True for CI/CD)",
    )

    group.addoption(
        "--eval-judge-model",
        action="store",
        default="gpt-4o-mini",
        help="Model to use for LLM judge evaluations",
    )


def pytest_configure(config):
    """Register custom markers and store config."""
    # Register markers
    config.addinivalue_line(
        "markers",
        "eval_scenario: Mark test as an evaluation scenario test",
    )
    config.addinivalue_line(
        "markers",
        "eval_critical: Mark test as a critical severity scenario",
    )
    config.addinivalue_line(
        "markers",
        "eval_regression: Mark test as a regression test",
    )

    # Initialize results collector for reporting
    config._eval_results: List[EvalResult] = []


def pytest_unconfigure(config):
    """Generate reports after test run if requested."""
    if not hasattr(config, "_eval_results"):
        return

    # Check if report generation is requested
    generate_report = config.getoption("--eval-report", default=False)
    results = config._eval_results

    if not results:
        if generate_report:
            print("\n" + "=" * 60)
            print("EVAL REPORT: No scenario results collected.")
            print("=" * 60)
            print("Reports are only generated when running scenario tests.")
            print("Unit tests (tests/eval/runner/) don't generate reports.")
            print("\nTo generate reports, run scenario tests with the API running:")
            print("  1. Start the API: uv run uvicorn src.application.api.main:app")
            print("  2. Set EVAL_API_KEY environment variable")
            print("  3. Run: uv run pytest tests/eval/test_scenarios.py --eval-report")
            print("=" * 60 + "\n")
        return

    if generate_report:
        report_dir = config.getoption("--eval-report-dir", default="eval_reports")
        manager = ReportManager(output_dir=report_dir)
        suite = manager.generate_all(results, name="Pytest Evaluation Run", print_console=False)
        print("\n" + "=" * 60)
        print(f"EVAL REPORT: Generated in {report_dir}/")
        print("=" * 60)
        print(f"  Scenarios: {suite.passed_scenarios}/{suite.total_scenarios} passed")
        print(f"  Assertions: {suite.passed_assertions}/{suite.total_assertions} passed")
        print(f"  Pass rate: {suite.pass_rate * 100:.1f}%")
        print("=" * 60 + "\n")


# ========================================
# Fixtures
# ========================================

@pytest.fixture(scope="session")
def eval_config(request):
    """Get evaluation configuration from pytest options."""
    return {
        "api_url": request.config.getoption("--eval-api-url"),
        "api_key": request.config.getoption("--eval-api-key"),
        "scenarios_dir": request.config.getoption("--eval-scenarios-dir"),
        "category": request.config.getoption("--eval-category"),
        "severity": request.config.getoption("--eval-severity"),
        "tag": request.config.getoption("--eval-tag"),
        "use_mock_judge": request.config.getoption("--eval-use-mock-judge"),
        "judge_model": request.config.getoption("--eval-judge-model"),
    }


@pytest.fixture(scope="session")
def eval_memory_inspector(eval_config):
    """Create a MemoryInspector for evaluation tests."""
    api_key = eval_config["api_key"]
    if not api_key:
        pytest.skip("EVAL_API_KEY not configured")

    return MemoryInspector(
        base_url=eval_config["api_url"],
        api_key=api_key,
    )


@pytest.fixture(scope="session")
def eval_judge(eval_config):
    """Create an LLM judge for evaluation tests."""
    if eval_config["use_mock_judge"]:
        return create_mock_judge(default_score=4)

    # Try to create a real judge
    try:
        from tests.eval.runner.evaluators import create_openai_judge
        return create_openai_judge(model=eval_config["judge_model"])
    except Exception:
        # Fall back to mock
        return create_mock_judge(default_score=4)


@pytest.fixture(scope="session")
def eval_orchestrator(eval_memory_inspector, eval_judge):
    """Create a ScenarioOrchestrator for evaluation tests."""
    return ScenarioOrchestrator(
        memory_inspector=eval_memory_inspector,
        judge_evaluator=eval_judge,
        turn_timeout=60.0,
        quiescence_timeout=120.0,
    )


@pytest.fixture(scope="session")
def eval_scenario_loader(eval_config):
    """Create a ScenarioLoader for evaluation tests."""
    scenarios_dir = eval_config["scenarios_dir"]
    if not scenarios_dir:
        # Default to tests/eval/scenarios
        scenarios_dir = Path(__file__).parent / "scenarios"

    return ScenarioLoader(scenarios_dir=str(scenarios_dir))


# ========================================
# Test Generation
# ========================================

def pytest_generate_tests(metafunc):
    """Generate parametrized tests from YAML scenarios."""
    # Only process tests that use the 'eval_scenario' fixture
    if "eval_scenario" not in metafunc.fixturenames:
        return

    # Get configuration
    config = metafunc.config
    scenarios_dir = config.getoption("--eval-scenarios-dir")
    if not scenarios_dir:
        scenarios_dir = Path(__file__).parent / "scenarios"

    category = config.getoption("--eval-category")
    severity = config.getoption("--eval-severity")
    tag = config.getoption("--eval-tag")

    # Load scenarios
    try:
        loader = ScenarioLoader(scenarios_dir=str(scenarios_dir))
        scenarios = loader.load_all_scenarios(
            category=category,
            severity=severity,
            tag=tag,
        )
    except Exception as e:
        # No scenarios found, skip test generation
        scenarios = []

    if not scenarios:
        return

    # Generate test IDs
    ids = [f"{s.category}/{s.id}" for s in scenarios]

    # Parametrize the test
    metafunc.parametrize("eval_scenario", scenarios, ids=ids)


# ========================================
# Helper Functions
# ========================================

def run_scenario_sync(
    orchestrator: ScenarioOrchestrator,
    scenario: Scenario,
) -> EvalResult:
    """Run a scenario synchronously (for pytest compatibility)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(orchestrator.run_scenario(scenario))
    finally:
        loop.close()


# ========================================
# Example Test Function
# ========================================

@pytest.fixture
def run_eval_scenario(eval_orchestrator, request):
    """
    Factory fixture for running evaluation scenarios.

    Usage in test files:
        def test_my_scenario(run_eval_scenario, eval_scenario):
            result = run_eval_scenario(eval_scenario)
            assert result.passed, f"Scenario failed: {result.error}"
    """
    def _run(scenario: Scenario) -> EvalResult:
        result = run_scenario_sync(eval_orchestrator, scenario)

        # Store result for reporting
        if hasattr(request.config, "_eval_results"):
            request.config._eval_results.append(result)

        return result

    return _run


# ========================================
# Assertion Helpers
# ========================================

def assert_scenario_passed(result: EvalResult, msg: str = "") -> None:
    """Assert that a scenario passed, with detailed failure message."""
    if result.passed:
        return

    # Build detailed failure message
    failures = []
    for turn in result.turns:
        for assertion in turn.failed_assertions:
            failures.append(
                f"  Turn {turn.turn_number}: [{assertion.assertion_type}] "
                f"{assertion.reason}\n    Details: {assertion.details}"
            )

    failure_details = "\n".join(failures) if failures else result.error or "Unknown error"

    pytest.fail(
        f"{msg}\n"
        f"Scenario '{result.scenario_id}' ({result.severity}) failed:\n"
        f"{failure_details}"
    )


def assert_no_critical_failures(results: List[EvalResult], msg: str = "") -> None:
    """Assert that no critical-severity scenarios failed."""
    critical_failures = [
        r for r in results
        if not r.passed and r.severity == "critical"
    ]

    if not critical_failures:
        return

    failure_ids = [r.scenario_id for r in critical_failures]
    pytest.fail(
        f"{msg}\n"
        f"{len(critical_failures)} critical scenarios failed: {failure_ids}"
    )
