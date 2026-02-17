## Context

The project uses `graphiti-core[falkordb]` v0.17.6 for episodic memory (patient conversations, knowledge enrichment). FalkorDB episode search is broken because v0.17.6's `fulltext_query()` builds RediSearch queries using Lucene syntax (`group_id:"value"`) which FalkorDB does not understand — it expects `@group_id:{value}`. This was fixed upstream in v0.27.0.

The library is imported across ~15 files. Key integration points:
- `EpisodicMemoryService` — search, store, retrieve episodes via `Graphiti` client and low-level `search()` function
- `CrystallizationService` — uses `search()` for knowledge enrichment
- `GraphitiBackend` — wraps `Graphiti` for the `KnowledgeGraphBackend` interface
- Agent handlers and `composition_root.py` — `Graphiti` client instantiation and `FalkorDriver` construction
- `domain_modeler.py` — uses `RawEpisode` for bulk episode ingestion

## Goals / Non-Goals

**Goals:**
- Fix the `RediSearch: Syntax error at offset 8 near group_id` error by upgrading to a version that generates correct RediSearch syntax
- Adapt all call sites to any API changes introduced between v0.17.6 and the target version
- Keep the `episodic-group-id` sanitization spec valid (update if upstream now handles colons natively)
- Maintain all existing tests passing

**Non-Goals:**
- Adopting new graphiti-core features (Sagas, custom instructions, communities) introduced after v0.17
- Refactoring episodic memory architecture beyond what the upgrade requires
- Upgrading other dependencies (Neo4j driver, FalkorDB client, etc.) unless required by graphiti-core

## Decisions

### 1. Target version: v0.27.1 (latest stable)

**Rationale:** v0.27.0 is the first version with the RediSearch group_id fix. v0.27.1 has additional bugfixes (duplicate edge prevention in summaries). Jumping directly to latest avoids a second upgrade soon after.

**Alternative considered:** Incremental upgrade (v0.17.6 → v0.18.x → ... → v0.27.x). Rejected — the API surface we use is largely backward-compatible across the entire range, making a single jump lower effort than multiple staged upgrades.

### 2. Keep `_sanitize_group_id()` even after upgrade

**Rationale:** Upstream v0.27.0 escapes special characters in fulltext queries, but our colon-to-dash sanitization happens at a different layer (before IDs are stored as `group_id` values in the graph). Removing it would create inconsistency between new and existing stored episodes. The sanitization is cheap and defensive.

**Alternative considered:** Remove `_sanitize_group_id()` entirely and rely on upstream escaping. Rejected — stored group_ids in FalkorDB already use the dash format; changing the format would require a data migration.

### 3. Pin to `>=0.27.1,<0.28` in pyproject.toml

**Rationale:** Allows patch updates within 0.27.x but prevents automatic jumps to 0.28.x which could introduce new breaking changes. The unpinned `"graphiti-core[falkordb]"` currently in pyproject.toml is what allowed the mismatch to accumulate.

**Alternative considered:** Exact pin (`==0.27.1`). Rejected — overly restrictive for a library still evolving; patch-level updates are low risk.

### 4. No changes needed for Graphiti constructor or search() signature

**Research findings:** The `Graphiti.__init__()` signature in v0.27.1 adds two optional parameters (`tracer`, `trace_span_prefix`) but keeps all existing parameters identical, including `store_raw_episode_content` and `graph_driver`. The `search()` function adds an optional `driver` parameter. All existing call sites remain valid without modification.

### 5. Verify internal search helper return type changes

**Research findings:** Internal helpers (`edge_search`, `node_search`, `episode_search`, `community_search`) changed return types from `list[T]` to `tuple[list[T], list[float]]` (adding scores). However, our code never calls these directly — we only use the high-level `search()` which returns `SearchResults` (unchanged). No code changes needed, but tests that mock these internals should be reviewed.

## Risks / Trade-offs

- **[Undocumented breaking changes]** → Mitigation: Run full test suite after upgrade; run manual smoke test with FalkorDB episode search to verify the RediSearch fix works end-to-end.
- **[Test mock fragility]** → Mitigation: Review all `graphiti_core` mocks in `tests/test_episodic_memory.py` to ensure they match the new API signatures. Update mock return values if internal functions now return tuples.
- **[New transitive dependencies]** → Mitigation: Review `uv sync` output for new/changed transitive deps. Run `uv pip check` for conflicts.
- **[FalkorDB index format changes]** → Mitigation: If the new version changes how indices are built (`build_indices_and_constraints`), existing FalkorDB data may need reindexing. Test with a fresh FalkorDB instance first, then with existing data.

## Migration Plan

1. Bump version in `pyproject.toml` and run `uv sync`
2. Fix any import errors (unlikely based on research)
3. Run unit tests — fix any mock signature mismatches
4. Start FalkorDB container and run integration smoke test for episode search
5. Rollback: revert `pyproject.toml` and `uv sync` — single-step rollback
