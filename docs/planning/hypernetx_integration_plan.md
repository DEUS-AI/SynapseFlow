# HyperNetX Integration Plan for SynapseFlow

## Context

SynapseFlow already has a custom hypergraph bridge layer (488 FactUnits, 6,589 PARTICIPATES_IN edges in Neo4j) connecting the Document Graph with the Knowledge Graph. However, this implementation lacks standard hypergraph algorithms (centrality, community detection, s-walks), visualization, and algebraic operations.

**HyperNetX** (PNNL, v2.3+) is a Python library for hypergraph analysis built on pandas DataFrames. It provides: s-centrality, community detection (Kumar's algorithm), s-walks/s-distance, Euler diagram visualization, hypergraph arithmetic (union/intersection/difference), and Hypergraph Interchange Format (HIF) export. It requires Python 3.10+ (we use 3.13).

**Goal**: Integrate HyperNetX as an analytical overlay on the existing Neo4j-persisted bridge layer. Neo4j stays as the persistence layer; HyperNetX operates as an ephemeral in-memory engine loaded from Neo4j on demand.

---

## Phase 1: Infrastructure Adapter (Foundation)

### 1.1 Add dependency
- Add `"hypernetx>=2.3.0,<3.0.0"` to `pyproject.toml` dependencies

### 1.2 Domain models
- **New file**: `src/domain/hypernetx_models.py` (pure dataclasses, no HyperNetX imports)
- Dataclasses: `HypergraphSnapshot`, `CentralityResult`, `CommunityResult`, `ConnectivityResult`, `TopologicalSummary`

### 1.3 Infrastructure adapter
- **New file**: `src/infrastructure/hypernetx_adapter.py`
- `HyperNetXAdapter` class that:
  - Queries Neo4j for FactUnit + PARTICIPATES_IN data (reuse Cypher patterns from `hypergraph_bridge_service.py:113-127`)
  - Constructs `hnx.Hypergraph` with edges=FactUnit IDs, nodes=Entity IDs
  - Attaches properties (fact_type, confidence, layer, entity_type)
  - Supports filtering by confidence threshold, DIKW layer, document_id, fact_type
  - 5-minute TTL cache to avoid redundant Neo4j queries

### 1.4 Tests
- **New file**: `tests/infrastructure/test_hypernetx_adapter.py`
- Follow `tests/application/test_hypergraph_bridge.py` patterns (AsyncMock for neo4j backend)

---

## Phase 2: Analytics Service (Core Value)

### 2.1 Analytics service
- **New file**: `src/application/services/hypergraph_analytics_service.py`
- `HypergraphAnalyticsService` with methods:

| Method | HyperNetX Algorithm | SynapseFlow Use Case |
|--------|---------------------|---------------------|
| `compute_entity_centrality(s=1)` | s-distance sampling + betweenness approximation | Find hub medical entities |
| `detect_knowledge_communities()` | `hnx.algorithms.hypergraph_modularity.kumar()` | Identify coherent topic clusters (cardiology, GI, etc.) |
| `analyze_connectivity(s_values=[1,2,3])` | `H.s_connected_components(s)` | Find knowledge islands at varying rigor |
| `compute_entity_distances(entity_id, s=1)` | `H.distance(source, target, s)` | Replace custom `find_fact_chains()` with standard s-walks |
| `get_topological_summary()` | Node/edge counts, density, diameter | Overall hypergraph health metrics |
| `compute_hypergraph_diff()` | `H1 - H2` (set difference) | Track knowledge changes between crystallization batches |

### 2.2 Bridge service integration
- Add optional `analytics` parameter to `HypergraphBridgeService.__init__()`
- `find_fact_chains()` stays for simple 2-hop (fast, Neo4j-native)
- `compute_entity_distances()` handles arbitrary-hop via HyperNetX s-walks

### 2.3 Tests
- **New file**: `tests/application/test_hypergraph_analytics.py`

---

## Phase 3: Reasoning & Quality Integration

### 3.1 New reasoning rule
- **Modify**: `src/application/agents/knowledge_manager/reasoning_engine.py`
- Add `hypergraph_structural_analysis` rule (medium priority) to `chat_query` rules (~line 117)
- Implementation: compute entity distances + identify structurally central entities + confidence boost for entities in dense clusters
- Optional `hypergraph_analytics` param in `ReasoningEngine.__init__()`

### 3.2 Quality assessment enhancement
- **Modify**: `src/application/services/ontology_quality_service.py`
- New method `_assess_hypergraph_coherence()`: run community detection, compute modularity, check for isolated components
- Adds "Hypergraph Coherence" metric to quality report

### 3.3 Crystallization cache invalidation
- **Modify**: `src/application/services/crystallization_service.py`
- After crystallization completes, call `adapter.invalidate_cache()` to refresh HyperNetX data

### 3.4 Dependency injection
- **Modify**: `src/application/api/dependencies.py`
- Add `_hypergraph_analytics_instance` singleton (following existing pattern at lines 14-37)
- Wire into `get_neurosymbolic_service()` → ReasoningEngine

---

## Phase 4: API Endpoints & Visualization

### 4.1 API router
- **New file**: `src/application/api/hypergraph_router.py` (prefix: `/api/hypergraph`)
- Endpoints:
  - `GET /summary` - topological summary
  - `GET /centrality` - entity centrality rankings
  - `GET /communities` - knowledge community detection
  - `GET /connectivity` - s-connected components
  - `GET /entity/{entity_id}/distances` - s-distances from entity
  - `GET /visualization/euler` - data for Euler diagram (D3-compatible JSON)
  - `GET /export/hif` - Hypergraph Interchange Format export

### 4.2 Register router
- **Modify**: `src/application/api/main.py` - include hypergraph_router

### 4.3 Tests
- **New file**: `tests/application/test_hypergraph_router.py`

---

## Files Summary

### New files (7)
| File | Layer | Purpose |
|------|-------|---------|
| `src/domain/hypernetx_models.py` | Domain | Pure dataclasses for analysis results |
| `src/infrastructure/hypernetx_adapter.py` | Infrastructure | Neo4j → HyperNetX loader with caching |
| `src/application/services/hypergraph_analytics_service.py` | Application | Algorithm wrappers |
| `src/application/api/hypergraph_router.py` | Interface | REST API endpoints |
| `tests/infrastructure/test_hypernetx_adapter.py` | Tests | Adapter tests |
| `tests/application/test_hypergraph_analytics.py` | Tests | Analytics tests |
| `tests/application/test_hypergraph_router.py` | Tests | API tests |

### Modified files (5)
| File | Change |
|------|--------|
| `pyproject.toml` | Add hypernetx dependency |
| `src/application/services/hypergraph_bridge_service.py` | Optional analytics parameter |
| `src/application/agents/knowledge_manager/reasoning_engine.py` | New reasoning rule |
| `src/application/api/dependencies.py` | DI wiring for analytics service |
| `src/application/api/main.py` | Register hypergraph_router |

---

## Design Decisions

1. **Analytical overlay, not replacement** - Neo4j persists FactUnits; HyperNetX is loaded on-demand for analysis. No dual-write complexity.
2. **Clean architecture preserved** - HyperNetX never leaks into domain layer. `hypernetx_models.py` is pure Python dataclasses.
3. **Graceful degradation** - All HyperNetX features are optional. If not installed, system works exactly as before (reasoning skips hypergraph rule, quality skips coherence metric, API returns 503).
4. **TTL cache** - 5-minute cache avoids re-querying Neo4j for repeated analytics calls. Invalidated on crystallization events.

---

## Verification

1. `uv sync` - verify hypernetx installs without conflicts
2. `uv run pytest tests/infrastructure/test_hypernetx_adapter.py -v` - adapter tests pass
3. `uv run pytest tests/application/test_hypergraph_analytics.py -v` - analytics tests pass
4. Start backend, call `GET /api/hypergraph/summary` - returns topological metrics
5. Call `GET /api/hypergraph/communities` - returns knowledge clusters from live Neo4j data
6. Call `GET /api/hypergraph/centrality` - returns ranked entities
7. Call `GET /api/hypergraph/export/hif` - returns valid HIF JSON

---

## HyperNetX Research Notes

### Key Library Facts
- **Repo**: https://github.com/pnnl/HyperNetX
- **Docs**: https://hypernetx.readthedocs.io/
- **Maintainer**: Pacific Northwest National Laboratory (PNNL)
- **Version**: 2.3+ (actively maintained)
- **Python**: 3.10+, built on pandas DataFrames
- **Install**: `pip install hypernetx`

### Core Concepts
- **Hyperedge**: An edge connecting any number of nodes (not just 2). Represents n-ary relationships.
- **s-walk**: A path through hyperedges where consecutive edges share at least `s` nodes. Higher `s` = stricter connectivity.
- **s-distance**: Minimum s-walk length between two nodes.
- **Incidence matrix**: Rows=nodes, columns=hyperedges. Entry (v,e) is nonzero if node v is in hyperedge e.

### Algorithms Available
- **Community detection**: Kumar's algorithm (hybrid Louvain + edge reweighting)
- **Modularity**: Hypergraph modularity scoring
- **Centrality**: s-centrality measures (generalized betweenness/closeness)
- **Connectivity**: s-connected components at varying thresholds
- **Topology**: Simplicial homology for structural analysis
- **Clustering**: Laplacian clustering for hypergraphs

### Visualization
- **Matplotlib**: Static Euler diagrams, UpSet-style incidence plots
- **HyperNetX-Widget**: Interactive Jupyter widget with drag-and-drop, bipartite views
- **Graphistry integration**: Bridge to Graphistry for large-scale visualization

### Why HyperNetX for SynapseFlow
1. Our FactUnits ARE hyperedges - they connect N entities from shared context
2. s-walks can replace custom `find_fact_chains()` with a mathematically rigorous algorithm
3. Community detection reveals coherent medical topic clusters across the knowledge graph
4. Centrality identifies hub medical entities (key drugs, diseases, treatments)
5. HIF export enables interoperability with other research tools
6. Euler diagrams provide intuitive visualization of multi-entity medical facts
