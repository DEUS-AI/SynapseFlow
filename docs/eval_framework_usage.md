# SynapseFlow Agent Evaluation Framework

## Overview

The Agent Evaluation Framework provides automated black-box testing for SynapseFlow's medical assistant agent. It enables:

- **Conversation-based testing**: Define multi-turn patient interactions as YAML scenarios
- **Response validation**: Deterministic assertions (regex, similarity, contains) and LLM-as-Judge evaluation
- **Memory verification**: Assert that entities are correctly stored/not stored in the DIKW knowledge graph
- **Regression prevention**: Critical tests gate PRs to prevent bugs like the "Muriel typo" issue
- **CI/CD integration**: GitHub Actions workflow for automated evaluation runs

## Quick Start

### 1. Run All Evaluation Tests

```bash
# Run all evaluation scenarios
uv run pytest tests/eval/ -v

# Run only critical scenarios
uv run pytest tests/eval/ -v --eval-severity=critical

# Run a specific category
uv run pytest tests/eval/ -v --eval-category=regression
```

### 2. Generate Reports

```bash
# Run with HTML/JSON report generation
uv run pytest tests/eval/ -v --eval-report --eval-report-dir=eval_reports
```

Reports are saved to `eval_reports/`:
- `report_<timestamp>.html` - Visual HTML report
- `report_<timestamp>.json` - Machine-readable JSON

## Writing Scenarios

Scenarios are YAML files in `tests/eval/scenarios/<category>/`. Each scenario defines a multi-turn conversation with assertions.

### Basic Structure

```yaml
id: medication_extraction_basic
name: "Basic Medication Extraction"
description: "Verify agent extracts medication names correctly"
category: entity_extraction
severity: high
tags:
  - medications
  - extraction

# Optional: Load shared fixtures
fixtures:
  - patient_ana_garcia

# Conversation turns
turns:
  - turn: 1
    patient_message: "Estoy tomando Omeprazol 20mg para la acidez"

    # Response assertions (what the agent should/shouldn't say)
    response_assertions:
      deterministic:
        - type: must_contain
          expected: ["Omeprazol"]
        - type: must_not_contain
          expected: ["error", "no entiendo"]

      judge:
        - criterion: empathy
          min_score: 3
        - criterion: medical_accuracy
          min_score: 4

    # Memory assertions (what should be stored in the knowledge graph)
    state_assertions:
      entities_must_exist:
        - name: "Omeprazol"
          type: "Medication"
          layer: "PERCEPTION"  # Optional: assert specific DIKW layer
          properties:          # Optional: assert specific properties
            dosage: "20mg"

      entities_must_not_exist:
        - name: "Muriel"
          type: "Medication"
          reason: "Typos should not be stored as medications"
```

### Fixtures

Fixtures define reusable patient contexts and are stored in `tests/eval/scenarios/fixtures/`:

```yaml
# tests/eval/scenarios/fixtures/patient_ana_garcia.yaml
patient_id: "test-patient-ana-garcia"
patient_data:
  nombre: "Ana García"
  edad: 45
  genero: "Femenino"
  alergias:
    - "Penicilina"
  condiciones_previas:
    - "Hipertensión"
  medicaciones_actuales:
    - nombre: "Lisinopril"
      dosis: "10mg"
      frecuencia: "Una vez al día"

# Pre-seed memories before the scenario runs
initial_memories:
  - text: "Paciente con historial de hipertensión controlada"
    layer: "SEMANTIC"
    confidence: 0.9
```

Reference fixtures in scenarios:

```yaml
fixtures:
  - patient_ana_garcia  # Will load patient_ana_garcia.yaml
```

## Assertion Types

### Deterministic Assertions

| Type | Description | Example |
|------|-------------|---------|
| `must_contain` | Response must contain all strings | `expected: ["Omeprazol", "20mg"]` |
| `must_not_contain` | Response must not contain any strings | `expected: ["error", "no sé"]` |
| `must_contain_one_of` | Response must contain at least one | `expected: ["sí", "claro", "entendido"]` |
| `regex_match` | Response must match regex | `pattern: "\\d+mg"` |
| `regex_not_match` | Response must not match regex | `pattern: "error:\\s*\\d+"` |
| `not_empty` | Response must not be empty | (no parameters) |
| `max_length` | Response must be under N chars | `max_length: 500` |
| `min_length` | Response must be at least N chars | `min_length: 10` |
| `similarity` | Fuzzy string similarity | `expected: "Omeprazol", threshold: 0.8` |
| `semantic_similarity` | Embedding-based similarity | `expected: "medication for stomach", threshold: 0.7` |
| `json_schema` | Response matches JSON schema | `schema: {type: object, ...}` |
| `intent_match` | Response matches intent | `expected_intent: "greeting"` |
| `starts_with` | Response starts with string | `prefix: "Entiendo que"` |
| `ends_with` | Response ends with string | `suffix: "?"` |
| `contains_question` | Response contains a question | (no parameters) |
| `word_count` | Word count in range | `min: 10, max: 100` |

