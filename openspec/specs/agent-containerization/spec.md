## ADDED Requirements

### Requirement: Every agent SHALL have an independent container definition
Each agent (DataArchitect, DataEngineer, KnowledgeManager, MedicalAssistant) SHALL have a dedicated service entry in `docker-compose.services.yml` with its own Dockerfile build, port mapping, environment variables, and dependency declarations. The Echo agent is excluded (test-only).

#### Scenario: KnowledgeManager container is defined
- **WHEN** `docker-compose.services.yml` is parsed
- **THEN** a `knowledge_manager` service entry SHALL exist with a unique port (8003), build context pointing to `Dockerfile.agent`, and command `python -m src.interfaces.cli run-agent --role knowledge_manager`

#### Scenario: MedicalAssistant container is defined
- **WHEN** `docker-compose.services.yml` is parsed
- **THEN** a `medical_assistant` service entry SHALL exist with a unique port (8004), build context pointing to `Dockerfile.agent`, and command `python -m src.interfaces.cli run-agent --role medical_assistant`

#### Scenario: MedicalAssistant depends on memory services
- **WHEN** the `medical_assistant` service starts
- **THEN** it SHALL declare `depends_on` for Redis and Qdrant (from `docker-compose.memory.yml`) in addition to Neo4j and RabbitMQ

### Requirement: Each agent container SHALL own its infrastructure connections
Agent containers SHALL NOT share database connections, event bus instances, or any singleton objects across process boundaries. Each container SHALL initialize its own Neo4j driver, RabbitMQ connection, and any other infrastructure client from its own environment variables.

#### Scenario: DataArchitect and KnowledgeManager use separate Neo4j connections
- **WHEN** both `data_architect` and `knowledge_manager` containers are running
- **THEN** each SHALL have its own Neo4j async driver instance, initialized from its own `NEO4J_URI` environment variable

#### Scenario: Agent container starts with missing required env var
- **WHEN** an agent container starts without `NEO4J_URI` set
- **THEN** the process SHALL fail fast with a clear error message within 5 seconds, not silently fall back to defaults

### Requirement: Agent containers SHALL expose a health endpoint
Each agent container SHALL expose an HTTP health endpoint at `GET /health` on its assigned port. The endpoint SHALL return the agent's health status including connectivity to its dependencies.

#### Scenario: Healthy agent returns 200
- **WHEN** `GET /health` is called on the KnowledgeManager container (port 8003)
- **AND** Neo4j and RabbitMQ are reachable
- **THEN** the response SHALL be HTTP 200 with JSON body containing `{"status": "healthy", "agent": "knowledge_manager", "dependencies": {"neo4j": "connected", "rabbitmq": "connected"}}`

#### Scenario: Agent with degraded dependency returns 503
- **WHEN** `GET /health` is called on a container
- **AND** Neo4j is unreachable
- **THEN** the response SHALL be HTTP 503 with JSON body containing `{"status": "unhealthy", "agent": "<role>", "dependencies": {"neo4j": "disconnected"}}`

### Requirement: Docker-compose SHALL support selective agent startup
Operators SHALL be able to start individual agent containers without starting all agents. The `docker-compose.services.yml` SHALL not create circular dependencies between agent services.

#### Scenario: Start only DataArchitect
- **WHEN** `docker-compose -f docker-compose.services.yml up data_architect` is run
- **THEN** only infrastructure services (Neo4j, RabbitMQ, FalkorDB) and the `data_architect` container SHALL start

#### Scenario: No circular dependencies between agents
- **WHEN** `docker-compose.services.yml` is validated
- **THEN** no agent service SHALL have a `depends_on` referencing another agent service — agents depend only on infrastructure services

### Requirement: Agent Dockerfile SHALL support role-based startup
The `Dockerfile.agent` SHALL accept a `--role` argument that determines which agent to bootstrap. The entrypoint SHALL use `composition_root.py` to initialize only the required agent and its dependencies, not all agents.

#### Scenario: Role selects single agent bootstrap
- **WHEN** a container starts with `--role knowledge_manager`
- **THEN** only the KnowledgeManager agent, its event subscriptions, and its infrastructure connections SHALL be initialized — DataArchitect, DataEngineer, and MedicalAssistant SHALL NOT be created

#### Scenario: Invalid role fails fast
- **WHEN** a container starts with `--role invalid_role`
- **THEN** the process SHALL exit with code 1 and an error message listing valid roles
