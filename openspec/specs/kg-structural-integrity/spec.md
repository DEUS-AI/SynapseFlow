## ADDED Requirements

### Requirement: Orphan node detection across Neo4j graph
The audit SHALL execute a Cypher query against the Neo4j graph to identify all nodes with zero relationships (both incoming and outgoing). Results SHALL include the node's `name`, `type`, `layer`, Neo4j labels, and total count of orphan nodes.

#### Scenario: Orphan nodes are detected
- **WHEN** the structural integrity audit runs the orphan detection query
- **THEN** it SHALL return a list of all nodes with zero relationships, including their `name`, `type`, `layer`, and Neo4j labels

#### Scenario: Connected nodes are excluded
- **WHEN** the orphan detection query runs
- **THEN** nodes with at least one relationship (incoming or outgoing) SHALL NOT appear in the results

### Requirement: Dangling relationship detection
The audit SHALL execute a Cypher query to detect relationships where either the source or target node is missing (dangling references). Results SHALL include the relationship type, direction, and the identifier of the missing endpoint.

#### Scenario: Dangling relationships are detected
- **WHEN** the structural integrity audit runs the dangling relationship query
- **THEN** it SHALL return all relationships that reference a non-existent source or target node

#### Scenario: Valid relationships are excluded
- **WHEN** the dangling relationship query runs
- **THEN** relationships where both source and target nodes exist SHALL NOT appear in the results

### Requirement: Layer assignment violation detection
The audit SHALL verify that every entity's `layer` property contains a valid DIKW value (`PERCEPTION`, `SEMANTIC`, `REASONING`, or `APPLICATION`). Entities with null, empty, or invalid layer values SHALL be reported as violations.

#### Scenario: Null layer is a violation
- **WHEN** an entity has `layer = null`
- **THEN** the audit SHALL report it as a layer assignment violation

#### Scenario: Invalid layer value is a violation
- **WHEN** an entity has `layer = "INVALID_VALUE"`
- **THEN** the audit SHALL report it as a layer assignment violation

#### Scenario: Valid DIKW layers pass
- **WHEN** an entity has `layer = "SEMANTIC"`
- **THEN** the audit SHALL NOT report it as a violation

### Requirement: Layer-confidence consistency check
The audit SHALL verify that entity confidence scores are consistent with their layer assignment per the promotion thresholds: PERCEPTION (any confidence), SEMANTIC (confidence >= 0.85), REASONING (confidence >= 0.90), APPLICATION (confidence ~1.0). Entities in higher layers with confidence below their layer's threshold SHALL be flagged.

#### Scenario: SEMANTIC entity with low confidence is flagged
- **WHEN** an entity has `layer = "SEMANTIC"` and `confidence = 0.60`
- **THEN** the audit SHALL flag it as a layer-confidence inconsistency

#### Scenario: PERCEPTION entity with low confidence passes
- **WHEN** an entity has `layer = "PERCEPTION"` and `confidence = 0.50`
- **THEN** the audit SHALL NOT flag it as an inconsistency

### Requirement: Duplicate entity detection
The audit SHALL identify potential duplicate entities by comparing entity names within the same type using exact match (case-insensitive) and fuzzy match (Levenshtein similarity >= 0.90). Results SHALL include both entity IDs, names, types, similarity score, and the match method used.

#### Scenario: Case-insensitive exact duplicates are detected
- **WHEN** two entities exist with `name = "Aspirin"` and `name = "aspirin"` of the same type
- **THEN** the audit SHALL report them as exact-match duplicates

#### Scenario: Fuzzy duplicates are detected
- **WHEN** two entities exist with `name = "Acetaminophen"` and `name = "Acetaminofen"` of the same type
- **THEN** the audit SHALL report them as fuzzy-match duplicates with the similarity score

#### Scenario: Different-type entities are not flagged as duplicates
- **WHEN** two entities with the same name exist but with different types
- **THEN** the audit SHALL NOT flag them as duplicates

### Requirement: Unmapped entity type detection
The audit SHALL query all distinct `type` values from the Neo4j graph and compare them against the unified ontology registry (DATA_ONTOLOGY_REGISTRY + MEDICAL_ONTOLOGY_REGISTRY + MEDICAL_TYPE_ALIASES). Types present in the graph but absent from all registries SHALL be reported as unmapped.

#### Scenario: Graph type not in any registry is unmapped
- **WHEN** the graph contains entities with `type = "CustomWidget"` and this type is not in any registry
- **THEN** the audit SHALL report `"CustomWidget"` as an unmapped type with its entity count

#### Scenario: Aliased type is not reported as unmapped
- **WHEN** the graph contains entities with `type = "Genus"` and `"genus"` maps to `"organism"` via MEDICAL_TYPE_ALIASES
- **THEN** the audit SHALL NOT report it as unmapped

### Requirement: Structural integrity summary report
The audit SHALL produce a summary report aggregating all structural findings into a single document with sections for: orphan nodes (count, breakdown by type), dangling relationships (count, by relationship type), layer violations (count, by violation type), layer-confidence inconsistencies (count, by layer), duplicates (count, by type), and unmapped types (count, type list).

#### Scenario: Summary report is generated
- **WHEN** all structural integrity queries have completed
- **THEN** the audit SHALL produce a summary with total counts and breakdowns for each finding category

#### Scenario: Clean graph produces empty findings
- **WHEN** all structural integrity queries return zero results
- **THEN** the summary SHALL report zero findings across all categories
