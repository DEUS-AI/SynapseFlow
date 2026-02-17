## ADDED Requirements

### Requirement: Automated TODO/FIXME/HACK/XXX scan
The audit SHALL scan all files under `src/` for TODO, FIXME, HACK, and XXX markers using case-insensitive pattern matching. Each finding SHALL include file path, line number, marker type, and the full comment text.

#### Scenario: TODO marker is captured
- **WHEN** a file contains `# TODO: implement text-to-Cypher`
- **THEN** the audit SHALL record the file path, line number, marker type `TODO`, and the comment text

#### Scenario: Multiline comments are captured
- **WHEN** a TODO comment spans multiple lines with continuation
- **THEN** the audit SHALL capture the full comment text including continuation lines

#### Scenario: Third-party code is excluded
- **WHEN** scanning for markers
- **THEN** files under `.venv/`, `node_modules/`, `__pycache__/`, and generated files SHALL be excluded

### Requirement: Feature classification taxonomy
Each incomplete feature SHALL be classified into one of the following categories: `incomplete-feature` (started but not finished), `technical-debt` (working but needs improvement), `known-bug` (incorrect behavior), `missing-test` (no test coverage for existing code), `placeholder` (stub or mock implementation).

#### Scenario: Mock text-to-Cypher is classified as placeholder
- **WHEN** the audit finds the text-to-Cypher heuristic-based mock in `kg_router.py`
- **THEN** it SHALL be classified as `placeholder`

#### Scenario: FalkorDB async wrapper is classified as technical-debt
- **WHEN** the audit finds the `run_in_executor()` pattern in `falkor_backend.py`
- **THEN** it SHALL be classified as `technical-debt`

### Requirement: Dependency chain mapping
The audit SHALL identify dependencies between incomplete features — features that must be completed before other features can proceed. The dependency chain SHALL be represented as a directed acyclic graph (list of edges: feature A blocks feature B).

#### Scenario: Crystallization depends on relationship handling
- **WHEN** the audit maps dependencies for relationship crystallization
- **THEN** it SHALL identify that relationship crystallization is blocked until relationship handling in the crystallization service is implemented

#### Scenario: Independent features have no blockers
- **WHEN** a feature has no upstream dependencies on other incomplete features
- **THEN** it SHALL be marked as independently implementable

### Requirement: Effort estimation with T-shirt sizing
Each incomplete feature SHALL receive a T-shirt size effort estimate: S (single file change, ~1-2 hours), M (multi-file same-service, ~half day), L (cross-service change, ~1-2 days), XL (architectural change, ~3-5 days).

#### Scenario: Simple TODO gets size S
- **WHEN** a TODO requires adding a single missing field to a model
- **THEN** it SHALL be estimated as size S

#### Scenario: Relationship crystallization gets size L or XL
- **WHEN** the relationship crystallization feature is estimated
- **THEN** it SHALL be estimated as size L or XL due to cross-service impact (crystallization service + Neo4j backend + API)

### Requirement: Feature inventory organized by system area
The inventory SHALL group features by system area: `agents` (DataArchitect, DataEngineer, KnowledgeManager, MedicalAssistant), `services` (entity resolution, crystallization, remediation, layer transition), `api` (routers, endpoints, metrics), `infrastructure` (backends, event bus, memory), `domain` (models, ontology, validation).

#### Scenario: Agent-related TODOs are grouped
- **WHEN** the inventory is generated
- **THEN** all TODOs from `src/application/agents/` SHALL appear under the `agents` area

#### Scenario: Cross-area features are tagged
- **WHEN** a feature spans multiple system areas (e.g., crystallization touches services + infrastructure + api)
- **THEN** it SHALL appear under its primary area with cross-references to other affected areas

### Requirement: Priority ranking of incomplete features
The audit SHALL rank each feature using the priority tiers: P0 (critical — blocking production use or data integrity risk), P1 (high — significant functional gap, next sprint), P2 (medium — improvement, planned), P3 (low — nice-to-have, backlog). Ranking criteria SHALL consider: data integrity impact, user-facing impact, dependency chain position (features that unblock many others rank higher), and effort-to-value ratio.

#### Scenario: Data integrity issue is P0
- **WHEN** an incomplete feature risks data corruption or loss (e.g., validation engine missing graph queries)
- **THEN** it SHALL be ranked P0

#### Scenario: Nice-to-have improvement is P3
- **WHEN** a TODO describes an optimization with no functional impact
- **THEN** it SHALL be ranked P3
