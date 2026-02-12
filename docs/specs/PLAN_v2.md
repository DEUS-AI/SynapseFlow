# Development Plan (v2)

This plan outlines the tasks required to implement the multi-agent system described in `PRD_v2.md`. The work is organized by the five architectural pillars.

---

### Pillar 1: Core Architecture: Collaborative Multi-Agent System

-   [x] **Refactor Agent Classes:**
    -   [x] Rename `ArxAgent` to `DataArchitectAgent`.
    -   [x] Rename `DeveloperAgent` to `DataEngineerAgent`.
-   [x] **Update Agent Registry:**
    -   [x] Modify `composition_root.py` to reflect the new agent class names and locations.
-   [ ] **Define Agent Responsibilities in Code:**
    -   [ ] Implement the initial logic for the `DataArchitectAgent` to generate metadata and delegate tasks.
    -   [ ] Implement the initial logic for the `DataEngineerAgent` to receive and act upon tasks.

### Pillar 2: Application Structure: Modular and Clean

-   [x] **Create New Directory Structure:**
    -   [x] Create `src/application/agents/`.
    -   [x] Create `src/application/agents/data_architect/` and `.../handlers/`.
    -   [x] Create `src/application/agents/data_engineer/` and `.../handlers/`.
    -   [x] Create `src/infrastructure/communication/`.
-   [x] **Migrate Existing Code:**
    -   [x] Move `DataArchitectAgent` logic to `src/application/agents/data_architect/agent.py`.
    -   [x] Move `DataEngineerAgent` logic to `src/application/agents/data_engineer/agent.py`.
    -   [x] Move `InMemoryCommunicationChannel` to `src/infrastructure/communication/memory_channel.py`.
    -   [x] Delete the old `src/application/agents.py` file.
-   [x] **Update Imports:**
    -   [x] Fix all imports that are broken by the file moves, especially in `composition_root.py` and tests.

### Pillar 3: Communication Protocol: Google A2A & MCP

-   [x] **Add Dependencies:**
    -   [x] Add `fastapi` and `uvicorn` to `pyproject.toml` for the agent servers.
    -   [ ] Add any necessary Google A2A or MCP client libraries.
-   [x] **Implement A2A Servers:**
    -   [x] Create `server.py` for the `DataArchitectAgent`.
    -   [x] Create `server.py` for the `DataEngineerAgent`.
    -   [x] Implement a basic FastAPI app in each server, exposing the `/v1/tasks/send` endpoint.
-   [x] **Implement A2A Client:**
    -   [x] Create `a2a_channel.py` in `src/infrastructure/communication/`.
    -   [x] Implement a new `A2ACommunicationChannel` class that implements the `CommunicationChannel` interface and sends HTTP requests to other agents.
-   [x] **Integrate MCP (Scaffolding):**
    -   [x] Define a `ToolDefinition` in the `domain` layer.
    -   [x] Create a service to convert `Command`s to `ToolDefinition`s.

### Pillar 4: Logic Abstraction: A2A Skills as Commands

-   [x] **Define Collaboration Commands:**
    -   [x] Create new command dataclasses (e.g., `BuildKGCommand`, `KGFeedbackCommand`, `NaturalLanguageQueryCommand`) in the `application/commands` module.
-   [x] **Implement Command Handlers:**
    -   [x] Create handler classes for the new commands in the appropriate agent's `handlers` directory.
-   [x] **Connect Server to Command Bus:**
    -   [x] In each agent's `server.py`, implement the adapter logic to translate incoming A2A skill requests into the appropriate `Command`.
    -   [x] Use the injected `CommandBus` to execute the command.

### Pillar 5: Discovery Mechanism: Hybrid Model

-   [x] **Implement `agent.json`:**
    -   [x] Create a Pydantic model for the `agent.json` structure (`AgentDefinition`).
    -   [x] Implement an endpoint in each agent's `server.py` to serve its `agent.json`.
-   [x] **Implement KG-based Service Registration:**
    -   [x] Add a `register_self()` method to the base `Agent` class.
    -   [x] The implementation uses the `GraphRepository` to create an `AgentService` node.
-   [x] **Implement KG-based Service Discovery:**
    -   [x] Add an abstract `discover_agent(capability: str)` method to the base `Agent` class.
    -   [x] The implementation queries the KG for a suitable agent and returns its endpoint.
