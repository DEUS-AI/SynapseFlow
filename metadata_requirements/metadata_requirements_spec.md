# Technical Specification: Metadata Graph Management

## 1. Architecture Overview

- **Entity and Relationship Model:** Represent each metadata entity as a node type with properties. Relationships correspond to edges. Entities include **Database**, **Cluster**, **Schema**, **Table**, **Column**, **ColumnStats**, **Tag**, **Watermark**, **Description**, **User** and **AirflowDag**. Relationships include `has_cluster`, `has_schema`, `belongs_to_schema`, `has_tag`, `has_watermark`, `has_description`, `has_column`, `has_stats`, `write_to_table`, `read_by`, `owned_by`, `replicated_from` and `previous`.
- **Layered Knowledge Model:** Adopt the layered architecture from neurosymbolic knowledge management with perception (parsing and extraction), semantic (ontology mapping), reasoning (validation and inference) and application (agent interactions) layers【900895539951631†L2-L10】.
- **Hybrid Knowledge Management:** Support integrated and dedicated modes; simple updates are executed by the agent itself, while complex validations are escalated to a centralized knowledge manager【900895539951631†L11-L18】.
- **Event‑Driven/API Updates:** Provide FastAPI endpoints and RabbitMQ events for graph updates. Agents use these mechanisms to submit changes; the knowledge manager applies reasoning and persists to Graphiti or Neo4j【900895539951631†L14-L19】.
- **Graph Backends:** Use Graphiti as the primary backend; allow fallback to Neo4j/FalkorDB for local development【900895539951631†L20-L23】.
- **MCP Integration:** Use the MCP client for side service communication and extensibility【900895539951631†L24-L26】.

## 2. Components

- **MetadataParserFactory:** Provides parser implementations for the supported DDA formats (Markdown, CSV, JSON). Returns a `MetadataParser` which produces a structured object model.
- **MetadataModeler:** Contains functions to map parsed metadata into a graph document; interacts with Graphiti to create episodes, groups, nodes and relationships.
- **KnowledgeManagerAgent:** Handles centralized validation, reasoning and conflict resolution; runs rules to ensure consistency and triggers rollbacks when necessary【900895539951631†L29-L33】.
- **Event Bus and API:** RabbitMQ for asynchronous updates; FastAPI for synchronous operations. Agents either emit events or call APIs【900895539951631†L14-L19】.
- **Layered Data Structures:** Define classes for each knowledge layer to support dynamic ontology extension【900895539951631†L34-L35】.
- **Audit & Monitoring:** Use OpenLLMetry for telemetry and logging; maintain rollback data for error recovery【900895539951631†L36-L37】.
- **RBAC:** Implement role‑based access control across endpoints and events【900895539951631†L38-L39】.
- **MCP Client:** Connect to external services for data enrichment or notifications【900895539951631†L40-L49】.

## 3. Interfaces

- **Graph API:** Create, update, query and delete nodes and edges; filter by entity type or relationship; support bulk operations. Use REST/gRPC endpoints.
- **Event Schema:** Define a standard message format for metadata operations (create/update/delete) including entity type, attributes and context.
- **Parser Interface:** Accept file paths or raw content; output structured metadata objects.
- **Monitoring API:** Expose metrics, audit logs and system health【900895539951631†L46-L47】.
- **MCP API:** Provide hooks for asynchronous service calls (e.g., notifications, third‑party integrations)【900895539951631†L48-L49】.

## 4. Workflows

- **DDA Parsing and Graph Update:**
  1. An agent retrieves a DDA document and converts it to Markdown (via MarkItDown).
  2. The MetadataParser extracts entities and relationships from the DDA.
  3. The agent emits an event or calls the graph API with the extracted data.
  4. The KnowledgeManagerAgent validates the changes, applies any reasoning rules and persists to the graph backend.
  5. Audit logs are recorded and feedback returned to the agent【900895539951631†L50-L57】.
- **Batch & Concurrent Updates:** Agents or services process multiple documents or updates concurrently; a queue manager ensures order and conflict resolution【900895539951631†L58-L60】.
- **Error Handling & Rollback:** On failure, revert the graph to a previous snapshot and inform the agent【900895539951631†L61-L63】.

## 5. Layered Knowledge Organization

- **Perception Layer:** Contains extraction models and document conversion adapters【900895539951631†L64-L66】.
- **Semantic Layer:** Handles ontology mapping and entity normalization【900895539951631†L66-L68】.
- **Reasoning Layer:** Houses the rule engine and validation logic【900895539951631†L68-L69】.
- **Application Layer:** Provides APIs, agent interfaces and user tools for interacting with the graph【900895539951631†L69-L70】.

## 6. Extensibility & Configuration

- Configurable graph backend: Graphiti vs. Neo4j/FalkorDB【900895539951631†L72-L73】.
- Configurable knowledge management mode (dedicated, integrated or hybrid)【900895539951631†L72-L73】.
- Pluggable event bus/API implementations【900895539951631†L74-L75】.
- Extensible rule modules and ontology definitions【900895539951631†L75-L76】.
- Replaceable model backends (OpenAI, Ollama, etc.)【900895539951631†L76-L77】.

## 7. Security & Access Control

- Enforce RBAC across all endpoints and events【900895539951631†L78-L80】.
- Sanitize and validate all inputs to prevent injection.

## 8. Documentation

Maintain a `docs/specs` folder with API references, developer guides and architecture diagrams【900895539951631†L82-L83】.