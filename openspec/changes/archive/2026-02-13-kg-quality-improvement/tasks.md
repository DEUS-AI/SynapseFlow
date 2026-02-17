## 1. Extend ODINMedical with missing types

- [x] 1.1 Add PROTEIN, BIOMARKER, CELL_TYPE, ORGANISM, VIRUS constants to `ODINMedical` class in `src/domain/ontologies/odin_medical.py`
- [x] 1.2 Add registry entries for protein, biomarker, cell_type, organism, virus to `MEDICAL_ONTOLOGY_REGISTRY` with layer, auto_relationships, and external_systems
- [x] 1.3 Remove the "biomarker"→"test" alias from `MEDICAL_TYPE_ALIASES` and add new aliases for the 5 new types (proteins, biomarkers, cell types, organisms, viruses, etc.)

## 2. Add medical schemas to ODIN_SCHEMAS

- [x] 2.1 Add `OntologyClassSchema` entries to `ODIN_SCHEMAS` in `src/domain/ontology_quality_models.py` for all 16 existing medical types (Symptom, Test, Observation, Measurement, Disease, Condition, Drug, Treatment, Anatomy, Pathway, Gene, Mechanism, Interaction, Guideline, Protocol, Study, Organization)
- [x] 2.2 Add `OntologyClassSchema` entries for the 5 new types (Protein, Biomarker, CellType, Organism, Virus)
- [x] 2.3 Add Schema.org mappings to `SCHEMA_ORG_MAPPINGS` for medical types (Disease→MedicalCondition, Drug→Drug, Symptom→MedicalSignOrSymptom, Treatment→MedicalTherapy, Study→MedicalStudy, Organization→Organization, Test→MedicalTest, Gene→Gene, Anatomy→AnatomicalStructure)

## 3. Add missing remediation queries

- [x] 3.1 Add Cypher queries for Protein, Biomarker, CellType, Organism, Virus to `REMEDIATION_QUERIES` in `scripts/ontology_batch_remediation.py`
- [x] 3.2 Add a null-type inference query that sets type from Neo4j labels matching known ODIN types
- [x] 3.3 Add a null-type fallback query that flags remaining untyped entities with `_needs_review=true`
- [x] 3.4 Add an orphan node flagging query that sets `_is_orphan=true` on entities with zero relationships
- [x] 3.5 Update the existing Biomarker handling — remove from Test query if previously included, ensure standalone Biomarker query handles it

## 4. Extract RemediationService

- [x] 4.1 Create `src/application/services/remediation_service.py` with a `RemediationService` class that accepts a Neo4j driver/backend and exposes `dry_run()`, `execute()`, `rollback()` async methods
- [x] 4.2 Move the remediation query definitions and execution logic from the CLI script into the service
- [x] 4.3 Update `scripts/ontology_batch_remediation.py` to use `RemediationService` instead of inline queries

## 5. Create remediation API router

- [x] 5.1 Create `src/application/api/remediation_router.py` with endpoints: `POST /api/ontology/remediation/dry-run`, `POST /api/ontology/remediation/execute`, `POST /api/ontology/remediation/rollback/{batch_id}`
- [x] 5.2 Add `GET /api/ontology/orphans` endpoint that lists entities flagged with `_is_orphan=true`
- [x] 5.3 Register the remediation router in `src/application/api/main.py`
- [x] 5.4 Add dependency injection for `RemediationService` in `src/application/api/dependencies.py`

## 6. Tests

- [x] 6.1 Add tests for `resolve_medical_type()` with new types (protein, biomarker, cell_type, organism, virus) and verify biomarker no longer resolves to test
- [x] 6.2 Add tests verifying all medical types have entries in `ODIN_SCHEMAS`
- [x] 6.3 Add tests for `RemediationService.dry_run()` and `RemediationService.execute()` with mocked Neo4j backend
- [x] 6.4 Add tests for remediation API endpoints (dry-run, execute, rollback, orphans)

## 7. Verification

- [x] 7.1 Run the full test suite to confirm no regressions
- [ ] 7.2 Run dry-run via API to verify remediation preview against the live graph
