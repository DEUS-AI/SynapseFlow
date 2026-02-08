"""
Tests for ScenarioLoader class.

Tests the loading, parsing, and validation of YAML evaluation scenarios.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import tempfile
import os

from tests.eval.runner.scenario_loader import (
    ScenarioLoader,
    ScenarioLoaderError,
    ScenarioValidationError,
    FixtureNotFoundError,
)
from tests.eval.runner.scenario_models import (
    Scenario,
    ScenarioTurn,
    DeterministicAssertion,
    JudgeAssertion,
    EntityAssertion,
    InitialStateEntity,
    InitialStateRelationship,
)


# ========================================
# Fixtures
# ========================================

@pytest.fixture
def temp_scenarios_dir():
    """Create a temporary directory for test scenarios."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_fixtures_dir(temp_scenarios_dir):
    """Create a temporary directory for test fixtures."""
    fixtures_dir = temp_scenarios_dir.parent / "fixtures" / "patient_states"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    return fixtures_dir


@pytest.fixture
def sample_scenario_yaml():
    """A minimal valid scenario YAML content."""
    return """
id: test_scenario
name: Test Scenario
description: A test scenario for unit tests
category: entity_extraction
severity: medium
tags:
  - test
  - unit

turns:
  - turn: 1
    patient_message: "Test message"
    response_assertions:
      deterministic:
        - type: not_empty
          reason: "Response should not be empty"
"""


@pytest.fixture
def scenario_with_initial_state_yaml():
    """Scenario YAML with initial state."""
    return """
id: scenario_with_state
name: Scenario with Initial State
category: test
severity: high

initial_state:
  patient_id: "test-patient-123"
  entities:
    - name: "Metformina"
      type: "Medication"
      properties:
        dosage: "500mg"
      dikw_layer: "SEMANTIC"
      confidence: 0.9
  relationships:
    - from: "Metformina"
      to: "Diabetes"
      type: "TREATS"

turns:
  - turn: 1
    patient_message: "Test message"
    state_assertions:
      entities_must_exist:
        - name: "Metformina"
          reason: "Should exist from initial state"
"""


@pytest.fixture
def fixture_yaml():
    """A patient state fixture YAML content."""
    return """
name: Test Fixture
description: Test patient fixture

entities:
  - name: "Diabetes tipo 2"
    type: "Condition"
    properties:
      status: "active"
    dikw_layer: "SEMANTIC"
    confidence: 0.95

relationships:
  - from: "Metformina"
    to: "Diabetes tipo 2"
    type: "TREATS"
"""


@pytest.fixture
def scenario_with_fixture_yaml():
    """Scenario that references a fixture."""
    return """
id: scenario_with_fixture
name: Scenario with Fixture
category: test
severity: medium

initial_state:
  fixture: test_fixture
  entities:
    - name: "Ibuprofeno"
      type: "Medication"

turns:
  - turn: 1
    patient_message: "Test"
    response_assertions:
      deterministic:
        - type: not_empty
          reason: "Should respond"
"""


# ========================================
# Basic Loading Tests
# ========================================

