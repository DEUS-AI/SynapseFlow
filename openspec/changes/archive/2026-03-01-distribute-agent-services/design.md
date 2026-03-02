## Context

SynapseFlow has 4 production agents (DataArchitect, DataEngineer, KnowledgeManager, MedicalAssistant) plus a test Echo agent. Today all agents run as in-process Python objects inside the FastAPI process. The abstractions for distribution exist — `CommunicationChannel` (memory/A2A), `EventBus` (memory/RabbitMQ), config files for local/distributed modes, and a `Dockerfile.agent` with docker-compose entries for 2 of 4 agents — but the implementation is incomplete: the A2A channel can only send (no receive handler), the CommandBus is local-only, and the API creates agents directly via `dependencies.py` globals regardless of deployment mode.

The existing RabbitMQ EventBus already supports RPC (`call_rpc`, `register_rpc_handler`) via aio-pika, and the config system (`agents.yaml` / `agents.distributed.yaml`) already distinguishes local vs distributed modes with per-agent URLs and capabilities.

## Goals / Non-Goals

**Goals:**
- Every agent can run as an independent container with its own infrastructure connections
- API layer delegates to agents through a gateway abstraction — no direct agent instantiation in distributed mode
- Bidirectional A2A communication (send + receive) between agent containers
- Commands can be dispatched across process boundaries via RabbitMQ RPC
- Local mode continues to work exactly as today for development
- Configuration-driven switching between local and distributed modes (no code changes to switch)

**Non-Goals:**
- Auto-scaling or Kubernetes orchestration — this is docker-compose level, not k8s
- Service mesh or API gateway as a separate service — the gateway is an in-process abstraction in the FastAPI app
- Agent hot-reload or zero-downtime deployment
- Changing the agent domain model or adding new agents
- Distributed tracing or observability (separate concern, covered by `operational-readiness` spec)
- mTLS or service-to-service authentication between containers (future work)

## Decisions

### D1: RabbitMQ RPC for distributed CommandBus (not HTTP)

**Choice**: Use the existing RabbitMQ RPC pattern (`aio_pika.patterns.RPC`) for the `DistributedCommandBus`.

**Alternatives considered**:
- **HTTP/REST calls to agent endpoints**: Simpler to implement, but requires each agent to expose a full REST API for every command type. Creates coupling between caller and callee URL structure, harder to load-balance, no built-in retry/DLQ.
- **gRPC**: Strong typing and performance, but adds a new dependency and build step (proto compilation). Overkill for the current scale.

**Rationale**: RabbitMQ is already in the stack and the `RabbitMQEventBus` already has RPC support (`call_rpc`, `register_rpc_handler`). Using RPC gives us reliable delivery, timeouts, and dead-letter queues without adding dependencies. Each agent registers an RPC handler on queue `cmd_<role>`, and the `DistributedCommandBus` routes commands to the correct queue based on a command-to-agent mapping.

### D2: AgentGateway as an application service (not a separate process)

**Choice**: `AgentGateway` is a Python class in `src/application/services/` that the API routes depend on via FastAPI dependency injection. It is NOT a separate proxy/gateway container.

**Alternatives considered**:
- **Separate reverse proxy (Nginx/Envoy)**: Full API gateway with routing, rate limiting, circuit breaking. Adds operational complexity and a new container to manage. Right approach for production scale but premature now.
- **API route duplication**: Maintain separate route files for local vs distributed mode. Leads to code duplication and divergence.

**Rationale**: The gateway is a strategy pattern — it resolves "local or remote?" at invocation time based on `deployment_mode` from config. In local mode, it creates the agent via `composition_root` and calls it directly. In distributed mode, it serializes the command and dispatches via `DistributedCommandBus`. This keeps the API routes unchanged — they call `gateway.invoke(role, command)` and don't care about the deployment topology.

