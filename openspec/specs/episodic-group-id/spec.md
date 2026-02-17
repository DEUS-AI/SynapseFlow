### Requirement: graphiti-core minimum version for FalkorDB fulltext search compatibility
The project SHALL depend on `graphiti-core[falkordb] >=0.27.1,<0.28` to ensure FalkorDB fulltext search queries use correct RediSearch syntax for `group_id` field filters.

#### Scenario: Episode search with group_ids succeeds on FalkorDB
- **WHEN** `search_episodes()` is called with patient_id `patient:demo` and session_id `session:abc-123`
- **THEN** the FalkorDB fulltext search query executes without `RediSearch: Syntax error` errors and returns matching episodes

#### Scenario: Episode search with patient-only group_id succeeds on FalkorDB
- **WHEN** `search_episodes()` is called with patient_id `patient:demo` and no session_id
- **THEN** the FalkorDB fulltext search query executes without errors and returns matching episodes filtered by the patient's group_id

### Requirement: Version pin prevents regression
The `pyproject.toml` dependency for graphiti-core SHALL be pinned to `>=0.27.1,<0.28` to allow patch updates while preventing major version jumps.

#### Scenario: Dependency is correctly pinned
- **WHEN** the project's `pyproject.toml` is inspected
- **THEN** the graphiti-core dependency reads `graphiti-core[falkordb] >=0.27.1,<0.28`

#### Scenario: Patch update within range is accepted
- **WHEN** graphiti-core publishes version 0.27.2
- **THEN** `uv sync` MAY resolve to 0.27.2 without manual intervention