class TestScenarioLoaderBasics:
    """Tests for basic ScenarioLoader functionality."""

    def test_init_with_defaults(self, temp_scenarios_dir):
        """Test initialization with default fixture directory."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        assert loader.scenarios_dir == temp_scenarios_dir
        assert "fixtures" in str(loader.fixtures_dir)
        assert "patient_states" in str(loader.fixtures_dir)

    def test_init_with_custom_fixtures_dir(self, temp_scenarios_dir, temp_fixtures_dir):
        """Test initialization with custom fixture directory."""
        loader = ScenarioLoader(
            scenarios_dir=str(temp_scenarios_dir),
            fixtures_dir=str(temp_fixtures_dir),
        )

        assert loader.fixtures_dir == temp_fixtures_dir

    def test_load_scenario_file_not_found(self, temp_scenarios_dir):
        """Test loading a non-existent scenario file."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        with pytest.raises(ScenarioLoaderError) as exc_info:
            loader.load_scenario("nonexistent.yaml")

        assert "not found" in str(exc_info.value).lower()

    def test_load_scenario_empty_file(self, temp_scenarios_dir):
        """Test loading an empty YAML file."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create empty file
        empty_file = temp_scenarios_dir / "empty.yaml"
        empty_file.write_text("")

        with pytest.raises(ScenarioLoaderError) as exc_info:
            loader.load_scenario("empty.yaml")

        assert "empty" in str(exc_info.value).lower()

    def test_load_scenario_valid(self, temp_scenarios_dir, sample_scenario_yaml):
        """Test loading a valid scenario file."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create scenario file
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(sample_scenario_yaml)

        scenario = loader.load_scenario("test.yaml")

        assert scenario.id == "test_scenario"
        assert scenario.name == "Test Scenario"
        assert scenario.category == "entity_extraction"
        assert scenario.severity == "medium"
        assert "test" in scenario.tags
        assert len(scenario.turns) == 1
        assert scenario.turns[0].turn == 1

    def test_load_scenario_with_absolute_path(self, temp_scenarios_dir, sample_scenario_yaml):
        """Test loading with absolute path."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(sample_scenario_yaml)

        scenario = loader.load_scenario(str(scenario_file))

        assert scenario.id == "test_scenario"


# ========================================
# Initial State Tests
# ========================================

class TestScenarioInitialState:
    """Tests for scenarios with initial state."""

    def test_load_scenario_with_initial_state(
        self,
        temp_scenarios_dir,
        scenario_with_initial_state_yaml,
    ):
        """Test loading scenario with inline initial state."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        scenario_file = temp_scenarios_dir / "with_state.yaml"
        scenario_file.write_text(scenario_with_initial_state_yaml)

        scenario = loader.load_scenario("with_state.yaml")

        assert scenario.initial_state is not None
        assert scenario.initial_state.patient_id == "test-patient-123"
        assert len(scenario.initial_state.entities) == 1
        assert scenario.initial_state.entities[0].name == "Metformina"
        assert scenario.initial_state.entities[0].type == "Medication"
        assert len(scenario.initial_state.relationships) == 1

    def test_initial_state_entity_properties(
        self,
        temp_scenarios_dir,
        scenario_with_initial_state_yaml,
    ):
        """Test that entity properties are parsed correctly."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        scenario_file = temp_scenarios_dir / "with_state.yaml"
        scenario_file.write_text(scenario_with_initial_state_yaml)

        scenario = loader.load_scenario("with_state.yaml")
        entity = scenario.initial_state.entities[0]

        assert entity.properties.get("dosage") == "500mg"
        assert entity.dikw_layer == "SEMANTIC"
        assert entity.confidence == 0.9


# ========================================
# Fixture Resolution Tests
# ========================================

class TestFixtureResolution:
    """Tests for fixture loading and resolution."""

    def test_load_fixture(self, temp_scenarios_dir, fixture_yaml):
        """Test loading a fixture file."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create fixtures directory and file
        fixtures_dir = loader.fixtures_dir
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        fixture_file = fixtures_dir / "test_fixture.yaml"
        fixture_file.write_text(fixture_yaml)

        fixture = loader._load_fixture("test_fixture")

        assert fixture.id == "test_fixture"
        assert fixture.name == "Test Fixture"
        assert len(fixture.entities) == 1
        assert fixture.entities[0].name == "Diabetes tipo 2"

    def test_fixture_not_found(self, temp_scenarios_dir):
        """Test error when fixture doesn't exist."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        with pytest.raises(FixtureNotFoundError):
            loader._load_fixture("nonexistent_fixture")

    def test_scenario_with_fixture_reference(
        self,
        temp_scenarios_dir,
        scenario_with_fixture_yaml,
        fixture_yaml,
    ):
        """Test scenario that references a fixture."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create fixtures directory and file
        fixtures_dir = loader.fixtures_dir
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        fixture_file = fixtures_dir / "test_fixture.yaml"
        fixture_file.write_text(fixture_yaml)

        # Create scenario file
        scenario_file = temp_scenarios_dir / "with_fixture.yaml"
        scenario_file.write_text(scenario_with_fixture_yaml)

        scenario = loader.load_scenario("with_fixture.yaml")

        # Should have merged entities from fixture + scenario
        assert scenario.initial_state is not None
        entities = scenario.initial_state.entities

        # Should have entities from both fixture and scenario
        entity_names = [e.name for e in entities]
        assert "Diabetes tipo 2" in entity_names  # From fixture
        assert "Ibuprofeno" in entity_names  # From scenario

    def test_fixture_caching(self, temp_scenarios_dir, fixture_yaml):
        """Test that fixtures are cached."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        fixtures_dir = loader.fixtures_dir
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        fixture_file = fixtures_dir / "cached_fixture.yaml"
        fixture_file.write_text(fixture_yaml)

        # Load fixture twice
        fixture1 = loader._load_fixture("cached_fixture")
        fixture2 = loader._load_fixture("cached_fixture")

        # Should be the same cached object
        assert fixture1 is fixture2

    def test_clear_fixture_cache(self, temp_scenarios_dir, fixture_yaml):
        """Test clearing the fixture cache."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        fixtures_dir = loader.fixtures_dir
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        fixture_file = fixtures_dir / "cached_fixture.yaml"
        fixture_file.write_text(fixture_yaml)

        # Load fixture
        loader._load_fixture("cached_fixture")
        assert "cached_fixture" in loader._fixtures_cache

        # Clear cache
        loader.clear_fixture_cache()
        assert len(loader._fixtures_cache) == 0


