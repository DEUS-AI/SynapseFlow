"""
Pytest configuration for evaluation framework tests.

This module provides fixtures for running agent evaluations:
- MemoryInspector for API interaction
- ScenarioLoader for loading YAML scenarios
- ScenarioOrchestrator for running evaluation scenarios
- Utility fixtures for common test patterns
"""

# Register the pytest plugin for eval command-line options
pytest_plugins = ["tests.eval.pytest_plugin"]

import os
import pytest
from pathlib import Path
from typing import Dict, List, Optional

from tests.eval.runner import (
    MemoryInspector,
    ScenarioLoader,
    ScenarioOrchestrator,
    Scenario,
    EvalResult,
)


# ========================================
# Configuration
# ========================================

def get_eval_api_url() -> str:
    """Get the evaluation API base URL from environment."""
    return os.getenv("SYNAPSEFLOW_EVAL_API_URL", "http://localhost:8000")


def get_eval_api_key() -> str:
    """Get the evaluation API key from environment."""
    api_key = os.getenv("SYNAPSEFLOW_EVAL_API_KEY", "")
    if not api_key:
        pytest.skip("SYNAPSEFLOW_EVAL_API_KEY environment variable not set")
    return api_key


def get_scenarios_dir() -> Path:
    """Get the scenarios directory path."""
    default = Path(__file__).parent / "scenarios"
    return Path(os.getenv("EVAL_SCENARIOS_DIR", str(default)))


def get_fixtures_dir() -> Path:
    """Get the fixtures directory path."""
    default = Path(__file__).parent / "fixtures" / "patient_states"
    return Path(os.getenv("EVAL_FIXTURES_DIR", str(default)))


# ========================================
# Core Fixtures
# ========================================

@pytest.fixture(scope="session")
def eval_api_url() -> str:
    """Session-scoped API URL fixture."""
    return get_eval_api_url()


@pytest.fixture(scope="session")
def eval_api_key() -> str:
    """Session-scoped API key fixture."""
    return get_eval_api_key()


