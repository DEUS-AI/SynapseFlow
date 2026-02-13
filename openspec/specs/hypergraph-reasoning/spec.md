## ADDED Requirements

### Requirement: Hypergraph structural analysis reasoning rule
The system SHALL add a `hypergraph_structural_analysis` rule to the reasoning engine's `chat_query` rules at medium priority, using hypergraph analytics to enrich reasoning with structural insights.

#### Scenario: Rule execution with analytics available
- **WHEN** a `chat_query` reasoning event is processed and the hypergraph analytics service is available
- **THEN** the rule SHALL compute entity centrality and community membership for entities mentioned in the query, and include these as additional context in the reasoning result

#### Scenario: Rule skipped when analytics unavailable
- **WHEN** a `chat_query` reasoning event is processed but the hypergraph analytics service is not provided (None)
- **THEN** the rule SHALL be skipped silently and not affect the reasoning pipeline

### Requirement: Confidence boost for entities in dense clusters
The system SHALL boost the confidence score of entities that are structurally central in the hypergraph or belong to dense knowledge communities.

#### Scenario: Central entity confidence boost
- **WHEN** an entity has an s-centrality score in the top 20% of all entities
- **THEN** the reasoning engine SHALL apply a confidence boost of up to 0.05 to that entity's inferences, proportional to its centrality rank

#### Scenario: Dense community membership boost
- **WHEN** an entity belongs to a community with modularity contribution above the mean
- **THEN** the reasoning engine SHALL apply a confidence boost of up to 0.03 to that entity's inferences

#### Scenario: Boost capping
- **WHEN** combined structural boosts would exceed 0.08
- **THEN** the total structural boost SHALL be capped at 0.08 to prevent over-inflation of confidence scores

### Requirement: Structural insights in reasoning provenance
The system SHALL include hypergraph structural data in reasoning provenance so that explanations can reference community membership and centrality.

#### Scenario: Provenance includes structural context
- **WHEN** the hypergraph structural analysis rule contributes to a reasoning result
- **THEN** the provenance SHALL include: `source: "hypergraph_structural_analysis"`, the entity's `centrality_score`, `community_id`, and `community_size`

### Requirement: Hypergraph coherence quality metric
The system SHALL add a "Hypergraph Coherence" metric to the ontology quality assessment pipeline, measuring structural integrity of the knowledge graph through the hypergraph lens.

#### Scenario: Coherence assessment
- **WHEN** `assess_ontology_quality()` is called and the hypergraph analytics service is available
- **THEN** the quality report SHALL include a "Hypergraph Coherence" metric with a score between 0.0 and 1.0

#### Scenario: Coherence scoring components
- **WHEN** hypergraph coherence is computed
- **THEN** the score SHALL be composed of: modularity score (weight 0.4), proportion of entities in non-trivial communities (weight 0.3), and inverse of isolated component ratio (weight 0.3)

#### Scenario: Quality assessment without analytics
- **WHEN** `assess_ontology_quality()` is called but the hypergraph analytics service is not available
- **THEN** the "Hypergraph Coherence" metric SHALL be omitted from the report and the overall score SHALL be computed from the remaining metrics only

### Requirement: Cache invalidation on crystallization
The system SHALL invalidate the hypergraph adapter's cache when a crystallization cycle completes, ensuring analytics reflect the latest knowledge state.

#### Scenario: Crystallization triggers invalidation
- **WHEN** the crystallization service emits a `crystallization_complete` event
- **THEN** the hypergraph adapter's `invalidate_cache()` method SHALL be called

#### Scenario: No adapter available
- **WHEN** a `crystallization_complete` event is emitted but the hypergraph adapter is not initialized
- **THEN** the event SHALL be ignored without error