# ========================================
# Validation Tests
# ========================================

class TestScenarioValidation:
    """Tests for scenario validation."""

    def test_turn_without_assertions_fails(self, temp_scenarios_dir):
        """Test that turns without assertions are rejected."""
        yaml_content = """
id: no_assertions
name: No Assertions
category: test

turns:
  - turn: 1
    patient_message: "Test"
    # No assertions!
"""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        scenario_file = temp_scenarios_dir / "no_assertions.yaml"
        scenario_file.write_text(yaml_content)

        with pytest.raises(ScenarioValidationError) as exc_info:
            loader.load_scenario("no_assertions.yaml")

        assert "assertion" in str(exc_info.value).lower()

    def test_sequential_turn_numbers(self, temp_scenarios_dir):
        """Test that turn numbers must be sequential."""
        yaml_content = """
id: bad_turns
name: Bad Turns
category: test

turns:
  - turn: 1
    patient_message: "First"
    response_assertions:
      deterministic:
        - type: not_empty
          reason: "Test"
  - turn: 3  # Should be 2!
    patient_message: "Third"
    response_assertions:
      deterministic:
        - type: not_empty
          reason: "Test"
"""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        scenario_file = temp_scenarios_dir / "bad_turns.yaml"
        scenario_file.write_text(yaml_content)

        with pytest.raises(ScenarioValidationError):
            loader.load_scenario("bad_turns.yaml")


# ========================================
# Bulk Loading Tests
# ========================================

class TestLoadAllScenarios:
    """Tests for loading all scenarios from a directory."""

    def test_load_all_scenarios(self, temp_scenarios_dir, sample_scenario_yaml):
        """Test loading all scenarios from a directory."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create multiple scenario files
        for i in range(3):
            scenario_file = temp_scenarios_dir / f"scenario_{i}.yaml"
            content = sample_scenario_yaml.replace("test_scenario", f"scenario_{i}")
            scenario_file.write_text(content)

        scenarios = loader.load_all_scenarios()

        assert len(scenarios) == 3

    def test_load_scenarios_from_subdirectories(self, temp_scenarios_dir, sample_scenario_yaml):
        """Test loading scenarios from subdirectories."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create subdirectory with scenario
        subdir = temp_scenarios_dir / "regression"
        subdir.mkdir()
        scenario_file = subdir / "test.yaml"
        scenario_file.write_text(sample_scenario_yaml)

        scenarios = loader.load_all_scenarios(include_subdirs=True)

        assert len(scenarios) == 1

    def test_filter_by_category(self, temp_scenarios_dir):
        """Test filtering scenarios by category."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create scenarios with different categories
        for i, category in enumerate(["regression", "entity_extraction", "regression"]):
            scenario_file = temp_scenarios_dir / f"{category}_{i}.yaml"
            content = f"""
id: {category}_scenario_{i}
name: {category} Scenario {i}
category: {category}

turns:
  - turn: 1
    patient_message: "Test"
    response_assertions:
      deterministic:
        - type: not_empty
          reason: "Test"
"""
            scenario_file.write_text(content)

        regression_scenarios = loader.load_all_scenarios(category="regression")

        assert len(regression_scenarios) == 2
        assert all(s.category == "regression" for s in regression_scenarios)

    def test_filter_by_severity(self, temp_scenarios_dir):
        """Test filtering scenarios by severity."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        for i, severity in enumerate(["critical", "high", "critical"]):
            scenario_file = temp_scenarios_dir / f"{severity}_{i}.yaml"
            content = f"""
id: {severity}_scenario_{i}
name: {severity} Scenario {i}
category: test
severity: {severity}

turns:
  - turn: 1
    patient_message: "Test"
    response_assertions:
      deterministic:
        - type: not_empty
          reason: "Test"
"""
            scenario_file.write_text(content)

        critical_scenarios = loader.load_all_scenarios(severity="critical")

        assert len(critical_scenarios) == 2
        assert all(s.severity == "critical" for s in critical_scenarios)

    def test_filter_by_tag(self, temp_scenarios_dir):
        """Test filtering scenarios by tag."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create scenarios with different tags
        scenarios_data = [
            ("scenario1", ["medication", "urgent"]),
            ("scenario2", ["condition"]),
            ("scenario3", ["medication", "chronic"]),
        ]

        for name, tags in scenarios_data:
            scenario_file = temp_scenarios_dir / f"{name}.yaml"
            tags_yaml = "\n  - ".join([""] + tags)
            content = f"""
