## Why

The Knowledge Graph quality assessment reports 0% knowledge-entity coverage and 50% schema compliance. All 502 knowledge entities lack ontology mapping flags despite the ODIN medical registry already defining their types (Drug, Disease, Symptom, Treatment, etc.). The batch remediation script covers most types but is missing Protein, Biomarker (as a standalone type), Cell Type, Organism, and Virus. The ODIN_SCHEMAS used for compliance checking only define 6 generic classes (DataEntity, Attribute, etc.) — none of the 16 medical types have schema definitions, so medical entities can never pass compliance. Additionally, 56 entities have null types and 77 are orphan nodes.

## What Changes

- **Extend ODIN_SCHEMAS with medical entity schemas** so Disease, Drug, Symptom, Treatment, Gene, Pathway, Test, Study, Organization, and other medical types have required/optional property definitions for compliance checking
- **Add missing type mappings to batch remediation script** for Protein, Biomarker, Cell Type, Organism, Virus, and any remaining unmapped types
- **Add Schema.org mappings for medical types** (e.g., Disease→MedicalCondition, Drug→Drug, Symptom→MedicalSignOrSymptom) to improve interoperability scoring
- **Add a remediation query for null-type entities** that attempts type inference from labels or relationships
- **Add an orphan node investigation/cleanup query** that either connects orphans to related entities or flags them for review
- **Expose a remediation API endpoint** so batch remediation can be triggered from the frontend quality dashboard instead of only via CLI script

## Capabilities

### New Capabilities
- `medical-schema-compliance`: Defines ODIN schema property requirements for medical entity types so compliance checking works for the medical domain
- `kg-remediation-api`: Exposes batch remediation (dry-run, execute, rollback) as API endpoints callable from the quality dashboard

### Modified Capabilities
_(None — existing ontology quality assessment logic works correctly; it just needs schemas and mappings to evaluate against)_

## Impact

- **Domain models** (1 file): `src/domain/ontology_quality_models.py` — add medical schemas to `ODIN_SCHEMAS`, medical mappings to `SCHEMA_ORG_MAPPINGS`
- **Medical ontology** (1 file): `src/domain/ontologies/odin_medical.py` — add missing types (Protein, Biomarker, CellType, Organism, Virus) and aliases
- **Batch remediation** (1 file): `scripts/ontology_batch_remediation.py` — add queries for missing types, null-type inference, orphan handling
- **API** (1 file): `src/application/api/main.py` — new `/api/ontology/remediation` endpoints (dry-run, execute, rollback)
- **Dependencies**: None (all changes use existing Neo4j backend and ODIN framework)
- **Risk**: Low for schema/mapping additions (additive only). Medium for remediation execution (writes to Neo4j, but rollback is supported per batch).
- **Data**: Neo4j graph — remediation will update `_ontology_mapped`, `_canonical_type`, and property flags on ~500 entities
