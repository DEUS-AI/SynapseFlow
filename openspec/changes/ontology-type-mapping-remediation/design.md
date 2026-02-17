## Context

The ODIN medical ontology currently defines 22 entity types across 4 DIKW layers with corresponding registry entries, type aliases, ODIN schemas, Schema.org mappings, and remediation queries. The ontology quality scan identified gaps: entity types present in the knowledge graph that have no ontology mapping (Species, Genus, Unknown, Model Organism, Food Component), 77 orphan nodes with zero relationships, and 14 type mappings where the same raw type resolves to different canonical forms.

The existing type resolution pipeline follows a clear path: raw type → `resolve_medical_type()` (alias lookup) → `MEDICAL_ONTOLOGY_REGISTRY` (config) → `ODIN_SCHEMAS` (compliance check). Remediation queries in `RemediationService` run batch Cypher to set `_ontology_mapped` and `_canonical_type` on graph entities. This change extends all layers of this pipeline for the missing types.

## Goals / Non-Goals

**Goals:**
- Every entity type present in the graph resolves to a canonical type via alias or direct registry lookup
- Orphan nodes are classified by source (episodic vs. knowledge graph) so the user can decide appropriate action
- Inconsistent type mappings are detected and normalized to a single canonical form per raw type
- Batch remediation covers all new types without requiring API changes

**Non-Goals:**
- Deleting or auto-connecting orphan nodes (investigation only, user decides)
- Creating new DIKW layer categories or restructuring the hierarchy
- Adding new external ontology system integrations (SNOMED, MeSH, etc. references are metadata only)
- Modifying the quality scan scoring algorithm itself

## Decisions

### Decision 1: Type mapping strategy for missing types

**Species, Genus, Model Organism → alias to `organism`**

These are all taxonomic/biological classifications that fit under the existing `Organism` type. "Species" is already aliased (line 392 of `odin_medical.py`). Adding "Genus" and "Model Organism" as aliases avoids ontology sprawl while correctly classifying the entities.

Alternative considered: Create separate `genus` and `model_organism` canonical types. Rejected because they share the same DIKW layer (SEMANTIC), parent type (`biological_entity`), external systems (MeSH, SNOMED-CT), and relationship patterns. The additional granularity would fragment the type hierarchy without benefit.

**Food Component → new canonical type `food_component`**

This is genuinely distinct from any existing type. Food components (nutrients, vitamins, compounds in food) don't map to Drug, Organism, or any existing category. Gets its own `ODINMedical.FOOD_COMPONENT` constant, registry entry, ODIN schema, and remediation query.

- DIKW Layer: SEMANTIC (validated concept, not raw observation)
- Parent type: `biological_entity` (alongside Protein, Organism, etc.)
- External systems: MeSH (nutrition terms), SNOMED-CT (dietary substances)
- Auto-relationships: ASSOCIATED_WITH, INTERACTS_WITH (nutrient-drug interactions)
- Schema.org mapping: `Thing` (no specific Schema.org type for food components)

**Unknown → flag-for-review strategy**

"Unknown" is not a real entity type — it indicates the LLM extraction couldn't classify the entity. These should NOT get an ontology mapping. Instead, extend the existing `null_type_flag_review` query pattern to also catch entities with `type = 'Unknown'` or `type = 'unknown'`, setting `_needs_review = true` and `_review_reason = 'unknown_type'`.

### Decision 2: Orphan node classification approach

Rather than a single `_is_orphan = true` flag, add an enrichment step after orphan detection that classifies orphan source:

```
_orphan_source = 'episodic'    → has Graphiti labels (EntityNode, EpisodicNode)
_orphan_source = 'knowledge'   → has ODIN/medical labels
_orphan_source = 'unclassified' → neither
```

This runs as a second pass after the existing `orphan_node_flagging` query, only touching nodes already flagged as orphans. This way the user can query orphans by source and decide bulk actions per category.

Implementation: Add a single `orphan_source_classification` query to `REMEDIATION_QUERIES` that matches `WHERE n._is_orphan = true` and sets `_orphan_source` based on label inspection.

### Decision 3: Inconsistency resolution approach

Add a `type_consistency_normalization` remediation query that:
1. Matches entities where `_ontology_mapped = true` but `_canonical_type` doesn't match what `resolve_medical_type(n.type)` would return
2. Updates `_canonical_type` to the correct canonical form
3. Logs the correction in `_consistency_fixed = true`

This runs as the **last** remediation step (after all type-specific queries) to catch any remaining mismatches. The query will use a Cypher `CASE` expression mapping known inconsistent raw types to their correct canonical form, based on `MEDICAL_TYPE_ALIASES`.

### Decision 4: File organization

All changes fit within existing files — no new modules needed:
- `odin_medical.py`: New class constant, registry entry, aliases
- `ontology_quality_models.py`: New ODIN_SCHEMAS entry, Schema.org mapping
- `remediation_service.py`: New queries appended to `REMEDIATION_QUERIES` list
- Tests follow existing patterns in `tests/domain/test_odin_medical_types.py`

## Risks / Trade-offs

**[Risk] "Food Component" is too broad as a single type** → Mitigation: Start with a single `food_component` type. If graph analysis reveals meaningful subtypes (e.g., macronutrient vs. micronutrient vs. phytochemical), these can be added as sub-aliases later without breaking the canonical type.

**[Risk] Orphan classification heuristic may misclassify nodes** → Mitigation: The label-based check (Graphiti labels vs. ODIN labels) is deterministic and verifiable. Nodes with no recognizable labels get `_orphan_source = 'unclassified'` for manual review rather than being silently categorized.

**[Risk] Consistency normalization could flip correct mappings** → Mitigation: The CASE expression only covers the specific 14 known inconsistent patterns. It uses explicit type-to-canonical mappings rather than dynamic resolution, so it won't affect correctly mapped entities. The `_consistency_fixed` flag enables auditing.

**[Trade-off] Aliasing Genus/Model Organism to `organism` loses taxonomic granularity** → Acceptable because the knowledge graph's purpose is clinical knowledge management, not biological taxonomy. If taxonomic rank becomes important, a `_taxonomic_rank` metadata property can be added without changing the canonical type.
