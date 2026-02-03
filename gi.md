# Development Plan: Neurosymbolic Knowledge Management

## Phase 1: Architecture & Design
- [x] Finalize requirements and PRD (reflecting MarkItDown, Graphiti/FalkorDB, hybrid management, etc.)
- [x] Design layered knowledge architecture (perception, semantic, reasoning, application; dynamic ontology)
- [x] Choose between dedicated agent, integrated, or hybrid approach (default: hybrid, configurable)
- [x] Define event-driven/API-based update mechanism (FastAPI, RabbitMQ; Flink for future)
- [x] Plan for MCP integration and model backend replacement (OpenAI, Ollama)

## Phase 2: Core Implementation
- [x] Implement MarkItDown wrapper for document conversion (with robust integration tests)
- [x] Implement knowledge management agent/service (for escalated/complex ops)
- [ ] Integrate KG update logic into agents (for simple ops)
- [ ] Implement event bus (RabbitMQ) and API (FastAPI) for KG operations
- [ ] Implement layered knowledge organization in codebase (dynamic ontology)
- [ ] Add support for Graphiti and FalkorDB as KG backends (configurable)
- [ ] Integrate MCP for side service communication

## Phase 3: Advanced Features
- [ ] Add audit trail, rollback, and error recovery for KG updates (future phase)
- [ ] Implement batch and concurrent processing (with queueing)
- [ ] Add monitoring and metrics for KG management (OpenLLMetry)
- [ ] Add basic RBAC for access control (four roles)

## Phase 4: Testing & Documentation
- [ ] End-to-end and integration tests for all workflows
- [ ] Performance and scalability benchmarks
- [ ] Complete user and technical documentation (Markdown, docs/specs folder) 