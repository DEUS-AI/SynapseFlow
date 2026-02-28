"""Configuration dataclasses for ReasoningEngine thresholds.

Follows the PromotionThresholds pattern from AutomaticLayerTransitionService:
injectable via constructor, all fields have defaults matching prior hardcoded values.
"""

from dataclasses import dataclass, field


@dataclass
class ConfidenceThresholds:
    """Confidence values assigned to inferences and decision thresholds in reasoning rules."""

    # _infer_properties
    id_pattern_confidence: float = 0.8
    person_keyword_confidence: float = 0.7
    transaction_keyword_confidence: float = 0.7
    contact_info_confidence: float = 0.9
    temporal_property_confidence: float = 0.8

    # _classify_entity
    classify_person_confidence: float = 0.8
    classify_financial_confidence: float = 0.7
    classify_process_confidence: float = 0.6

    # _suggest_relationships
    suggest_email_rel_confidence: float = 0.7
    suggest_date_rel_confidence: float = 0.6

    # _suggest_inverse_relationship
    inverse_relationship_confidence: float = 0.8

    # _apply_transitive_closure
    transitive_closure_confidence: float = 0.9

    # _validate_medical_context
    medical_high_threshold: float = 0.8
    medical_low_threshold: float = 0.6
    validated_entity_confidence: float = 0.9

    # _check_treatment_recommendations
    treatment_recommendation_confidence: float = 0.95

    # _infer_cross_graph_relationships
    cross_graph_table_confidence: float = 0.75
    cross_graph_column_confidence: float = 0.70


@dataclass
class ScoringConfig:
    """Parameters for data availability assessment and answer confidence scoring."""

    # _assess_data_availability
    base_availability_score: float = 0.5
    entity_boost_per_item: float = 0.1
    max_entity_boost_items: int = 3
    relationship_boost_per_item: float = 0.1
    max_relationship_boost_items: int = 2
    table_boost_per_item: float = 0.1
    max_table_boost_items: int = 2
    column_boost: float = 0.05
    quality_high_threshold: float = 0.8
    quality_medium_threshold: float = 0.6
    availability_assessment_confidence: float = 0.85

    # _score_answer_confidence
    base_answer_confidence: float = 0.5
    validated_entity_threshold: float = 0.8
    answer_entity_boost: float = 0.1
    max_answer_entity_boost_items: int = 3
    answer_relationship_boost: float = 0.05
    max_answer_relationship_boost_items: int = 2
    answer_cross_graph_boost: float = 0.1
    warning_penalty_factor: float = 0.95


@dataclass
class StrategyConfig:
    """Strategy-level parameters controlling reasoning behavior."""

    # _symbolic_first_reasoning: LLM gap-filling triggered when inferences < this
    symbolic_first_min_inferences: int = 2

    # Default confidence for neural inferences when not provided
    default_neural_confidence: float = 0.7

    # apply_advanced_reasoning: consolidation suggestion threshold
    relationship_type_consolidation_threshold: int = 10


@dataclass
class CrossLayerConfig:
    """Thresholds for cross-layer reasoning rules."""

    # _perception_to_semantic_reasoning
    concept_match_threshold: float = 0.4
    min_concept_confidence: float = 0.6
    concept_confidence_boost: float = 0.4
    promote_to_semantic_confidence: float = 0.8
    domain_classification_confidence: float = 0.75

    # _semantic_to_reasoning_reasoning
    quality_rule_confidence: float = 0.85
    referential_integrity_confidence: float = 0.95
    composition_rule_confidence: float = 0.9
    promote_to_reasoning_confidence: float = 0.8

    # _reasoning_to_application_reasoning
    duplicate_detection_confidence: float = 0.8
    temporal_analysis_confidence: float = 0.75
    aggregation_confidence: float = 0.8
    materialized_view_threshold: float = 0.9
    materialized_view_confidence: float = 0.7
    fk_index_confidence: float = 0.9

    # _application_to_perception_reasoning
    temporal_data_confidence: float = 0.75
    aggregate_metadata_confidence: float = 0.7
    high_access_threshold: int = 100
    data_gap_confidence: float = 0.8
    query_error_threshold: int = 10
    review_data_confidence: float = 0.85


@dataclass
class ReasoningEngineConfig:
    """Top-level configuration for the ReasoningEngine.

    All fields have defaults matching the original hardcoded values.
    Construct with no arguments for identical behavior to prior code.
    """

    confidence: ConfidenceThresholds = field(default_factory=ConfidenceThresholds)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    cross_layer: CrossLayerConfig = field(default_factory=CrossLayerConfig)
