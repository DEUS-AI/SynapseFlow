## Context

The quality assessment reports 358 potential duplicate groups (738 entities). Two independent detection methods currently exist:

1. **Assessment normalizer** (`_assess_normalization`): Python-side `SemanticNormalizer.normalize()` groups entities by canonical form. Catches case, spacing, abbreviations, synonyms — across all types. This produces the 358 count.
2. **DeduplicationService** (`DETECT_DUPLICATES_QUERY`): Neo4j-side `toLower(trim(name))` matching, same-type only. Catches ~321 of the 358.

The gap: 38 cross-type groups and ~handful of normalizer-specific matches (abbreviation/synonym expansion) are invisible to the dedup service. Additionally, the remediation router is defined (`remediation_router.py`) but never mounted in `main.py`, so the dry-run/execute endpoints are unreachable.

## Goals / Non-Goals

**Goals:**
- Make the deduplication endpoints accessible via the API
- Align detection so the assessment count matches what the dedup service can act on
- Support cross-type duplicate detection (as review-only, not auto-mergeable)
- Allow false-positive exclusion to prevent the same pairs from being flagged repeatedly
- Ensure post-merge assessment accurately reflects the reduced duplicate count

**Non-Goals:**
- Fuzzy/embedding-based duplicate detection (future work, requires EntityResolver integration)
- Automated merging of cross-type duplicates (too risky without human review)
- Retroactive deduplication of historical merge decisions
- UI for reviewing individual duplicate pairs (backend-only for now)

## Decisions

### D1: Two-tier detection (Neo4j fast path + Python normalizer)

Keep the existing Neo4j `toLower(trim())` query for same-type detection — it's performant and handles the common case (321 of 358 groups). Add a second Python-side pass using `SemanticNormalizer` for cross-type and normalizer-specific matches.

**Why not move everything to Python?** The Neo4j query is a single Cypher statement with relationship counts and confidence scores included. Replicating this in Python would require pulling all entities + computing relationship counts separately. The two-tier approach keeps the fast path fast and adds the normalizer pass only for the additional matches.

**Why not move everything to Neo4j?** The `SemanticNormalizer` has abbreviation maps, synonym maps, and custom rules that are impractical to port to Cypher. Keeping the normalizer in Python means it stays in sync with the assessment automatically.

**Alternative considered:** Store pre-computed canonical forms as `_canonical_name` properties on entities. Rejected because it adds a remediation dependency and stale-data risk — the normalizer rules can change independently.

### D2: Cross-type duplicates are flagged, not auto-merged

Cross-type matches (e.g., "corticosteroids" as both Drug and Treatment) are reported in the dry-run with `category: "cross_type"` but excluded from `execute`. They may represent legitimate separate entities or true duplicates requiring domain judgement.

**Alternative considered:** Offer an `execute` flag like `--include-cross-type`. Rejected because wrong merges are destructive and hard to reverse. Better to keep the safe default and let operators manually handle cross-type via targeted Cypher.

### D3: False-positive exclusion via `_dedup_skip` property

When a pair is dismissed as a false positive, both entities get `_dedup_skip = true`. Detection queries (both Neo4j and Python) exclude entities with this flag. This is consistent with the existing remediation metadata pattern (`_needs_review`, `_is_orphan`, `_merged_into`).

**API**: `POST /api/ontology/remediation/deduplication/dismiss` with `{ "entity_ids": ["id1", "id2"] }` sets the flag.

**Alternative considered:** An exclusion list stored outside the graph. Rejected because graph properties are queryable in Cypher and auditable with the rest of the remediation metadata.

### D4: Mount remediation router at `/api/ontology/remediation`

The router already exists with proper dependency injection via `set_deduplication_service()`. Mount it in `main.py` during the lifespan setup, alongside the existing service initialization. The dedup service needs the Neo4j async driver, which is already available in the lifespan context.

### D5: Assessment excludes merged/dismissed entities from duplicate count

After dedup execution, loser entities are deleted (existing behavior). But to handle edge cases (partial execution, soft-delete scenarios), the assessment's `_assess_normalization` will also skip entities with `_merged_into` or `_dedup_skip` properties. This ensures the recommendation count drops after deduplication even if some entities survive deletion.

## Risks / Trade-offs

- **Two-tier detection complexity** → Mitigated by keeping the existing Cypher query untouched and adding the Python normalizer as a separate `detect_cross_type_duplicates()` method
- **False-positive flag permanence** → The `_dedup_skip` flag persists across runs. If the normalizer rules change and a previously-dismissed pair becomes a true duplicate, it won't be re-flagged. Mitigation: the dismiss endpoint can also unset the flag via `POST /dismiss` with `{ "undo": true }`
- **APOC dependency for relationship transfer** → The existing merge queries use `apoc.create.relationship()`. If APOC is not installed, execute will fail. Mitigation: check APOC availability at startup and disable the execute endpoint if missing (dry-run still works)
- **Large merge batches** → Merging hundreds of entities in a single transaction could be slow. Mitigation: the existing service already processes one pair at a time in a loop, which is safe if slow. No change needed for now.
