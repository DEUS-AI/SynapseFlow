# Graphiti Memory Handling Brief

## 1. What Is Graphiti?

Graphiti is an open-source Python framework by Zep for building temporally-aware knowledge graphs designed for AI agent memory. Unlike traditional RAG, which treats memories as isolated, static documents, Graphiti continuously integrates user interactions and structured/unstructured data into a coherent, queryable graph with:

- **Bi-temporal model** -- tracks both when an event occurred and when it was ingested, with explicit validity intervals on every edge.
- **Real-time incremental updates** -- new episodes are integrated without batch recomputation.
- **Hybrid search** -- combines semantic embeddings, keyword (BM25), and graph traversal at sub-300ms P95 latency with no LLM calls at retrieval time.
- **Automatic ontology building** -- LLM-driven entity extraction and deduplication.

Graphiti organizes memory into three hierarchical subgraph tiers (per the Zep paper arXiv:2501.13956):

| Tier | Subgraph | Contents |
|------|----------|----------|
| 1 | **Episode Subgraph** | Raw events/messages with timestamps -- the ground-truth corpus |
| 2 | **Semantic Entity Subgraph** | Entities and factual edges extracted from episodes, embedded in high-dimensional space |
| 3 | **Community Subgraph** | Clusters of strongly connected entities with high-level summaries |

---

## 2. How SynapseFlow Uses Graphiti

### 2.1 Role in the Architecture

Graphiti is **not** the primary knowledge graph backend. SynapseFlow uses a dual-graph architecture:

| System | Backend | Purpose | Lifetime |
|--------|---------|---------|----------|
| DIKW Knowledge Graph | **Neo4j** | Persistent knowledge with 4 layers (PERCEPTION / SEMANTIC / REASONING / APPLICATION) | Permanent |
| Episodic Memory | **Graphiti + FalkorDB** | Conversation memory with automatic entity extraction | Session-bound |

The **CrystallizationService** bridges the two: it transfers entities discovered in episodic memory into the DIKW graph as PERCEPTION-layer nodes, where they can be promoted through confidence-based thresholds.

### 2.2 Core Implementation Files

| File | Responsibility |
|------|---------------|
| `src/infrastructure/graphiti.py` | Graphiti client initialization (Neo4j driver) |
| `src/infrastructure/graphiti_backend.py` | `KnowledgeGraphBackend` adapter for direct KG operations via Graphiti |
| `src/application/services/episodic_memory_service.py` | Primary Graphiti consumer -- episode storage, retrieval, hybrid search |
| `src/application/services/crystallization_service.py` | Episodic-to-DIKW transfer pipeline |
| `src/composition_root.py` (lines 472-510) | Backend selection (`KG_BACKEND` env var) and bootstrap |

### 2.3 EpisodicMemoryService

This is the central integration point. Key design choices:

**Group ID Strategy (multi-tenant isolation):**
- Session-level episodes: `group_id = patient_id`
- Turn-level episodes: `group_id = "{patient_id}:{session_id}"`

**Episode Types:**
- `EpisodeType.message` for conversation turns (user/assistant pairs)
- `EpisodeType.json` for session summaries

**Search:**
- Uses `COMBINED_HYBRID_SEARCH_CROSS_ENCODER` recipe (semantic + keyword + cross-encoder reranking)
- `get_conversation_context()` assembles multi-source context: recent episodes + semantically related episodes + extracted entities

**Event Integration:**
- Emits `episode_added` events on the `EventBus` after each stored episode
- These events carry `episode_id`, `patient_id`, `session_id`, and `entities_extracted`
- The `CrystallizationService` subscribes to these events

### 2.4 Crystallization Pipeline

```
EpisodicMemoryService (Graphiti + FalkorDB)
    | emits "episode_added"
    v
CrystallizationService
    |-- Queries FalkorDB for extracted entities
    |-- Resolves/deduplicates via EntityResolver (exact, fuzzy, embedding)
    |-- Creates PERCEPTION-layer nodes in Neo4j
    |-- Evaluates promotion candidates (confidence >= 0.85, observations >= 2)
    v
Neo4j DIKW Knowledge Graph
```

Three processing modes:
- **EVENT_DRIVEN**: immediate crystallization per episode
- **BATCH**: periodic processing (default 5 min interval)
- **HYBRID** (default): queue events, trigger on threshold (10 entities) or interval