### LLM Judge Criteria

The LLM judge evaluates subjective qualities on a 1-5 scale:

| Criterion | Description |
|-----------|-------------|
| `empathy` | Shows understanding and compassion |
| `medical_accuracy` | Provides correct medical information |
| `safety` | Avoids harmful advice, recommends professional help |
| `clarity` | Clear, understandable language |
| `completeness` | Addresses all aspects of the query |
| `relevance` | Stays on topic, directly addresses the question |
| `professionalism` | Maintains appropriate professional tone |
| `cultural_sensitivity` | Respects cultural context and preferences |
| `patient_education` | Explains medical concepts clearly |
| `follow_up` | Asks appropriate follow-up questions |
| `boundary_respect` | Knows limitations, refers to professionals |
| `consistency` | Maintains consistent information |
| `actionability` | Provides actionable recommendations |

Custom criteria:

```yaml
judge:
  - criterion: custom
    description: "Response acknowledges patient's specific medication concern"
    rubric: |
      5: Explicitly names the medication and addresses the specific concern
      4: Addresses the concern with some medication context
      3: General acknowledgment without specifics
      2: Vague response
      1: Ignores the medication concern entirely
    min_score: 4
```

### State Assertions

Verify what's stored in the knowledge graph:

```yaml
state_assertions:
  # Entities that MUST exist after this turn
  entities_must_exist:
    - name: "Omeprazol"
      type: "Medication"
      layer: "PERCEPTION"      # Optional: PERCEPTION, SEMANTIC, REASONING, APPLICATION
      confidence_min: 0.7      # Optional: minimum confidence
      properties:              # Optional: verify specific properties
        dosage: "20mg"

  # Entities that MUST NOT exist (prevents typos, hallucinations)
  entities_must_not_exist:
    - name: "Muriel"
      type: "Medication"
      reason: "Patient typo - not a valid medication"

  # Relationships that must exist
  relationships_must_exist:
    - from_name: "Ana García"
      from_type: "Patient"
      relation: "TAKES"
      to_name: "Omeprazol"
      to_type: "Medication"

  # Memory layer assertions
  memory_assertions:
    short_term:
      must_contain: ["Omeprazol"]
    long_term:
      must_not_contain: ["Muriel"]
```

## Severity Levels

| Severity | Purpose | CI Behavior |
|----------|---------|-------------|
| `critical` | Must never fail (data integrity, safety) | Blocks PR merge |
| `high` | Important functionality | Reported, may block |
| `medium` | Standard features | Reported only |
| `low` | Nice-to-have behaviors | Reported only |

## Project Structure

```
tests/eval/
├── conftest.py              # Pytest configuration
├── pytest_plugin.py         # Dynamic test generation
├── __init__.py
│
├── runner/                  # Core framework
│   ├── __init__.py
│   ├── scenario_loader.py   # YAML parsing
│   ├── scenario_orchestrator.py  # Test execution
│   ├── memory_inspector.py  # Knowledge graph queries
│   ├── reporting.py         # HTML/JSON/Console reports
│   └── evaluators/
│       ├── __init__.py
│       ├── deterministic.py # 16 assertion types
│       └── llm_judge.py     # LLM-based evaluation
│
├── scenarios/               # Test scenarios
│   ├── fixtures/            # Shared patient contexts
│   │   └── patient_ana_garcia.yaml
│   ├── regression/          # Regression tests
│   │   └── muriel_bug.yaml
│   ├── entity_extraction/   # Entity extraction tests
│   └── conversation_flow/   # Multi-turn flow tests
│
└── runner/tests/            # Framework unit tests
    ├── test_scenario_loader.py
    ├── test_orchestrator_unit.py
    └── evaluators/
        ├── test_deterministic_evaluators.py
        └── test_llm_judge.py
```

## CI/CD Integration

The GitHub Actions workflow (`.github/workflows/eval-tests.yml`) provides:

### Trigger Events

- **Pull Requests**: Runs unit tests + critical regression checks
- **Scheduled (Nightly)**: Runs full evaluation suite
- **Manual Dispatch**: Run with custom filters

### Jobs

1. **Unit Tests**: Evaluator tests (no API required)
2. **Integration Tests**: Full scenario execution against running API
3. **Regression Gate**: Critical scenario validation for PRs

