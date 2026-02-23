# Graphiti Alignment Specs — 5 Sanity-Check Gaps

> Generated from the failing items in the Graphiti Memory Brief (§4 sanity checklist).
> Each spec targets one `[ ]` item and brings it to `[x]`.

---

## SPEC-1: Community / Summary Layer

**Checklist item**: §4.1 — *Community/summary layer — Graphiti supports community detection for high-level summaries. Not implemented.*

### Problem

Graphiti's Tier 3 (Community Subgraph) clusters strongly-connected entities and produces high-level summaries via label propagation. SynapseFlow never consumes these summaries, so for patients with long conversation histories there is no aggregated view — every retrieval must assemble context from individual episodes and entities.

### Goal

Expose community summaries from the episodic graph and make them available as an optional context source in `get_conversation_context()`.

### Design

```
EpisodicMemoryService
├── get_conversation_context()      ← existing
│   └── community_summaries: [...]  ← NEW field in returned dict
│
├── get_community_summaries()       ← NEW method
│   ├── calls graphiti_core community API
│   ├── filters by group_id (patient isolation)
│   └── returns List[CommunitySummary]
│
└── CommunitySummary (dataclass)    ← NEW
    ├── community_id: str
    ├── summary: str
    ├── entity_count: int
    ├── key_entities: List[str]
    └── updated_at: datetime
```

### Files to Change

| File | Change |
|------|--------|
| `src/application/services/episodic_memory_service.py` | Add `CommunitySummary` dataclass, `get_community_summaries()` method, extend `get_conversation_context()` return dict |
| `tests/test_episodic_memory.py` | Add tests for `get_community_summaries()` and extended context |

### Implementation Details

**`CommunitySummary` dataclass** — add after `ConversationEpisode`:

```python
@dataclass
class CommunitySummary:
    """A community-level summary from Graphiti's community subgraph."""
    community_id: str
    summary: str
    entity_count: int
    key_entities: List[str]
    updated_at: Optional[datetime] = None
```

**`get_community_summaries()`** — add to `EpisodicMemoryService`:

```python
async def get_community_summaries(
    self,
    patient_id: str,
    limit: int = 5,
) -> List[CommunitySummary]:
```

