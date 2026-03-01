## ADDED Requirements

### Requirement: Pure-logic rule unit tests
The ReasoningEngine SHALL have unit tests for all pure-logic rules that require no external service mocks. These rules are: `_infer_properties`, `_classify_entity`, `_suggest_relationships`, `_validate_relationship_logic`, `_suggest_inverse_relationship`, `_check_treatment_recommendations`, `_validate_medical_context`, `_assess_data_availability`, `_score_answer_confidence`, `_infer_cross_graph_relationships`.

#### Scenario: Property inference from ID patterns
- **WHEN** a `KnowledgeEvent` with `action="create_entity"` has an entity ID ending in `_id`
- **THEN** the `_infer_properties` rule SHALL return an inference with `entity_type="identifier"` and `confidence=0.8`

#### Scenario: Property inference from person keywords
- **WHEN** a `KnowledgeEvent` has an entity ID containing "customer"
- **THEN** the `_infer_properties` rule SHALL return an inference with `entity_type="person"` and `confidence=0.7`

#### Scenario: Entity classification with name and email
- **WHEN** a `KnowledgeEvent` has properties containing both "name" and "email"
- **THEN** the `_classify_entity` rule SHALL return a suggestion with `classification="person"` and `confidence=0.8`

#### Scenario: Inverse relationship suggestion
- **WHEN** a `KnowledgeEvent` with `action="create_relationship"` has `type="has_part"`
- **THEN** the `_suggest_inverse_relationship` rule SHALL return a suggestion with `inverse_type="part_of"` and `confidence=0.8`

#### Scenario: Treatment recommendation detection
- **WHEN** a `KnowledgeEvent` with `action="chat_query"` has a question containing "should i take"
- **THEN** the `_check_treatment_recommendations` rule SHALL return a warning about treatment recommendations and an inference with `disclaimer_required=True`

#### Scenario: Medical entity validation thresholds
- **WHEN** a `KnowledgeEvent` has medical entities with confidence >= 0.8
- **THEN** the `_validate_medical_context` rule SHALL classify them as high-confidence and return `validated_medical_entity` inferences

#### Scenario: Low-confidence medical entity warning
- **WHEN** a `KnowledgeEvent` has medical entities with confidence < 0.6
- **THEN** the `_validate_medical_context` rule SHALL return a warning about entities needing verification

#### Scenario: Data availability scoring
- **WHEN** a `KnowledgeEvent` has 3 medical entities, 2 relationships, and 1 data table
- **THEN** the `_assess_data_availability` rule SHALL return a score reflecting all context boosts

#### Scenario: Cross-graph relationship inference
- **WHEN** a `KnowledgeEvent` has a medical entity named "diabetes" and a data table named "diabetes_patients"
- **THEN** the `_infer_cross_graph_relationships` rule SHALL return an `inferred_cross_graph_link` inference

### Requirement: Strategy behavior tests
The ReasoningEngine SHALL have tests verifying each reasoning strategy's execution pattern with a mock backend.

#### Scenario: Neural-first strategy applies LLM before symbolic rules
- **WHEN** `apply_reasoning` is called with `strategy="neural_first"` and an LLM reasoner is provided
- **THEN** the result SHALL include `llm_semantic_inference` in `applied_rules` before symbolic rules, and neural inferences SHALL have `certainty="tentative"`

#### Scenario: Symbolic-first strategy applies rules before LLM gap-filling
- **WHEN** `apply_reasoning` is called with `strategy="symbolic_first"` and the symbolic rules produce fewer than 2 inferences
- **THEN** the engine SHALL invoke the LLM reasoner to fill gaps, and neural inferences SHALL have `certainty="tentative"`

#### Scenario: Symbolic-first skips LLM when symbolic produces enough
- **WHEN** `apply_reasoning` is called with `strategy="symbolic_first"` and symbolic rules produce 2+ inferences
- **THEN** the engine SHALL NOT invoke the LLM reasoner

#### Scenario: Collaborative strategy runs all rules
- **WHEN** `apply_reasoning` is called with `strategy="collaborative"`
- **THEN** all registered rules for the action SHALL be executed, and neural rules SHALL be marked `tentative` while symbolic rules SHALL be marked `certain`

#### Scenario: Engine works without LLM
- **WHEN** `ReasoningEngine` is constructed with `llm=None`
- **THEN** `apply_reasoning` SHALL succeed, LLM-dependent rules SHALL return None, and only symbolic rules SHALL contribute to results

### Requirement: Provenance and custom rule tests
The ReasoningEngine SHALL have tests for provenance tracking and the custom rule API.

#### Scenario: Provenance recorded after reasoning
- **WHEN** `apply_reasoning` is called with `enable_confidence_tracking=True`
- **THEN** `get_inference_provenance(entity_id)` SHALL return a list of provenance records with `rule`, `type`, and `contribution` fields

#### Scenario: Custom rule addition and execution
- **WHEN** a custom rule is added via `add_custom_reasoning_rule` and `apply_reasoning` is called for that action
- **THEN** the custom rule SHALL be executed and its results SHALL appear in the reasoning output

#### Scenario: Custom rule removal
- **WHEN** `remove_reasoning_rule` is called with a valid action and rule name
- **THEN** the method SHALL return True and the rule SHALL no longer execute

#### Scenario: Remove non-existent rule
- **WHEN** `remove_reasoning_rule` is called with a rule name that doesn't exist
- **THEN** the method SHALL return False

### Requirement: Cross-layer reasoning tests
The ReasoningEngine SHALL have tests for `apply_cross_layer_reasoning` covering each layer transition.

#### Scenario: PERCEPTION to SEMANTIC inference
- **WHEN** `apply_cross_layer_reasoning` is called with a Table entity in PERCEPTION layer having columns matching "customer_id" and "email"
- **THEN** the result SHALL contain a `business_concept_inference` for "Customer" with confidence reflecting match score

#### Scenario: SEMANTIC to REASONING inference
- **WHEN** `apply_cross_layer_reasoning` is called with a Customer concept entity in SEMANTIC layer
- **THEN** the result SHALL contain quality rules like `email_required` and `unique_email`

#### Scenario: Unknown layer returns empty
- **WHEN** `apply_cross_layer_reasoning` is called with `current_layer="UNKNOWN"`
- **THEN** the result SHALL have empty inferences and suggestions lists

### Requirement: Advanced reasoning tests
The ReasoningEngine SHALL have tests for `apply_advanced_reasoning` covering cross-event consistency.

#### Scenario: Orphaned relationship detection
- **WHEN** `apply_advanced_reasoning` is called with events that include a relationship whose source entity is not in the event list
- **THEN** the result SHALL contain an `orphaned_relationship` consistency check with severity "high"

#### Scenario: Relationship consolidation suggestion
- **WHEN** `apply_advanced_reasoning` is called with events containing more than 10 distinct relationship types
- **THEN** the result SHALL contain a `relationship_consolidation` optimization suggestion