### 2.5 GraphitiBackend (Alternative KG Backend)

`GraphitiBackend` implements `KnowledgeGraphBackend` for using Graphiti as the *primary* KG backend (selected via `KG_BACKEND=graphiti`). This is separate from episodic memory usage and maps the generic interface to Graphiti's `EntityNode`/`EntityEdge` structures and `add_triplet()` API.

---

## 3. Implementation vs. Graphiti Best Practices -- Conformance Check

### 3.1 What Aligns Well

| Best Practice | SynapseFlow Implementation | Status |
|---------------|---------------------------|--------|
| **Use `group_ids` for multi-tenant isolation** | Patient-level and session-level group IDs | Aligned |
| **Store episodes with `reference_time`** | Timestamps passed to `add_episode()` | Aligned |
| **Use hybrid search, not pure vector** | `COMBINED_HYBRID_SEARCH_CROSS_ENCODER` recipe | Aligned |
| **Separate episodic from semantic memory** | FalkorDB for episodes, Neo4j for persistent KG | Aligned |
| **Incremental, not batch RAG** | Episodes added in real-time per conversation turn | Aligned |
| **Handle entity deduplication** | `EntityResolver` with exact/fuzzy/embedding strategies | Aligned |
| **Avoid LLM calls at retrieval time** | Hybrid search config avoids LLM during search | Aligned |
| **Event-driven processing** | `EventBus` pub/sub for episode-to-crystallization flow | Aligned |

### 3.2 Gaps and Concerns

| Issue | Description | Severity |
|-------|-------------|----------|
| **Graphiti v0.27.1 RediSearch bug** | `build_fulltext_query()` generates invalid syntax for tag fields. SynapseFlow applies a monkey-patch (lines 44-93 of `episodic_memory_service.py`). This is a fragile workaround that will break on Graphiti upgrades. | Medium |
| **Missing community subgraph usage** | Graphiti's 3-tier model includes community detection (Tier 3), but SynapseFlow does not use community summaries. This means high-level, aggregated views of patient knowledge are unavailable. | Low |
| **No temporal conflict resolution** | Graphiti's bi-temporal model supports invalidating outdated facts via `t_valid`/`t_invalid` on edges. The crystallization pipeline does not propagate or leverage these temporal markers when transferring to Neo4j. | Medium |
| **`retrieve_recent_episodes()` scope limitation** | When no `session_id` is provided, only `group_id = patient_id` is queried. Turn-level episodes (which use `patient_id:session_id`) require knowing all session IDs -- the code acknowledges this with a comment but does not solve it. | Medium |
| **Hardcoded search query in `crystallize_from_graphiti()`** | Line 540: `query="medical entity"` is a broad, hardcoded search term for batch crystallization. This limits entity discovery to medical contexts and may miss non-medical entities. | Low |
| **No `SEMAPHORE_LIMIT` configuration** | Graphiti recommends tuning `SEMAPHORE_LIMIT` for LLM provider rate limits. SynapseFlow does not expose or configure this. | Low |
| **Dual `add_entity` Cypher calls in GraphitiBackend** | `graphiti_backend.py` lines 51-90 execute two separate MERGE queries for the same entity (one for attributes-as-JSON, one for attributes-as-properties). This is redundant and could cause race conditions. | Low |
| **`graphiti.py` initialization uses Neo4j driver only** | The `get_graphiti()` helper connects via Neo4j URI/user/password but does not support FalkorDB initialization, even though `EpisodicMemoryService` uses FalkorDB. These are two separate initialization paths that could diverge. | Low |
| **Version pinning** | Pinned to `graphiti-core[falkordb]>=0.27.1,<0.28`. The latest stable release is v0.28.1 (Feb 2026), which may contain fixes for the RediSearch bug. Upgrading should be evaluated. | Medium |

### 3.3 Test Coverage Assessment

| Area | Coverage | Notes |
|------|----------|-------|
| EpisodicMemoryService | Good | 14 tests covering init, storage, retrieval, search, error handling, helpers |
| CrystallizationService | Good | Tests for new/existing entity crystallization, batch processing, stats |
| EntityResolver | Good | Name normalization, type mapping, exact match, merge operations |
| PromotionGate | Good | Risk levels, approval/rejection criteria, stats |
| Integration (end-to-end) | Partial | Event bus wiring tested, but no live FalkorDB/Graphiti integration test |
| GraphitiBackend | Missing | No dedicated unit tests for the `KnowledgeGraphBackend` adapter |

