## Why

SynapseFlow's knowledge graph has grown organically across multiple backends (Neo4j, Graphiti, FalkorDB), 4 DIKW layers, a multi-agent system, and a medical ontology — but there has been no systematic audit of the graph's structural integrity, completeness, or operational readiness. Recent remediation work (conversation-node reclassification, ontology type completeness, batch remediation API) exposed gaps piecemeal; a comprehensive audit is needed to surface all remaining issues at once and produce a prioritized roadmap for the next development cycle.

## What Changes

- **Graph integrity analysis**: Audit all entity types, relationships, and layer assignments across Neo4j and Graphiti backends for orphan nodes, dangling relationships, missing ontology mappings, and layer-assignment violations
- **Backend consistency review**: Identify impedance mismatches between the 4 backend implementations (Neo4j, Graphiti, Falkor, InMemory) — serialization differences, Cypher abstraction leaks, missing capabilities
- **Feature completeness inventory**: Catalog all TODO/FIXME/incomplete features (text-to-Cypher mock, relationship crystallization, medical assistant Phase 2E, validation engine graph queries, auto-promotion scanner) with effort estimates and dependency mapping
- **Ontology coverage audit**: Validate the unified registry (DATA + MEDICAL) against actual graph data — unmapped types, missing aliases, orphan classification gaps beyond the recently-added FoodComponent/Genus/ModelOrganism mappings
- **Test coverage gap analysis**: Map test coverage against critical KG operations — identify untested paths in layer transitions, entity resolution strategies, crystallization pipeline, and remediation rollback
- **Observability and operational readiness assessment**: Evaluate API metrics gaps, missing health checks, logging coverage, and production deployment readiness
- **Prioritized recommendations document**: Produce a ranked action plan (P0/P1/P2/P3) with concrete next steps, estimated scope, and dependency ordering

## Capabilities

### New Capabilities

- `kg-structural-integrity`: Audit rules and queries for detecting orphan nodes, dangling relationships, layer-assignment violations, and duplicate entities across Neo4j and Graphiti
- `backend-consistency`: Analysis of backend abstraction gaps — serialization mismatches, Cypher leakage, missing interface methods, async wrapper risks (FalkorDB thread pool)
- `feature-completeness-inventory`: Structured inventory of all incomplete features with dependency mapping, effort estimation, and prioritized implementation order
- `test-coverage-gaps`: Gap analysis mapping test coverage against critical KG code paths — layer transitions, entity resolution, crystallization, remediation, agent escalation
- `operational-readiness`: Assessment of observability, API metrics, health checks, error handling, and production deployment readiness

### Modified Capabilities

- `ontology-type-completeness`: Extend the existing ontology type audit beyond FoodComponent/Genus/ModelOrganism to cover ALL unmapped types, stale aliases, and registry-vs-graph drift
- `kg-remediation-api`: Evaluate current remediation pipeline completeness — identify remediation query gaps, untested rollback scenarios, and missing dry-run coverage

## Impact

- **Code**: All 4 backend implementations (`infrastructure/`), all services in `application/services/`, all 4 agents, API routers, domain models and ontology registry
- **APIs**: KG query endpoints, remediation API, crystallization API, evaluation endpoints — audit may recommend new health/metrics endpoints
- **Dependencies**: graphiti-core version pinning, FalkorDB async wrapper, sentence-transformers for entity resolution, RabbitMQ event bus reliability
- **Systems**: Neo4j (primary), Graphiti/FalkorDB (episodic), Redis/Qdrant (memory), RabbitMQ (events) — all infrastructure services assessed for operational gaps
- **Downstream**: Recommendations document will directly inform the next 2-3 development sprints and may trigger new OpenSpec changes for each P0/P1 item
