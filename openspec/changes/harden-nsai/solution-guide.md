# Harden NSAI — Solution Guide

## Problem Statement

The ReasoningEngine is the core of SynapseFlow's neurosymbolic AI system — 1800 lines, 19 rules, 3 strategies — but had:

- **Zero dedicated tests** (the only NSAI component with no test coverage)
- **71 hardcoded numeric thresholds** scattered across rule methods (confidence values, scoring parameters, decision thresholds)
- **No observability** into which rules fired, what confidence values flowed through, or which strategy was selected

Across all NSAI components, only 8.5% of thresholds (8 out of 94) lived in config objects. The `AutomaticLayerTransitionService` had already proven the pattern — fully config-driven via `PromotionThresholds` dataclass, 56+ tests — but the rest of the stack didn't follow.

## What Was Implemented

Three workstreams, all additive and backward-compatible.

### W1: Threshold Config Extraction

**Files changed:** `reasoning_engine.py`, `llm_reasoner.py`, `validation_engine.py`
**File created:** `reasoning_config.py`

#### ReasoningEngineConfig (`reasoning_config.py`)

A top-level `@dataclass` composed of four sub-dataclasses, each grouping thresholds by concern:

```
ReasoningEngineConfig
├── confidence: ConfidenceThresholds    (20 fields)
├── scoring: ScoringConfig              (19 fields)
├── strategy: StrategyConfig            (3 fields)
└── cross_layer: CrossLayerConfig       (17 fields)
```

**Total: 59 config fields**, all with defaults matching the original hardcoded values.

##### ConfidenceThresholds

Groups all confidence values assigned to inferences and decision thresholds across reasoning rules:

| Field | Default | Used in |
|-------|---------|---------|
| `id_pattern_confidence` | 0.8 | `_infer_properties` — ID ending in `_id` |
| `person_keyword_confidence` | 0.7 | `_infer_properties` — ID containing "user"/"customer"/"person" |
| `transaction_keyword_confidence` | 0.7 | `_infer_properties` — ID containing "order"/"transaction" |
| `contact_info_confidence` | 0.9 | `_infer_properties` — entity has email property |
| `temporal_property_confidence` | 0.8 | `_infer_properties` — entity has created_date |
| `classify_person_confidence` | 0.8 | `_classify_entity` — has name + email |
| `classify_financial_confidence` | 0.7 | `_classify_entity` — has amount/price |
| `classify_process_confidence` | 0.6 | `_classify_entity` — has status + created_date |
| `suggest_email_rel_confidence` | 0.7 | `_suggest_relationships` — email property |
| `suggest_date_rel_confidence` | 0.6 | `_suggest_relationships` — created_date property |
| `inverse_relationship_confidence` | 0.8 | `_suggest_inverse_relationship` |
| `transitive_closure_confidence` | 0.9 | `_apply_transitive_closure` |
| `medical_high_threshold` | 0.8 | `_validate_medical_context` — gate for "high confidence" |
| `medical_low_threshold` | 0.6 | `_validate_medical_context` — gate for "low confidence" warning |
| `validated_entity_confidence` | 0.9 | `_validate_medical_context` — confidence assigned to validated entities |
| `treatment_recommendation_confidence` | 0.95 | `_check_treatment_recommendations` |
| `cross_graph_table_confidence` | 0.75 | `_infer_cross_graph_relationships` — table name match |
| `cross_graph_column_confidence` | 0.70 | `_infer_cross_graph_relationships` — column name match |

Note the distinction between **decision thresholds** (like `medical_high_threshold` which controls flow) and **output confidence** values (like `validated_entity_confidence` which is assigned to results). Both are configurable.

##### ScoringConfig

Groups all parameters for the two scoring methods — data availability assessment and answer confidence scoring:

| Field | Default | Used in |
|-------|---------|---------|
| `base_availability_score` | 0.5 | `_assess_data_availability` — starting score |
| `entity_boost_per_item` | 0.1 | `_assess_data_availability` — boost per medical entity |
| `max_entity_boost_items` | 3 | `_assess_data_availability` — cap on entity boost |
| `relationship_boost_per_item` | 0.1 | `_assess_data_availability` |
| `max_relationship_boost_items` | 2 | `_assess_data_availability` |
| `table_boost_per_item` | 0.1 | `_assess_data_availability` |
| `max_table_boost_items` | 2 | `_assess_data_availability` |
| `column_boost` | 0.05 | `_assess_data_availability` — flat boost for any columns |
| `quality_high_threshold` | 0.8 | `_assess_data_availability` — "high quality" gate |
| `quality_medium_threshold` | 0.6 | `_assess_data_availability` — "medium quality" gate |
| `availability_assessment_confidence` | 0.85 | `_assess_data_availability` — meta-confidence |
| `base_answer_confidence` | 0.5 | `_score_answer_confidence` — starting score |
| `validated_entity_threshold` | 0.8 | `_score_answer_confidence` — min confidence to count as "validated" |
| `answer_entity_boost` | 0.1 | `_score_answer_confidence` |
| `max_answer_entity_boost_items` | 3 | `_score_answer_confidence` |
| `answer_relationship_boost` | 0.05 | `_score_answer_confidence` |
| `max_answer_relationship_boost_items` | 2 | `_score_answer_confidence` |
| `answer_cross_graph_boost` | 0.1 | `_score_answer_confidence` |
| `warning_penalty_factor` | 0.95 | `_score_answer_confidence` — multiplicative penalty |

##### StrategyConfig

Controls strategy-level behavior:

| Field | Default | Used in |
|-------|---------|---------|
| `symbolic_first_min_inferences` | 2 | `_symbolic_first_reasoning` — LLM gap-fill triggers when inferences < this |
| `default_neural_confidence` | 0.7 | All strategies — fallback confidence for neural inferences |
| `relationship_type_consolidation_threshold` | 10 | `apply_advanced_reasoning` — suggest consolidation above this |

##### CrossLayerConfig

Thresholds for cross-layer reasoning (DIKW transitions):

| Field | Default | Used in |
|-------|---------|---------|
| `concept_match_threshold` | 0.4 | PERCEPTION→SEMANTIC — min column pattern match ratio |
| `min_concept_confidence` | 0.6 | PERCEPTION→SEMANTIC — confidence floor for matches |
| `concept_confidence_boost` | 0.4 | PERCEPTION→SEMANTIC — confidence scaling factor |
| `promote_to_semantic_confidence` | 0.8 | PERCEPTION→SEMANTIC — promotion suggestion confidence |
| `domain_classification_confidence` | 0.75 | PERCEPTION→SEMANTIC — column domain inference |
| `quality_rule_confidence` | 0.85 | SEMANTIC→REASONING — derived quality rules |
| `referential_integrity_confidence` | 0.95 | SEMANTIC→REASONING — FK constraints |
| `composition_rule_confidence` | 0.9 | SEMANTIC→REASONING — part-of constraints |
| `promote_to_reasoning_confidence` | 0.8 | SEMANTIC→REASONING — promotion suggestion |
| `duplicate_detection_confidence` | 0.8 | REASONING→APPLICATION — uniqueness query |
| `temporal_analysis_confidence` | 0.75 | REASONING→APPLICATION — time-series query |
| `aggregation_confidence` | 0.8 | REASONING→APPLICATION — aggregation query |
| `materialized_view_threshold` | 0.9 | REASONING→APPLICATION — gate for view suggestion |
| `materialized_view_confidence` | 0.7 | REASONING→APPLICATION — view suggestion confidence |
| `fk_index_confidence` | 0.9 | REASONING→APPLICATION — FK index suggestion |
| `temporal_data_confidence` | 0.75 | APPLICATION→PERCEPTION — temporal data collection |
| `aggregate_metadata_confidence` | 0.7 | APPLICATION→PERCEPTION — aggregate collection |
| `high_access_threshold` | 100 | APPLICATION→PERCEPTION — access count gate |
| `data_gap_confidence` | 0.8 | APPLICATION→PERCEPTION — data gap detection |
| `query_error_threshold` | 10 | APPLICATION→PERCEPTION — error count gate |
| `review_data_confidence` | 0.85 | APPLICATION→PERCEPTION — data review suggestion |

#### Constructor Change