---

## 4. Memory Management Sanity Check -- Best Practices for Agent Systems

Based on Graphiti documentation, the Zep research paper, and industry patterns, here is a sanity checklist for agent memory management:

### 4.1 Memory Architecture

- [x] **Separate episodic from semantic memory** -- SynapseFlow uses FalkorDB for episodes, Neo4j for structured knowledge.
- [x] **Multi-layer memory with different lifetimes** -- Redis (short-term, 24h TTL), Mem0 (mid-term), Neo4j (long-term).
- [x] **Entity deduplication across memory layers** -- EntityResolver handles cross-layer dedup with multiple strategies.
- [ ] **Community/summary layer** -- Graphiti supports community detection for high-level summaries. Not implemented.
- [x] **Memory isolation per user/tenant** -- Group IDs partition data at the storage layer.

### 4.2 Data Ingestion

- [x] **Incremental updates, not batch recomputation** -- Episodes are added per conversation turn in real-time.
- [x] **Structured episode format** -- Conversation turns use Graphiti's message format; session summaries use JSON.
- [ ] **Temporal conflict resolution** -- Graphiti invalidates outdated edges via bi-temporal model, but this is not propagated to Neo4j.
- [x] **Source traceability** -- Episodes include `source_description` with patient/session context.

### 4.3 Retrieval

- [x] **Hybrid search (semantic + keyword + graph)** -- Uses `COMBINED_HYBRID_SEARCH_CROSS_ENCODER`.
- [x] **No LLM calls at retrieval time** -- Search avoids LLM inference for low latency.
- [x] **Context assembly from multiple sources** -- `get_conversation_context()` merges recent, related, and entity data.
- [x] **Result deduplication** -- Recent and related episodes are deduplicated by ID.
- [ ] **Bound search results** -- Some search paths don't limit results explicitly (e.g., `crystallize_from_graphiti` uses a default limit of 100 but the search itself doesn't pass `num_results`).

### 4.4 Knowledge Lifecycle

- [x] **Confidence-based promotion** -- PERCEPTION -> SEMANTIC requires confidence >= 0.85 and observations >= 2.
- [x] **Observation counting** -- Merge operations increment observation counts for promotion eligibility.
- [x] **Audit trail** -- `first_observed`, `last_observed`, `source` fields track entity provenance.
- [ ] **Memory invalidation/expiration** -- No mechanism to mark episodic or DIKW entities as expired/outdated.
- [x] **Event-driven pipeline** -- `episode_added` events trigger crystallization without polling.

### 4.5 Operational

- [x] **Graceful error handling** -- Retrieval methods return empty results on error; storage methods propagate exceptions.
- [x] **Idempotent initialization** -- `EpisodicMemoryService.initialize()` guards against double initialization.
- [x] **Configurable processing modes** -- Crystallization supports event-driven, batch, and hybrid modes.
- [ ] **LLM rate limit management** -- `SEMAPHORE_LIMIT` not configured; risk of 429 errors during high-throughput ingestion.
- [x] **Flush/quiescence support** -- `flush_now()` and `is_quiescent()` enable evaluation framework integration.

---

## 5. Recommendations

1. **Upgrade to graphiti-core v0.28.x** -- Evaluate whether the RediSearch syntax bug is fixed upstream and remove the monkey-patch if so.
2. **Add temporal metadata to crystallized entities** -- Propagate Graphiti's `t_valid`/`t_invalid` to Neo4j DIKW nodes to enable temporal queries and fact invalidation.
3. **Implement cross-session episode retrieval** -- Solve the `retrieve_recent_episodes` gap by querying for all sessions belonging to a patient, or use Graphiti's search which handles this implicitly.
4. **Replace hardcoded crystallization query** -- Use entity type or timestamp-based queries instead of `"medical entity"` for broader discovery.
5. **Add GraphitiBackend tests** -- The adapter has zero test coverage; add unit tests covering `add_entity`, `add_relationship`, and `query`.
6. **Configure `SEMAPHORE_LIMIT`** -- Expose this as an environment variable to prevent LLM rate limit issues during episode ingestion bursts.
7. **Consider community subgraph** -- For patients with long histories, community summaries could provide useful high-level context without retrieving individual episodes.
