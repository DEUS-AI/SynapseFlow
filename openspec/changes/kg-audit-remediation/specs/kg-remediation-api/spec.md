## ADDED Requirements

### Requirement: Cytokine type mapping query
`REMEDIATION_QUERIES` SHALL include a `cytokine_mapping` query that matches entities with `type IN ['Cytokine', 'cytokine', 'Cytokines', 'cytokines']` or labels `['Cytokine']`, and sets `_ontology_mapped=true`, `_canonical_type='protein'`, `_original_type=n.type`, `layer=COALESCE(n.layer, 'SEMANTIC')`. The query SHALL skip entities where `_ontology_mapped=true`.

#### Scenario: Cytokine entities are mapped to protein
- **WHEN** batch remediation runs and entities with `type = "Cytokine"` exist
- **THEN** those entities SHALL have `_ontology_mapped=true`, `_canonical_type="protein"`, and `_original_type="Cytokine"`

#### Scenario: Original type is preserved
- **WHEN** a Cytokine entity is remediated
- **THEN** `_original_type` SHALL retain the original value (e.g., `"Cytokine"`) for traceability

### Requirement: Chemical type mapping query
`REMEDIATION_QUERIES` SHALL include a `chemical_mapping` query that matches entities with `type IN ['Chemical', 'chemical', 'Chemicals', 'chemicals']` or labels `['Chemical']`, and sets `_ontology_mapped=true`, `_canonical_type='drug'`, `_original_type=n.type`, `layer=COALESCE(n.layer, 'SEMANTIC')`. The query SHALL skip entities where `_ontology_mapped=true`.

#### Scenario: Chemical entities are mapped to drug
- **WHEN** batch remediation runs and entities with `type = "Chemical"` exist
- **THEN** those entities SHALL have `_ontology_mapped=true` and `_canonical_type="drug"`

#### Scenario: Already-mapped chemicals are skipped
- **WHEN** a Chemical entity already has `_ontology_mapped=true`
- **THEN** the chemical_mapping query SHALL NOT modify it
