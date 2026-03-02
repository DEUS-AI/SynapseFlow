## MODIFIED Requirements

### Requirement: Health check endpoint assessment
The audit SHALL evaluate whether health check endpoints exist for: Neo4j connectivity, Graphiti/FalkorDB connectivity, Redis connectivity, Qdrant connectivity, RabbitMQ connectivity. Missing health checks SHALL be flagged with the service name and connection parameters. Health checks SHALL be assessed both at the API level AND at each individual agent container level. Each agent container SHALL expose its own `/health` endpoint covering the specific dependencies it uses.

#### Scenario: Missing Neo4j health check is flagged
- **WHEN** no endpoint verifies Neo4j connectivity
- **THEN** the audit SHALL flag "Neo4j health check" as missing

#### Scenario: Existing health check is documented
- **WHEN** a `/health` endpoint exists that checks Redis connectivity
- **THEN** the audit SHALL document it as covered with the endpoint path

#### Scenario: Agent-level health check is assessed
- **WHEN** the KnowledgeManager container does not expose a `/health` endpoint
- **THEN** the audit SHALL flag "KnowledgeManager agent health check" as missing, separate from the API-level health check

#### Scenario: Agent health check covers agent-specific dependencies
- **WHEN** the MedicalAssistant container exposes `/health`
- **AND** the health check covers Neo4j and RabbitMQ but NOT Redis and Qdrant
- **THEN** the audit SHALL flag the missing dependency checks (Redis, Qdrant) since MedicalAssistant depends on PatientMemoryService which uses both

### Requirement: Docker deployment readiness check
The audit SHALL verify docker-compose configurations for: service dependency ordering (`depends_on`), volume persistence for stateful services (Neo4j, Redis), resource limits (memory, CPU), restart policies, and network isolation. The audit SHALL now also verify that ALL agent containers (DataArchitect, DataEngineer, KnowledgeManager, MedicalAssistant) are defined with correct dependency ordering, health checks, and per-agent environment configuration.

#### Scenario: Missing volume persistence is flagged
- **WHEN** a stateful service (Neo4j) does not have a persistent volume configured
- **THEN** the audit SHALL flag data loss risk on container restart

#### Scenario: Missing restart policy is flagged
- **WHEN** a service does not have a restart policy configured
- **THEN** the audit SHALL flag it with the service name

#### Scenario: Missing agent container is flagged
- **WHEN** KnowledgeManager or MedicalAssistant does not have a docker-compose service entry
- **THEN** the audit SHALL flag the missing agent container as a deployment gap

#### Scenario: Agent container without health check dependency is flagged
- **WHEN** an agent container's `depends_on` does not use `condition: service_healthy` for its infrastructure dependencies
- **THEN** the audit SHALL flag the missing health check condition with the service names
