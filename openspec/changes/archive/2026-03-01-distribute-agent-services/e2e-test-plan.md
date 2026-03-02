# End-to-End Test Plan: distribute-agent-services

## Overview

This plan covers the testing strategy for the agent distribution change across 4 tiers: unit tests (mocked, fast), component tests (single process, real FastAPI), integration tests (Docker, real infrastructure), and E2E smoke tests (full stack with API gateway).

**Test framework**: pytest, asyncio_mode="auto", markers: `unit`, `integration`
**Mocking**: pytest-httpx (HTTPXMock), unittest.mock, AsyncMock
**HTTP testing**: FastAPI TestClient (sync) + httpx AsyncClient (async)

---

## Tier 1 — Unit Tests (no infrastructure, mocked I/O)

### 1.1 CommandRegistry (`tests/application/commands/test_registry.py`)

| # | Test | Description |
|---|------|-------------|
| U1 | `test_serialize_pydantic_command` | `ModelingCommand(dda_path="/tmp/x.md")` → dict with `__command_type__: "ModelingCommand"` and `dda_path` |
| U2 | `test_serialize_echo_command` | `EchoCommand(message="hi")` → dict with `__command_type__: "EchoCommand"` |
| U3 | `test_deserialize_modeling_command` | dict → `ModelingCommand` instance with correct field values |
| U4 | `test_deserialize_echo_command` | dict → `EchoCommand` instance with correct field values |
| U5 | `test_round_trip_all_commands` | For each of `[ModelingCommand, GenerateMetadataCommand, EchoCommand]`: serialize → deserialize → assert `==` original |
| U6 | `test_deserialize_unknown_type_raises` | payload with `__command_type__: "BogusCommand"` → `CommandDeserializationError` |
| U7 | `test_deserialize_missing_type_raises` | payload without `__command_type__` → `CommandDeserializationError` |
| U8 | `test_serialize_unregistered_raises` | serialize an unregistered command class → error |
| U9 | `test_get_agent_role` | `registry.get_agent_role(ModelingCommand)` → `"data_architect"`, `EchoCommand` → `"echo"` |
| U10 | `test_get_agent_role_unknown` | `registry.get_agent_role(UnknownCommand)` → `None` |
| U11 | `test_serialize_result_types` | Verify `serialize_result` for `None`, `str`, `int`, `dict`, `list`, Pydantic model |
| U12 | `test_deserialize_result` | JSON string round-trips through `serialize_result` / `deserialize_result` |

### 1.2 A2ACommunicationChannel (`tests/infrastructure/test_a2a_channel.py` — rewrite)

| # | Test | Description |
|---|------|-------------|
| U13 | `test_send_resolves_url_from_agent_urls` | Channel with `agent_urls={"km": "http://km:8003"}`, send to `receiver_id="km"` → POST to `http://km:8003/v1/tasks/send` |
| U14 | `test_send_falls_back_to_base_url` | Channel with only `base_url`, send to any receiver → POST to `base_url/v1/tasks/send` |
| U15 | `test_send_unknown_agent_raises` | Channel without `base_url`, send to unknown receiver → `AgentNotFoundError` |
| U16 | `test_send_wire_format` | Verify POST body contains `taskId`, `message.id`, `message.sender_id`, `message.receiver_id`, `message.content`, `message.metadata` |
| U17 | `test_send_dict_content_preserved` | Send `content={"key": "val"}` → verify content arrives as dict, not stringified |
| U18 | `test_send_http_error_raises` | Mock 500 response → raises `httpx.HTTPStatusError` |
| U19 | `test_receive_empty_returns_none` | `receive("agent_x")` on fresh channel → `None` |
| U20 | `test_enqueue_then_receive` | `enqueue_inbound(msg)` → `receive(agent_id)` returns same message with all fields |
| U21 | `test_receive_fifo_order` | Enqueue 3 messages → receive returns them in order |
| U22 | `test_get_all_messages_drains_queue` | Enqueue 5 messages → `get_all_messages()` returns 5, second call returns `[]` |
| U23 | `test_queue_size` | Enqueue 3 → `queue_size()` returns 3, receive 1 → returns 2 |
| U24 | `test_from_agent_config` | Build channel from an `AgentInfraConfig` mock → verify `_agent_urls` dict populated |

