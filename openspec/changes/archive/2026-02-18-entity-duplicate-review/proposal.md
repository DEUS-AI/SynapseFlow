## Why

The quality assessment's last remaining recommendation is "Review 358 potential duplicate entities." Investigation reveals two misaligned detection systems: the assessment uses Python-side canonical-form normalization (catches abbreviations, synonyms, spacing variants across all types), while the `DeduplicationService` uses Neo4j-side case-insensitive exact matching within same-type only. Additionally, the remediation router housing the dedup endpoints is not mounted in `main.py`, making the existing dry-run/execute API inaccessible. The 358 groups break down as 321 same-type, 38 cross-type, and 2 structural — but there is no cross-type handling, no false-positive exclusion, and no safe review workflow.

## What Changes

- **Mount the remediation router** in `main.py` so `/api/ontology/remediation/deduplication/*` endpoints become reachable
- **Align duplicate detection** between the assessment normalizer and the dedup service so both report consistent counts
- **Add cross-type duplicate detection** as a separate category in the dedup service (flagged for review, not auto-merged)
- **Add false-positive exclusion** so pairs marked `_dedup_false_positive` are skipped in future detection runs
- **Enhance the dry-run response** with categorized groups (same-type auto-mergeable vs. cross-type review-needed) and sample context
- **Reduce the assessment recommendation** — after a dedup run, the count should reflect only remaining unresolved duplicates

## Capabilities

### New Capabilities
- `duplicate-review-workflow`: Covers the full review lifecycle — detection alignment, cross-type categorization, false-positive exclusion, safe merge execution, and post-merge assessment accuracy

### Modified Capabilities
- `entity-deduplication`: Existing spec adds cross-type detection, false-positive exclusion, and remediation router mounting

## Impact

- **`src/application/api/main.py`**: Mount remediation router
- **`src/application/services/deduplication_service.py`**: Cross-type detection, false-positive exclusion, aligned normalization
- **`src/application/api/remediation_router.py`**: Enhanced dry-run response with categories
- **`src/application/services/ontology_quality_service.py`**: Post-dedup assessment accuracy (exclude `_merged_into` entities, align normalizer count)
- **`src/domain/ontology_quality_models.py`**: Potential model updates for categorized duplicate reporting
- **`tests/`**: New and updated tests for all changes
