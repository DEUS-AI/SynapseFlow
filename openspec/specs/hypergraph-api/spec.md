## ADDED Requirements

### Requirement: Topological summary endpoint
The system SHALL expose a GET endpoint that returns the hypergraph's topological summary.

#### Scenario: Successful summary
- **WHEN** `GET /api/hypergraph/summary` is called
- **THEN** the response SHALL be 200 with JSON containing `node_count`, `edge_count`, `density`, `avg_edge_size`, `max_edge_size`, `avg_node_degree`, and `diameter`

#### Scenario: HyperNetX unavailable
- **WHEN** `GET /api/hypergraph/summary` is called but HyperNetX is not installed
- **THEN** the response SHALL be 503 with a JSON body containing `detail: "HyperNetX analytics not available"`

### Requirement: Centrality endpoint
The system SHALL expose a GET endpoint that returns entity centrality rankings.

#### Scenario: Default centrality
- **WHEN** `GET /api/hypergraph/centrality` is called
- **THEN** the response SHALL be 200 with a JSON array of entities ranked by s-centrality at s=1, each with `entity_id`, `entity_name`, `entity_type`, `centrality_score`, and `participating_fact_count`

#### Scenario: Custom s parameter
- **WHEN** `GET /api/hypergraph/centrality?s=2` is called
- **THEN** the system SHALL compute centrality at s=2

#### Scenario: Limit results
- **WHEN** `GET /api/hypergraph/centrality?limit=10` is called
- **THEN** only the top 10 entities by centrality score SHALL be returned

### Requirement: Community detection endpoint
The system SHALL expose a GET endpoint that returns knowledge community clusters.

#### Scenario: Detect communities
- **WHEN** `GET /api/hypergraph/communities` is called
- **THEN** the response SHALL be 200 with JSON containing `total_communities`, `overall_modularity`, and an array of community objects with `community_id`, `member_count`, `dominant_types`, and `member_entity_ids`

### Requirement: Connectivity endpoint
The system SHALL expose a GET endpoint that returns s-connected component analysis.

#### Scenario: Default connectivity
- **WHEN** `GET /api/hypergraph/connectivity` is called
- **THEN** the response SHALL be 200 with connectivity analysis at s=1, including `component_count` and an array of components with `component_id`, `size`, and `entity_ids`

#### Scenario: Multiple s values
- **WHEN** `GET /api/hypergraph/connectivity?s_values=1,2,3` is called
- **THEN** the response SHALL include connectivity analysis for each s value

### Requirement: Entity distances endpoint
The system SHALL expose a GET endpoint that returns s-distances from a specific entity.

#### Scenario: Distances from entity
- **WHEN** `GET /api/hypergraph/entity/{entity_id}/distances` is called
- **THEN** the response SHALL be 200 with an array of entities sorted by ascending s-distance, each with `entity_id`, `entity_name`, `distance`, and `reachable`

#### Scenario: Entity not found
- **WHEN** the specified entity_id does not exist in the hypergraph
- **THEN** the response SHALL be 404 with `detail: "Entity not found in hypergraph"`

### Requirement: Euler diagram visualization data endpoint
The system SHALL expose a GET endpoint that returns D3-compatible JSON for rendering Euler diagrams of the hypergraph.

#### Scenario: Visualization data
- **WHEN** `GET /api/hypergraph/visualization/euler` is called
- **THEN** the response SHALL be 200 with JSON containing `nodes` (array of entity objects with position hints) and `sets` (array of hyperedge objects with member node IDs), formatted for D3 rendering

#### Scenario: Filtered visualization
- **WHEN** `GET /api/hypergraph/visualization/euler?max_edges=50` is called
- **THEN** only the top 50 FactUnits by confidence SHALL be included to keep the visualization readable

### Requirement: HIF export endpoint
The system SHALL expose a GET endpoint that exports the hypergraph in Hypergraph Interchange Format (HIF) for interoperability with other research tools.

#### Scenario: Full export
- **WHEN** `GET /api/hypergraph/export/hif` is called
- **THEN** the response SHALL be 200 with `Content-Type: application/json` and the body SHALL be a valid HIF JSON document containing all FactUnits and entities with their properties

#### Scenario: Filtered export
- **WHEN** `GET /api/hypergraph/export/hif?min_confidence=0.7` is called
- **THEN** only FactUnits with confidence >= 0.7 SHALL be included in the export

### Requirement: Query parameter filtering across all endpoints
All analytics endpoints SHALL support optional query parameters for filtering the underlying hypergraph before analysis.

#### Scenario: Confidence filter
- **WHEN** any endpoint is called with `?min_confidence=0.8`
- **THEN** the analytics SHALL only consider FactUnits with `aggregate_confidence >= 0.8`

#### Scenario: Layer filter
- **WHEN** any endpoint is called with `?layer=SEMANTIC`
- **THEN** the analytics SHALL only consider entities and FactUnits in the SEMANTIC DIKW layer

#### Scenario: Document filter
- **WHEN** any endpoint is called with `?document_id=doc_001`
- **THEN** the analytics SHALL only consider FactUnits sourced from that document