### 1.3 DistributedCommandBus — local fallback (`tests/infrastructure/test_distributed_command_bus.py`)

| # | Test | Description |
|---|------|-------------|
| U25 | `test_dispatch_falls_back_local_when_disconnected` | Bus not connected, local handler registered → local handler called |
| U26 | `test_dispatch_falls_back_local_no_route` | Bus connected but command has no agent role → local handler called |
| U27 | `test_dispatch_no_handler_raises` | Bus disconnected, no local handler → `TypeError` |
| U28 | `test_register_local_handler` | Register handler for type → dispatch calls handler.handle() |

### 1.4 AgentGateway (`tests/application/services/test_agent_gateway.py`)

| # | Test | Description |
|---|------|-------------|
| U29 | `test_local_mode_dispatches_locally` | Config `deployment_mode: local` → `_invoke_local` called, no RabbitMQ needed |
| U30 | `test_distributed_mode_wraps_dispatch_error` | Mock `DistributedCommandBus.dispatch` raises `CommandDispatchError` → `AgentUnavailableError` |
| U31 | `test_deployment_mode_property` | Gateway reflects config's deployment mode |
| U32 | `test_initialize_idempotent` | Calling `initialize()` twice doesn't reconnect |

### 1.5 AgentServer endpoints (`tests/interfaces/test_agent_server.py`)

Use `TestClient(create_app(state))` with a pre-populated `AgentServerState` (no bootstrap).

| # | Test | Description |
|---|------|-------------|
| U33 | `test_health_healthy` | State with mock connected deps → GET /health → 200, `status: "healthy"` |
| U34 | `test_health_unhealthy` | State with disconnected dep → GET /health → 503, `status: "unhealthy"` |
| U35 | `test_a2a_receive_valid` | POST /v1/tasks/send with valid payload → 200, message enqueued |
| U36 | `test_a2a_receive_missing_fields` | POST missing `sender_id` → 400 |
| U37 | `test_a2a_receive_queue_full` | Fill queue to MAX → POST → 429 with `retry_after` |
| U38 | `test_a2a_receive_message_fields` | After POST, message in queue has correct `id`, `sender_id`, `receiver_id`, `content`, `metadata` |

### 1.6 API Gateway integration (`tests/application/api/test_dda_upload_gateway.py`)

| # | Test | Description |
|---|------|-------------|
| U39 | `test_dda_upload_uses_gateway` | Mock `get_agent_gateway` → verify `invoke("data_architect", ModelingCommand(...))` called |
| U40 | `test_agent_unavailable_returns_503` | Gateway raises `AgentUnavailableError` → API returns 503 with `error: "agent_unavailable"` |

### 1.7 Env validation (`tests/interfaces/test_env_validation.py`)

| # | Test | Description |
|---|------|-------------|
| U41 | `test_validate_env_vars_all_present` | Set required vars → no `SystemExit` |
| U42 | `test_validate_env_vars_missing_common` | Unset `NEO4J_URI` → `SystemExit` |
| U43 | `test_validate_env_vars_missing_role_specific` | Role=medical_assistant, unset `REDIS_HOST` → `SystemExit` |

---

## Tier 2 — Component Tests (real FastAPI, mocked infrastructure)

These test the agent server as a running ASGI app with `httpx.AsyncClient`, but mock out Neo4j/RabbitMQ/Graphiti.

### 2.1 Agent Server round-trip (`tests/component/test_agent_server_component.py`)

