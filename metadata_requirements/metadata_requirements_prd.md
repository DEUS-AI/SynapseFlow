# Metadata Graph Management PRD

## Overview

This document describes the requirements for implementing metadata graph management in the multi‑agent system. The objective is to transform Data Delivery Agreements (DDAs) into a structured metadata knowledge graph that captures assets such as databases, clusters, schemas, tables and columns, along with their attributes (tags, watermarks, descriptions) and interactions with users and workflows. The approach complements neural extraction and symbolic reasoning to ensure robust, scalable and explainable metadata management【244507880803558†L8-L20】.

## Goals

* Define a metadata ontology and relationships for representing data assets and their dependencies.
* Provide agent‑driven and centralized workflows to parse DDAs into a knowledge graph.
* Support multiple input formats for DDAs (Markdown, PDF, DOCX) via MarkItDown.
* Ensure consistency, scalability and explainability of metadata updates.
* Support multiple graph backends (Graphiti, Neo4j/FalkorDB) for dev and production environments.
* Integrate with the MCP for side services and future extensibility【244507880803558†L16-L20】.

## User Stories

* As a **Data Architect**, I want DDAs to be parsed automatically into the metadata graph, so I can focus on data modeling.
* As a **Data Engineer**, I want to query and update metadata with confidence that updates are validated and consistent【244507880803558†L25-L27】.
* As a **Knowledge Manager**, I want to review, validate and reason over metadata changes and resolve conflicts.
* As a **System Admin**, I want to monitor metadata graph operations and audit trails【244507880803558†L21-L31】.

## Requirements

* **R1: Metadata Entities and Relationships** – Define core entities: `Database`, `Cluster`, `Schema`, `Table`, `Column`, `ColumnStats`, `Tag`, `Watermark`, `Description`, `User`, `AirflowDag`. Define relationships as in the domain model: `has_cluster`, `has_schema`, `belongs_to_schema`, `has_tag`, `has_watermark`, `has_description`, `has_column`, `has_stats`, `write_to_table`, `read_by`, `owned_by`, `replicated_from`, `previous`. These should be configurable and extensible.
* **R2: DDA Parsing** – Implement a flexible parser capable of reading DDAs in Markdown/CSV/JSON formats and converting them into a structured model for ingestion.
* **R3: Event‑Driven and API‑Based Updates** – Provide both asynchronous (RabbitMQ/Flink) and synchronous (FastAPI) mechanisms to apply metadata changes to the graph【244507880803558†L32-L36】.
* **R4: Layered Knowledge Organization** – Organize metadata into layers (perception, semantic, reasoning, application) to separate extraction, mapping, validation and usage【244507880803558†L37-L39】.
* **R5: Validation and Conflict Resolution** – Provide rules and policies for validating metadata updates and resolving conflicts or duplicates.
* **R6: Audit, Rollback and Monitoring** – Maintain audit trails, enable rollback and expose metrics for metadata operations【244507880803558†L40-L46】.
* **R7: Extensibility** – Allow schema extensions and integration with additional backends and services (MCP, model backends).
* **R8: Access Control** – Implement basic role‑based access control (RBAC) across roles (Data Architect, Data Engineer, Knowledge Manager, System Admin)【244507880803558†L49-L50】.

## Success Criteria

* A complete metadata ontology defined and used across the agents.
* End‑to‑end tests verifying that DDA documents are parsed and inserted into the graph.
* Demonstrated ability to update the graph and roll back changes.
* Documentation of APIs, workflows and policies.
* Support for multiple backends and integration with the MCP and telemetry【244507880803558†L54-L62】.