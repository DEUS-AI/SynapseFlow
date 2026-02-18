## ADDED Requirements

### Requirement: Admin agents endpoint returns real agent data
The `GET /api/admin/agents` endpoint SHALL call the agent discovery service to return real agent registration data instead of hardcoded mock data. The endpoint SHALL return a list of agent objects each containing: `agent_id`, `name`, `status` (active/inactive/degraded/starting), `capabilities` (list of strings), `last_heartbeat` (ISO-8601 timestamp or null), `heartbeat_seconds_ago` (computed integer or null), `tier` (core/optional), `description`, and `version`.

#### Scenario: Agents are registered and active
- **WHEN** the agent discovery service has registered agents
- **THEN** the endpoint returns a JSON array with one object per agent
- **THEN** each object includes `agent_id`, `name`, `status`, `capabilities`, `last_heartbeat`, `heartbeat_seconds_ago`, `tier`, `description`, and `version`
- **THEN** `heartbeat_seconds_ago` is computed as the difference between now and `last_heartbeat`

#### Scenario: No agents registered
- **WHEN** the agent discovery service has no registered agents
- **THEN** the endpoint returns an empty JSON array `[]`

#### Scenario: Agent discovery service unavailable
- **WHEN** the agent discovery service raises an exception
- **THEN** the endpoint returns HTTP 500 with an error detail message

### Requirement: Admin agents endpoint supports status filtering
The `GET /api/admin/agents` endpoint SHALL accept an optional `status` query parameter to filter agents by status (active, inactive, degraded, starting).

#### Scenario: Filter by active status
- **WHEN** the request includes `?status=active`
- **THEN** only agents with status "active" are returned

#### Scenario: No filter provided
- **WHEN** the request has no `status` query parameter
- **THEN** all agents are returned regardless of status

### Requirement: Mock data removed
The `GET /api/admin/agents` endpoint SHALL NOT return hardcoded mock data. The static list of 4 agents with fixed uptime and task counts SHALL be removed entirely.

#### Scenario: Endpoint returns dynamic data
- **WHEN** the endpoint is called at two different times with agents changing status between calls
- **THEN** the responses reflect the actual current state of agent registrations, not identical static data