| # | Test | Description |
|---|------|-------------|
| C1 | `test_a2a_send_then_receive_via_server` | Start TestClient → POST message to /v1/tasks/send → read directly from state.message_queues → verify round-trip |
| C2 | `test_health_reflects_dependency_state` | Swap `check_dependencies` to return various states → verify 200/503 |
| C3 | `test_multiple_agents_queue_isolation` | POST messages for agent_a and agent_b → queues are separate |

---

## Tier 3 — Integration Tests (Docker infrastructure required)

**Prerequisite**: `docker-compose -f docker-compose.services.yml up -d` (Neo4j, RabbitMQ, FalkorDB)

Mark all with `@pytest.mark.integration`.

### 3.1 Container health (`tests/integration/test_distributed_health.py`)

| # | Test | Description | How |
|---|------|-------------|-----|
| I1 | `test_all_containers_health` | All 4 agent containers respond 200 on /health | `docker-compose up` all agents, then `httpx.get(f"http://localhost:{port}/health")` for each |
| I2 | `test_health_503_when_neo4j_down` | Stop neo4j → agent /health → 503 | Stop neo4j container, hit health endpoint, restart |

### 3.2 A2A cross-container messaging (`tests/integration/test_distributed_a2a.py`)

| # | Test | Description | How |
|---|------|-------------|-----|
| I3 | `test_a2a_cross_container` | Send message from DA → KM via HTTP | POST to `localhost:8003/v1/tasks/send` with sender_id="data_architect", verify 200 |
| I4 | `test_a2a_message_fields_preserved` | All Message fields arrive intact | POST message with metadata, structured content; inspect response or agent logs |
| I5 | `test_a2a_queue_backpressure` | Send 1001 messages rapidly to one agent | Verify 429 on overflow |

### 3.3 DistributedCommandBus RPC (`tests/integration/test_distributed_command_bus_rpc.py`)

| # | Test | Description | How |
|---|------|-------------|-----|
| I6 | `test_echo_command_rpc` | Dispatch `EchoCommand("hello")` through RabbitMQ to echo agent | Create DistributedCommandBus pointing at local RabbitMQ, start echo agent, dispatch, verify `"hello"` returned |
| I7 | `test_rpc_timeout` | Dispatch to non-existent queue | Verify `CommandDispatchError` after timeout |
| I8 | `test_rpc_deserialization_error` | Send malformed payload to cmd_echo queue | Verify error response, no crash |

### 3.4 Docker-compose validation (`tests/integration/test_docker_compose.py`)

| # | Test | Description | How |
|---|------|-------------|-----|
| I9 | `test_compose_config_valid` | `docker-compose config` succeeds | `subprocess.run(["docker-compose", "-f", "docker-compose.services.yml", "config"])` |
| I10 | `test_no_circular_depends` | No circular dependency in depends_on | Parse compose config, build DAG, check acyclic |

---

## Tier 4 — E2E Smoke Tests (full distributed stack)

**Prerequisite**: Full `docker-compose up` with all infrastructure + all 4 agent containers + API server.

### 4.1 DDA Upload distributed flow (`tests/e2e/test_distributed_dda.py`)

| # | Test | Description | How |
|---|------|-------------|-----|
| E1 | `test_dda_upload_distributed` | Upload DDA file via API → routed through AgentGateway → DistributedCommandBus → DataArchitect container → result returned | `POST /api/dda/upload` with `DEPLOYMENT_MODE=distributed`, verify 200 and entities created |
| E2 | `test_dda_upload_local_fallback` | Same with `DEPLOYMENT_MODE=local` | Verify same result, no RabbitMQ traffic |
| E3 | `test_dda_upload_agent_down_503` | Stop DA container → upload → 503 with `agent_unavailable` | Stop data_architect, POST /api/dda/upload, verify 503 response body |

### 4.2 Multi-agent escalation (`tests/e2e/test_distributed_escalation.py`)

