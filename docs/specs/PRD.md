# Product Requirements Document

## Overview
This project implements a multi-agent system where agents collaborate through a shared knowledge graph generated via `LLMGraphTransformer`. The goal is to enable an architect agent (Arx) and a developer agent (D) to discuss, design, and implement software solutions. Agents will communicate using the Google A2A framework and persist symbolic knowledge to Neo4J.

## Objectives
- Support Python **3.12**.
- Containerized agents using **Docker** and orchestrated via a `make` target (e.g. `make run ROLE=arx`).
- Package management with **uv**.
- Provide SDK and CLI entry points for interacting with the system.
- Enforce clean code with linting, formatting, and pre-commit hooks.
- Unit tests covering core components.
- Clean architecture with an abstract command pattern for the primary use case (executing commands); other use cases may follow standard implementations.
- Integrate `LLMGraphTransformer` for generating knowledge graphs shared through Neo4J.

## Functional Requirements
1. **Agent Roles**
   - Architect (Arx) focuses on high-level design and problem solving.
   - Developer (D) handles implementation and may challenge the design.
2. **Communication**
   - Agents exchange messages using Google A2A.
   - Discussion results are stored as nodes/relationships in Neo4J.
3. **Command Execution**
   - Commands follow an abstract command pattern allowing extensibility.
   - A CLI will expose command execution and agent interactions.
4. **Knowledge Sharing**
   - `LLMGraphTransformer` converts dialogues and artifacts into a graph format.
   - Each agent may read/write to specific subgraphs.
5. **Testing and Quality**
   - Pre-commit configured with lint (e.g. `ruff` or `flake8`) and formatting (e.g. `black`).
   - Unit tests executed via `pytest`.
6. **Deployment**
   - Provide Dockerfiles for agent containers.
   - A make target simplifies running a given agent role.

## Non‑Functional Requirements
- Code base adheres to clean architecture principles: separation of concerns, domain-driven design, and decoupled infrastructure.
- Dependencies managed using `uv` for reproducible builds.
- Documentation includes usage instructions and development guidelines.

