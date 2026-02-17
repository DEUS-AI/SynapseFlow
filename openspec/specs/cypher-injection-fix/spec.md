## ADDED Requirements

### Requirement: Relationship type input validation
All Neo4j backend methods that interpolate relationship types into Cypher queries SHALL validate the type against an allowlist pattern (`^[A-Za-z_][A-Za-z0-9_]*$`) before query construction. Inputs that fail validation SHALL raise a `ValueError` with a descriptive message.

#### Scenario: Valid relationship type is accepted
- **WHEN** `delete_relationship()` is called with `relationship_type = "ASSOCIATED_WITH"`
- **THEN** the query SHALL execute normally

#### Scenario: Injection attempt is rejected
- **WHEN** `delete_relationship()` is called with `relationship_type = "ASSOCIATED_WITH`]->(t) DELETE t//"`
- **THEN** a `ValueError` SHALL be raised before any Cypher query is constructed

#### Scenario: Empty relationship type is rejected
- **WHEN** `delete_relationship()` is called with `relationship_type = ""`
- **THEN** a `ValueError` SHALL be raised

#### Scenario: Backtick in type is rejected
- **WHEN** any backend method receives a relationship type containing backtick characters
- **THEN** a `ValueError` SHALL be raised

### Requirement: Centralized Cypher sanitization utility
A shared utility function `validate_cypher_identifier(value: str, label: str) -> str` SHALL be provided in the infrastructure layer. All backend methods that interpolate identifiers into Cypher queries SHALL use this function. The function SHALL return the validated string or raise `ValueError`.

#### Scenario: Utility is used in delete_relationship
- **WHEN** `delete_relationship()` constructs a Cypher query with a relationship type
- **THEN** it SHALL call `validate_cypher_identifier(relationship_type, "relationship_type")` before interpolation

#### Scenario: Utility rejects SQL/Cypher keywords
- **WHEN** `validate_cypher_identifier("DROP", "type")` is called
- **THEN** it SHALL raise `ValueError` (reserved Cypher keyword)

### Requirement: All Cypher interpolation points are audited
The Neo4j backend SHALL NOT contain any string interpolation (`%`, `.format()`, or f-string) of user-controllable values in Cypher queries. All dynamic values SHALL use Neo4j parameterized queries (`$param`) except for relationship types and labels, which SHALL use the validation utility.

#### Scenario: No unprotected interpolation exists
- **WHEN** the Neo4j backend source code is scanned for `%s`, `.format(`, and f-string patterns in Cypher query strings
- **THEN** every occurrence SHALL either use `$param` parameterization or be preceded by a `validate_cypher_identifier()` call