| # | Test | Description | How |
|---|------|-------------|-----|
| E4 | `test_escalation_da_to_km` | DA processes a DDA that triggers escalation to KM | Upload complex DDA, verify KM container received and processed the escalation via A2A |
| E5 | `test_command_routing_to_correct_agent` | Dispatch ModelingCommand → DA, GenerateMetadataCommand → DE | Dispatch both, verify each reached the correct container (check logs or responses) |

---

## Execution Strategy

### Running by tier

```bash
# Tier 1: Fast, no infrastructure needed
uv run pytest tests/application/commands/test_registry.py \
              tests/infrastructure/test_a2a_channel.py \
              tests/infrastructure/test_distributed_command_bus.py \
              tests/application/services/test_agent_gateway.py \
              tests/interfaces/test_agent_server.py \
              tests/interfaces/test_env_validation.py \
              tests/application/api/test_dda_upload_gateway.py -v -m "not integration"

# Tier 2: Component (still no external services)
uv run pytest tests/component/ -v

# Tier 3: Integration (needs docker-compose infra running)
docker-compose -f docker-compose.services.yml up -d
uv run pytest tests/integration/test_distributed_*.py -v -m integration

# Tier 4: E2E (needs full stack)
docker-compose -f docker-compose.services.yml up -d  # all agents + infra
uv run uvicorn application.api.main:app --port 8000 &
uv run pytest tests/e2e/ -v -m integration
```

### Recommended marker convention

```python
@pytest.mark.unit          # Tier 1 — no external dependencies
@pytest.mark.integration   # Tier 3+4 — needs Docker services running
```

### CI pipeline suggestion

```
Stage 1: Tier 1 unit tests (every push, ~10s)
Stage 2: Tier 2 component tests (every push, ~15s)
Stage 3: Tier 3 integration tests (merge to main, docker-compose up in CI)
Stage 4: Tier 4 E2E smoke tests (nightly or manual trigger)
```

---

## Fixtures to Create

### `conftest.py` additions

```python
# tests/conftest.py — shared fixtures for distributed tests

@pytest.fixture
def command_registry():
    """Pre-built CommandRegistry with all default commands."""
    from application.commands.registry import create_default_registry
    return create_default_registry()

@pytest.fixture
def agent_server_state():
    """AgentServerState with role='echo' for testing endpoints without bootstrap."""
    from interfaces.agent_server import AgentServerState
    state = AgentServerState(role="echo")
    state._healthy = True
    state._dependency_status = {"neo4j": "connected", "rabbitmq": "connected"}
    return state

@pytest.fixture
def agent_server_app(agent_server_state):
    """FastAPI test app from agent_server (no lifespan bootstrap)."""
    from interfaces.agent_server import create_app
    return create_app(agent_server_state)

@pytest.fixture
def a2a_channel():
    """A2ACommunicationChannel with test URLs."""
    from infrastructure.communication.a2a_channel import A2ACommunicationChannel
    return A2ACommunicationChannel(agent_urls={
        "data_architect": "http://localhost:8001",
        "knowledge_manager": "http://localhost:8003",
    })
```

---

## Test count summary

| Tier | Tests | Infra needed | Approx time |
|------|-------|--------------|-------------|
| 1 — Unit | 43 | None | ~5s |
| 2 — Component | 3 | None | ~3s |
| 3 — Integration | 10 | Docker services | ~30s |
| 4 — E2E | 5 | Full stack | ~60s |
| **Total** | **61** | | |

---

## Priority order for implementation

1. **U1–U12** (CommandRegistry) — validates the serialization backbone; blocks nothing
2. **U13–U24** (A2A channel) — existing tests need rewrite for new interface
3. **U25–U28** (DistributedCommandBus local fallback) — unit tests for local mode
4. **U33–U38** (AgentServer endpoints) — validates receive endpoint + health
5. **U29–U32** (AgentGateway) — validates routing strategy
6. **U39–U43** (API + env) — validates the glue layer
7. **C1–C3** (Component) — round-trip without Docker
8. **I1–I10** (Integration) — requires running containers
9. **E1–E5** (E2E) — full distributed smoke
