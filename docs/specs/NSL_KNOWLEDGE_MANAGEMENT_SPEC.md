# Technical Specification: Neurosymbolic Knowledge Management

## 1. Architecture Overview
- **Layered Knowledge Model:**
  - Perception Layer: Neural extraction of entities/relations from documents (using MarkItDown for conversion from PDF, DOCX, etc. to Markdown)
  - Semantic Layer: Mapping to ontology/KG, normalization, linking (dynamic and extendable, inspired by Data Vault 2.0)
  - Reasoning Layer: Symbolic rules, validation, inference (start simple, evolve to advanced logic/metaprogramming)
  - Application Layer: Agent/user interaction, queries, updates
- **Knowledge Management Approaches:**
  - Hybrid (default): Agents handle simple KG updates, escalate complex ones to a dedicated agent/service. Configurable for dedicated/integrated/hybrid.
- **Event-Driven/API-Based Updates:**
  - FastAPI for APIs, RabbitMQ for event-driven updates (Flink for future stream processing)
  - Agents emit events or call API for KG operations
  - Knowledge manager processes events/requests, updates KG, applies reasoning
- **KG Backends:**
  - Graphiti (primary)
  - FalkorDB (for local/dev, configurable)
  - Model backend replacement supported (e.g., OpenAI → Ollama)
- **MCP Integration:**
  - Use MCP for side service integration and extensibility

## 2. Components
- **MarkItDown Wrapper:** Utility for converting documents to Markdown
- **KnowledgeManagerAgent/Service:** Handles centralized KG updates, validation, reasoning (for escalated/complex ops)
- **Agent KG Update Logic:** For integrated/hybrid approach, agents update KG directly for simple ops
- **Event Bus/API:** FastAPI endpoints, RabbitMQ event bus
- **Layered KG Data Structures:** Classes/modules for each knowledge layer, dynamic ontology
- **Audit & Monitoring:** Logging, rollback, metrics (OpenLLMetry for telemetry)
- **RBAC:** Basic role-based access control (four roles)
- **MCP Client:** For side service communication

## 3. Interfaces
- **KG Update API:** REST/gRPC endpoints for create/update/query KG
- **Event Schema:** Standardized event format for KG operations
- **Agent Interfaces:** Methods for submitting, escalating, or validating KG updates
- **Monitoring API:** Expose metrics and audit logs (OpenLLMetry)
- **MarkItDown API:** For document conversion
- **MCP API:** For side service integration

## 4. Workflows
- **Neural Extraction → KG Update:**
  1. Agent converts document to Markdown (MarkItDown)
  2. Agent extracts entities/relations
  3. Agent emits event or calls API with extracted data
  4. Knowledge manager validates, applies rules, updates KG (Graphiti/FalkorDB)
  5. Audit/logging, error handling, and feedback to agent
- **Batch/Concurrent Processing:**
  - Multiple agents or documents processed in parallel, with conflict resolution and queueing
- **Rollback/Error Recovery:**
  - On failure, revert KG to previous state, notify agents (future phase)

## 5. Layered Knowledge Organization
- **Perception Layer:** Extraction models, MarkItDown adapters
- **Semantic Layer:** Ontology mapping, entity/relationship classes (dynamic)
- **Reasoning Layer:** Rule engine, validation logic (evolving)
- **Application Layer:** Agent APIs, user interfaces, analytics

## 6. Configuration & Extensibility
- Configurable KG backend (Graphiti, FalkorDB)
- Configurable knowledge management mode (dedicated, integrated, hybrid)
- Pluggable event bus/API implementations
- Extensible rule and ontology modules
- Model backend replacement (OpenAI, Ollama, etc.)

## 7. Security & Access Control
- Basic RBAC (four roles)
- Validation and sanitization of all inputs

## 8. Documentation
- API reference, user/developer guides, architecture diagrams (Markdown, docs/specs folder) 