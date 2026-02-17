## MODIFIED Requirements

### Requirement: Unknown type entities are flagged for review not mapped
Entities with `type = 'Unknown'` or `type = 'unknown'` SHALL NOT receive an ontology mapping. The remediation pipeline SHALL flag them with `_needs_review = true` and `_review_reason = 'unknown_type'`. Additionally, the audit SHALL query the graph for ALL distinct type values not covered by any registry (DATA_ONTOLOGY_REGISTRY, MEDICAL_ONTOLOGY_REGISTRY, MEDICAL_TYPE_ALIASES) — not limited to `Unknown` — and produce a complete unmapped type inventory with entity counts per type. The quality assessment service SHALL exclude `_needs_review=true` entities from the `unmapped_types` list in coverage scoring, so that "Unknown" does not appear as an actionable recommendation.

#### Scenario: Unknown type is not mapped
- **WHEN** `resolve_medical_type("Unknown")` is called
- **THEN** it SHALL return `"unknown"` (passthrough, no alias match)

#### Scenario: Unknown type is not in the registry
- **WHEN** `is_medical_type("Unknown")` is called
- **THEN** it SHALL return `False`

#### Scenario: Unknown type entity is flagged during remediation
- **WHEN** batch remediation runs and an entity has `type = 'Unknown'`
- **THEN** the entity SHALL have `_needs_review = true` and `_review_reason = 'unknown_type'` set, and SHALL NOT have `_ontology_mapped = true`

#### Scenario: All unmapped types are inventoried
- **WHEN** the audit queries all distinct `type` values from the graph
- **THEN** it SHALL produce a list of every type not found in DATA_ONTOLOGY_REGISTRY, MEDICAL_ONTOLOGY_REGISTRY, or MEDICAL_TYPE_ALIASES, with the count of entities per unmapped type

#### Scenario: Registry-vs-graph drift is quantified
- **WHEN** the unmapped type inventory is complete
- **THEN** the audit SHALL report the drift ratio: (unmapped entity count) / (total entity count) as a percentage

#### Scenario: Assessment excludes review-pending types from recommendations
- **WHEN** the quality assessment runs and all unmapped entities have `_needs_review=true`
- **THEN** the assessment SHALL NOT generate an "Add ontology mappings for types" recommendation