### Manual Trigger

```bash
# Via GitHub CLI
gh workflow run eval-tests.yml \
  --field category=regression \
  --field severity=critical
```

## Configuration

### Environment Variables

```bash
# API Configuration
EVAL_API_URL=http://localhost:8000
EVAL_API_KEY=your-eval-api-key

# LLM Judge (optional - uses mock by default)
OPENAI_API_KEY=sk-...

# Framework mode
SYNAPSEFLOW_EVAL_MODE=true  # Enables test isolation
```

### Pytest Options

```bash
--eval-api-url          # API base URL (default: http://localhost:8000)
--eval-api-key          # API key for authentication
--eval-scenarios-dir    # Custom scenarios directory
--eval-category         # Filter by category
--eval-severity         # Filter by severity
--eval-tag              # Filter by tag
--eval-report           # Generate HTML/JSON reports
--eval-report-dir       # Report output directory
--eval-use-mock-judge   # Use mock LLM judge (default: True)
--eval-judge-model      # LLM model for judge (default: gpt-4o-mini)
```

## API Endpoints

The evaluation framework uses these API endpoints:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/chat/{patient_id}` | Send patient message |
| `GET /api/eval/health` | Check API health |
| `POST /api/eval/reset/{patient_id}` | Reset patient state for test isolation |
| `GET /api/eval/memories/{patient_id}` | Get all memories for patient |
| `GET /api/eval/entities/{patient_id}` | Get all entities for patient |

## Example: The Muriel Bug

The framework was created to catch bugs like the "Muriel typo" issue:

**Bug**: Patient typed "Muriel" (a name) instead of their medication name. The agent accepted "Muriel" as a valid medication and stored it in the knowledge graph.

**Regression Test** (`tests/eval/scenarios/regression/muriel_bug.yaml`):

```yaml
id: muriel_bug_regression
name: "Muriel Typo Medication Bug"
category: regression
severity: critical
description: |
  Regression test for the Muriel bug where patient typos
  were incorrectly stored as valid medications.

turns:
  - turn: 1
    patient_message: "Estoy tomando Muriel para mi problema de estómago"

    response_assertions:
      deterministic:
        - type: must_not_contain
          expected: ["Muriel"]
          case_sensitive: false

      judge:
        - criterion: medical_accuracy
          min_score: 4
          context: "Agent should recognize 'Muriel' is not a valid medication"

    state_assertions:
      entities_must_not_exist:
        - name: "Muriel"
          type: "Medication"
          reason: "Muriel is a typo/name, not a valid medication"

      entities_must_not_exist:
        - name: "muriel"
          type: "Medication"
          reason: "Case-insensitive check for typo"
```

## Programmatic Usage

```python
from tests.eval.runner import (
    ScenarioLoader,
    ScenarioOrchestrator,
    MemoryInspector,
)
from tests.eval.runner.evaluators import (
    DeterministicEvaluator,
    create_mock_judge,
)
from tests.eval.runner.reporting import ReportManager

# Load scenarios
loader = ScenarioLoader(scenarios_dir="tests/eval/scenarios")
scenarios = loader.load_all_scenarios(severity="critical")

# Create orchestrator
inspector = MemoryInspector(base_url="http://localhost:8000", api_key="key")
orchestrator = ScenarioOrchestrator(
    memory_inspector=inspector,
    deterministic_evaluator=DeterministicEvaluator(),
    judge_evaluator=create_mock_judge(),
)

# Run scenarios
results = []
for scenario in scenarios:
    result = await orchestrator.run_scenario(scenario)
    results.append(result)

# Generate reports
manager = ReportManager(output_dir="eval_reports")
suite_report = manager.generate_all(results, name="My Evaluation Run")

print(f"Passed: {suite_report.passed}/{suite_report.total}")
```

## Troubleshooting

### Common Issues

1. **"EVAL_API_KEY not configured"**
   - Set `EVAL_API_KEY` environment variable or use `--eval-api-key`

2. **"Could not connect to API"**
   - Ensure API is running: `uv run uvicorn src.application.api.main:app --port 8000`

3. **"No scenarios found"**
   - Check `--eval-scenarios-dir` path
   - Verify YAML files are valid

4. **LLM Judge timeout**
   - Use `--eval-use-mock-judge` for faster tests
   - Increase timeout in orchestrator config

### Debug Mode

```bash
# Verbose output with full tracebacks
uv run pytest tests/eval/ -v --tb=long -s

# Run single scenario
uv run pytest tests/eval/ -v -k "muriel_bug"
```
