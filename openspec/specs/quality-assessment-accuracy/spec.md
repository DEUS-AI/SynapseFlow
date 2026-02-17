## ADDED Requirements

### Requirement: Coverage assessment excludes review-pending entities from unmapped types
The `_assess_coverage()` method SHALL exclude entities with `_needs_review=true` from the `unmapped_types` list. These entities SHALL still count as unmapped in the `coverage_ratio` calculation, but SHALL NOT appear in the recommendation "Add ontology mappings for types: X".

#### Scenario: Unknown type with _needs_review is excluded from unmapped_types
- **WHEN** the assessment runs and entities with `type='Unknown'` have `_needs_review=true`
- **THEN** `"Unknown"` SHALL NOT appear in `coverage.unmapped_types`

#### Scenario: Truly unmapped type without _needs_review is included
- **WHEN** the assessment runs and entities with `type='NewType'` exist without `_needs_review` or `_ontology_mapped`
- **THEN** `"NewType"` SHALL appear in `coverage.unmapped_types`

#### Scenario: Review-pending entities still count as unmapped in ratio
- **WHEN** the assessment computes `coverage_ratio`
- **THEN** entities with `_needs_review=true` SHALL count as unmapped (not inflating the mapped count)

### Requirement: Consistency assessment incorporates remediation canonical types
The `_assess_consistency()` method SHALL consider `_canonical_type` from remediation when grouping entities for consistency analysis. If an entity has `_ontology_mapped=true` and `_canonical_type` set but no ODIN label, the `_canonical_type` value SHALL be used as the resolved class for consistency grouping.

#### Scenario: Remediation-mapped entity is included in consistency check
- **WHEN** an entity has `type='Cytokine'`, `_ontology_mapped=true`, `_canonical_type='protein'`, and no `Protein` ODIN label
- **THEN** the consistency check SHALL group it under `protein` (from `_canonical_type`)

#### Scenario: Entities with same raw type mapping to same canonical type are consistent
- **WHEN** all entities of `type='Cytokine'` have `_canonical_type='protein'`
- **THEN** the consistency check SHALL count `Cytokine` as a consistent type

#### Scenario: Entities with conflicting canonical types are inconsistent
- **WHEN** entities of `type='Mercury'` have some with `_canonical_type='chemical'` and others with `_canonical_type='planet'`
- **THEN** the consistency check SHALL count `Mercury` as inconsistent

### Requirement: Taxonomy assessment reports orphan breakdown by source
The `_assess_taxonomy()` method SHALL report orphan node counts broken down by `_orphan_source` category (`episodic`, `knowledge`, `unclassified`). The `TaxonomyCoherenceScore` dataclass SHALL include an `orphan_breakdown` field of type `Dict[str, int]`.

#### Scenario: Orphan breakdown is populated from remediation metadata
- **WHEN** the assessment runs and orphan nodes have `_orphan_source` set
- **THEN** `taxonomy.orphan_breakdown` SHALL contain counts per source category (e.g., `{"episodic": 4388, "knowledge": 12, "unclassified": 0}`)

#### Scenario: Orphan breakdown falls back when no remediation metadata exists
- **WHEN** the assessment runs and no entities have `_is_orphan` or `_orphan_source` properties
- **THEN** the assessment SHALL compute orphans from scratch (knowledge entities minus connected nodes) and set `orphan_breakdown` to `{"unclassified": <count>}`

#### Scenario: Orphan count matches breakdown total
- **WHEN** `orphan_breakdown` is computed
- **THEN** `taxonomy.orphan_nodes` SHALL equal the sum of all values in `taxonomy.orphan_breakdown`

### Requirement: Structural entity labels include conversation nodes
`STRUCTURAL_ENTITY_LABELS` in `OntologyQualityService` SHALL include `ConversationSession` and `Message` alongside the existing `Chunk`, `StructuralChunk`, `Document`, and `DocumentQuality` labels.

#### Scenario: ConversationSession is treated as structural
- **WHEN** the assessment encounters an entity with the `ConversationSession` label
- **THEN** `_is_structural_entity()` SHALL return `True`

#### Scenario: Message is treated as structural
- **WHEN** the assessment encounters an entity with the `Message` label
- **THEN** `_is_structural_entity()` SHALL return `True`

### Requirement: Recommendations are context-aware with orphan breakdown
The `generate_recommendations()` method SHALL produce specific orphan recommendations distinguishing knowledge orphans from episodic orphans. When `orphan_breakdown` is available, the recommendation SHALL reference only knowledge orphans as actionable (e.g., "Connect 12 knowledge orphan nodes to the hierarchy") and note episodic orphans as informational.

#### Scenario: Recommendation uses knowledge orphan count
- **WHEN** `orphan_breakdown` shows `{"episodic": 4388, "knowledge": 12, "unclassified": 0}`
- **THEN** the orphan recommendation SHALL reference `12` (the knowledge count), not `4400` (the total)

#### Scenario: No knowledge orphans suppresses orphan recommendation
- **WHEN** `orphan_breakdown` shows `{"episodic": 4388, "knowledge": 0, "unclassified": 0}`
- **THEN** no actionable orphan recommendation SHALL be generated (episodic orphans are deferred)

#### Scenario: Unmapped types recommendation excludes review-pending types
- **WHEN** `coverage.unmapped_types` is empty (all unmapped types have `_needs_review`)
- **THEN** no "Add ontology mappings for types" recommendation SHALL be generated

### Requirement: Quick ontology check includes knowledge coverage and orphan breakdown
The `quick_ontology_check()` function response SHALL include `knowledge_coverage` (ratio of mapped knowledge entities to total knowledge entities) and `orphan_breakdown` (dict of counts by source) alongside existing fields.

#### Scenario: Quick check includes knowledge_coverage
- **WHEN** `quick_ontology_check()` is called
- **THEN** the response SHALL include a `knowledge_coverage` field with a float between 0.0 and 1.0

#### Scenario: Quick check includes orphan_breakdown
- **WHEN** `quick_ontology_check()` is called
- **THEN** the response SHALL include an `orphan_breakdown` field with keys `episodic`, `knowledge`, and `unclassified`
