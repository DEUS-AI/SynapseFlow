## Context

The `RemediationService` in `src/application/services/remediation_service.py` contains 28 remediation queries. Query #20 (`conversation_mapping`) maps ConversationSession/Message nodes to `_canonical_type='usage'` in the APPLICATION layer. This was a pragmatic categorization to handle unexpected node types, but it's semantically wrong — these are operational/audit nodes, not clinical knowledge.

Three queries in the service reference structural labels but don't include conversation nodes:
- `MARK_STRUCTURAL_QUERY` (line 481): marks `['Chunk', 'StructuralChunk', 'Document', 'DocumentQuality', 'ExtractedEntity']`
- `PRE_STATS_QUERY` (line 524): detects structural via `['Chunk', 'Document', 'ExtractedEntity']`
- `UNMAPPED_TYPES_QUERY` (line 539): excludes `['Chunk', 'Document', 'ExtractedEntity']`

## Goals / Non-Goals

**Goals:**
- Reclassify ConversationSession/Message as structural so they're excluded from ontology metrics
- Fix any nodes already incorrectly mapped as APPLICATION/usage
- Keep conversation nodes in Neo4j (they have provenance value via HAS_SESSION/HAS_MESSAGE relationships)

**Non-Goals:**
- Changing how PatientMemoryService creates conversation nodes
- Adding a new OPERATIONAL or AUDIT label system (future improvement)
- Modifying the quality dashboard UI

## Decisions

### 1. Remove conversation_mapping query, add labels to MARK_STRUCTURAL_QUERY

**Decision**: Delete the `conversation_mapping` tuple from `REMEDIATION_QUERIES` and add `'ConversationSession', 'Message'` to the label list in `MARK_STRUCTURAL_QUERY`.

**Rationale**: This is the simplest approach — conversation nodes get the same treatment as Chunk/Document nodes. The `MARK_STRUCTURAL_QUERY` already runs before remediation queries, so conversation nodes will be marked structural before any ontology mapping runs.

**Alternative considered**: Adding a separate `MARK_CONVERSATION_STRUCTURAL_QUERY` — rejected because it duplicates logic already in MARK_STRUCTURAL_QUERY.

### 2. Update PRE_STATS_QUERY and UNMAPPED_TYPES_QUERY label lists

**Decision**: Add `'ConversationSession', 'Message'` to the label-based structural detection in both `PRE_STATS_QUERY` and `UNMAPPED_TYPES_QUERY`.

**Rationale**: These queries use a hardcoded label list for structural detection (separate from the `_is_structural` flag). Adding conversation labels ensures accurate stats even before remediation runs. The `_exclude_from_ontology` flag provides a secondary guard, but the label check is the primary filter.

### 3. Add a migration query to fix already-remediated nodes

**Decision**: Add a one-time migration query to `REMEDIATION_QUERIES` that removes `_ontology_mapped` and `_canonical_type` from conversation nodes and sets `_is_structural=true`. Place it early in the query list (before the type-mapping queries).

**Rationale**: Existing nodes may have `_ontology_mapped=true` and `_canonical_type='usage'` from prior remediation runs. Without this migration, they'd remain incorrectly classified until manually fixed. The query is idempotent — guarded by `NOT coalesce(n._is_structural, false)`.

## Risks / Trade-offs

- **[Low] Coverage metrics will shift**: After reclassification, total knowledge entity count drops (conversation nodes excluded) and coverage percentage may increase. This is the correct behavior — the previous numbers were inflated.
- **[Low] Migration query runs every batch**: The migration query is idempotent (guarded by `NOT _is_structural`), so it's safe to include in every run. After the first execution, it will match 0 nodes.

## Migration Plan

1. Update `MARK_STRUCTURAL_QUERY`, `PRE_STATS_QUERY`, and `UNMAPPED_TYPES_QUERY` label lists
2. Remove `conversation_mapping` from `REMEDIATION_QUERIES`
3. Add migration query to `REMEDIATION_QUERIES`
4. Run tests to confirm no regressions
5. Run dry-run via API to verify metric changes
6. Execute remediation to apply migration