Implementation strategy:
1. Call `search()` with the `COMBINED_HYBRID_SEARCH_CROSS_ENCODER` recipe, which already returns `results.communities` (a list of `CommunityNode` objects per Graphiti's `SearchResults` schema).
2. Filter by `group_id` matching `patient_id`.
3. Convert to `CommunitySummary` dataclasses.
4. If `results.communities` is empty or not present (version dependent), fall back to returning `[]` with a debug log — this keeps the feature gracefully degradable.

**Extend `get_conversation_context()`**:

Add a `community_summaries` key to the returned dict, populated by calling `get_community_summaries()`. This is appended *after* the existing recent/related/entities retrieval so it does not block core context assembly on failure.

```python
# In get_conversation_context(), after entities retrieval:
community_summaries = []
try:
    community_summaries = await self.get_community_summaries(
        patient_id=patient_id,
        limit=3,
    )
except Exception as e:
    logger.debug(f"Community summaries unavailable: {e}")

return {
    "recent_episodes": ...,
    "related_episodes": ...,
    "entities": entities,
    "community_summaries": [self._summary_to_dict(s) for s in community_summaries],
    "total_context_items": len(recent) + len(related) + len(entities) + len(community_summaries),
}
```

### Test Plan

| Test | Asserts |
|------|---------|
| `test_get_community_summaries_returns_results` | Mock `search()` returning community nodes → service returns `CommunitySummary` list |
| `test_get_community_summaries_empty_graceful` | Mock `search()` returning no communities → returns `[]` |
| `test_get_community_summaries_error_graceful` | Mock `search()` raising → returns `[]`, no exception propagated |
| `test_context_includes_community_summaries` | `get_conversation_context()` return dict has `community_summaries` key |

### Acceptance Criteria

- `get_conversation_context()` response includes `community_summaries` field.
- If Graphiti version doesn't expose communities, the field is `[]` and no error is raised.
- Community summaries are filtered by `patient_id` group — no cross-patient leakage.

---

## SPEC-2: Temporal Conflict Resolution

**Checklist item**: §4.2 — *Temporal conflict resolution — Graphiti invalidates outdated edges via bi-temporal model, but this is not propagated to Neo4j.*

### Problem

Graphiti edges carry four timestamps (`created_at`, `expired_at`, `valid_at`, `invalid_at`). When new information contradicts a prior fact, Graphiti invalidates the old edge by setting `expired_at` — it never deletes it. The crystallization pipeline ignores these timestamps entirely: it reads entity names and confidence scores but discards the temporal validity markers. This means:

1. Outdated facts transferred to Neo4j remain active indefinitely.
2. Two contradictory facts (e.g., "Patient takes Metformin" and later "Patient stopped Metformin") both live in the DIKW graph as current truths.
3. Point-in-time queries against the DIKW graph are impossible.

### Goal

Propagate Graphiti's bi-temporal metadata through the crystallization pipeline into Neo4j DIKW nodes and edges, and add a mechanism to invalidate superseded facts.

### Design

```
Graphiti Edge
├── created_at (DB time)
├── expired_at (DB invalidation time)
├── valid_at   (real-world start)
└── invalid_at (real-world end)
        │
        ▼
CrystallizationService.crystallize_entities()
        │  reads temporal fields from Graphiti edges
        │  propagates to Neo4j node properties
        ▼
Neo4j DIKW Node
├── valid_from: datetime    ← NEW (mapped from valid_at)
├── valid_until: datetime   ← NEW (mapped from invalid_at)
├── invalidated_at: datetime← NEW (mapped from expired_at)
├── is_current: bool        ← NEW (computed: valid_until is null)
└── (existing fields)

CrystallizationService._resolve_temporal_conflicts()  ← NEW
        │  when new fact contradicts existing:
        │  mark old entity's valid_until = new fact's valid_from
        │  set old entity's is_current = false
        ▼
```

### Files to Change

| File | Change |
|------|--------|
| `src/application/services/crystallization_service.py` | Add `_resolve_temporal_conflicts()`, update `crystallize_entities()` to extract and propagate temporal fields, update `_create_perception_entity()` to include temporal properties |
| `src/application/services/entity_resolver.py` | Update `merge_for_crystallization()` to handle temporal conflict during merge |
| `tests/test_crystallization_pipeline.py` | Add temporal conflict resolution tests |

### Implementation Details

**New temporal fields on PERCEPTION entities** — update `_create_perception_entity()`:

```python
properties = {
    # ... existing fields ...
    "valid_from": source_data.get("valid_at", datetime.utcnow().isoformat()),
    "valid_until": source_data.get("invalid_at"),  # None = still current
    "invalidated_at": source_data.get("expired_at"),  # None = not invalidated
    "is_current": source_data.get("invalid_at") is None,
}
```

**New method `_resolve_temporal_conflicts()`** in `CrystallizationService`:

```python
async def _resolve_temporal_conflicts(
    self,
    entity_name: str,
    entity_type: str,
    new_valid_from: Optional[str],
) -> int:
    """
    Invalidate existing DIKW entities that are superseded by a newer fact.

    When the same entity (by name+type) appears with a newer valid_from,
    all previous is_current=true versions get marked:
      valid_until = new_valid_from
      is_current = false
      invalidated_at = now()

    Returns:
        Number of entities invalidated.
    """
```

Query pattern:

```cypher
MATCH (n:Entity)
WHERE toLower(n.name) = $name
  AND n.entity_type = $type
  AND n.is_current = true
  AND n.valid_from < $new_valid_from
SET n.valid_until = $new_valid_from,
    n.is_current = false,
    n.invalidated_at = datetime()
RETURN count(n) as invalidated
```

**Call site** — in `crystallize_entities()`, after the entity is created or merged, if `source_data` includes a `valid_at` field:

```python
if entity_data.get("valid_at"):
    invalidated = await self._resolve_temporal_conflicts(
        entity_name=name,
        entity_type=entity_type,
        new_valid_from=entity_data["valid_at"],
    )
    if invalidated > 0:
        logger.info(f"Temporal conflict: invalidated {invalidated} prior version(s) of '{name}'")
```

**Update `merge_for_crystallization()` in EntityResolver** — when merging, if the incoming data has `valid_at`/`invalid_at`, store them and update `is_current`:

```python
# In merge_for_crystallization(), within the updates dict:
if "valid_at" in new_data:
    updates["valid_from"] = new_data["valid_at"]
if "invalid_at" in new_data:
    updates["valid_until"] = new_data["invalid_at"]
    updates["is_current"] = False
```

**Extracting temporal data from Graphiti** — in `crystallize_from_graphiti()`, after the `search()` call, extract temporal metadata from edges:

```python
for node in results.nodes[:limit]:
    # Gather edge temporal data for this node
    node_edges = [e for e in (results.edges or []) if e.source_node_uuid == node.uuid or e.target_node_uuid == node.uuid]
    latest_edge = max(node_edges, key=lambda e: e.created_at, default=None) if node_edges else None

    entities.append({
        # ... existing fields ...
        "valid_at": latest_edge.valid_at.isoformat() if latest_edge and hasattr(latest_edge, 'valid_at') and latest_edge.valid_at else None,
        "invalid_at": latest_edge.invalid_at.isoformat() if latest_edge and hasattr(latest_edge, 'invalid_at') and latest_edge.invalid_at else None,
        "expired_at": latest_edge.expired_at.isoformat() if latest_edge and hasattr(latest_edge, 'expired_at') and latest_edge.expired_at else None,
    })
```

### Test Plan

| Test | Asserts |
|------|---------|
| `test_new_entity_gets_temporal_fields` | PERCEPTION entity has `valid_from`, `valid_until=None`, `is_current=True` |
| `test_contradicting_fact_invalidates_old` | Creating "Patient takes Metformin" then "Patient stopped Metformin" → first entity gets `is_current=False`, `valid_until` set |
| `test_merge_preserves_temporal_on_update` | Merging with `valid_at`/`invalid_at` stores them on the Neo4j node |
| `test_no_temporal_data_defaults_safe` | Entity without temporal fields gets `valid_from=now`, `is_current=True` |
| `test_invalidation_scoped_to_name_and_type` | Invalidating "Metformin/Medication" does NOT affect "Metformin/Allergy" |

### Acceptance Criteria

- All crystallized PERCEPTION entities have `valid_from`, `valid_until`, `is_current` properties.
- When a newer version of the same entity (name+type) is crystallized, older versions are marked `is_current=false`.
- Old entities are never deleted — only invalidated (preserving history per Graphiti best practice).
- Entities without temporal data from Graphiti default to `valid_from=now, is_current=true`.

---

## SPEC-3: Bound Search Results

**Checklist item**: §4.3 — *Bound search results — Some search paths don't limit results explicitly (e.g., `crystallize_from_graphiti` uses a default limit of 100 but the search itself doesn't pass `num_results`).*

