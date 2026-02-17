## 1. Environment Setup

- [x] 1.1 Verify Neo4j is running and accessible at bolt://localhost:7687 via docker-compose services
- [x] 1.2 Create `audit/` output directory for all audit reports and query scripts
- [x] 1.3 Verify Python environment has all required dependencies (`uv sync`)

## 2. Graph Structural Integrity Audit

- [x] 2.1 Write and execute Cypher query to detect all orphan nodes (zero relationships) — capture name, type, layer, labels, count
- [x] 2.2 Write and execute Cypher query to detect dangling relationships (missing source or target node)
- [x] 2.3 Write and execute Cypher query to find entities with null, empty, or invalid `layer` values (not in PERCEPTION/SEMANTIC/REASONING/APPLICATION)
- [x] 2.4 Write and execute Cypher query to find layer-confidence inconsistencies (SEMANTIC with confidence < 0.85, REASONING < 0.90)
- [x] 2.5 Write and execute Cypher query to detect duplicate entities (case-insensitive exact match within same type)
- [x] 2.6 Write and execute Cypher query to list all distinct `type` values in the graph with entity counts
- [x] 2.7 Diff graph types against unified registry (DATA_ONTOLOGY_REGISTRY + MEDICAL_ONTOLOGY_REGISTRY + MEDICAL_TYPE_ALIASES) to identify unmapped types
- [x] 2.8 Compile structural integrity summary report with counts and breakdowns per finding category
- [x] 2.9 Save all Cypher queries as reusable scripts in `audit/queries/` for future re-execution

## 3. Backend Consistency Analysis

- [x] 3.1 Compare all method signatures in Neo4jBackend, GraphitiBackend, FalkorBackend, InMemoryGraphBackend against KnowledgeGraphBackend abstract class
- [x] 3.2 Document serialization behavior differences for complex types (dict, list, Enum, None, datetime) across all 4 backends
- [x] 3.3 Identify all Cypher abstraction leaks — places where raw Cypher syntax is exposed through the backend interface
- [x] 3.4 Analyze FalkorBackend `run_in_executor()` pattern — document thread pool exhaustion risk, missing max_workers config, blocking call inventory
- [x] 3.5 Compare label handling across backends — document which backends support labels and the impact on cross-backend entity resolution
- [x] 3.6 Produce backend consistency severity matrix (critical/high/medium/low) organized by backend pair

## 4. Feature Completeness Inventory

- [x] 4.1 Run automated grep scan for TODO/FIXME/HACK/XXX across `src/` (excluding .venv, __pycache__, node_modules)
- [x] 4.2 Classify each finding into taxonomy: incomplete-feature, technical-debt, known-bug, missing-test, placeholder
- [x] 4.3 Map dependency chains between incomplete features (which features block others)
- [x] 4.4 Assign T-shirt size effort estimates (S/M/L/XL) to each feature using anchors: S=single file, M=multi-file same-service, L=cross-service, XL=architectural
- [x] 4.5 Group features by system area: agents, services, api, infrastructure, domain
- [x] 4.6 Rank each feature P0–P3 based on data integrity impact, user-facing impact, dependency position, and effort-to-value ratio

## 5. Ontology Coverage Audit

- [x] 5.1 Query all distinct `type` values from Neo4j and compare against MEDICAL_TYPE_ALIASES — identify stale aliases (source type not in graph) and broken aliases (target type not in registry)
- [x] 5.2 Query entities with `_ontology_mapped=true` and verify `_canonical_type` matches current alias/registry mappings — detect post-remediation drift
- [x] 5.3 Produce orphan node statistics broken down by `_orphan_source` (episodic/knowledge/unclassified) with top 5 examples per source
- [x] 5.4 Calculate registry-vs-graph drift ratio: (unmapped entity count) / (total entity count)
- [x] 5.5 Compile ontology coverage report with unmapped type inventory, stale alias list, drift metrics

## 6. Remediation Pipeline Assessment

- [x] 6.1 Compare graph entity types against REMEDIATION_QUERIES match patterns — identify types not covered by any remediation query
- [x] 6.2 Execute dry-run and identify no-op queries (queries matching zero entities) — flag as stale/misconfigured
- [x] 6.3 Assess rollback completeness — verify rollback handles: partial batches, `_consistency_fixed`, `_needs_review`/`_review_reason`, `_orphan_source` properties
- [x] 6.4 Verify remediation idempotency — confirm double execution produces zero new mappings
- [x] 6.5 Compile remediation pipeline assessment with coverage gaps, rollback gaps, and idempotency findings

## 7. Test Coverage Gap Analysis

- [x] 7.1 Run `uv run pytest --cov=src --cov-report=json` and extract per-module coverage percentages
- [x] 7.2 Identify modules with zero test coverage
- [x] 7.3 Map critical KG operations to test files: layer transitions (all 4 paths), entity resolution (all 5 strategies), crystallization, remediation (dry-run/execute/rollback), agent escalation
- [x] 7.4 Identify untested error paths: connection failures, invalid data, concurrent modification, timeouts
- [x] 7.5 Identify missing integration tests: ingestion→extraction→storage→query, conversation→episodic→crystallization→Neo4j, remediation full cycle, agent escalation flow
- [x] 7.6 Produce test coverage gap summary ranked by risk: critical (untested mutations), high (untested errors), medium (untested happy paths), low (untested utilities)

## 8. Operational Readiness Assessment

- [x] 8.1 Audit API routers for missing request/response logging, query counters, response time tracking
- [x] 8.2 Check for health check endpoints covering: Neo4j, Graphiti/FalkorDB, Redis, Qdrant, RabbitMQ connectivity
- [x] 8.3 Review error handling patterns: bare exception catches, generic 500s, swallowed exceptions, missing retry logic for transient failures
- [x] 8.4 Scan for hardcoded secrets, missing env var validation, sensitive config in logs
- [x] 8.5 Review docker-compose files for: dependency ordering, volume persistence, resource limits, restart policies, network isolation
- [x] 8.6 Produce operational readiness maturity matrix across 5 dimensions (observability, reliability, security, deployment, scalability) with ratings (not-started/basic/intermediate/production-ready)

## 9. Consolidated Recommendations Document

- [x] 9.1 Aggregate all findings from tasks 2–8 into a single audit report document
- [x] 9.2 Assign P0–P3 priority to each finding (cap P0 at 5 items, P1 at 10)
- [x] 9.3 Map each P0/P1 recommendation to a proposed OpenSpec change name (kebab-case)
- [x] 9.4 Order recommendations by dependency — changes that unblock others listed first
- [x] 9.5 Add effort estimates and suggested sprint assignments for P0/P1 items
- [x] 9.6 Final review: verify all spec requirements are covered, no audit dimension is missed, and the document is actionable
