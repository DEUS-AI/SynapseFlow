## ADDED Requirements

### Requirement: API observability gap assessment
The audit SHALL evaluate the API layer for: missing request/response logging, absence of query execution counters, missing response time tracking, and lack of structured error reporting. Each gap SHALL be documented with its impact on production debugging.

#### Scenario: Missing query counter is identified
- **WHEN** the API does not track the number of KG queries executed per endpoint
- **THEN** the audit SHALL flag this as an observability gap with impact description

#### Scenario: Existing logging is documented
- **WHEN** an API endpoint has structured logging for requests and responses
- **THEN** the audit SHALL document it as covered

### Requirement: Health check endpoint assessment
The audit SHALL evaluate whether health check endpoints exist for: Neo4j connectivity, Graphiti/FalkorDB connectivity, Redis connectivity, Qdrant connectivity, RabbitMQ connectivity. Missing health checks SHALL be flagged with the service name and connection parameters.

#### Scenario: Missing Neo4j health check is flagged
- **WHEN** no endpoint verifies Neo4j connectivity
- **THEN** the audit SHALL flag "Neo4j health check" as missing

#### Scenario: Existing health check is documented
- **WHEN** a `/health` endpoint exists that checks Redis connectivity
- **THEN** the audit SHALL document it as covered with the endpoint path

### Requirement: Error handling pattern review
The audit SHALL review error handling patterns across all API routers and services for: bare exception catches (catch-all without specific handling), missing error response codes (generic 500 instead of specific 4xx/5xx), swallowed exceptions (caught but not logged or re-raised), and missing retry logic for transient failures (database connections, external API calls).

#### Scenario: Bare exception catch is flagged
- **WHEN** a service catches `Exception` without specific handling or re-raising
- **THEN** the audit SHALL flag the file, line, and the exception pattern

#### Scenario: Missing retry logic for transient failure
- **WHEN** a database connection call has no retry/backoff logic
- **THEN** the audit SHALL flag it with the service name and connection type

### Requirement: Configuration and secrets management review
The audit SHALL verify that: no hardcoded secrets exist in source code (API keys, passwords, tokens), environment variables are properly validated on startup (fail fast if missing), default values for configuration are documented, and sensitive configuration is not logged.

#### Scenario: Hardcoded secret is detected
- **WHEN** a file contains a hardcoded API key or password string
- **THEN** the audit SHALL flag it as a critical security finding

#### Scenario: Missing env var validation is flagged
- **WHEN** an environment variable is read with a silent fallback to empty string
- **THEN** the audit SHALL flag it as a configuration risk

### Requirement: Docker deployment readiness check
The audit SHALL verify docker-compose configurations for: service dependency ordering (`depends_on`), volume persistence for stateful services (Neo4j, Redis), resource limits (memory, CPU), restart policies, and network isolation.

#### Scenario: Missing volume persistence is flagged
- **WHEN** a stateful service (Neo4j) does not have a persistent volume configured
- **THEN** the audit SHALL flag data loss risk on container restart

#### Scenario: Missing restart policy is flagged
- **WHEN** a service does not have a restart policy configured
- **THEN** the audit SHALL flag it with the service name

### Requirement: Operational readiness summary with maturity rating
The audit SHALL produce a summary rating operational readiness across 5 dimensions: observability (logging, metrics, tracing), reliability (health checks, error handling, retries), security (secrets, CORS, auth), deployment (Docker, configuration, persistence), and scalability (connection pooling, async patterns, resource limits). Each dimension SHALL receive a maturity rating: not-started, basic, intermediate, or production-ready.

#### Scenario: Maturity matrix is generated
- **WHEN** all operational readiness checks are complete
- **THEN** the audit SHALL produce a matrix with each dimension and its maturity rating

#### Scenario: Observability rated as basic
- **WHEN** the API has basic logging but no metrics or tracing
- **THEN** observability SHALL be rated as "basic"