### Problem

Several search call sites in the codebase do not pass explicit `num_results` to the Graphiti search API. While the caller may slice results afterward (`results.nodes[:limit]`), the underlying search may return unbounded intermediate results, wasting tokens and compute:

1. `crystallize_from_graphiti()` — line 536-542: `search()` called without `num_results`, results sliced post-hoc at `[:limit]`.
2. `search_episodes()` — line 430-436: `search()` called without `num_results`, results sliced at `[:limit]`.
3. `get_related_entities()` — line 473-478: `search()` called without `num_results`, results sliced at `[:limit]`.
4. `_get_existing_entities()` in EntityResolver — line 217-221: `LIMIT 100` is hardcoded in the Cypher string rather than parameterized.

### Goal

Ensure every search path passes an explicit bound to the underlying search API, and parameterize all Cypher `LIMIT` clauses.

### Files to Change

| File | Change |
|------|--------|
| `src/application/services/episodic_memory_service.py` | Pass `num_results` to `search()` in `search_episodes()` and `get_related_entities()` |
| `src/application/services/crystallization_service.py` | Pass `num_results` to `search()` in `crystallize_from_graphiti()` |
| `src/application/services/entity_resolver.py` | Parameterize `LIMIT` in `_get_existing_entities()` |
| `tests/test_episodic_memory.py` | Verify `num_results` is passed in mock assertions |
| `tests/test_crystallization_pipeline.py` | Verify `num_results` is passed in mock assertions |

