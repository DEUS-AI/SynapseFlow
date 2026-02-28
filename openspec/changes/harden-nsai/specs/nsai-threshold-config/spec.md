## ADDED Requirements

### Requirement: ReasoningEngineConfig dataclass
The ReasoningEngine SHALL accept an optional `ReasoningEngineConfig` parameter that centralizes all numeric thresholds. The config SHALL use sub-dataclasses grouped by concern. Default values SHALL exactly match current hardcoded values.

#### Scenario: Default config matches current behavior
- **WHEN** a `ReasoningEngine` is constructed without a config parameter (or `config=None`)
- **THEN** it SHALL behave identically to the current implementation with all hardcoded defaults

#### Scenario: Custom config overrides thresholds
- **WHEN** a `ReasoningEngine` is constructed with a config that sets `confidence.property_inference_person=0.9`
- **THEN** the `_infer_properties` rule SHALL use 0.9 instead of the default 0.7 for person-keyword entity inference

#### Scenario: Config is a plain dataclass
- **WHEN** `ReasoningEngineConfig()` is instantiated
- **THEN** it SHALL be a `@dataclass` with no required arguments and all fields having default values

### Requirement: Confidence thresholds sub-config
The `ConfidenceThresholds` dataclass SHALL contain all confidence score thresholds used in reasoning rules. Each field name SHALL clearly indicate the rule and context where it is used.

#### Scenario: All property inference confidences are configurable
- **WHEN** `_infer_properties` executes
- **THEN** it SHALL read confidence values from `config.confidence` instead of hardcoded literals

#### Scenario: All classification confidences are configurable
- **WHEN** `_classify_entity` executes
- **THEN** it SHALL read confidence values from `config.confidence` instead of hardcoded literals

#### Scenario: Medical validation thresholds are configurable
- **WHEN** `_validate_medical_context` evaluates entity confidence
- **THEN** it SHALL use `config.confidence.medical_high_threshold` (default 0.8) and `config.confidence.medical_low_threshold` (default 0.6)

### Requirement: Scoring sub-config
The `ScoringConfig` dataclass SHALL contain all scoring parameters used in data availability assessment and answer confidence scoring.

#### Scenario: Data availability boosts are configurable
- **WHEN** `_assess_data_availability` calculates the availability score
- **THEN** it SHALL use `config.scoring.base_availability_score`, `config.scoring.entity_boost_per_item`, `config.scoring.max_entity_boost_items`, and related fields instead of hardcoded values

#### Scenario: Answer confidence scoring is configurable
- **WHEN** `_score_answer_confidence` calculates confidence
- **THEN** it SHALL use `config.scoring.base_answer_confidence`, `config.scoring.warning_penalty_factor`, and related fields instead of hardcoded values

### Requirement: Strategy sub-config
The `StrategyConfig` dataclass SHALL contain configuration for strategy-specific behavior.

#### Scenario: Symbolic-first gap threshold is configurable
- **WHEN** `_symbolic_first_reasoning` decides whether to invoke LLM gap-filling
- **THEN** it SHALL use `config.strategy.symbolic_first_min_inferences` (default 2) instead of the hardcoded `< 2` check

#### Scenario: Neural confidence defaults are configurable
- **WHEN** strategies create neural confidence objects with a fallback
- **THEN** they SHALL use `config.strategy.default_neural_confidence` (default 0.7) instead of the hardcoded 0.7

### Requirement: Cross-layer sub-config
The `CrossLayerConfig` dataclass SHALL contain thresholds used in cross-layer reasoning rules.

#### Scenario: Business concept match threshold is configurable
- **WHEN** `_perception_to_semantic_reasoning` evaluates column pattern matches
- **THEN** it SHALL use `config.cross_layer.concept_match_threshold` (default 0.4) instead of the hardcoded 0.4

#### Scenario: Cross-layer confidence values are configurable
- **WHEN** cross-layer rules assign confidence to inferences
- **THEN** they SHALL use values from `config.cross_layer` instead of hardcoded literals

### Requirement: LLMReasonerConfig dataclass
The LLMReasoner SHALL accept an optional `LLMReasonerConfig` parameter centralizing its confidence defaults.

#### Scenario: LLM inference default confidence is configurable
- **WHEN** `LLMReasoner.suggest_semantic_relationships` assigns confidence to suggestions
- **THEN** it SHALL use `config.default_inference_confidence` (default 0.7)

#### Scenario: LLM semantic linking confidence is configurable
- **WHEN** `LLMReasoner.suggest_business_concepts` assigns confidence to suggestions
- **THEN** it SHALL use `config.default_linking_confidence` (default 0.8)

### Requirement: ValidationLimits dataclass
The ValidationEngine SHALL accept an optional `ValidationLimits` parameter centralizing its size limits.

#### Scenario: ID length limit is configurable
- **WHEN** the ValidationEngine validates an entity ID
- **THEN** it SHALL use `config.max_id_length` (default 100) instead of the hardcoded 100

#### Scenario: Property value size is configurable
- **WHEN** the ValidationEngine validates property values
- **THEN** it SHALL use `config.max_property_value_size` (default 1000) instead of the hardcoded 1000

#### Scenario: Relationship type length is configurable
- **WHEN** the ValidationEngine validates a relationship type name
- **THEN** it SHALL use `config.max_relationship_type_length` (default 50) instead of the hardcoded 50
