## 1. Agent Container Infrastructure (Phase 1)

- [x] 1.1 Add `knowledge_manager` service entry to `docker-compose.services.yml` with port 8003, `Dockerfile.agent` build, role command, env vars, and `depends_on` health checks for Neo4j, RabbitMQ, FalkorDB
- [x] 1.2 Add `medical_assistant` service entry to `docker-compose.services.yml` with port 8004, `Dockerfile.agent` build, role command, and `depends_on` health checks for Neo4j, RabbitMQ, FalkorDB, Redis, Qdrant
- [x] 1.3 Create `src/interfaces/agent_server.py` — lightweight FastAPI app that accepts `--role` argument, bootstraps only that agent's dependencies via `composition_root`, and starts uvicorn on the agent's assigned port
- [x] 1.4 Add `GET /health` endpoint to `agent_server.py` that checks Neo4j and RabbitMQ connectivity and returns JSON status with agent role and dependency states
- [x] 1.5 Update `Dockerfile.agent` CMD to use `agent_server.py` instead of the CLI `run-agent` command
- [x] 1.6 Add env var validation on agent startup — fail fast with clear error if required vars (`NEO4J_URI`, `RABBITMQ_URL`) are missing
- [x] 1.7 Ensure each agent process creates its own Neo4j driver and RabbitMQ connection from its env vars — no shared singletons across containers
- [x] 1.8 Update `config/agents.distributed.yaml` with correct container hostnames and ports for all 4 agents
- [x] 1.9 Test: start all 4 agent containers (manual verification) via `docker-compose up` and verify each `/health` returns 200 with correct dependency status

## 2. A2A Receive Handler (Phase 2)

- [x] 2.1 Add `POST /v1/tasks/send` endpoint to `agent_server.py` that accepts A2A message payloads, deserializes to `domain.communication.Message`, and enqueues into the agent's async mailbox
- [x] 2.2 Add request validation — return 400 for missing `taskId` or `message` fields, return 429 when queue exceeds configurable threshold (default 1000)
- [x] 2.3 Refactor `A2ACommunicationChannel.__init__` to accept agent config dict (from `agents.yaml`) and build a `{role: url}` lookup table instead of single `base_url`
- [x] 2.4 Implement `A2ACommunicationChannel.receive(agent_id)` to return messages from the inbound async queue (FIFO), return `None` when empty
- [x] 2.5 Implement `A2ACommunicationChannel.get_all_messages(agent_id)` to drain the inbound queue
- [x] 2.6 Update `A2ACommunicationChannel.send()` to resolve target URL from the agent config lookup by `message.receiver_id`, raise `AgentNotFoundError` for unknown agents
- [x] 2.7 Ensure A2A wire format preserves all `Message` fields (`id`, `sender_id`, `receiver_id`, `content`, `metadata`) with structured content support (dict payloads round-trip as dicts, not strings)
- [x] 2.8 Test: send a message from DataArchitect container to KnowledgeManager container via A2A and verify `receive()` returns it with all fields intact

## 3. Distributed CommandBus (Phase 3)

- [x] 3.1 Create `CommandRegistry` in `src/application/commands/registry.py` — dict mapping command type names to classes, with `serialize(command) -> dict` and `deserialize(dict) -> Command` methods using `dataclasses.asdict` + `__command_type__` discriminator
- [x] 3.2 Create command-to-agent routing table in `CommandRegistry` mapping each command type to the agent role that handles it (e.g., `ModelingCommand -> data_architect`, `GenerateMetadataCommand -> data_engineer`)
- [x] 3.3 Create `DistributedCommandBus` in `src/infrastructure/command_bus/distributed_command_bus.py` implementing `domain.command_bus.CommandBus` — serializes commands via `CommandRegistry`, dispatches via RabbitMQ RPC to `cmd_<role>` queue, deserializes response
- [x] 3.4 Add timeout handling (default 30s) and `CommandDispatchError` for unreachable agents, `CommandDeserializationError` for unknown command types
- [x] 3.5 Add RPC handler registration to `agent_server.py` startup — on boot, each agent registers an RPC consumer on `cmd_<role>` queue that deserializes commands, dispatches to local `CommandBus`, and returns serialized result
- [x] 3.6 Update `bootstrap_command_bus()` in `composition_root.py` to return `DistributedCommandBus` when `deployment_mode: distributed`, existing `CommandBus` when `deployment_mode: local`
- [ ] 3.7 Test: dispatch `EchoCommand` from API process to Echo agent in a separate container via `DistributedCommandBus` and verify round-trip result
- [x] 3.8 Test: serialization round-trip for all command types (`ModelingCommand`, `GenerateMetadataCommand`, `EchoCommand`, etc.)

## 4. Agent Gateway + API Refactor (Phase 4)

- [x] 4.1 Create `AgentGateway` class in `src/application/services/agent_gateway.py` with `invoke(role: str, command: Command) -> Any` method that routes to local agent (via `composition_root`) or remote agent (via `DistributedCommandBus`) based on `deployment_mode` config
- [x] 4.2 Add `AgentUnavailableError` exception with `agent_role` and `retry_after_seconds` fields
- [x] 4.3 Add `get_agent_gateway()` FastAPI dependency in `dependencies.py` that initializes and caches the gateway with the current deployment config
- [x] 4.4 Refactor DDA upload route to use `AgentGateway.invoke("data_architect", ModelingCommand(...))` instead of creating `DataArchitectAgent` in-process
- [x] 4.5 Refactor any other API routes that call agent methods directly to use `AgentGateway.invoke()` (only DDA upload route called agents — no other routes needed changes)
- [x] 4.6 Remove `_data_architect_agent` usage from API routes — DDA upload now uses gateway; global kept for backward compat but unused in routes
- [x] 4.7 Add exception handler in API for `AgentUnavailableError` → return HTTP 503 with `{"error": "agent_unavailable", "agent": "<role>", "retry_after": 30}`
- [x] 4.8 Verify local mode still works: set `deployment_mode: local`, run API, call DDA upload — should behave identically to today
- [ ] 4.9 Test: set `deployment_mode: distributed`, start agent containers + API, call DDA upload via API — should route through gateway to DataArchitect container

## 5. Integration Testing + Validation

- [ ] 5.1 Add integration test: all 4 containers start, each `/health` returns 200
- [ ] 5.2 Add integration test: A2A message from DataArchitect → KnowledgeManager (escalation) works across containers
- [ ] 5.3 Add integration test: `DistributedCommandBus` dispatches `ModelingCommand` to DataArchitect container and receives result
- [ ] 5.4 Add integration test: agent container with unreachable Neo4j returns 503 on `/health`
- [ ] 5.5 Add integration test: `AgentGateway` returns `AgentUnavailableError` when target container is stopped
- [ ] 5.6 Verify all existing unit tests pass with `deployment_mode: local` (no regressions)
- [ ] 5.7 Add docker-compose validation test: `docker-compose config` succeeds, no circular dependencies between agent services
