## Why

The ontology quality scan reveals three categories of gaps that reduce coverage and consistency scores: 5+ entity types in the graph lack ontology registry mappings (Species, Genus, Unknown, Model Organism, Food Component), 77 orphan nodes are disconnected from the hierarchy without clear explanation, and 14 type mappings are inconsistent (same entity type mapped to different canonical forms). Addressing these brings the knowledge graph closer to full ontology compliance and makes the quality metrics actionable rather than noisy.

## What Changes

- Add `MEDICAL_ONTOLOGY_REGISTRY` entries, `MEDICAL_TYPE_ALIASES`, and `ODIN_SCHEMAS` definitions for missing types: **Genus**, **Model Organism**, **Food Component**, and a fallback strategy for **Unknown** types
- Add `ODINMedical` class constants for new entity types (e.g., `FOOD_COMPONENT`, `MODEL_ORGANISM`) and corresponding `SCHEMA_ORG_MAPPINGS`
- Add `REMEDIATION_QUERIES` for the new types so batch remediation covers them
- Extend the `resolve_medical_type()` alias chain so "Species" resolves to `organism`, "Genus" to `organism`, "Model Organism" to `organism`, and "Food Component" to its own canonical type
- Add an orphan investigation query that classifies orphans by source graph (episodic/Graphiti vs. knowledge/ODIN) and flags them with `_orphan_source` metadata
- Add a consistency resolution remediation step that detects and normalizes the 14 inconsistent type mappings to their canonical forms

## Capabilities

### New Capabilities
- `ontology-type-completeness`: Adding missing entity type definitions (Genus, Model Organism, Food Component, Unknown) to the ODIN medical ontology registry, type aliases, ODIN schemas, Schema.org mappings, and remediation queries. Includes orphan node investigation/classification and inconsistent type mapping resolution.

### Modified Capabilities
- `medical-schema-compliance`: Add `OntologyClassSchema` entries in `ODIN_SCHEMAS` for the new types (FoodComponent, ModelOrganism) and ensure Schema.org mappings exist
- `kg-remediation-api`: Add remediation queries for new types, orphan source classification query, and consistency normalization step

## Impact

- **Domain layer**: `src/domain/ontologies/odin_medical.py` (new constants, registry entries, aliases), `src/domain/ontology_quality_models.py` (new ODIN_SCHEMAS, Schema.org mappings)
- **Application layer**: `src/application/services/remediation_service.py` (new remediation queries for the added types, orphan classification, consistency fix)
- **Scripts**: `scripts/ontology_batch_remediation.py` (no changes needed - already delegates to RemediationService)
- **Tests**: New tests for type resolution of the added types, updated remediation service tests
- **No API changes**: Existing `/api/ontology/remediation/*` endpoints work unchanged since they delegate to RemediationService
- **No breaking changes**: All additions are backward-compatible extensions to existing registries
