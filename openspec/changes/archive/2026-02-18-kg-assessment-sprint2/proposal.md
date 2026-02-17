## Why

The Quality Dashboard's "Top Recommendations" are stale after Sprint 1 remediation. The assessment service (`OntologyQualityService`) doesn't account for remediation metadata (`_ontology_mapped`, `_canonical_type`, `_is_orphan`, `_needs_review`), so it reports issues that are either already resolved or intentionally deferred. Specifically:

- **"Add ontology mappings for types: Unknown"** — `Unknown` type entities are intentionally flagged for review (`_needs_review=true`), not mapped. The assessment should distinguish "unmapped" from "pending review."
- **"Connect 77 orphan nodes"** — The orphan count doesn't leverage the `_is_orphan`/`_orphan_source` classification from remediation. Knowledge vs. episodic orphans need different treatment.
- **"Resolve 14 inconsistent type mappings"** — The consistency check only examines ODIN labels, ignoring `_canonical_type` set by remediation. Entities mapped via remediation appear inconsistent.

Additionally, `STRUCTURAL_ENTITY_LABELS` in the quality service is missing `ConversationSession` and `Message`, which were added as structural during Sprint 1 remediation.

## What Changes

- Update `OntologyQualityService._assess_coverage()` to exclude `_needs_review` entities from `unmapped_types` (they're intentionally deferred, not missing)
- Update `OntologyQualityService._assess_consistency()` to incorporate `_canonical_type` from remediation — entities with consistent canonical types should not be flagged as inconsistent
- Update `OntologyQualityService._assess_taxonomy()` to report orphan breakdown by source (`episodic`, `knowledge`, `unclassified`) using `_orphan_source` metadata
- Add `ConversationSession` and `Message` to `STRUCTURAL_ENTITY_LABELS`
- Update `generate_recommendations()` to produce actionable, context-aware messages (e.g., "77 knowledge orphan nodes need hierarchy connections" instead of generic "Connect 77 orphan nodes")
- Update `quick_ontology_check()` response to include `orphan_breakdown` and `knowledge_coverage` alongside overall metrics

## Capabilities

### New Capabilities

- `quality-assessment-accuracy`: Requirements for how the quality assessment handles remediation metadata, orphan classification, consistency checks, and recommendation generation

### Modified Capabilities

- `ontology-type-completeness`: Add requirement that `Unknown` type entities flagged with `_needs_review` are excluded from "unmapped types" in assessment coverage reporting

## Impact

- `src/application/services/ontology_quality_service.py` — Main assessment logic changes (coverage, consistency, taxonomy methods)
- `src/domain/ontology_quality_models.py` — Recommendation generation, possibly new fields on score dataclasses
- `frontend/src/components/admin/QualityDashboard.tsx` — May benefit from new orphan breakdown data, but no breaking changes to API contract
- `GET /api/ontology/quality` and `POST /api/ontology/quality/assess` — Response content will change (more accurate numbers) but schema remains compatible