### Implementation Details

**`search_episodes()`** — add `num_results` to the search config:

The `COMBINED_HYBRID_SEARCH_CROSS_ENCODER` recipe is a `SearchConfig` object. Graphiti's `search()` function accepts a `config` parameter which has a `limit` field. We should create a modified config per call:

```python
from graphiti_core.search.search_config import SearchConfig
from copy import deepcopy

async def search_episodes(self, patient_id, query, limit=10, session_id=None):
    # ...
    config = deepcopy(COMBINED_HYBRID_SEARCH_CROSS_ENCODER)
    config.limit = limit

    results: SearchResults = await search(
        clients=self.graphiti.clients,
        query=query,
        group_ids=group_ids,
        search_filter=SearchFilters(),
        config=config,
    )
    # No longer need post-hoc slicing on episodes
    return [self._convert_episode(ep, patient_id) for ep in results.episodes]
```

If `SearchConfig` doesn't have a `limit` field (version-dependent), use `num_results` kwarg:

```python
results = await search(
    clients=self.graphiti.clients,
    query=query,
    group_ids=group_ids,
    search_filter=SearchFilters(),
    config=COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
    num_results=limit,
)
```

Check Graphiti's `search()` signature at implementation time and use whichever parameter is available. If neither exists, keep post-hoc slicing but add a `# BOUNDED:` comment for auditability.

**`get_related_entities()`** — same approach, pass `limit` to the search call.

**`crystallize_from_graphiti()`** — same approach, pass `limit` to the search call.

**`_get_existing_entities()`** in EntityResolver — parameterize the Cypher:

```python
query = f"""
MATCH (e:{entity_type})
RETURN e.id AS id, e.name AS name, e AS properties
LIMIT $limit
"""
results = await self.backend.query(query, {"limit": limit})
```

Add a `limit` parameter to the method signature (default 100):

```python
async def _get_existing_entities(
    self,
    entity_type: str,
    context: Dict[str, Any],
    limit: int = 100,
) -> List[Dict[str, Any]]:
```

### Test Plan

| Test | Asserts |
|------|---------|
| `test_search_episodes_passes_limit` | Mock `search()` → assert `num_results` or `config.limit` matches caller's `limit` |
| `test_get_related_entities_passes_limit` | Same pattern |
| `test_crystallize_from_graphiti_passes_limit` | Same pattern |
| `test_entity_resolver_parameterized_limit` | Mock `backend.query()` → assert query params include `limit` |

### Acceptance Criteria

- No search call site relies solely on post-hoc slicing for bounding.
- Every `search()` call passes an explicit result count.
- Every Cypher `LIMIT` clause uses a parameter, not a hardcoded string.

---

## SPEC-4: Memory Invalidation / Expiration

**Checklist item**: §4.4 — *Memory invalidation/expiration — No mechanism to mark episodic or DIKW entities as expired/outdated.*