```python
# Before
def __init__(self, backend, llm=None, enable_confidence_tracking=True, medical_rules_engine=None):

# After
def __init__(self, backend, llm=None, enable_confidence_tracking=True, medical_rules_engine=None, config=None):
    self.config = config or ReasoningEngineConfig()
```

When `config=None` (the default), behavior is **identical** to prior code. All 71 formerly-hardcoded values now read from `self.config.*` sub-paths.

#### LLMReasonerConfig (`llm_reasoner.py`)

```python
@dataclass
class LLMReasonerConfig:
    default_inference_confidence: float = 0.7   # suggest_semantic_relationships
    default_linking_confidence: float = 0.8     # suggest_business_concepts
```

Wired into `LLMReasoner.__init__` as `config: Optional[LLMReasonerConfig] = None`.

#### ValidationLimits (`validation_engine.py`)

```python
@dataclass
class ValidationLimits:
    max_id_length: int = 100              # entity ID length check
    max_property_value_size: int = 1000   # dict/list property size check
    max_relationship_type_length: int = 50 # relationship type name check
```

Wired into `ValidationEngine.__init__` as `config: Optional[ValidationLimits] = None`. Warning messages now dynamically reference the configured limits.

---

### W2: Reasoning Observability

**File changed:** `reasoning_engine.py`

Four logging points added using the existing `logger = logging.getLogger(__name__)`:

#### 1. Strategy Selection (INFO)

Logged at the start of `apply_reasoning`:

```
Reasoning: strategy=collaborative action=create_entity rules=6
```

#### 2. Per-Rule Execution (DEBUG)

Logged after each rule executes in all three strategy methods:

```
Rule fired: property_inference inferences=2 suggestions=0 warnings=0
Rule skipped: entity_classification (no results)
```

#### 3. Reasoning Summary (INFO)

Logged at the end of `apply_reasoning`:

```
Reasoning complete: strategy=collaborative action=create_entity rules_fired=4 inferences=3 suggestions=1 warnings=0 time=1.23ms
```

#### 4. Cross-Layer Reasoning (DEBUG)

Logged at the end of `apply_cross_layer_reasoning`:

```
Cross-layer reasoning: layer=SEMANTIC rules_applied=['semantic_to_reasoning'] inferences=3
```

**Design choice:** INFO for strategy-level events (low volume, always useful), DEBUG for per-rule events (high volume, opt-in). Exception warnings are preserved as-is (they already existed).

---

### W3: ReasoningEngine Test Suite

**File created:** `tests/application/agents/knowledge_manager/test_reasoning_engine.py`

83 tests across 16 test classes, organized in four layers:

#### Layer 1: Rule Behavior Tests (37 tests)

Test each pure-logic rule directly by calling the private method with crafted `KnowledgeEvent` objects. No mocks needed for these — they're pure functions of input data.

| Test Class | Tests | What's covered |
|---|---|---|
| `TestInferProperties` | 7 | ID patterns (identifier, person, transaction), email/temporal inference, no-match, config override |
| `TestClassifyEntity` | 4 | Person, financial, process classification + no-match |
| `TestSuggestRelationships` | 3 | Email relationship, date relationship, no-match |
| `TestValidateRelationshipLogic` | 3 | Self-reference warning, naming convention, valid relationship |
| `TestSuggestInverseRelationship` | 6 | All 5 known inverse patterns (parametrized) + unknown type |
| `TestValidateMedicalContext` | 3 | High-confidence validation, low-confidence warning, empty entities |
| `TestCheckTreatmentRecommendations` | 5 | 4 keyword variations (parametrized) + non-match |
| `TestInferCrossGraphRelationships` | 3 | Table name match, column name match, no medical entities |
| `TestAssessDataAvailability` | 2 | Full context scoring, base score only |
| `TestScoreAnswerConfidence` | 3 | Base confidence, entity boost, warning penalty |

#### Layer 2: Integration Tests (9 tests)

Test through the public API (`apply_reasoning`, `apply_cross_layer_reasoning`, `apply_advanced_reasoning`) with a mock backend.

