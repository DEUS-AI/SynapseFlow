# Product Requirements Document (v2) - Collaborative Data Agents for an Autonomous Metalake

## 1. Overview
This project implements a multi-agent system where a **Data Architect Agent** and a **Data Engineer Agent** collaborate to build and manage an autonomous, metadata-driven Knowledge Graph (KG). This system functions as an "agent-based metalake," where agents autonomously handle the lifecycle of metadata from extraction to insight generation.

The core workflow involves the Data Architect creating structured metadata from various sources and the Data Engineer using that metadata to build, validate, and query a persistent Knowledge Graph in Neo4j.

## 2. Objectives
- Implement a multi-agent architecture with two specialized, collaborative agents: `DataArchitectAgent` and `DataEngineerAgent`.
- Define and implement a robust communication protocol for the agents to delegate tasks, provide feedback, and query each other.
- Solidify the agent roles: the Architect focuses on "what" (modeling the data landscape) and the Engineer on "how" (implementing and managing the KG).
- Leverage the existing clean architecture to support this collaborative model.
- Fix existing implementation gaps and bugs, particularly in the graph repository and agent message processing.

## 3. Functional Requirements

### 3.1. Agent Roles & Responsibilities

#### 3.1.1. Data Architect Agent (`DataArchitectAgent`)
- **Primary Goal:** To understand and model the data landscape.
- **Responsibilities:**
    - Ingests high-level goals or unstructured/semi-structured data sources (e.g., documents, API specs).
    - Uses `LLMGraphTransformer` to produce structured metadata.
    - Publishes this metadata to a location accessible by the Data Engineer.
    - Delegates KG construction and querying tasks to the Data Engineer via commands.
    - Receives and processes feedback from the Data Engineer to iterate on and improve the metadata.
    - Can send natural language queries to the Data Engineer to get insights from the KG.

#### 3.1.2. Data Engineer Agent (`DataEngineerAgent`)
- **Primary Goal:** To build, manage, and provide access to the Knowledge Graph.
- **Responsibilities:**
    - Acts upon commands received from the Data Architect.
    - Consumes the structured metadata to build or update the KG in Neo4j.
    - Validates the integrity and quality of the KG (e.g., checks for inconsistencies, orphan nodes).
    - Provides structured feedback to the Data Architect about the metadata quality based on the KG validation.
    - Exposes a query interface that can translate natural language questions from the Architect into Cypher queries and return the results.

### 3.2. Collaborative Workflow Example
1.  **Initiation:** A user provides the `DataArchitectAgent` with a goal, like "Model the project's codebase."
2.  **Metadata Generation:** The Architect analyzes the source files and uses the `LLMGraphTransformer` to create a structured representation of classes, functions, and their relationships.
3.  **Task Delegation:** The Architect sends a `BuildKGCommand` message to the `DataEngineerAgent`, pointing to the location of the generated metadata.
4.  **KG Construction:** The Engineer receives the command, processes the metadata, and populates the Neo4j graph.
5.  **Validation & Feedback:** The Engineer validates the graph and finds that some function calls point to non-existent modules. It sends a `KGFEEDBACK` message to the Architect with a report of these dangling relationships.
6.  **Iteration:** The Architect receives the feedback, re-analyzes the problematic areas, corrects the metadata, and sends an `UpdateKGCommand` to the Engineer.
7.  **Ad-hoc Querying:** The Architect asks the Engineer via a message: "Which modules have the highest number of dependencies?" The Engineer translates this to a Cypher query, executes it, and returns the answer.

### 3.3. Core Services and Modular Architecture
The system is composed of two primary parts: a **Shared Core** and the **Agent Modules**.

-   **Shared Core (`infrastructure`, `interfaces`):** These layers provide common, reusable services for all agents. This includes database connections (`Neo4JGraphRepository`), communication channels, and other foundational components. This ensures that agents are lightweight and focused on their specific business logic, while the underlying plumbing is centralized and shared.

-   **Agent Modules (`application/agents`):** To adhere to clean architecture principles and ensure high modularity, the agents and their specific logic will be organized into a dedicated `agents` module. The principle of **one object per file** will be strictly followed. The proposed structure is:

```
src/
└── application/
    └── agents/
        ├── __init__.py
        ├── data_architect/
        │   ├── agent.py
        │   └── handlers/
        └── data_engineer/
            ├── agent.py
            └── handlers/
```

### 3.4. Communication Protocol: Google A2A and MCP
To enable robust, scalable, and interoperable communication, the system will adopt Google's A2A (Agent-to-Agent) and MCP (Model-Context Protocol) frameworks.

