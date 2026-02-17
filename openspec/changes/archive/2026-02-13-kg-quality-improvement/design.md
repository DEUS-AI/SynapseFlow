## Context

The KG quality assessment system (`OntologyQualityService`) evaluates entities against `ODIN_SCHEMAS` for compliance and checks `_ontology_mapped` flags for coverage. Currently:

- `ODIN_SCHEMAS` in `ontology_quality_models.py` defines 6 generic classes (DataEntity, Attribute, InformationAsset, BusinessConcept, Domain, DataQualityRule) — none of the 16 medical types from `odin_medical.py` are represented
- `SCHEMA_ORG_MAPPINGS` maps 6 generic types — no medical mappings exist
- The batch remediation script (`scripts/ontology_batch_remediation.py`) has 20 Cypher queries but is missing Protein, Biomarker (standalone), Cell Type, Organism, Virus
- The API has 5 ontology endpoints under `/api/ontology/` but no remediation endpoints — remediation is CLI-only
- 502 knowledge entities have 0% coverage, 56 have null types, 77 are orphans

## Goals / Non-Goals

**Goals:**
- Achieve >80% knowledge coverage by mapping all entities with known types
- Make compliance scoring meaningful for medical entities by adding their schemas
- Enable remediation from the quality dashboard via API endpoints
- Handle edge cases: null-type entities, orphan nodes, and unmapped minor types

**Non-Goals:**
- External ontology integration (SNOMED-CT, ICD-10 lookups) — future work
- Changing the scoring weights or quality level thresholds
- Modifying the ingestion pipeline to auto-map on ingest (separate change)
- UI changes to the quality dashboard

## Decisions

### 1. Add medical schemas to ODIN_SCHEMAS using the same OntologyClassSchema dataclass

**Decision**: Add schemas for all 16 medical types defined in `ODINMedical` (Symptom, Test, Observation, Measurement, Disease, Condition, Drug, Treatment, Anatomy, Pathway, Gene, Mechanism, Interaction, Guideline, Protocol, Study, Organization) plus Protein, Biomarker, CellType, Organism, Virus as new entries.

**Rationale**: The `OntologyClassSchema` dataclass already supports everything needed. Adding entries to the existing `ODIN_SCHEMAS` dict is the simplest approach. Required properties will be `["name", "id"]` for all medical types (matching the existing pattern), with type-specific optional properties like `layer`, `confidence`, `canonical_type`, and medical-specific fields.

**Alternative considered**: Creating a separate `MEDICAL_SCHEMAS` dict — rejected because the compliance checker iterates `ODIN_SCHEMAS` and would need modification to also check a second dict.

### 2. Add missing types to ODINMedical class and registry

**Decision**: Add `PROTEIN`, `BIOMARKER`, `CELL_TYPE`, `ORGANISM`, `VIRUS` to the `ODINMedical` class constants and `MEDICAL_ONTOLOGY_REGISTRY` with appropriate layer assignments and aliases.

**Rationale**: These 5 types account for 23 entities (Protein 5, Biomarker 12, Cell Type 2, Organism 2, Virus 2). Without registry entries, `resolve_medical_type()` and `is_medical_type()` return false for them. Biomarker is currently aliased to Test, but the detailed coverage shows it as a distinct type with 12 entities.

### 3. API remediation endpoints as a new router

**Decision**: Create a `remediation_router.py` with three endpoints:
- `POST /api/ontology/remediation/dry-run` — preview what would change
- `POST /api/ontology/remediation/execute` — run remediation, return batch ID
- `POST /api/ontology/remediation/rollback/{batch_id}` — undo a batch

Extract the remediation logic from the CLI script into a reusable `RemediationService` class in `src/application/services/`, so both the CLI script and the API can call the same code.

**Rationale**: The CLI script directly creates a Neo4j driver and runs queries. Extracting to a service follows the existing clean architecture pattern (services in `application/`, backend access via injected dependencies). The router follows the same pattern as `crystallization_router.py` and `hypergraph_router.py`.

**Alternative considered**: Adding endpoints directly to `main.py` — rejected because main.py is already ~3900 lines and the existing pattern uses separate routers for feature domains.

### 4. Null-type entity handling via label-based inference

**Decision**: Add a remediation query that infers types for null-type entities by examining their Neo4j labels and relationships. For entities with labels matching known ODIN types (e.g., label `Disease` → type `disease`), set the type directly. For entities with only generic labels, attempt inference from relationship types (e.g., entity with `TREATS` relationship → likely Drug or Treatment).

**Rationale**: 56 entities have null types but may have Neo4j labels or relationship patterns that reveal their type. This is better than leaving them unmapped, and the remediation can be rolled back if results are wrong.

### 5. Orphan node handling: flag rather than delete

**Decision**: Add a remediation query that flags orphan nodes (no relationships) with `_is_orphan=true` rather than deleting them. Add a separate endpoint to list orphans for manual review.

**Rationale**: Orphans may be valid entities that simply haven't been connected yet, or they may be ingestion artifacts. Flagging preserves data while enabling the quality dashboard to surface them. Deletion should be an explicit user action.

## Risks / Trade-offs

- **[Medium] Batch remediation writes to Neo4j** → Mitigated by dry-run preview, batch ID tracking, and rollback support. All remediation properties use `_` prefix convention to distinguish from domain properties.
- **[Low] Schema property requirements may not match all entities** → Using `["name", "id"]` as base required properties is conservative. Entities created by different ingestion paths may use different property names. Compliance will correctly report these as non-compliant, surfacing the issue.
- **[Low] Biomarker split from Test alias** → Currently `biomarker` aliases to `test`. Changing this means previously remediated biomarker entities (if any) would need re-remediation. Since coverage is 0%, this is a non-issue.

## Migration Plan

1. Add schemas and type definitions (pure additive, no runtime impact)
2. Create remediation service and router (new code, no existing behavior changes)
3. Run dry-run via API or CLI to preview impact
4. Execute remediation batch
5. Re-run quality assessment to verify improvement
6. If results are wrong, rollback via batch ID

## Open Questions

- Should the remediation API require authentication (like the eval endpoints with `SYNAPSEFLOW_EVAL_MODE`)? Leaning toward no for dev, can add later.
- Should Biomarker be its own ODIN class or stay as a Test alias? Proposing: own class, since the data shows 12 distinct biomarker entities separate from 44 test entities.
