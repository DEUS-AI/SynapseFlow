## ADDED Requirements

### Requirement: API layer SHALL delegate to agent services instead of instantiating agents in-process
The FastAPI application SHALL NOT create agent instances directly in `dependencies.py`. In distributed mode, the API SHALL delegate agent operations to remote agent services via the `DistributedCommandBus` or A2A HTTP calls. In local mode, the API SHALL continue creating agents in-process for development convenience.

#### Scenario: DDA upload delegates to remote DataArchitect in distributed mode
- **WHEN** `POST /api/dda/upload` is called
- **AND** the system is running in distributed mode
- **THEN** the API SHALL dispatch a `ModelingCommand` via the `DistributedCommandBus` to the DataArchitect service, NOT create a `DataArchitectAgent` instance in the FastAPI process

#### Scenario: DDA upload creates agent in-process in local mode
- **WHEN** `POST /api/dda/upload` is called
- **AND** the system is running in local mode
- **THEN** the API SHALL create a `DataArchitectAgent` in-process as it does today — no behavioral change for local development

#### Scenario: dependencies.py has no agent singletons in distributed mode
- **WHEN** the API starts in distributed mode
- **THEN** `_data_architect_agent` and any future agent globals in `dependencies.py` SHALL NOT be initialized — agent operations go through the gateway

### Requirement: AgentGateway service SHALL abstract local vs remote agent invocation
An `AgentGateway` service SHALL exist that provides a unified interface for invoking agent operations. The gateway SHALL determine whether to call agents in-process or route to remote services based on the deployment mode configuration.

#### Scenario: Gateway routes to local agent
- **WHEN** `AgentGateway.invoke("data_architect", command)` is called in local mode
- **THEN** the gateway SHALL create the agent in-process via `composition_root` and execute the command directly

#### Scenario: Gateway routes to remote agent
- **WHEN** `AgentGateway.invoke("data_architect", command)` is called in distributed mode
- **THEN** the gateway SHALL dispatch the command via the `DistributedCommandBus` without creating any local agent instance

#### Scenario: Gateway discovers available agents
- **WHEN** the gateway is initialized in distributed mode
- **THEN** it SHALL use the agent configuration (`agents.distributed.yaml`) to know which agents exist and their service URLs

### Requirement: API routes SHALL use AgentGateway for all agent operations
All API routes that currently call agent methods directly SHALL be refactored to use `AgentGateway`. No API route SHALL import or instantiate agent classes directly.

#### Scenario: KG update route uses gateway
- **WHEN** a knowledge graph update API endpoint is called
- **THEN** it SHALL invoke `AgentGateway.invoke("data_engineer", command)` instead of calling `DataEngineerAgent.update_knowledge_graph()` directly

#### Scenario: Agent-independent API routes remain unchanged
- **WHEN** an API endpoint does NOT involve agent operations (e.g., direct KG queries via `NeurosymbolicQueryService`)
- **THEN** it SHALL continue operating as-is — only agent-invoking routes go through the gateway

### Requirement: Gateway SHALL handle agent unavailability gracefully
When a remote agent service is unreachable, the gateway SHALL return a structured error response with the failing agent role and a retry-after hint, rather than letting exceptions propagate as generic 500 errors.

#### Scenario: Remote agent is down
- **WHEN** `AgentGateway.invoke("knowledge_manager", command)` fails because the KnowledgeManager container is unreachable
- **THEN** the gateway SHALL raise an `AgentUnavailableError` with `agent_role="knowledge_manager"` and `retry_after_seconds=30`

#### Scenario: API returns 503 for unavailable agent
- **WHEN** an API route catches `AgentUnavailableError`
- **THEN** it SHALL return HTTP 503 with body `{"error": "agent_unavailable", "agent": "knowledge_manager", "retry_after": 30}`
