## ADDED Requirements

### Requirement: Compute entity centrality
The system SHALL compute s-centrality scores for entities in the hypergraph, identifying hub entities that participate in the most interconnected facts.

#### Scenario: Centrality with default s=1
- **WHEN** `compute_entity_centrality()` is called without parameters
- **THEN** the system SHALL return a ranked list of entities with their s-betweenness centrality scores at s=1, sorted descending by score

#### Scenario: Centrality with custom s value
- **WHEN** `compute_entity_centrality(s=2)` is called
- **THEN** the system SHALL compute centrality considering only connections where entities share at least 2 FactUnits

#### Scenario: Result format
- **WHEN** centrality is computed
- **THEN** each result SHALL include: `entity_id`, `entity_name`, `entity_type`, `centrality_score`, and `participating_fact_count`

### Requirement: Detect knowledge communities
The system SHALL detect communities of related entities using hypergraph community detection, revealing coherent topic clusters in the knowledge graph.

#### Scenario: Community detection
- **WHEN** `detect_knowledge_communities()` is called
- **THEN** the system SHALL apply Kumar's algorithm for hypergraph modularity and return a list of communities, each containing its member entity IDs, a modularity score, and the dominant entity types within the community

#### Scenario: Community summary
- **WHEN** communities are detected
- **THEN** the result SHALL include: total number of communities, overall modularity score, and for each community: `community_id`, `member_entity_ids`, `member_count`, `dominant_types`, and `modularity_contribution`

### Requirement: Analyze connectivity at varying rigor
The system SHALL compute s-connected components to find knowledge islands at different strictness levels.

#### Scenario: Connectivity analysis
- **WHEN** `analyze_connectivity(s_values=[1, 2, 3])` is called
- **THEN** for each s value, the system SHALL return the number of connected components and the sizes of each component

#### Scenario: Identifying isolated clusters
- **WHEN** s-connected components are computed at s=1
- **THEN** any component with fewer than 3 entities SHALL be flagged as a potential knowledge island

### Requirement: Compute entity distances
The system SHALL compute s-distances between entities using s-walks, providing a mathematically rigorous measure of how closely related two entities are through shared facts.

#### Scenario: Distance between two entities
- **WHEN** `compute_entity_distances(entity_id="metformin", s=1)` is called
- **THEN** the system SHALL return distances from the specified entity to all reachable entities, sorted ascending by distance

#### Scenario: Unreachable entities
- **WHEN** two entities are not s-connected at the given s value
- **THEN** the distance SHALL be reported as infinity with `reachable=False`

### Requirement: Topological summary
The system SHALL provide a topological summary of the hypergraph including node count, edge count, density, diameter, and degree distribution.

#### Scenario: Summary computation
- **WHEN** `get_topological_summary()` is called
- **THEN** the result SHALL include: `node_count`, `edge_count`, `density`, `avg_edge_size` (average number of entities per FactUnit), `max_edge_size`, `avg_node_degree` (average number of FactUnits per entity), and `diameter` (longest shortest s-path at s=1)

### Requirement: Compute hypergraph diff
The system SHALL compute the set difference between two hypergraph snapshots to track knowledge changes between crystallization batches.

#### Scenario: Diff between snapshots
- **WHEN** `compute_hypergraph_diff(before_snapshot, after_snapshot)` is called
- **THEN** the result SHALL include: `added_edges` (new FactUnits), `removed_edges` (deleted FactUnits), `added_nodes` (new entities), `removed_nodes` (entities no longer participating), and `modified_edges` (FactUnits with changed confidence or participant sets)

### Requirement: Graceful handling of empty or small graphs
The system SHALL handle edge cases where the hypergraph has insufficient data for meaningful analytics.

#### Scenario: Empty hypergraph
- **WHEN** any analytics method is called on an empty hypergraph (0 edges)
- **THEN** the system SHALL return a valid but empty result with appropriate zero values, not raise an error

#### Scenario: Single-edge hypergraph
- **WHEN** the hypergraph contains only 1 FactUnit
- **THEN** centrality SHALL return uniform scores, community detection SHALL return a single community, and connectivity SHALL return 1 component