### Problem

There is currently no way to expire or invalidate entities in either the episodic graph (FalkorDB/Graphiti) or the DIKW graph (Neo4j). Entities accumulate indefinitely. For a medical domain this is particularly problematic — discontinued medications, resolved conditions, and outdated vitals remain "active" forever.

This is related to but distinct from SPEC-2 (temporal conflict resolution). SPEC-2 handles automatic invalidation when a contradicting fact arrives. This spec covers explicit invalidation via API and TTL-based expiration for stale entities.

### Goal

Add an invalidation mechanism for DIKW entities (explicit API + TTL-based staleness detection), and an expiration sweep for episodic memory.

### Design

```
                    ┌────────────────────────────┐
                    │    Invalidation Sources     │
                    ├────────────────────────────┤
                    │ 1. Explicit API call        │
                    │ 2. Temporal conflict (SPEC-2)│
                    │ 3. TTL staleness sweep      │
                    └─────────┬──────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   MemoryInvalidationService   │  ← NEW
              ├───────────────────────────────┤
              │ invalidate_entity()           │
              │ invalidate_by_query()         │
              │ sweep_stale_entities()        │
              │ get_invalidation_stats()      │
              └───────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         Neo4j DIKW     FalkorDB Episodic   Stats/Audit
         SET is_current  (future: TTL on     log invalidated
         = false         episode nodes)      entities
```

### Files to Change

| File | Change |
|------|--------|
| `src/application/services/memory_invalidation_service.py` | **NEW** — `MemoryInvalidationService` class |
| `src/application/services/crystallization_service.py` | Import and call `MemoryInvalidationService.sweep_stale_entities()` in the periodic batch |
| `src/composition_root.py` | Wire `MemoryInvalidationService` into the bootstrap |
| `tests/test_memory_invalidation.py` | **NEW** — unit tests |

### Implementation Details

**`MemoryInvalidationService`** — new service:

```python
@dataclass
class InvalidationConfig:
    """Configuration for memory invalidation."""
    stale_threshold_days: int = 90          # PERCEPTION entities not seen in N days
    stale_check_enabled: bool = True
    episodic_ttl_days: Optional[int] = None # None = no auto-expiry for episodes

@dataclass
class InvalidationResult:
    """Result of an invalidation operation."""
    entities_invalidated: int
    entity_ids: List[str]
    reason: str
    timestamp: datetime


class MemoryInvalidationService:

    def __init__(
        self,
        neo4j_backend: KnowledgeGraphBackend,
        config: Optional[InvalidationConfig] = None,
    ):
        self.neo4j_backend = neo4j_backend
        self.config = config or InvalidationConfig()

    async def invalidate_entity(
        self,
        entity_id: str,
        reason: str = "manual",
    ) -> InvalidationResult:
        """
        Explicitly invalidate a single DIKW entity.

        Sets is_current=false, invalidated_at=now(), invalidation_reason=reason.
        Does NOT delete the entity.
        """
```

Cypher for explicit invalidation:

```cypher
MATCH (n:Entity {id: $entity_id})
WHERE n.is_current = true OR n.is_current IS NULL
SET n.is_current = false,
    n.invalidated_at = datetime(),
    n.invalidation_reason = $reason,
    n.valid_until = COALESCE(n.valid_until, datetime())
RETURN n.id as id
```

**`invalidate_by_query()`** — invalidate multiple entities matching criteria:

```python
async def invalidate_by_query(
    self,
    patient_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_name: Optional[str] = None,
    reason: str = "bulk_invalidation",
) -> InvalidationResult:
```

Builds a dynamic Cypher WHERE clause from provided filters.

**`sweep_stale_entities()`** — TTL-based staleness:

```python
async def sweep_stale_entities(self) -> InvalidationResult:
    """
    Find and invalidate PERCEPTION entities not observed recently.

    Uses config.stale_threshold_days to determine staleness.
    Only targets PERCEPTION layer (higher layers are considered validated).
    """
```

