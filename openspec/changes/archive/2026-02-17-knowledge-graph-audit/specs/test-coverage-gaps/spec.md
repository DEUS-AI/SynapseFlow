## ADDED Requirements

### Requirement: Quantitative test coverage report generation
The audit SHALL execute `pytest --cov=src --cov-report=json` to produce a machine-readable coverage report. The report SHALL capture line coverage percentages for every module under `src/`.

#### Scenario: Coverage report is generated
- **WHEN** the test coverage analysis runs
- **THEN** it SHALL produce a JSON coverage report with per-module line coverage percentages

#### Scenario: Modules with zero coverage are identified
- **WHEN** a module under `src/` has no test coverage
- **THEN** the report SHALL list it with 0% coverage

### Requirement: Critical KG operation test mapping
The audit SHALL map the following critical KG operations to their existing test files and identify gaps: layer transitions (PERCEPTION→SEMANTIC→REASONING→APPLICATION), entity resolution (all 5 strategies: exact, fuzzy, embedding, graph structure, hybrid), crystallization pipeline (episodic→Neo4j), remediation pipeline (dry-run, execute, rollback), agent escalation (DataArchitect→KnowledgeManager), ontology mapping (type resolution, alias handling, unknown type flagging).

#### Scenario: Layer transition tests are mapped
- **WHEN** the audit maps layer transition test coverage
- **THEN** it SHALL list which transition paths (e.g., PERCEPTION→SEMANTIC) have test coverage and which do not

#### Scenario: Entity resolution strategy gap is found
- **WHEN** the embedding similarity strategy has no dedicated test
- **THEN** the audit SHALL flag `EMBEDDING_SIMILARITY` as an untested entity resolution strategy

#### Scenario: All strategies are covered
- **WHEN** every entity resolution strategy has at least one test
- **THEN** the audit SHALL report entity resolution as fully covered

### Requirement: Error path coverage analysis
The audit SHALL identify critical error paths in KG operations (connection failures, invalid data, concurrent modification, timeout handling) and check whether tests exist for these scenarios. Error paths without test coverage SHALL be flagged.

#### Scenario: Backend connection failure is untested
- **WHEN** no test simulates a Neo4j connection failure in the backend
- **THEN** the audit SHALL flag "Neo4j connection failure handling" as an untested error path

#### Scenario: Tested error path is documented
- **WHEN** a test exists that simulates invalid entity data being rejected
- **THEN** the audit SHALL document the test file and test function covering this path

### Requirement: Integration test gap identification
The audit SHALL identify end-to-end workflows that lack integration tests. Critical workflows include: document ingestion → entity extraction → KG storage → query, patient conversation → episodic memory → crystallization → Neo4j, remediation dry-run → execute → rollback cycle, agent message → escalation → KnowledgeManager processing.

#### Scenario: Crystallization integration test is missing
- **WHEN** no integration test covers the full episodic→crystallization→Neo4j pipeline
- **THEN** the audit SHALL flag this as a critical integration test gap

#### Scenario: Existing integration test is documented
- **WHEN** an integration test covers document ingestion end-to-end
- **THEN** the audit SHALL reference the test file and describe what it covers

### Requirement: Test coverage gap summary with risk assessment
The audit SHALL produce a summary ranking test gaps by risk: critical (untested data mutation paths), high (untested error handling in production code), medium (untested happy paths for secondary features), low (untested utility functions or logging).

#### Scenario: Summary prioritizes data mutation gaps
- **WHEN** the summary is generated
- **THEN** untested data mutation paths (entity creation, deletion, layer promotion) SHALL be ranked as critical risk

#### Scenario: Utility function gaps are low risk
- **WHEN** a helper function for string formatting has no tests
- **THEN** the summary SHALL rank it as low risk