```
┌─ FastAPI Process ─────────────────────────────────────┐
│                                                        │
│  API Route ──→ AgentGateway.invoke(role, command)     │
│                     │                                  │
│           ┌─────────┴──────────┐                      │
│           │ deployment_mode?   │                      │
│           └─────────┬──────────┘                      │
│              local  │  distributed                    │
│          ┌──────────┴──────────────┐                  │
│          ▼                         ▼                  │
│  composition_root          DistributedCommandBus      │
│  → create agent               → RabbitMQ RPC          │
│  → call directly               → cmd_<role> queue     │
│                                    │                  │
└────────────────────────────────────┼──────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  Agent Container    │
                          │  (separate process) │
                          │  RPC handler        │
                          │  → local CommandBus │
                          │  → execute handler  │
                          └─────────────────────┘
```

### D3: Each agent container runs a lightweight FastAPI app

**Choice**: Each agent container runs a small FastAPI app (not just a CLI loop) that provides: the A2A receive endpoint (`POST /v1/tasks/send`), the health endpoint (`GET /health`), and RPC consumer registration on startup.

**Alternatives considered**:
- **Pure CLI with RabbitMQ-only communication**: Agent runs as a background consumer with no HTTP server. Simpler, but no health endpoint for docker-compose `healthcheck`, no A2A HTTP endpoint, harder to debug.
- **Full copy of the API app per agent**: Reuse `application/api/main.py` in each container. Too heavy — brings in all routes, all dependencies, all singletons.

**Rationale**: A minimal FastAPI app per agent gives us HTTP endpoints for health checks and A2A receive, while keeping the footprint small. The app is created in a new `src/interfaces/agent_server.py` that takes a `--role` argument and bootstraps only that agent's dependencies.

```
agent_server.py --role data_architect
├── FastAPI app (minimal)
│   ├── GET  /health          → check Neo4j, RabbitMQ connectivity
│   └── POST /v1/tasks/send   → A2A receive, enqueue to agent mailbox
├── Agent bootstrap
│   ├── composition_root.create_data_architect_agent(...)
│   ├── Own Neo4j driver, own RabbitMQ connection
│   └── Register RPC handler on cmd_data_architect queue
└── Startup sequence
    1. Connect to infrastructure (Neo4j, RabbitMQ)
    2. Create agent via composition_root
    3. Register RPC handlers
    4. Start FastAPI server on assigned port
```

### D4: Command serialization via dataclass-to-dict with type discriminator

**Choice**: Commands are serialized as JSON dicts with a `__command_type__` field for deserialization. A `CommandRegistry` maps type names to classes.

**Alternatives considered**:
- **pickle**: Native Python serialization. Security risk (arbitrary code execution), version-fragile, not human-readable.
- **Protocol Buffers / MessagePack**: Binary formats, faster, but add build steps and dependencies.

**Rationale**: Commands are already dataclasses. Adding `dataclasses.asdict()` + a type discriminator is minimal code. A `CommandRegistry` (dict of `{type_name: CommandClass}`) handles deserialization. This is simple, debuggable (JSON is human-readable on RabbitMQ management UI), and requires no new dependencies.

```python
# Serialization
{"__command_type__": "ModelingCommand", "dda_content": "...", "domain": "..."}

# CommandRegistry
COMMAND_REGISTRY = {
    "ModelingCommand": ModelingCommand,
    "GenerateMetadataCommand": GenerateMetadataCommand,
    "EchoCommand": EchoCommand,
    ...
}
```

### D5: A2A channel gets per-agent URL resolution from config

**Choice**: Refactor `A2ACommunicationChannel` to accept agent config (from `agents.yaml` or `agents.distributed.yaml`) and resolve target URLs per-agent instead of using a single `base_url`.

**Rationale**: The current implementation takes one `base_url` and posts everything there. In distributed mode, each agent has its own URL (e.g., `http://data-architect:8002`). The config already has per-agent URLs. The channel should read the agent config on init and build a `{role: url}` lookup table. `send(message)` resolves the URL from `message.receiver_id`.

### D6: Phased implementation — containers first, gateway second