Cypher:

```cypher
MATCH (n:Entity)
WHERE n.dikw_layer = 'PERCEPTION'
  AND (n.is_current = true OR n.is_current IS NULL)
  AND n.last_observed < $cutoff_date
SET n.is_current = false,
    n.invalidated_at = datetime(),
    n.invalidation_reason = 'stale_ttl'
RETURN n.id as id, n.name as name
```

**Integration with periodic crystallization** — in `CrystallizationService._periodic_crystallization()`, after the existing batch logic, optionally run the sweep:

```python
if self.invalidation_service and self.invalidation_service.config.stale_check_enabled:
    sweep_result = await self.invalidation_service.sweep_stale_entities()
    if sweep_result.entities_invalidated > 0:
        logger.info(f"Stale sweep: invalidated {sweep_result.entities_invalidated} entities")
```

**Composition root** — instantiate `MemoryInvalidationService` alongside the crystallization pipeline and inject it:

```python
invalidation_service = MemoryInvalidationService(
    neo4j_backend=neo4j_backend,
    config=InvalidationConfig(
        stale_threshold_days=int(os.getenv("MEMORY_STALE_THRESHOLD_DAYS", "90")),
        stale_check_enabled=os.getenv("ENABLE_STALE_SWEEP", "true").lower() in ("true", "1"),
    ),
)
```

### Test Plan

| Test | Asserts |
|------|---------|
| `test_invalidate_entity_sets_flags` | After invalidation, entity has `is_current=false`, `invalidated_at` set, `invalidation_reason` stored |
| `test_invalidate_entity_idempotent` | Invalidating already-invalidated entity returns count 0, no error |
| `test_invalidate_by_query_filters` | With `patient_id` filter, only matching entities invalidated |
| `test_sweep_targets_perception_only` | SEMANTIC/REASONING entities are untouched even if stale |
| `test_sweep_respects_threshold` | Entity observed 30 days ago with 90-day threshold is NOT invalidated |
| `test_sweep_disabled_config` | `stale_check_enabled=False` → sweep returns 0 immediately |

### Acceptance Criteria

- Entities can be explicitly invalidated via `invalidate_entity()` without deletion.
- Stale PERCEPTION entities are automatically invalidated by the periodic sweep.
- Higher-layer entities (SEMANTIC, REASONING, APPLICATION) are never auto-invalidated.
- All invalidations are auditable: `invalidated_at`, `invalidation_reason` are stored on the node.
- New env vars: `MEMORY_STALE_THRESHOLD_DAYS` (default 90), `ENABLE_STALE_SWEEP` (default true).

---

## SPEC-5: LLM Rate Limit Management

**Checklist item**: §4.5 — *LLM rate limit management — `SEMAPHORE_LIMIT` not configured; risk of 429 errors during high-throughput ingestion.*

### Problem

Graphiti makes concurrent LLM calls during episode ingestion (entity extraction, edge inference, deduplication). The library uses an internal semaphore (`SEMAPHORE_LIMIT` env var, default 10) to cap concurrency. SynapseFlow does not expose or configure this value, meaning:

1. During burst ingestion (e.g., uploading a full conversation history), 10 concurrent LLM calls may exceed provider rate limits.
2. 429 errors from the LLM provider cause ingestion failures with no retry.
3. There is no visibility into whether rate limiting is occurring.

### Goal

Expose `SEMAPHORE_LIMIT` as a configurable environment variable, add a health check for LLM rate status, and document tuning guidance.

### Design

