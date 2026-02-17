## Why

FalkorDB episode search is broken due to a bug in graphiti-core v0.17.6: the `fulltext_query()` function constructs RediSearch queries using Lucene syntax (`group_id:"value"`), but FalkorDB's RediSearch engine requires `@group_id:{value}` syntax. This causes `RediSearch: Syntax error at offset 8 near group_id` on every search that passes `group_ids`. The fix shipped upstream in v0.27.0 ("Sanitization of special characters in fulltext queries and escaping of group_ids").

## What Changes

- **BREAKING**: Upgrade `graphiti-core[falkordb]` from 0.17.6 to 0.27.x
- Adapt all import paths and API call sites across ~15 files that import from `graphiti_core`
- Update `EpisodicMemoryService.search_episodes()` if the `search()` function signature changed
- Update `Graphiti` client initialization in `composition_root.py` and `dependencies.py` if constructor changed
- Update `FalkorDriver` usage if driver API changed
- Validate that the `episodic-group-id` spec (group_id sanitization) still holds — the upstream fix may make some of our sanitization redundant but shouldn't conflict
- Remove the workaround `_sanitize_group_id` if upstream now handles special characters natively (or keep it if still needed)

## Capabilities

### New Capabilities

_(none — this is a dependency upgrade, not a new feature)_

### Modified Capabilities

- `episodic-group-id`: Upstream v0.27.0 now sanitizes/escapes group_ids in fulltext queries. Requirements may simplify — our `_sanitize_group_id()` colon-to-dash replacement may become unnecessary if upstream handles colons. Need to verify and update spec accordingly.

## Impact

- **Dependencies**: `graphiti-core[falkordb]` version bump from 0.17.6 to 0.27.x in `pyproject.toml` — 10 minor versions, potential breaking API changes
- **Code**: ~15 files import from `graphiti_core` (heaviest usage in `episodic_memory_service.py`, `graphiti_backend.py`, `composition_root.py`, `crystallization_service.py`, agent handlers)
- **Key imports at risk**: `search`, `SearchResults`, `SearchFilters`, `COMBINED_HYBRID_SEARCH_CROSS_ENCODER`, `EpisodeType`, `EpisodicNode`, `EntityNode`, `EntityEdge`, `FalkorDriver`, `RawEpisode`, `bulk_utils`
- **Tests**: Episodic memory tests mock graphiti internals — mocks may need updating if class signatures changed
- **Runtime**: FalkorDB and Neo4j backends both affected — need integration smoke test after upgrade
