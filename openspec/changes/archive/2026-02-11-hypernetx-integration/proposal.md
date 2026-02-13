## Why

SynapseFlow's hypergraph bridge layer already models N-ary medical facts as FactUnits (488 FactUnits, 6,589 PARTICIPATES_IN edges in Neo4j), but lacks standard hypergraph algorithms for centrality, community detection, connectivity analysis, and s-walk distance computation. The current `find_fact_chains()` is a custom 2-hop Cypher query that cannot generalize to arbitrary-hop reasoning. Integrating HyperNetX (PNNL, v2.3+) provides mathematically rigorous hypergraph analytics as an ephemeral in-memory overlay on the existing Neo4j-persisted bridge, unlocking knowledge community detection, hub entity identification, and structural quality metrics — all critical for the neurosymbolic reasoning pipeline.

## What Changes

- Add `hypernetx` as a Python dependency for hypergraph analytics
- New infrastructure adapter that loads FactUnit/PARTICIPATES_IN data from Neo4j into HyperNetX `Hypergraph` objects (with TTL caching)
- New analytics service exposing s-centrality, community detection (Kumar's algorithm), s-connected components, s-distances, topological summaries, and hypergraph diff
- New REST API endpoints under `/api/hypergraph` for analytics, visualization data (Euler diagrams), and HIF export
- New reasoning rule (`hypergraph_structural_analysis`) that uses centrality and community data to boost confidence for entities in dense clusters
- New quality metric (`Hypergraph Coherence`) using community detection and modularity scoring
- Domain models (pure dataclasses) for analytics results — no HyperNetX imports in the domain layer
- Cache invalidation hook after crystallization completes

## Capabilities

### New Capabilities
- `hypergraph-analytics`: Core analytics service wrapping HyperNetX algorithms (centrality, communities, connectivity, distances, topology, diff)
- `hypergraph-adapter`: Infrastructure adapter for loading Neo4j FactUnit data into HyperNetX with filtering and TTL caching
- `hypergraph-api`: REST API endpoints for hypergraph analytics, Euler diagram visualization data, and HIF export
- `hypergraph-reasoning`: Reasoning engine integration — structural analysis rule using centrality and community data for confidence boosting

### Modified Capabilities
<!-- No existing openspec/specs/ to modify — this is a greenfield integration -->

## Impact

- **Dependencies**: New `hypernetx>=2.3.0,<3.0.0` in `pyproject.toml` (Python 3.10+, pandas-based)
- **Domain layer**: New `src/domain/hypernetx_models.py` with pure dataclasses (no external imports, clean architecture preserved)
- **Infrastructure layer**: New `src/infrastructure/hypernetx_adapter.py` (Neo4j → HyperNetX loader)
- **Application layer**: New `src/application/services/hypergraph_analytics_service.py`; modifications to `reasoning_engine.py` (new rule), `ontology_quality_service.py` (new metric), `crystallization_service.py` (cache invalidation)
- **API layer**: New `src/application/api/hypergraph_router.py`; modification to `main.py` (router registration) and `dependencies.py` (DI wiring)
- **Graceful degradation**: All HyperNetX features are optional — if the library is not available or no FactUnits exist, the system works exactly as before (reasoning skips the rule, quality skips the metric, API returns 503)