id: {name}
name: {name}
category: test
tags:{tags_yaml}

turns:
  - turn: 1
    patient_message: "Test"
    response_assertions:
      deterministic:
        - type: not_empty
          reason: "Test"
"""
            scenario_file.write_text(content)

        medication_scenarios = loader.load_all_scenarios(tag="medication")

        assert len(medication_scenarios) == 2

    def test_scenarios_sorted_by_severity(self, temp_scenarios_dir):
        """Test that scenarios are sorted by severity (critical first)."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        for severity in ["low", "critical", "medium", "high"]:
            scenario_file = temp_scenarios_dir / f"{severity}.yaml"
            content = f"""
id: {severity}_scenario
name: {severity}
category: test
severity: {severity}

turns:
  - turn: 1
    patient_message: "Test"
    response_assertions:
      deterministic:
        - type: not_empty
          reason: "Test"
"""
            scenario_file.write_text(content)

        scenarios = loader.load_all_scenarios()

        assert scenarios[0].severity == "critical"
        assert scenarios[1].severity == "high"
        assert scenarios[2].severity == "medium"
        assert scenarios[3].severity == "low"


# ========================================
# Suite Loading Tests
# ========================================

class TestScenarioSuite:
    """Tests for scenario suite loading."""

    def test_load_suite(self, temp_scenarios_dir, sample_scenario_yaml):
        """Test loading a scenario suite."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create scenarios
        for i in range(3):
            scenario_file = temp_scenarios_dir / f"scenario_{i}.yaml"
            content = sample_scenario_yaml.replace("test_scenario", f"scenario_{i}")
            scenario_file.write_text(content)

        suite = loader.load_suite(name="test_suite")

        assert suite.name == "test_suite"
        assert suite.total_scenarios == 3
        assert len(suite.scenarios) == 3


# ========================================
# Utility Tests
# ========================================

class TestLoaderUtilities:
    """Tests for ScenarioLoader utility methods."""

    def test_get_categories(self, temp_scenarios_dir):
        """Test getting available categories from subdirectories."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create category subdirectories
        for category in ["regression", "entity_extraction", "memory_pollution"]:
            (temp_scenarios_dir / category).mkdir()

        categories = loader.get_categories()

        assert "regression" in categories
        assert "entity_extraction" in categories
        assert "memory_pollution" in categories

    def test_get_fixtures(self, temp_scenarios_dir, fixture_yaml):
        """Test getting available fixtures."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        fixtures_dir = loader.fixtures_dir
        fixtures_dir.mkdir(parents=True, exist_ok=True)

        # Create fixture files
        for name in ["diabetic", "elderly", "pregnant"]:
            (fixtures_dir / f"{name}.yaml").write_text(fixture_yaml)

        fixtures = loader.get_fixtures()

        assert "diabetic" in fixtures
        assert "elderly" in fixtures
        assert "pregnant" in fixtures


# ========================================
# Error Handling Tests
# ========================================

class TestErrorHandling:
    """Tests for error handling in ScenarioLoader."""

    def test_invalid_yaml_syntax(self, temp_scenarios_dir):
        """Test handling of invalid YAML syntax."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        invalid_yaml = """
id: test
  name: indentation error
"""
        scenario_file = temp_scenarios_dir / "invalid.yaml"
        scenario_file.write_text(invalid_yaml)

        with pytest.raises(ScenarioLoaderError) as exc_info:
            loader.load_scenario("invalid.yaml")

        assert "yaml" in str(exc_info.value).lower()

    def test_missing_required_field(self, temp_scenarios_dir):
        """Test handling of missing required fields."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        yaml_content = """
id: test
name: Test
# Missing category and turns
"""
        scenario_file = temp_scenarios_dir / "missing_fields.yaml"
        scenario_file.write_text(yaml_content)

        with pytest.raises((ScenarioLoaderError, ScenarioValidationError)):
            loader.load_scenario("missing_fields.yaml")

    def test_load_all_with_some_invalid(self, temp_scenarios_dir, sample_scenario_yaml):
        """Test that invalid scenarios don't stop loading others."""
        loader = ScenarioLoader(scenarios_dir=str(temp_scenarios_dir))

        # Create valid scenario
        valid_file = temp_scenarios_dir / "valid.yaml"
        valid_file.write_text(sample_scenario_yaml)

        # Create invalid scenario
        invalid_file = temp_scenarios_dir / "invalid.yaml"
        invalid_file.write_text("invalid: yaml: content:")

        # Should load the valid one and skip the invalid
        scenarios = loader.load_all_scenarios()

        assert len(scenarios) == 1
        assert scenarios[0].id == "test_scenario"