```
                    ┌────────────────────────────────┐
                    │        Environment              │
                    │  GRAPHITI_SEMAPHORE_LIMIT=5     │ ← NEW env var
                    │  GRAPHITI_LLM_RETRY_ENABLED=true│ ← NEW env var
                    │  GRAPHITI_LLM_MAX_RETRIES=3     │ ← NEW env var
                    └───────────┬────────────────────┘
                                │
                    ┌───────────▼────────────────────┐
                    │   composition_root.py           │
                    │   bootstrap_episodic_memory()   │
                    │   os.environ["SEMAPHORE_LIMIT"] │ ← set before Graphiti import
                    └───────────┬────────────────────┘
                                │
                    ┌───────────▼────────────────────┐
                    │   EpisodicMemoryService         │
                    │   ├── _rate_limit_stats         │ ← NEW tracking dict
                    │   ├── store_turn_episode()      │
                    │   │   └── try/except 429 →      │
                    │   │       log + retry w/ backoff │
                    │   └── get_health()              │ ← NEW method
                    └────────────────────────────────┘
```

### Files to Change

| File | Change |
|------|--------|
| `src/composition_root.py` | Set `SEMAPHORE_LIMIT` env var before Graphiti imports in `bootstrap_episodic_memory()` |
| `src/application/services/episodic_memory_service.py` | Add rate-limit-aware retry wrapper, tracking stats, health method |
| `tests/test_episodic_memory.py` | Add tests for retry and health |

### Implementation Details

**Set `SEMAPHORE_LIMIT` at bootstrap** — in `bootstrap_episodic_memory()`, before importing Graphiti:

```python
async def bootstrap_episodic_memory(event_bus=None):
    import os

    # Configure Graphiti's LLM concurrency BEFORE importing graphiti_core
    semaphore_limit = os.getenv("GRAPHITI_SEMAPHORE_LIMIT", "5")
    os.environ["SEMAPHORE_LIMIT"] = semaphore_limit
    logger.info(f"Graphiti SEMAPHORE_LIMIT set to {semaphore_limit}")

    # ... rest of existing bootstrap ...
```

Default is lowered from Graphiti's 10 to 5, as SynapseFlow's medical domain use case favors reliability over throughput.

**Rate-limit-aware retry in `store_turn_episode()`** — wrap the `add_episode()` call:

```python
async def _add_episode_with_retry(self, **kwargs) -> Any:
    """Call graphiti.add_episode with retry on rate limit errors."""
    max_retries = int(os.getenv("GRAPHITI_LLM_MAX_RETRIES", "3"))
    retry_enabled = os.getenv("GRAPHITI_LLM_RETRY_ENABLED", "true").lower() in ("true", "1")

    for attempt in range(max_retries + 1):
        try:
            return await self.graphiti.add_episode(**kwargs)
        except Exception as e:
            is_rate_limit = "429" in str(e) or "rate" in str(e).lower()
            if is_rate_limit and retry_enabled and attempt < max_retries:
                wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
                self._rate_limit_stats["retries"] += 1
                logger.warning(
                    f"LLM rate limit hit (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {wait}s"
                )
                await asyncio.sleep(wait)
            else:
                if is_rate_limit:
                    self._rate_limit_stats["failures"] += 1
                raise
```

**Tracking stats** — add to `__init__`:

```python
self._rate_limit_stats = {
    "retries": 0,
    "failures": 0,
    "last_rate_limit": None,
}
```

**Health method** — add to `EpisodicMemoryService`:

```python
def get_health(self) -> Dict[str, Any]:
    """Return health/status information including rate limit stats."""
    return {
        "initialized": self._initialized,
        "rate_limit_retries": self._rate_limit_stats["retries"],
        "rate_limit_failures": self._rate_limit_stats["failures"],
        "last_rate_limit": self._rate_limit_stats["last_rate_limit"],
        "semaphore_limit": int(os.getenv("SEMAPHORE_LIMIT", "10")),
    }
```

**Use the retry wrapper** — in `store_turn_episode()` and `store_session_episode()`, replace direct `self.graphiti.add_episode()` calls with `self._add_episode_with_retry()`.

### Test Plan

