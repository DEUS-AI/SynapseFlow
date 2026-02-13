## ADDED Requirements

### Requirement: Group ID sanitization
All `group_id` values passed to Graphiti/FalkorDB SHALL contain only alphanumeric characters, dashes, and underscores. A centralised `_sanitize_group_id(raw_id: str) -> str` method SHALL replace colons with dashes.

#### Scenario: Patient ID with colon is sanitized
- **WHEN** a patient_id `patient:demo` is used as a group_id
- **THEN** the value passed to Graphiti is `patient-demo`

#### Scenario: Composite patient+session ID is sanitized
- **WHEN** a group_id is constructed from patient_id `patient:demo` and session_id `session:19e7d4d9-d33b-48c1-b351-97511b67bc12`
- **THEN** the value passed to Graphiti is `patient-demo--session-19e7d4d9-d33b-48c1-b351-97511b67bc12`

#### Scenario: ID without colons passes through unchanged
- **WHEN** an ID `dda_customer_analytics` is passed through sanitization
- **THEN** the value is unchanged: `dda_customer_analytics`

### Requirement: Composite group ID construction with double-dash separator
Composite group IDs (patient + session) SHALL be constructed as `f"{sanitize(patient_id)}--{sanitize(session_id)}"`, using `--` as the separator between the patient and session components.

#### Scenario: store_turn_episode uses sanitized composite group ID
- **WHEN** `store_turn_episode()` is called with patient_id `patient:demo` and session_id `session:abc-123`
- **THEN** the `group_id` passed to `graphiti.add_episode()` is `patient-demo--session-abc-123`

#### Scenario: search_episodes uses sanitized composite group ID
- **WHEN** `search_episodes()` is called with patient_id `patient:demo` and session_id `session:abc-123`
- **THEN** the `group_ids` list passed to `search()` includes `patient-demo--session-abc-123`

#### Scenario: retrieve_recent_episodes uses sanitized composite group ID
- **WHEN** `retrieve_recent_episodes()` is called with patient_id `patient:demo` and session_id `session:abc-123`
- **THEN** the `group_ids` list passed to `graphiti.retrieve_episodes()` includes `patient-demo--session-abc-123`

### Requirement: Patient-only group ID sanitization
When a patient_id is used alone as a group_id (for session-level episodes or broad searches), it SHALL also be sanitized.

#### Scenario: Patient-only group ID in retrieve_recent_episodes
- **WHEN** `retrieve_recent_episodes()` is called with patient_id `patient:demo` and no session_id
- **THEN** the `group_ids` list includes `patient-demo` (not `patient:demo`)

#### Scenario: Patient-only group ID in search_episodes
- **WHEN** `search_episodes()` is called with patient_id `patient:demo` and no session_id
- **THEN** the `group_ids` list includes `patient-demo`

### Requirement: Group ID parsing in _convert_episode
The `_convert_episode()` method SHALL parse stored group IDs by splitting on `--` to extract the session component. If no `--` separator is present, session_id SHALL be None.

#### Scenario: Composite group ID is parsed to extract session_id
- **WHEN** an episode has `group_id = "patient-demo--session-abc-123"`
- **THEN** `_convert_episode()` extracts session_id as `session-abc-123`

#### Scenario: Patient-only group ID has no session_id
- **WHEN** an episode has `group_id = "patient-demo"`
- **THEN** `_convert_episode()` sets session_id to `None`

#### Scenario: Legacy colon-separated group ID is handled gracefully
- **WHEN** an episode has `group_id = "patient:demo:session:abc"` (old format)
- **THEN** `_convert_episode()` does not crash and sets session_id to `None` (no `--` separator found)