-   **A2A for Inter-Agent Communication:** The `InMemoryCommunicationChannel` will be replaced by a full A2A implementation.
    -   **A2A Server:** Each agent will run as a standalone A2A server using a web framework like FastAPI. It will expose a `/v1/tasks/send` endpoint to receive skill invocations from other agents.
    -   **A2A Client:** To initiate communication, an agent will use a dedicated A2A client that sends structured JSON-RPC messages to the target agent's server endpoint. This client will be a new implementation of our `CommunicationChannel` interface.

-   **MCP for Tool Integration:** The system will incorporate MCP to allow agents to interact with external tools and APIs (e.g., databases, file systems, web APIs) in a standardized, model-agnostic way. This decouples the agent's core logic from the specifics of tool implementation.

### 3.5. Dynamic Agent Discovery (Hybrid Model)
We will implement a hybrid model for agent discovery that combines the A2A standard with our dynamic Knowledge Graph registry.

-   **Standard Discovery (`agent.json`):** Each agent server will expose a standard `/.well-known/agent.json` file. This file acts as an "agent card," publicly describing its identity, capabilities (skills), and endpoint, enabling discovery by any A2A-compliant system.
-   **Advanced Discovery (Knowledge Graph):** On startup, agents will also register their `agent.json` metadata within the central Knowledge Graph. This allows our agents to perform advanced, dynamic queries to find collaborators (e.g., "Find me an agent that has the `BuildKGCommand` skill and has been online for the last 24 hours").

### 3.6. Abstracting A2A Skills with the Command Pattern
To maintain a clean separation of concerns, we will treat the A2A server as an adapter that translates external requests into internal commands.

-   **Workflow:**
    1.  The agent's A2A server (FastAPI) receives an incoming request to execute a skill.
    2.  The endpoint acts as an **Adapter**. It parses the A2A task message and transforms it into a corresponding `Command` object (e.g., `BuildKGCommand`).
    3.  The `Command` is dispatched to the `CommandBus`.
    4.  The `CommandBus` routes the command to the registered `CommandHandler`, which contains the core business logic and is completely unaware of the A2A protocol.

### 3.7. Updated Directory Structure
The proposed structure will be updated to include the agent servers.

```
src/
├── application/
│   └── agents/
│       ├── data_architect/
│       │   ├── agent.py
│       │   ├── server.py        # NEW: FastAPI server for this agent.
│       │   └── handlers/
│       └── data_engineer/
│           ├── agent.py
│           ├── server.py        # NEW: FastAPI server for this agent.
│           └── handlers/
└── infrastructure/
    ├── __init__.py
    ├── communication/           # NEW: Module for communication channels
    │   ├── __init__.py
    │   ├── a2a_channel.py       # NEW: A2A Client implementation.
    │   └── memory_channel.py
    ├── llm_graph_transformer.py
    └── neo4j_graph.py
```

### 3.8. Technical Implementation Details
- **Agent Lifecycle:** An agent's lifecycle will now include a `register()` method called on startup.
- **Agent-Specific Handlers:** Complex logic for processing commands will be encapsulated in dedicated handler classes within each agent's `handlers` submodule.
- **Communication:** Agents will continue to use the `CommunicationChannel` and the `CommandBus` for interactions after discovery.
- **Refactoring Plan:** Once this PRD is approved, the existing code in `src/application/agents.py` will be migrated to this new, more modular structure, and the dynamic discovery logic will be implemented.

## 4. Non-Functional Requirements
- The system will remain containerized with Docker, with separate roles for each agent.
- The command pattern and dependency injection will be used to keep the codebase clean and testable.
- The codebase will be fully linted and tested.

---

## Appendix: The Five Architectural Pillars

This project is built upon five core architectural pillars that guide its design and implementation:

1.  **Core Architecture: Collaborative Multi-Agent System**
    *   A system of two specialized, collaborating agents (`DataArchitectAgent` and `DataEngineerAgent`) forms the foundation, enabling a distributed, divide-and-conquer approach to complex data tasks.

2.  **Communication Protocol: Google A2A & MCP**
    *   The adoption of Google's A2A protocol for inter-agent communication and MCP for standardized tool use ensures the system is robust, scalable, and interoperable with a wider ecosystem.

3.  **Discovery Mechanism: Hybrid Model**
    *   A hybrid discovery model using both standard `agent.json` files and a dynamic Knowledge Graph registry provides a powerful, flexible way for agents to find and learn about each other.

4.  **Application Structure: Modular and Clean**
    *   A strict "one object per file" policy and a modular directory structure for agents and their handlers ensure the codebase is clean, maintainable, and easy to reason about.

5.  **Logic Abstraction: A2A Skills as Commands**
    *   The use of the Command and Adapter patterns to translate incoming A2A skill requests into internal commands decouples the business logic from the communication protocol, maximizing testability and flexibility. 