## ADDED Requirements

### Requirement: Load hypergraph from Neo4j
The system SHALL load FactUnit nodes and PARTICIPATES_IN edges from Neo4j and construct an in-memory HyperNetX `Hypergraph` object where each FactUnit ID is a hyperedge and each participating entity ID is a node.

#### Scenario: Successful hypergraph construction
- **WHEN** the adapter is asked to load the hypergraph
- **THEN** it SHALL query Neo4j for all FactUnit nodes and their PARTICIPATES_IN relationships, construct an `hnx.Hypergraph` with edges keyed by FactUnit ID and node sets from participant entity IDs, and return the Hypergraph object

#### Scenario: Empty graph
- **WHEN** no FactUnit nodes exist in Neo4j
- **THEN** the adapter SHALL return an empty `hnx.Hypergraph` with zero edges and zero nodes

### Requirement: Attach entity and fact properties
The system SHALL attach metadata properties to hypergraph nodes and edges so that downstream analytics can filter and weight by these properties.

#### Scenario: Properties on edges
- **WHEN** a hypergraph is constructed
- **THEN** each hyperedge SHALL carry properties: `fact_type`, `aggregate_confidence`, `validated`, `validation_count`, `extraction_method`, and `source_document_id` from the corresponding FactUnit node

#### Scenario: Properties on nodes
- **WHEN** a hypergraph is constructed
- **THEN** each node SHALL carry properties: `entity_type` (from Neo4j labels), `name`, `layer` (DIKW layer), and `confidence` from the corresponding entity node

### Requirement: Filter hypergraph by criteria
The system SHALL support filtering the loaded hypergraph by confidence threshold, DIKW layer, document ID, and fact type, so that analytics can target specific subgraphs.

#### Scenario: Filter by confidence threshold
- **WHEN** the adapter is called with `min_confidence=0.8`
- **THEN** only FactUnits with `aggregate_confidence >= 0.8` SHALL be included as hyperedges

#### Scenario: Filter by DIKW layer
- **WHEN** the adapter is called with `layer="SEMANTIC"`
- **THEN** only entities in the SEMANTIC layer SHALL be included as nodes, and only FactUnits where all participants are in SEMANTIC layer SHALL be included as edges

#### Scenario: Filter by document
- **WHEN** the adapter is called with `document_id="doc_001"`
- **THEN** only FactUnits with `source_document_id="doc_001"` SHALL be included

#### Scenario: Combined filters
- **WHEN** multiple filters are provided
- **THEN** they SHALL be applied conjunctively (AND logic)

### Requirement: TTL cache for loaded hypergraph
The system SHALL cache the loaded hypergraph with a 5-minute TTL to avoid redundant Neo4j queries on consecutive analytics calls.

#### Scenario: Cache hit within TTL
- **WHEN** a hypergraph is requested with the same filter parameters within 5 minutes of a previous load
- **THEN** the cached hypergraph SHALL be returned without querying Neo4j

#### Scenario: Cache miss after TTL expires
- **WHEN** more than 5 minutes have elapsed since the last load
- **THEN** the adapter SHALL query Neo4j and construct a fresh hypergraph

#### Scenario: Explicit cache invalidation
- **WHEN** `invalidate_cache()` is called
- **THEN** all cached hypergraphs SHALL be discarded and the next request SHALL reload from Neo4j

### Requirement: Graceful degradation when HyperNetX unavailable
The system SHALL handle the case where the `hypernetx` package is not installed without crashing.

#### Scenario: HyperNetX not installed
- **WHEN** the adapter is initialized but `hypernetx` cannot be imported
- **THEN** `is_available()` SHALL return `False` and all load methods SHALL raise an informative error indicating HyperNetX is not installed

#### Scenario: HyperNetX installed
- **WHEN** `hypernetx` is importable
- **THEN** `is_available()` SHALL return `True` and all methods SHALL function normally
