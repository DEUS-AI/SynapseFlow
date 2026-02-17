## ADDED Requirements

### Requirement: ConversationSession and Message nodes are classified as structural
ConversationSession and Message nodes SHALL be treated as structural/operational entities, not knowledge entities. They SHALL have `_is_structural=true` and `_exclude_from_ontology=true` set, placing them in the same category as Chunk, Document, and ExtractedEntity nodes.

#### Scenario: ConversationSession is excluded from knowledge metrics
- **WHEN** the quality assessment calculates knowledge entity coverage
- **THEN** ConversationSession nodes SHALL NOT be counted as knowledge entities

#### Scenario: Message is excluded from knowledge metrics
- **WHEN** the quality assessment calculates knowledge entity coverage
- **THEN** Message nodes SHALL NOT be counted as knowledge entities

#### Scenario: New conversation nodes are marked structural during remediation
- **WHEN** batch remediation runs and ConversationSession or Message nodes exist without `_is_structural=true`
- **THEN** the structural marking step SHALL set `_is_structural=true` and `_exclude_from_ontology=true` on those nodes

### Requirement: ConversationSession and Message are not ontology-mapped
The remediation pipeline SHALL NOT set `_ontology_mapped=true` or `_canonical_type` on ConversationSession or Message nodes. These nodes are operational metadata, not domain entities in the DIKW pyramid.

#### Scenario: Conversation nodes are not mapped to APPLICATION layer
- **WHEN** batch remediation runs
- **THEN** no ConversationSession or Message node SHALL have `_canonical_type='usage'` or `layer='APPLICATION'` set by the remediation pipeline

#### Scenario: Conversation nodes do not appear in unmapped types
- **WHEN** the unmapped types query runs to list entities needing ontology mapping
- **THEN** ConversationSession and Message nodes SHALL NOT appear in the results (excluded as structural)

### Requirement: Previously remediated conversation nodes are migrated
The remediation pipeline SHALL include a migration query that corrects any ConversationSession or Message nodes previously mapped as APPLICATION/usage by removing `_ontology_mapped`, `_canonical_type`, and setting `_is_structural=true` and `_exclude_from_ontology=true`.

#### Scenario: Previously mapped conversation node is corrected
- **WHEN** a ConversationSession node has `_ontology_mapped=true` and `_canonical_type='usage'` from a prior remediation batch
- **THEN** the migration query SHALL remove `_ontology_mapped` and `_canonical_type`, and set `_is_structural=true` and `_exclude_from_ontology=true`

#### Scenario: Migration is idempotent
- **WHEN** the migration query runs on a ConversationSession node already marked as structural
- **THEN** it SHALL not modify the node (guarded by `NOT coalesce(n._is_structural, false)`)
