## Context

After Sprint 1 remediation, the knowledge graph has 522 ontology-mapped knowledge entities (100% of typed), 945 structural nodes marked, and 4,400 orphan nodes flagged. The `OntologyQualityService` generates quality scores and recommendations dynamically from graph queries, but its logic predates the remediation metadata properties (`_ontology_mapped`, `_canonical_type`, `_is_orphan`, `_orphan_source`, `_needs_review`). The Quality Dashboard shows stale recommendations because the assessment doesn't use these properties.

**Current state of assessment methods:**

- `_assess_coverage()` (line 204): Checks `_ontology_mapped` flag (good), but defaults `type=None` to `"Unknown"` (line 225) and adds all non-structural unmapped entity types to `unmapped_types` — including entities flagged `_needs_review=true` that are intentionally deferred.
- `_assess_consistency()` (line 538): Only checks ODIN labels on entities, ignoring `_canonical_type` set by remediation. An entity with `type="Cytokine"` mapped to `_canonical_type="protein"` but without a `Protein` ODIN label gets missed entirely.
- `_assess_taxonomy()` (line 371): Computes orphans from scratch (knowledge entities minus connected nodes). Doesn't use `_is_orphan` or `_orphan_source`. No breakdown by source category.
- `STRUCTURAL_ENTITY_LABELS` (line 39): Only contains `Chunk`, `StructuralChunk`, `Document`, `DocumentQuality`. Missing `ConversationSession` and `Message` added as structural in Sprint 1.
- `generate_recommendations()` (line 273): Produces generic messages without distinguishing knowledge orphans from episodic orphans, or truly unmapped types from review-pending types.

## Goals / Non-Goals

**Goals:**
- Assessment correctly reflects post-remediation graph state
- Recommendations are actionable (distinguish knowledge orphans from episodic, review-pending from unmapped)
- Consistency check incorporates `_canonical_type` from remediation
- `STRUCTURAL_ENTITY_LABELS` matches actual structural node labels
- `quick_ontology_check()` response includes knowledge-specific coverage and orphan breakdown

**Non-Goals:**
- Changing the 7-metric scoring weights or quality level thresholds
- Adding new assessment metrics beyond the existing 7
- Frontend dashboard changes (the API contract stays compatible; improved data flows through existing fields)
- Fixing the actual orphan nodes (that's Sprint 4 — Graphiti relationship crystallization)

## Decisions

### D1: Exclude `_needs_review` entities from `unmapped_types` list

**Decision:** In `_assess_coverage()`, entities with `_needs_review=true` will be excluded from `unmapped_types`. They'll still count as unmapped in the ratio (they genuinely aren't mapped), but the recommendation won't suggest "Add ontology mappings for types: Unknown" since that type is intentionally deferred.

**Alternative considered:** Map `Unknown` to a special `_pending_review` canonical type. Rejected — this would inflate the "mapped" count with entities that aren't actually mapped to meaningful ontology classes.

**Implementation:** Check `properties._needs_review` alongside `is_structural` and `is_noise` when building `unmapped_types` at line 258-260.

### D2: Incorporate `_canonical_type` in consistency check

**Decision:** In `_assess_consistency()`, also group entities by `_canonical_type` when ODIN labels are absent. If an entity has `_ontology_mapped=true` and `_canonical_type` set, use that canonical type as the resolved class for consistency grouping.

**Alternative considered:** Only check ODIN labels and rely on remediation adding labels. Rejected — remediation uses property-based mapping (`_canonical_type`) rather than label assignment, and retrofitting labels on 522 entities is a larger scope change.

**Implementation:** Extend the loop at line 545-552 to also check `properties._canonical_type` when no ODIN labels are found.

### D3: Report orphan breakdown by source using `_orphan_source`

**Decision:** Add `orphan_breakdown` dict to `TaxonomyCoherenceScore` with counts per source (`episodic`, `knowledge`, `unclassified`). The `generate_recommendations()` method will use this to produce specific messages like "Connect 12 knowledge orphan nodes" instead of "Connect 4400 orphan nodes."

**Alternative considered:** Always recalculate from labels rather than trusting `_orphan_source`. Rejected — the remediation already did this classification, and recalculating adds query complexity for no benefit.

**Implementation:** Add `orphan_breakdown: Dict[str, int]` field to `TaxonomyCoherenceScore`. In `_assess_taxonomy()`, query `_is_orphan` and `_orphan_source` properties. Fall back to current computation if remediation hasn't been run.

### D4: Update `STRUCTURAL_ENTITY_LABELS`

**Decision:** Add `ConversationSession` and `Message` to the constant. Also respect `_is_structural=true` property (already done at line 160, but the constant is used independently elsewhere).

**No alternative needed** — this is a straightforward data fix.

### D5: Update recommendations to be context-aware

**Decision:** `generate_recommendations()` will:
- For orphans: Show knowledge orphan count separately ("12 knowledge orphan nodes need hierarchy connections; 4,388 episodic orphans deferred to Sprint 4")
- For unmapped types: Exclude `_needs_review` types, only list truly missing mappings
- For inconsistencies: Show which types are ambiguous with their conflicting classes

**Implementation:** Update recommendation strings at lines 286-323 to use the enriched score data.

## Risks / Trade-offs

- **Backward compatibility** — Adding fields to `TaxonomyCoherenceScore` dataclass is additive; `to_dict()` serialization will include new fields automatically. Frontend reads `recommendations` array (strings), so enriched messages flow through without schema changes. → Low risk.

- **Remediation not run** — If someone runs the assessment on a graph without Sprint 1 remediation, `_is_orphan`/`_orphan_source`/`_needs_review` won't exist. → Mitigation: Fall back to current behavior (compute from scratch) when remediation properties are absent. Use `coalesce()` in queries.

- **Consistency check broadening** — Including `_canonical_type` means remediation-mapped entities now participate in consistency scoring. If remediation mapped inconsistently, the score could drop. → Mitigation: This is correct behavior — it surfaces real inconsistencies that were previously invisible.