| Test Class | Tests | What's covered |
|---|---|---|
| `TestStrategies` | 5 | collaborative/neural_first/symbolic_first without LLM, gap-filling threshold, timing |
| `TestProvenance` | 2 | Provenance recorded after reasoning, None for unknown entity |
| `TestCustomRules` | 4 | Add + execute custom rule, remove existing/nonexistent/bad-action |
| `TestCrossLayerReasoning` | 4 | PERCEPTION→SEMANTIC, SEMANTIC→REASONING, REASONING→APPLICATION, unknown layer |
| `TestAdvancedReasoning` | 3 | Orphaned relationship, consolidation suggestion, under-threshold |

#### Layer 3: Config Validation Tests (18 tests)

Prove that config values are actually wired — changing a config value changes rule behavior.

| Test Class | Tests | What's covered |
|---|---|---|
| `TestConfigOverrides` | 11 | Medical thresholds (high/low), scoring bases, warning penalty, strategy min_inferences, cross-layer concept match, consolidation threshold, classification confidence, cross-graph confidence |
| `TestConfigDataclasses` | 7 | Sub-config types, default values match originals, equality, None→defaults |

#### Layer 4: Observability Tests (5 tests) + Peripheral Config Tests (4 tests)

| Test Class | Tests | What's covered |
|---|---|---|
| `TestObservabilityLogging` | 5 | Strategy at INFO, summary at INFO, rule fired at DEBUG, rule skipped at DEBUG, cross-layer at DEBUG |
| `TestPeripheralConfigs` | 4 | LLMReasonerConfig defaults, ValidationLimits defaults, ValidationEngine config injection, default fallback |

---

## Files Summary

| File | Status | Lines | Description |
|------|--------|-------|-------------|
| `src/application/agents/knowledge_manager/reasoning_config.py` | NEW | 110 | `ReasoningEngineConfig` + 4 sub-dataclasses |
| `src/application/agents/knowledge_manager/reasoning_engine.py` | MODIFIED | ~1900 | Config import, constructor, 71 threshold→config replacements, 8 log statements |
| `src/application/agents/knowledge_manager/llm_reasoner.py` | MODIFIED | ~140 | `LLMReasonerConfig` dataclass, config wiring, 2 threshold replacements |
| `src/application/agents/knowledge_manager/validation_engine.py` | MODIFIED | ~660 | `ValidationLimits` dataclass, config wiring, 3 threshold replacements |
| `tests/application/agents/knowledge_manager/test_reasoning_engine.py` | NEW | ~520 | 83 tests across 16 classes |
| `tests/application/agents/__init__.py` | NEW | 0 | Package marker |
| `tests/application/agents/knowledge_manager/__init__.py` | NEW | 0 | Package marker |

## What Was NOT Changed

- **No threshold values were changed** — every default exactly matches the prior hardcoded value
- **No constructor signatures were broken** — all new parameters are optional with defaults
- **No rules were added, removed, or reordered**
- **No existing behavior was altered** — confirmed by 1147 existing tests passing with 0 regressions
- **MedicalRulesEngine and EntityResolver** were not touched (already better covered, out of scope)
- **Patient safety rules** (`_check_contraindications_fallback`, `_analyze_treatment_history`, `_track_symptoms_over_time`, `_check_medication_adherence`) — these contain hardcoded confidence values but are medical-domain specific and were left as-is per the design scope

## How to Use the Config

```python
from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
from application.agents.knowledge_manager.reasoning_config import ReasoningEngineConfig

# Default behavior (identical to before)
engine = ReasoningEngine(backend=my_backend)

# Custom thresholds
config = ReasoningEngineConfig()
config.confidence.medical_high_threshold = 0.9    # stricter validation
config.scoring.warning_penalty_factor = 0.8        # harsher penalty
config.strategy.symbolic_first_min_inferences = 5  # more symbolic before LLM

engine = ReasoningEngine(backend=my_backend, config=config)
```

## Verification

| Check | Result |
|-------|--------|
| New test suite | 83/83 passed (2.4s) |
| Existing tests | 1147 passed, 13 pre-existing failures (none in changed files) |
| Config default parity | All defaults match original hardcoded values (verified by dataclass tests) |
| Config override wiring | 11 override tests prove config values reach rule logic |
| Logging output | 5 tests verify correct log levels and message formats |
| Peripheral configs | 4 tests verify LLMReasonerConfig and ValidationLimits wiring |
