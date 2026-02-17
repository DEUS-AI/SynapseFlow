## ADDED Requirements

### Requirement: Interface method coverage comparison
The audit SHALL compare all 4 backend implementations (Neo4jBackend, GraphitiBackend, FalkorBackend, InMemoryGraphBackend) against the `KnowledgeGraphBackend` abstract class to identify: methods that are abstract but not implemented, methods with inconsistent signatures (different parameter names/types), and extra methods not defined in the abstract interface.

#### Scenario: Missing abstract method is detected
- **WHEN** a backend class does not implement an abstract method from `KnowledgeGraphBackend`
- **THEN** the audit SHALL report the missing method, backend name, and the method signature expected

#### Scenario: Signature mismatch is detected
- **WHEN** a backend implements a method with different parameter names or types than the abstract definition
- **THEN** the audit SHALL report the mismatch with both the expected and actual signatures

#### Scenario: Fully compliant backend passes
- **WHEN** a backend implements all abstract methods with matching signatures
- **THEN** the audit SHALL report it as fully compliant

### Requirement: Serialization behavior comparison
The audit SHALL document how each backend handles complex property types (dict, list, Enum, None, datetime) during entity creation and retrieval. Differences in serialization behavior SHALL be flagged with severity (breaking vs cosmetic).

#### Scenario: Dict property serialization differs
- **WHEN** Neo4j stores a dict property as a native map and Graphiti serializes it as a JSON string
- **THEN** the audit SHALL flag this as a serialization inconsistency with severity "breaking"

#### Scenario: Enum property handling differs
- **WHEN** one backend stores Enum values as strings and another stores them as raw values
- **THEN** the audit SHALL flag this with severity and the specific backends affected

### Requirement: Cypher abstraction leak analysis
The audit SHALL identify places where Cypher query syntax is exposed through the `KnowledgeGraphBackend` interface (e.g., the `query()` method accepting raw Cypher strings). Each leak point SHALL be documented with the method name, backend, and whether it makes the interface non-backend-agnostic.

#### Scenario: Raw Cypher method is identified
- **WHEN** the backend interface exposes a `query()` method that accepts a raw Cypher string
- **THEN** the audit SHALL flag it as a Cypher abstraction leak with the method signature

#### Scenario: Backend-specific operations are cataloged
- **WHEN** a backend implements operations that only work with its specific database technology
- **THEN** the audit SHALL list those operations and note which backends support them

### Requirement: FalkorDB async wrapper risk assessment
The audit SHALL analyze the FalkorBackend's `run_in_executor()` async wrapping pattern for: thread pool exhaustion risk under concurrent requests, absence of max_workers configuration, and potential event loop blocking. The assessment SHALL include a severity rating and recommended mitigation.

#### Scenario: Thread pool exhaustion risk is assessed
- **WHEN** the FalkorBackend uses `loop.run_in_executor()` without configuring max_workers
- **THEN** the audit SHALL flag this as a concurrency risk with severity "high" and document the default thread pool size

#### Scenario: Blocking call patterns are identified
- **WHEN** the FalkorBackend wraps synchronous FalkorDB calls in the executor
- **THEN** the audit SHALL list each blocking call, its expected duration, and the impact on the event loop

### Requirement: Label handling consistency check
The audit SHALL compare how each backend handles Neo4j labels during entity creation, update, and query. Backends that do not support labels (e.g., Graphiti) SHALL be documented with the impact on cross-backend entity resolution.

#### Scenario: Label support gap is identified
- **WHEN** Neo4jBackend supports labels but GraphitiBackend does not
- **THEN** the audit SHALL document this gap and its impact on entity queries that filter by label

### Requirement: Backend consistency summary with severity matrix
The audit SHALL produce a severity matrix rating each finding as critical (data loss/corruption risk), high (functional inconsistency), medium (developer friction), or low (cosmetic). The matrix SHALL be organized by backend pair (Neo4j vs Graphiti, Neo4j vs Falkor, etc.).

#### Scenario: Severity matrix is generated
- **WHEN** all backend consistency checks are complete
- **THEN** the audit SHALL produce a matrix with finding, affected backends, severity, and recommended action
