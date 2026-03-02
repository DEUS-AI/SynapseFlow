## Why

All five agents (DataArchitect, DataEngineer, KnowledgeManager, MedicalAssistant, Echo) run as in-process Python objects inside a single FastAPI process, sharing singleton instances of the EventBus, CommandBus, KG backend, and PatientMemoryService. The distributed infrastructure exists (RabbitMQ EventBus, A2A HTTP channel, Neo4j discovery, Dockerfile.agent, docker-compose entries for 2 of 5 agents) but is incomplete and untested — the A2A channel has no receive handler, the CommandBus has no distributed variant, and the API layer creates agents in-process regardless of configuration. This blocks independent scaling, fault isolation, and production deployment of individual agents.

## What Changes

- **BREAKING**: API layer stops instantiating agents in-process; delegates to agent services via HTTP (A2A protocol) or message bus
- Complete the A2A CommunicationChannel with a receive/webhook endpoint so agents can accept inbound messages over HTTP
- Add containers and docker-compose entries for KnowledgeManager and MedicalAssistant (DataArchitect and DataEngineer already have them)
- Each agent process owns its own connections to infrastructure (Neo4j, Redis, RabbitMQ) — no shared singletons across process boundaries
- Introduce an API gateway pattern so the FastAPI app routes requests to the correct agent service instead of calling agent methods directly
- Add health-check endpoints per agent container for orchestration readiness
- Make the CommandBus work across process boundaries (dispatch commands to remote agents via RabbitMQ RPC or HTTP)
- Ensure local (in-memory) mode remains fully functional for development — both modes must be switchable via configuration

## Capabilities

### New Capabilities
- `agent-containerization`: Container definitions, Dockerfiles, health checks, and docker-compose configuration for all agents to run as independent services
- `distributed-command-bus`: CommandBus implementation that dispatches commands across process boundaries via RabbitMQ RPC or HTTP, with fallback to in-memory for local mode
- `agent-gateway`: API gateway pattern in the FastAPI app that delegates requests to agent services (HTTP/A2A) instead of instantiating agents in-process
- `a2a-receive-handler`: Inbound message endpoint for agents so the A2A CommunicationChannel supports bidirectional communication

### Modified Capabilities
- `operational-readiness`: Health checks and readiness probes now required per-agent, not just per-API — each agent container must expose liveness/readiness endpoints

## Impact

- **Code**: `application/api/dependencies.py` (remove agent singletons), `application/api/main.py` (startup changes), `composition_root.py` (per-process bootstrap), `infrastructure/communication/a2a_channel.py` (receive handler), `application/commands/base.py` (distributed dispatch)
- **APIs**: Agent endpoints become internal service APIs; public API delegates instead of calling agents directly. Breaking change for any code that imports and calls agent instances from `dependencies.py`.
- **Infrastructure**: docker-compose.services.yml gains KnowledgeManager and MedicalAssistant containers; RabbitMQ becomes required for distributed mode; each agent needs its own Neo4j connection config
- **Dependencies**: No new Python packages expected — RabbitMQ (aio-pika) and HTTP (httpx/aiohttp) are already in the stack
- **Testing**: Need integration tests that validate agent communication across process boundaries; existing unit tests (in-memory mode) must continue to pass