@pytest.fixture(scope="session")
def scenarios_dir() -> Path:
    """Session-scoped scenarios directory fixture."""
    return get_scenarios_dir()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Session-scoped fixtures directory fixture."""
    return get_fixtures_dir()


@pytest.fixture
def memory_inspector(eval_api_url: str, eval_api_key: str) -> MemoryInspector:
    """
    Create a MemoryInspector instance.

    This fixture creates a fresh inspector for each test.
    """
    return MemoryInspector(
        base_url=eval_api_url,
        api_key=eval_api_key,
    )


@pytest.fixture
def scenario_loader(scenarios_dir: Path, fixtures_dir: Path) -> ScenarioLoader:
    """
    Create a ScenarioLoader instance.

    This fixture creates a fresh loader for each test.
    """
    return ScenarioLoader(
        scenarios_dir=str(scenarios_dir),
        fixtures_dir=str(fixtures_dir),
    )


@pytest.fixture
def scenario_orchestrator(memory_inspector: MemoryInspector) -> ScenarioOrchestrator:
    """
    Create a ScenarioOrchestrator instance.

    This fixture creates an orchestrator with default configuration.
    """
    return ScenarioOrchestrator(
        memory_inspector=memory_inspector,
        turn_timeout=30.0,
        quiescence_timeout=60.0,
        reset_before_scenario=True,
    )


# ========================================
# Integration Test Markers
# ========================================

def pytest_configure(config):
    """Register custom markers for evaluation tests."""
    config.addinivalue_line(
        "markers",
        "eval_integration: marks tests as requiring the eval API (deselect with '-m \"not eval_integration\"')"
    )
    config.addinivalue_line(
        "markers",
        "eval_critical: marks tests as critical severity scenarios"
    )
    config.addinivalue_line(
        "markers",
        "eval_regression: marks tests as regression scenarios from bugs"
    )
    config.addinivalue_line(
        "markers",
        "eval_slow: marks tests as slow-running scenarios"
    )


# ========================================
# Scenario Loading Fixtures
# ========================================

@pytest.fixture
def load_scenario(scenario_loader: ScenarioLoader):
    """
    Factory fixture for loading individual scenarios.

    Usage:
        def test_something(load_scenario):
            scenario = load_scenario("entity_extraction/basic_medication.yaml")
    """
    def _load(path: str) -> Scenario:
        return scenario_loader.load_scenario(path)
    return _load


@pytest.fixture
def load_scenarios_by_category(scenario_loader: ScenarioLoader):
    """
    Factory fixture for loading scenarios by category.

    Usage:
        def test_all_regression(load_scenarios_by_category):
            scenarios = load_scenarios_by_category("regression")
    """
    def _load(category: str) -> List[Scenario]:
        return scenario_loader.load_all_scenarios(category=category)
    return _load


@pytest.fixture
def load_scenarios_by_severity(scenario_loader: ScenarioLoader):
    """
    Factory fixture for loading scenarios by severity.

    Usage:
        def test_critical_scenarios(load_scenarios_by_severity):
            scenarios = load_scenarios_by_severity("critical")
    """
    def _load(severity: str) -> List[Scenario]:
        return scenario_loader.load_all_scenarios(severity=severity)
    return _load


@pytest.fixture
def load_scenarios_by_tag(scenario_loader: ScenarioLoader):
    """
    Factory fixture for loading scenarios by tag.

    Usage:
        def test_medication_scenarios(load_scenarios_by_tag):
            scenarios = load_scenarios_by_tag("medication")
    """
    def _load(tag: str) -> List[Scenario]:
        return scenario_loader.load_all_scenarios(tag=tag)
    return _load


# ========================================
# Orchestration Fixtures
# ========================================

@pytest.fixture
def run_scenario(scenario_orchestrator: ScenarioOrchestrator):
    """
    Factory fixture for running a single scenario.

    Usage:
        async def test_scenario(run_scenario, load_scenario):
            scenario = load_scenario("regression/muriel_bug.yaml")
            result = await run_scenario(scenario)
            assert result.passed
    """
    async def _run(scenario: Scenario) -> EvalResult:
        return await scenario_orchestrator.run_scenario(scenario)
    return _run


@pytest.fixture
def run_scenarios(scenario_orchestrator: ScenarioOrchestrator):
    """
    Factory fixture for running multiple scenarios.

    Usage:
        async def test_all_critical(run_scenarios, load_scenarios_by_severity):
            scenarios = load_scenarios_by_severity("critical")
            results = await run_scenarios(scenarios)
            assert all(r.passed for r in results)
    """
    async def _run(
        scenarios: List[Scenario],
        stop_on_failure: bool = False,
        parallel: bool = False,
    ) -> List[EvalResult]:
        return await scenario_orchestrator.run_scenarios(
            scenarios,
            stop_on_failure=stop_on_failure,
            parallel=parallel,
        )
    return _run


# ========================================
# Utility Fixtures
# ========================================

@pytest.fixture
def assert_scenario_passed():
    """
    Assertion helper for scenario results.

    Usage:
        async def test_scenario(run_scenario, assert_scenario_passed, scenario):
            result = await run_scenario(scenario)
            assert_scenario_passed(result)
    """
    def _assert(result: EvalResult, message: str = ""):
        if not result.passed:
            # Build detailed failure message
            failures = []
            for turn in result.turns:
                for assertion in turn.failed_assertions:
                    failures.append(
                        f"Turn {turn.turn_number}: [{assertion.assertion_type}] "
                        f"{assertion.reason} - {assertion.details}"
                    )

            failure_msg = "\n".join(failures) if failures else result.error or "Unknown error"
            pytest.fail(f"{message}\nScenario '{result.scenario_id}' failed:\n{failure_msg}")

    return _assert


@pytest.fixture
def check_api_available(memory_inspector: MemoryInspector):
    """
    Check if the evaluation API is available.

    Usage:
        async def test_api_required(check_api_available):
            await check_api_available()
            # Continue with test...
    """
    async def _check():
        try:
            health = await memory_inspector.health_check()
            if health.get("status") != "healthy":
                pytest.skip(f"Eval API not healthy: {health}")
        except Exception as e:
            pytest.skip(f"Eval API not available: {e}")

    return _check


# ========================================
# Test Patient Fixtures
# ========================================

@pytest.fixture
def test_patient_id() -> str:
    """Generate a unique patient ID for testing."""
    import time
    return f"test-patient-{int(time.time())}"


@pytest.fixture
async def clean_patient(memory_inspector: MemoryInspector, test_patient_id: str):
    """
    Fixture that provides a clean patient and resets after the test.

    Usage:
        async def test_with_clean_patient(clean_patient):
            patient_id = clean_patient
            # Run test...
            # Patient is automatically reset after test
    """
    # Reset patient before test
    await memory_inspector.reset_patient(test_patient_id)

    yield test_patient_id

    # Reset patient after test
    await memory_inspector.reset_patient(test_patient_id)


# ========================================
# Parametrized Scenario Collection
# ========================================

def collect_scenarios_for_parametrize(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[Scenario]:
    """
    Collect scenarios for pytest parametrize.

    This function can be used with pytest.mark.parametrize to
    dynamically generate tests for each scenario.

    Usage:
        @pytest.mark.parametrize("scenario", collect_scenarios_for_parametrize(category="regression"))
        async def test_regression_scenario(run_scenario, scenario):
            result = await run_scenario(scenario)
            assert result.passed
    """
    try:
        loader = ScenarioLoader(
            scenarios_dir=str(get_scenarios_dir()),
            fixtures_dir=str(get_fixtures_dir()),
        )
        return loader.load_all_scenarios(
            category=category,
            severity=severity,
            tag=tag,
        )
    except Exception:
        # Return empty list if scenarios can't be loaded
        # (avoids breaking pytest collection)
        return []


def scenario_id_func(scenario: Scenario) -> str:
    """Generate a test ID from a scenario for parametrize."""
    return f"{scenario.category}/{scenario.id}"