| Test | Asserts |
|------|---------|
| `test_semaphore_limit_set_at_bootstrap` | After `bootstrap_episodic_memory()`, `os.environ["SEMAPHORE_LIMIT"]` equals configured value |
| `test_retry_on_rate_limit` | Mock `add_episode` raising 429 twice then succeeding → result returned, `retries=2` |
| `test_retry_exhausted_raises` | Mock `add_episode` raising 429 beyond max_retries → exception propagated, `failures=1` |
| `test_non_rate_limit_error_no_retry` | Mock `add_episode` raising `ValueError` → immediate propagation, `retries=0` |
| `test_retry_disabled_no_retry` | Set `GRAPHITI_LLM_RETRY_ENABLED=false` → 429 error propagated immediately |
| `test_get_health_includes_rate_stats` | `get_health()` returns dict with all expected keys |

### Acceptance Criteria

- `GRAPHITI_SEMAPHORE_LIMIT` env var controls Graphiti's internal concurrency (default: 5).
- Rate-limited `add_episode` calls are retried with exponential backoff (2s, 4s, 8s).
- After max retries exhausted, the error propagates normally.
- `get_health()` exposes rate limit stats for monitoring.
- New env vars: `GRAPHITI_SEMAPHORE_LIMIT` (default 5), `GRAPHITI_LLM_RETRY_ENABLED` (default true), `GRAPHITI_LLM_MAX_RETRIES` (default 3).

---

## Cross-Cutting Concerns

### New Environment Variables Summary

| Variable | Default | Spec | Purpose |
|----------|---------|------|---------|
| `GRAPHITI_SEMAPHORE_LIMIT` | `5` | SPEC-5 | Graphiti LLM concurrency cap |
| `GRAPHITI_LLM_RETRY_ENABLED` | `true` | SPEC-5 | Enable retry on 429 errors |
| `GRAPHITI_LLM_MAX_RETRIES` | `3` | SPEC-5 | Max retries before propagating error |
| `MEMORY_STALE_THRESHOLD_DAYS` | `90` | SPEC-4 | Days before PERCEPTION entity considered stale |
| `ENABLE_STALE_SWEEP` | `true` | SPEC-4 | Enable periodic staleness sweep |

### New Files Summary

| File | Spec | Description |
|------|------|-------------|
| `src/application/services/memory_invalidation_service.py` | SPEC-4 | Entity invalidation + TTL sweep |
| `tests/test_memory_invalidation.py` | SPEC-4 | Unit tests for invalidation service |

### Modified Files Summary

| File | Specs |
|------|-------|
| `src/application/services/episodic_memory_service.py` | SPEC-1, SPEC-3, SPEC-5 |
| `src/application/services/crystallization_service.py` | SPEC-2, SPEC-3, SPEC-4 |
| `src/application/services/entity_resolver.py` | SPEC-2, SPEC-3 |
| `src/composition_root.py` | SPEC-4, SPEC-5 |
| `tests/test_episodic_memory.py` | SPEC-1, SPEC-3, SPEC-5 |
| `tests/test_crystallization_pipeline.py` | SPEC-2, SPEC-3 |

### Dependency on SPEC-2 from SPEC-4

SPEC-4 (memory invalidation) depends on the `is_current`, `valid_until`, `invalidated_at` fields introduced by SPEC-2 (temporal conflict resolution). Implementation order: **SPEC-2 → SPEC-4**.

### Recommended Implementation Order

1. **SPEC-5** (LLM rate limits) — standalone, zero coupling, immediate operational benefit
2. **SPEC-3** (bound search results) — standalone, small diff, prevents resource waste
3. **SPEC-2** (temporal conflict resolution) — adds schema fields needed by SPEC-4
4. **SPEC-4** (memory invalidation) — depends on SPEC-2's schema
5. **SPEC-1** (community summaries) — feature addition, version-dependent, lowest urgency
