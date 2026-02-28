## 1. ReasoningEngineConfig Dataclass

- [x] 1.1 Create `ReasoningEngineConfig` with sub-dataclasses (`ConfidenceThresholds`, `ScoringConfig`, `StrategyConfig`, `CrossLayerConfig`) in a new file `src/application/agents/knowledge_manager/reasoning_config.py`, with all defaults matching current hardcoded values
- [x] 1.2 Add `config: Optional[ReasoningEngineConfig] = None` to `ReasoningEngine.__init__`, defaulting to `ReasoningEngineConfig()` when None
- [x] 1.3 Replace all hardcoded thresholds in `_infer_properties`, `_classify_entity`, `_suggest_relationships`, `_suggest_inverse_relationship` with `self.config.confidence.*` references
- [x] 1.4 Replace all hardcoded thresholds in `_validate_medical_context`, `_check_treatment_recommendations`, `_infer_cross_graph_relationships` with `self.config.confidence.*` references
- [x] 1.5 Replace all hardcoded thresholds in `_assess_data_availability`, `_score_answer_confidence` with `self.config.scoring.*` references
- [x] 1.6 Replace the hardcoded `< 2` inference gap threshold in `_symbolic_first_reasoning` and neural confidence default `0.7` across strategies with `self.config.strategy.*` references
- [x] 1.7 Replace all hardcoded thresholds in cross-layer rules (`_perception_to_semantic_reasoning`, `_semantic_to_reasoning_reasoning`, `_reasoning_to_application_reasoning`) with `self.config.cross_layer.*` references

## 2. LLMReasoner and ValidationEngine Configs

- [x] 2.1 Create `LLMReasonerConfig` dataclass in `llm_reasoner.py` with `default_inference_confidence=0.7` and `default_linking_confidence=0.8`, wire into `LLMReasoner.__init__`
- [x] 2.2 Create `ValidationLimits` dataclass in `validation_engine.py` with `max_id_length=100`, `max_property_value_size=1000`, `max_relationship_type_length=50`, wire into `ValidationEngine.__init__`

## 3. Reasoning Observability

- [x] 3.1 Add INFO log at strategy selection in `apply_reasoning` with strategy, action, and rule count
- [x] 3.2 Add DEBUG log per rule execution in strategy methods (fired with counts, or skipped)
- [x] 3.3 Add INFO summary log after `apply_reasoning` completes with rules_fired, inferences, suggestions, warnings, time
- [x] 3.4 Add DEBUG log in `apply_cross_layer_reasoning` for layer transition evaluation

## 4. ReasoningEngine Test Suite

- [x] 4.1 Create test file `tests/application/agents/knowledge_manager/test_reasoning_engine.py` with fixtures: mock backend, sample KnowledgeEvents for each action type
- [x] 4.2 Add unit tests for pure-logic create_entity rules: `_infer_properties` (ID patterns, person keywords, email, temporal), `_classify_entity` (person, financial, process), `_suggest_relationships` (email, date patterns)
- [x] 4.3 Add unit tests for create_relationship rules: `_validate_relationship_logic` (self-reference, naming), `_suggest_inverse_relationship` (all 5 patterns + unknown)
- [x] 4.4 Add unit tests for chat_query rules: `_validate_medical_context` (high/low confidence thresholds), `_check_treatment_recommendations` (keyword detection), `_infer_cross_graph_relationships` (name matching), `_assess_data_availability` (scoring), `_score_answer_confidence` (combined factors)
- [x] 4.5 Add strategy tests: `apply_reasoning` with each of neural_first, symbolic_first, collaborative; verify no-LLM path; verify symbolic-first gap-filling threshold
- [x] 4.6 Add provenance tests: verify `get_inference_provenance` returns records after reasoning; verify None for unknown entity
- [x] 4.7 Add custom rule tests: `add_custom_reasoning_rule` execution, `remove_reasoning_rule` success and failure
- [x] 4.8 Add cross-layer tests: `apply_cross_layer_reasoning` for PERCEPTION, SEMANTIC, REASONING layers; unknown layer returns empty
- [x] 4.9 Add advanced reasoning tests: `apply_advanced_reasoning` orphaned relationship detection, relationship consolidation suggestion

## 5. Verification

- [x] 5.1 Run the new test suite and verify all tests pass (83/83 passing — required `pythonpath = ["src"]` in pyproject.toml)
- [x] 5.2 Run existing tests to confirm no regressions from config extraction (524 passed; 3 pre-existing errors in test_modeling_command_basic.py due to ModelingWorkflow signature change, 1 pre-existing failure in test_data_engineer_metadata_integration.py — none related to this change)
