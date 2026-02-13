## Context

SynapseFlow's hypergraph bridge layer stores FactUnits as Neo4j nodes with `PARTICIPATES_IN` edges connecting N entities per fact. The current implementation (`hypergraph_bridge_service.py`) provides `build_bridge_layer()`, `get_facts_for_entity()`, `propagate_to_knowledge_graph()`, and `find_fact_chains()` — all using direct Cypher queries against Neo4j. There are 488 FactUnits and 6,589 PARTICIPATES_IN edges in production.

The limitation is that Neo4j's graph model treats FactUnits as intermediate nodes rather than true hyperedges. This means standard hypergraph algorithms (s-centrality, s-walks, community detection) cannot be expressed efficiently in Cypher. The current `find_fact_chains()` is hardcoded to 2-hop paths and cannot generalize.

HyperNetX (PNNL, v2.3+) is a Python library built on pandas DataFrames that natively represents hypergraphs and provides these algorithms. It requires Python 3.10+ (we use 3.13).

## Goals / Non-Goals

**Goals:**
- Provide standard hypergraph analytics (centrality, communities, connectivity, distances) over the existing FactUnit data
- Expose analytics through REST API endpoints for frontend consumption
- Integrate structural insights into the reasoning engine and quality assessment pipeline
- Maintain clean architecture: HyperNetX confined to infrastructure layer, domain models remain pure dataclasses
- Graceful degradation: everything works without HyperNetX installed

**Non-Goals:**
- Replacing Neo4j as the persistence layer for FactUnits
- Real-time streaming analytics (batch/on-demand is sufficient)
- Frontend visualization components (API provides data, frontend work is separate)
- Modifying the existing `HypergraphBridgeService` API contract
- Supporting HyperNetX as a write-back layer (read-only analytical overlay)

## Decisions

### 1. Ephemeral in-memory overlay vs. dual persistence

**Decision**: HyperNetX operates as an ephemeral in-memory engine loaded from Neo4j on demand.

**Alternatives considered**:
- *Dual-write to Neo4j + HyperNetX*: Adds write-path complexity, consistency concerns, and doubles mutation cost. Rejected — analytics are read-only.
- *Replace Neo4j for hypergraph data*: Loses all existing Cypher queries, provenance tracking, and DIKW layer integration. Rejected.

**Rationale**: Neo4j is the source of truth. HyperNetX loads a snapshot, runs analytics, and returns results. No synchronization needed — just cache invalidation on data changes.

### 2. Cache strategy: TTL with event-based invalidation

**Decision**: 5-minute TTL cache on the loaded `hnx.Hypergraph` object, invalidated on `crystallization_complete` events.

**Alternatives considered**:
- *No cache (reload every request)*: With 488 FactUnits and 6,589 edges, the Neo4j query + DataFrame construction takes ~200-500ms. Acceptable per-request, but wasteful for consecutive analytics calls.
- *Long-lived cache (invalidate only on events)*: Risk of serving stale data if events are missed.

**Rationale**: TTL provides a safety net. Event-based invalidation handles the common case (crystallization writes new FactUnits). The adapter subscribes to `crystallization_complete` via the existing `EventBus`.

### 3. Adapter placement: infrastructure layer

**Decision**: `HyperNetXAdapter` lives in `src/infrastructure/hypernetx_adapter.py`.

**Rationale**: It depends on both `hypernetx` (external library) and `neo4j` (database). Infrastructure layer is the correct home per clean architecture. The adapter returns domain dataclasses (`CentralityResult`, `CommunityResult`, etc.) defined in `src/domain/hypernetx_models.py` which have zero external imports.

### 4. Analytics service: application layer orchestrator

**Decision**: `HypergraphAnalyticsService` in `src/application/services/` wraps the adapter and provides high-level methods.

**Rationale**: Follows the existing pattern where `HypergraphBridgeService` sits in application layer and delegates to `neo4j_backend`. The analytics service delegates to `HyperNetXAdapter` and adds business logic (e.g., filtering by DIKW layer, combining analytics with quality scoring).

### 5. Reasoning integration: optional dependency via constructor

**Decision**: Add `hypergraph_analytics` as an optional parameter to `ReasoningEngine.__init__()`. New rule `hypergraph_structural_analysis` added to the `chat_query` rule list at medium priority.

**Alternatives considered**:
- *Mandatory dependency*: Would break existing initialization paths and tests. Rejected.
- *Runtime discovery via service locator*: Violates explicit dependency injection pattern used throughout the codebase. Rejected.

**Rationale**: Follows the same pattern as `medical_rules_engine` (optional, checked via `if self.hypergraph_analytics:` before use). Rule skips gracefully when analytics service is not provided.

### 6. API router: separate module under `/api/hypergraph`

**Decision**: New `hypergraph_router.py` registered in `main.py`, prefix `/api/hypergraph`.

**Rationale**: Follows the pattern of `document_router`, `crystallization_router`. Keeps hypergraph endpoints cohesive and independently testable. Endpoints return 503 if HyperNetX is not available.

### 7. Quality metric: additive, not replacing

**Decision**: Add `_assess_hypergraph_coherence()` as a new metric in `OntologyQualityService`, contributing to the overall score alongside the existing 7 metrics.

**Rationale**: The metric measures structural coherence (modularity, isolated components, community distribution) — orthogonal to existing coverage, compliance, and taxonomy metrics. Adds a new dimension to quality assessment without modifying existing scoring.

## Risks / Trade-offs

**[Memory usage for large hypergraphs]** HyperNetX loads the full incidence matrix into pandas DataFrames. At 488 FactUnits / 6,589 edges this is trivial (~1MB). At 10,000+ FactUnits, memory could reach 50-100MB.
→ Mitigation: Support filtered loading (by document, DIKW layer, confidence threshold) so only relevant subgraphs are loaded. Add max-size guard in adapter.

**[Algorithm runtime on large graphs]** Kumar's community detection and s-centrality can be O(n^2) or worse on dense hypergraphs.
→ Mitigation: Set configurable timeouts on analytics calls. Return partial results with a warning when timeout is hit. Cache results aggressively.

**[HyperNetX API stability]** Library is actively developed by PNNL; API may change between major versions.
→ Mitigation: Pin `hypernetx>=2.3.0,<3.0.0`. Adapter pattern isolates all HyperNetX calls to a single file — version upgrades only affect the adapter.

**[Stale cache during high ingestion]** During batch document ingestion, FactUnits are created rapidly. The 5-minute TTL means analytics may reflect older data.
→ Mitigation: Acceptable for analytics use case. Users can call a manual refresh endpoint. Crystallization events trigger invalidation for the most impactful changes.

**[Optional dependency complexity]** Every integration point must check if HyperNetX is available, adding conditional branches.
→ Mitigation: Centralize the availability check in the adapter (`HyperNetXAdapter.is_available()`). Dependency injection handles the rest — services that don't receive the analytics instance simply skip hypergraph features.

## Open Questions

- Should community detection results be persisted back to Neo4j as entity properties (e.g., `community_id`)? This would enable Cypher queries filtered by community but adds a write path.
- What `s` value thresholds are most useful for medical knowledge? s=1 (entities share any fact) vs s=2 (entities share 2+ facts) — may need empirical tuning after initial deployment.
- Should the Euler diagram visualization endpoint return SVG server-side or just D3-compatible JSON for the frontend to render? JSON is more flexible but requires frontend work.
