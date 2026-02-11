## 1. Dependency & Domain Models

- [ ] 1.1 Add `hypernetx>=2.3.0,<3.0.0` to `pyproject.toml` dependencies and run `uv sync` to verify installation
- [ ] 1.2 Add analytics result dataclasses to `src/domain/hypernetx_models.py`: `CentralityResult`, `CommunityResult`, `ConnectivityResult`, `TopologicalSummary`, `HypergraphDiff` (pure dataclasses, no external imports)

## 2. Infrastructure Adapter

- [ ] 2.1 Create `src/infrastructure/hypernetx_adapter.py` with `HyperNetXAdapter` class: conditional `hypernetx` import, `is_available()` check, Neo4j driver injection
- [ ] 2.2 Implement `load_hypergraph()` method: query FactUnit + PARTICIPATES_IN from Neo4j, construct `hnx.Hypergraph` with entity/fact properties attached
- [ ] 2.3 Implement filter parameters: `min_confidence`, `layer`, `document_id`, `fact_type` with conjunctive (AND) logic
- [ ] 2.4 Implement TTL cache: 5-minute expiry keyed by filter parameters, `invalidate_cache()` method
- [ ] 2.5 Write tests in `tests/infrastructure/test_hypernetx_adapter.py`: mock Neo4j driver, test loading, filtering, cache hit/miss, graceful degradation when HyperNetX unavailable

## 3. Analytics Service

- [ ] 3.1 Create `src/application/services/hypergraph_analytics_service.py` with `HypergraphAnalyticsService` class, injected with `HyperNetXAdapter`
- [ ] 3.2 Implement `compute_entity_centrality(s=1)`: s-betweenness centrality, return ranked `CentralityResult` list
- [ ] 3.3 Implement `detect_knowledge_communities()`: Kumar's algorithm via `hnx.algorithms.hypergraph_modularity`, return `CommunityResult` list with modularity scores
- [ ] 3.4 Implement `analyze_connectivity(s_values=[1,2,3])`: s-connected components for each s value, flag knowledge islands (components < 3 entities)
- [ ] 3.5 Implement `compute_entity_distances(entity_id, s=1)`: s-distances from entity to all reachable entities, handle unreachable as infinity
- [ ] 3.6 Implement `get_topological_summary()`: node/edge counts, density, avg/max edge size, avg node degree, diameter
- [ ] 3.7 Implement `compute_hypergraph_diff(before, after)`: set difference of edges/nodes between two snapshots
- [ ] 3.8 Handle edge cases: empty hypergraph returns valid zero-value results, single-edge returns uniform scores
- [ ] 3.9 Write tests in `tests/application/test_hypergraph_analytics.py`: unit tests for each method with mock adapter, test edge cases

## 4. Reasoning & Quality Integration

- [ ] 4.1 Add optional `hypergraph_analytics` parameter to `ReasoningEngine.__init__()` in `reasoning_engine.py`
- [ ] 4.2 Add `hypergraph_structural_analysis` rule to `chat_query` rules at medium priority in `_initialize_reasoning_rules()`
- [ ] 4.3 Implement `_hypergraph_structural_analysis()` method: compute centrality + community for query entities, apply confidence boosts (up to 0.05 centrality + 0.03 community, capped at 0.08 total), include provenance
- [ ] 4.4 Add `_assess_hypergraph_coherence()` to `OntologyQualityService`: modularity (weight 0.4) + non-trivial community coverage (weight 0.3) + inverse isolated ratio (weight 0.3), skip when analytics unavailable
- [ ] 4.5 Subscribe to `crystallization_complete` event in `crystallization_service.py` to call `adapter.invalidate_cache()`

## 5. API Endpoints

- [ ] 5.1 Create `src/application/api/hypergraph_router.py` with prefix `/api/hypergraph`, shared query parameter dependencies for `min_confidence`, `layer`, `document_id`
- [ ] 5.2 Implement `GET /summary` endpoint returning topological summary
- [ ] 5.3 Implement `GET /centrality` endpoint with optional `s` and `limit` query params
- [ ] 5.4 Implement `GET /communities` endpoint returning community detection results
- [ ] 5.5 Implement `GET /connectivity` endpoint with optional `s_values` query param
- [ ] 5.6 Implement `GET /entity/{entity_id}/distances` endpoint with 404 for unknown entities
- [ ] 5.7 Implement `GET /visualization/euler` endpoint returning D3-compatible JSON with optional `max_edges` param
- [ ] 5.8 Implement `GET /export/hif` endpoint returning HIF JSON with optional `min_confidence` filter
- [ ] 5.9 Add 503 responses for all endpoints when HyperNetX is unavailable

## 6. Dependency Injection & Registration

- [ ] 6.1 Add `_hypergraph_analytics_instance` singleton and `get_hypergraph_analytics()` factory to `dependencies.py`
- [ ] 6.2 Wire `HyperNetXAdapter` into analytics service, pass analytics into `get_neurosymbolic_service()` for ReasoningEngine
- [ ] 6.3 Register `hypergraph_router` in `main.py` alongside existing routers

## 7. Integration Testing & Verification

- [ ] 7.1 Write API integration tests in `tests/application/test_hypergraph_router.py`: test all endpoints with mock analytics service, test 503 when unavailable, test filter parameter passthrough
- [ ] 7.2 Run full test suite (`uv run pytest tests/ -v`) and verify no regressions
- [ ] 7.3 Manual verification: start backend, call `GET /api/hypergraph/summary` against live Neo4j data, verify response structure