**Choice**: Implement in 4 phases:
1. **Agent containers + health endpoints** — Get all 4 agents running independently in docker-compose
2. **A2A receive handler** — Complete bidirectional HTTP messaging between containers
3. **Distributed CommandBus** — Enable cross-process command dispatch via RabbitMQ RPC
4. **Agent Gateway + API refactor** — Refactor API to delegate through the gateway

**Rationale**: Each phase is independently testable and deployable. Phase 1 is the foundation — containers must exist before anything else. Phase 2 completes inter-agent messaging. Phase 3 adds the command dispatch layer. Phase 4 ties it together at the API level. This avoids a big-bang refactor and lets us validate each layer before building on it.

## Risks / Trade-offs

**[Risk] RabbitMQ becomes a single point of failure in distributed mode**
→ Mitigation: RabbitMQ EventBus already has local fallback when disconnected. The DistributedCommandBus should follow the same pattern — fall back to local dispatch if RabbitMQ is unreachable and all agents happen to be in-process. For true distributed mode, RabbitMQ availability is a prerequisite (same as Neo4j).

**[Risk] Command serialization breaks when Command classes change**
→ Mitigation: The `CommandRegistry` validates on deserialization. Add a basic round-trip test for each command type. Avoid pickle — JSON serialization will surface field mismatches as errors rather than silent corruption.

**[Risk] Two communication paths (A2A HTTP + RabbitMQ RPC) add complexity**
→ Trade-off: A2A is for agent-to-agent messaging (escalations, notifications — fire-and-forget). RabbitMQ RPC is for command dispatch (request-response with timeout). These serve different patterns. Consolidating to one would either lose async messaging (drop A2A) or lose reliable RPC (drop RabbitMQ). Keeping both matches the existing abstractions.

**[Risk] Local mode diverges from distributed mode over time**
→ Mitigation: The AgentGateway is the convergence point — both modes use the same gateway interface. Integration tests should run in both modes. The `agents.yaml` config switch is the only difference.

**[Risk] Agent containers double the resource footprint (each agent loads Python + dependencies)**
→ Trade-off: This is the cost of process isolation. Mitigate with `python:3.11-slim` base image (already used), shared Docker build cache, and the ability to run selective agents (`docker-compose up data_architect` only). Local mode remains available for resource-constrained development.

**[Risk] API refactor (Phase 4) is a breaking change for `dependencies.py` consumers**
→ Mitigation: Phase 4 is last, giving time to identify all callers. The gateway provides the same operations — callers switch from `agent.process_dda()` to `gateway.invoke("data_architect", ModelingCommand(...))`. Internal consumers only (no external API contract change).

## Migration Plan

1. **Phase 1** can be deployed immediately — new containers alongside existing infrastructure, no changes to the API.
2. **Phase 2** adds the A2A receive endpoint to agent servers — backward compatible, the in-memory channel continues to work in local mode.
3. **Phase 3** adds the DistributedCommandBus — new class, no changes to existing CommandBus. Activated by config.
4. **Phase 4** refactors API routes to use AgentGateway — this is the breaking change. Rollback: revert to direct agent instantiation by switching `deployment_mode: local`.

Rollback at any phase: set `deployment_mode: local` in config and restart the API. All agents fall back to in-process mode.

## Open Questions

- **Port assignment convention**: Should agent ports be configurable via env vars or hardcoded per role? Current docker-compose uses fixed ports (8001-8004). Env var override would be more flexible for dynamic environments.
- **Shared Neo4j namespace**: All agents write to the same Neo4j database. Should distributed agents use separate databases or labeled subgraphs to avoid conflicts? Current architecture assumes shared graph — this may need revisiting for true isolation.
- **MedicalAssistant cross-compose dependencies**: MedicalAssistant needs Redis + Qdrant from `docker-compose.memory.yml`. Should we merge the compose files, use `extends`, or reference external networks? Docker Compose v2 supports `include` directives.
