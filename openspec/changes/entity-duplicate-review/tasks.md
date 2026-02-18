## 1. Mount Remediation Router

- [x] 1.1 Import remediation router in `main.py` and mount it with `app.include_router(remediation_router)`
- [x] 1.2 Initialize `DeduplicationService` with the Neo4j driver in `startup_event()` and call `set_deduplication_service()`
- [x] 1.3 Add test verifying the remediation router endpoints return non-404 responses

## 2. Add `_dedup_skip` Exclusion to Detection Query

- [x] 2.1 Add `AND NOT coalesce(a._dedup_skip, false)` and `AND NOT coalesce(b._dedup_skip, false)` filters to `DETECT_DUPLICATES_QUERY`
- [x] 2.2 Add unit test `test_query_excludes_dismissed_entities` verifying `_dedup_skip` is in the query

## 3. Cross-Type Duplicate Detection

- [x] 3.1 Add `CrossTypeDuplicateGroup` dataclass with fields: `canonical_form`, `entities` (list of dicts with id/name/type/relationship_count), `entity_count`
- [x] 3.2 Add `FETCH_ALL_ENTITIES_QUERY` Cypher query that returns id, name, type, and relationship count for all non-structural, non-merged, non-dismissed entities
- [x] 3.3 Implement `detect_cross_type_duplicates()` method: fetch all entities, normalize names with `SemanticNormalizer`, group by canonical form, return only groups spanning multiple types
- [x] 3.4 Add tests for cross-type detection: cross-type group detected, same-type excluded from cross-type results, normalizer-only matches detected

## 4. False-Positive Dismissal

- [x] 4.1 Add `DISMISS_ENTITIES_QUERY` and `UNDISMISS_ENTITIES_QUERY` Cypher queries to set/remove `_dedup_skip` property
- [x] 4.2 Implement `dismiss_entities(entity_ids, undo=False)` method on `DeduplicationService`
- [x] 4.3 Add `POST /deduplication/dismiss` endpoint in `remediation_router.py` accepting `{ "entity_ids": [...], "undo": false }`
- [x] 4.4 Add tests for dismiss: sets flag, undo removes flag, query text validates property names

## 5. Categorized Dry-Run Response

- [x] 5.1 Update `deduplication_dry_run` endpoint to call both `detect_duplicates()` and `detect_cross_type_duplicates()`
- [x] 5.2 Return categorized response with `total_same_type`, `same_type_plan`, `total_cross_type`, `cross_type_groups`
- [x] 5.3 Add test for categorized dry-run response structure

## 6. Execute With Cross-Type Awareness

- [x] 6.1 Update `deduplication_execute` endpoint to compute cross-type count but only merge same-type pairs
- [x] 6.2 Add `skipped_cross_type` to the execute response
- [x] 6.3 Add test verifying execute response includes `skipped_cross_type` field

## 7. Assessment Excludes Dismissed and Merged Entities

- [x] 7.1 In `_assess_normalization()`, skip entities where `_dedup_skip = true` or `_merged_into` is set before canonical grouping
- [x] 7.2 Add test: dismissed entities excluded from `deduplication_candidates` count
- [x] 7.3 Add test: entities with `_merged_into` excluded from `deduplication_candidates` count
- [x] 7.4 Run full test suite to verify no regressions
