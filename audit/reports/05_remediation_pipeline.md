# Remediation Pipeline Assessment

**Date**: 2026-02-17
**Service**: `src/application/services/remediation_service.py` (931 lines)
**Queries**: 27 REMEDIATION_QUERIES + 6 auxiliary queries

---

## Executive Summary

The remediation pipeline is well-architected with 27 type-mapping queries, dry-run preview, batch execution, and rollback support. However, it has **never been executed** against the live graph. 6 graph types lack dedicated remediation queries (Cytokine, Chemical, Compound, Bacteria, Species, Cell). Rollback handles the core `_ontology_mapped` and `_canonical_type` properties but may not revert all auxiliary properties. Idempotency is designed in but untested against live data.

---

## 1. Query Coverage Audit

### Covered Types (25 direct type-mapping queries)

| Query | Source Types | Canonical Target | Layer |
|-------|-------------|-----------------|-------|
| business_concept_mapping | BusinessConcept, Concept, concept, business_concept | business_concept | REASONING |
| person_mapping | Person, People, User, Owner, Stakeholder | person | SEMANTIC |
| data_product_mapping | DataProduct, Data Product, Product | data_product | SEMANTIC |
| table_mapping | Table, DataEntity, Entity | table | PERCEPTION |
| column_mapping | Column, Attribute, Field | column | PERCEPTION |
| process_mapping | Process, Pipeline, ETL, Job, Workflow | process | REASONING |
| disease_mapping | Disease, MedicalCondition, Condition, Disorder | disease | SEMANTIC |
| drug_mapping | Drug, Medication, Medicine, Pharmaceutical | drug | SEMANTIC |
| symptom_mapping | Symptom, Sign, Manifestation | symptom | PERCEPTION |
| treatment_mapping | Treatment, Therapy, Procedure, Intervention | treatment | SEMANTIC |
| organization_mapping | Organization, Company, Institution, University, Hospital | organization | APPLICATION |
| gene_mapping | Gene, GeneticMarker | gene | REASONING |
| metric_mapping | Metric, KPI, Indicator, Measure | metric | APPLICATION |
| system_mapping | System, Application, Service | system | PERCEPTION |
| database_mapping | Database, DB | database | PERCEPTION |
| factunit_mapping | FactUnit, Bridge | business_concept | REASONING |
| patient_mapping | Patient | person | SEMANTIC |
| medication_mapping | Medication, MedicalEntity | drug | SEMANTIC |
| diagnosis_mapping | Diagnosis | disease | SEMANTIC |
| protein_mapping | Protein, Enzyme | protein | SEMANTIC |
| biomarker_mapping | Biomarker, BiologicalMarker | biomarker | PERCEPTION |
| cell_type_mapping | Cell Type, CellType, celltype, Cell | cell_type | SEMANTIC |
| organism_mapping | Organism, Species, Pathogen, Bacterium, bacteria | organism | SEMANTIC |
| virus_mapping | Virus, ViralAgent | virus | SEMANTIC |
| food_component_mapping | FoodComponent, Nutrient, Vitamin, DietarySubstance | food_component | SEMANTIC |

### Plus specialty queries:
- `genus_mapping`: Genus → organism
- `model_organism_mapping`: Model Organism → organism
- `conversation_structural_migration`: ConversationSession/Message reclassification

### Auxiliary queries:
- `null_type_label_inference`: Infer type from Neo4j labels for null-type entities
- `null_type_flag_review`: Flag remaining null-type entities for manual review
- `unknown_type_flag_review`: Flag "Unknown" type entities
- `orphan_node_flagging`: Flag zero-relationship entities
- `orphan_source_classification`: Classify orphans by source (episodic/knowledge/unclassified)
- `type_consistency_normalization`: Normalize inconsistent canonical types

---

## 2. Types NOT Covered by Remediation Queries

| Graph Type | Count | Suggested Action |
|-----------|-------|-----------------|
| Cytokine | 9 | Add `cytokine_mapping` query → protein OR new type |
| Chemical | 4 | Add `chemical_mapping` query → drug |
| Compound | 4 | Partially covered by drug_mapping (if type matches), but "Compound" not in drug list |
| Bacteria | 2 | Covered by organism_mapping (bacteria in list) |
| Species | 2 | Covered by organism_mapping (Species in list) |
| Cell | 1 | Covered by cell_type_mapping (Cell in list) |

**Actually uncovered**: Cytokine (9 entities), Chemical (4 entities), Compound (4 entities partially)

### Medical registry types with no remediation query:
- `pathway`, `mechanism`, `interaction` (REASONING layer)
- `guideline`, `protocol`, `study` (APPLICATION layer — study entities exist in graph!)
- `anatomy`, `observation`, `measurement` (PERCEPTION/SEMANTIC layer)

**Missing remediation for existing graph types**: Pathway (52 entities), Study (46 entities), Guideline (1 entity)

---

## 3. Dry-Run / No-Op Analysis

Without executing, based on graph type distribution:
- **Likely no-ops** (0 matching entities): database_mapping, system_mapping, data_product_mapping, table_mapping, column_mapping, process_mapping, metric_mapping, factunit_mapping, person_mapping (no "Person" type in graph)
- **Likely high-impact**: disease_mapping (179), drug_mapping (194), treatment_mapping (151), gene_mapping (134), organization_mapping (215), symptom_mapping (91)
- **Assessment**: ~15 queries will be no-ops (data architecture types not in graph)

---

## 4. Rollback Completeness

### Properties handled by ROLLBACK_QUERY:
- `_ontology_mapped` → removed
- `_canonical_type` → removed
- `_ontology_class` → removed
- `_original_type` → used to restore `type`
- `_mapping_batch_id` → used for batch targeting

### Properties NOT explicitly rolled back:
- `_is_orphan` → set by orphan_node_flagging, not rolled back
- `_orphan_source` → set by orphan_source_classification, not rolled back
- `_consistency_fixed` → set by type_consistency_normalization, not rolled back
- `_needs_review` → set by null_type_flag_review/unknown_type_flag_review, not rolled back
- `_review_reason` → set alongside `_needs_review`, not rolled back
- `layer` → modified by type mappings, **not explicitly rolled back** (original layer not saved)

**Risk**: Rolling back a batch will restore types but leave orphan flags, review markers, and potentially modified layers in place.

---

## 5. Idempotency Assessment

**Design**: Queries use `WHERE NOT n._ontology_mapped = true` guard, so re-execution should skip already-mapped entities.

**Potential issues**:
- If rollback is partial (removes `_ontology_mapped` but not `_canonical_type`), re-execution may create inconsistent state
- `type_consistency_normalization` sets `_consistency_fixed` but doesn't check for it — could re-apply
- Orphan flagging queries don't check existing `_is_orphan` — will re-flag already-flagged orphans

---

## Recommendations

**P0**: Execute dry-run against live graph to validate query impact
**P1**: Add remediation queries for: Cytokine, Chemical, Compound, Pathway, Study
**P1**: Save `_original_layer` before modifying layer in remediation queries
**P2**: Add rollback support for auxiliary properties (_is_orphan, _needs_review, etc.)
**P2**: Add idempotency guards to orphan flagging and consistency normalization queries
**P3**: Remove no-op queries from execution path (skip data architecture queries when no DDA entities exist)
