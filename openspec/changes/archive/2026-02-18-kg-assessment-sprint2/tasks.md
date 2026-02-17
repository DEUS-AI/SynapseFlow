## 1. Structural Labels Fix

- [x] 1.1 Add `ConversationSession` and `Message` to `STRUCTURAL_ENTITY_LABELS` in `ontology_quality_service.py:39`
- [x] 1.2 Write tests verifying `_is_structural_entity()` returns `True` for entities with `ConversationSession` or `Message` labels

## 2. Coverage Assessment — Exclude Review-Pending Types

- [x] 2.1 Update `_assess_coverage()` in `ontology_quality_service.py:204` to check `properties._needs_review` when building `unmapped_types` — exclude entities with `_needs_review=true` from the list
- [x] 2.2 Write tests: entity with `type='Unknown'` and `_needs_review=true` does NOT appear in `unmapped_types`; entity with `type='NewType'` without `_needs_review` DOES appear
- [x] 2.3 Write test: review-pending entities still count as unmapped in `coverage_ratio` (ratio is not inflated)

## 3. Consistency Assessment — Incorporate Canonical Types

- [x] 3.1 Update `_assess_consistency()` in `ontology_quality_service.py:538` to also group by `_canonical_type` when entity has `_ontology_mapped=true` but no ODIN labels
- [x] 3.2 Write test: entity with `type='Cytokine'`, `_ontology_mapped=true`, `_canonical_type='protein'` and no Protein label is grouped under `protein`
- [x] 3.3 Write test: all entities of same raw type with same `_canonical_type` are counted as consistent
- [x] 3.4 Write test: entities of same raw type with conflicting `_canonical_type` values are counted as inconsistent

## 4. Taxonomy Assessment — Orphan Breakdown by Source

- [x] 4.1 Add `orphan_breakdown: Dict[str, int]` field to `TaxonomyCoherenceScore` dataclass in `ontology_quality_models.py:94`
- [x] 4.2 Update `_assess_taxonomy()` in `ontology_quality_service.py:371` to populate `orphan_breakdown` from `_is_orphan`/`_orphan_source` properties when available
- [x] 4.3 Add fallback in `_assess_taxonomy()` — when no `_is_orphan` metadata exists, compute orphans from scratch and set `orphan_breakdown = {"unclassified": count}`
- [x] 4.4 Ensure `orphan_nodes` equals sum of `orphan_breakdown` values
- [x] 4.5 Write tests for orphan breakdown: metadata-based path, fallback path, and total consistency

## 5. Context-Aware Recommendations

- [x] 5.1 Update orphan recommendation in `generate_recommendations()` at `ontology_quality_models.py:314` to use `orphan_breakdown.get("knowledge", 0)` instead of total `orphan_nodes`; suppress recommendation when knowledge orphans = 0
- [x] 5.2 Update unmapped types recommendation at `ontology_quality_models.py:286` to skip generation when `unmapped_types` is empty (after review-pending exclusion)
- [x] 5.3 Write test: orphan recommendation shows knowledge count (12) not total (4400) when breakdown is available
- [x] 5.4 Write test: no orphan recommendation generated when only episodic orphans exist
- [x] 5.5 Write test: no "Add ontology mappings" recommendation when `unmapped_types` is empty

## 6. Quick Ontology Check Enrichment

- [x] 6.1 Add `knowledge_coverage` field to `quick_ontology_check()` response in `ontology_quality_service.py:769` — read from `coverage.class_distribution["_knowledge_coverage"]`
- [x] 6.2 Add `orphan_breakdown` field to `quick_ontology_check()` response — read from `taxonomy.orphan_breakdown`
- [x] 6.3 Write tests for `quick_ontology_check()` response including both new fields

## 7. Serialization and Integration

- [x] 7.1 Update `TaxonomyCoherenceScore` serialization in `to_dict()` at `ontology_quality_models.py` to include `orphan_breakdown`
- [x] 7.2 Run full test suite (`tests/application/test_ontology_quality_service.py`) to verify no regressions
