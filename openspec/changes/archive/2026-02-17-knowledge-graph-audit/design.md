## Context

SynapseFlow's knowledge graph spans 4 backends (Neo4j, Graphiti, FalkorDB, InMemory), a 4-layer DIKW pyramid, a unified ontology registry (DATA + MEDICAL with 50+ type mappings), 4 agents with escalation patterns, and ~40 services. Recent piecemeal remediation (conversation-node reclassification, FoodComponent/Genus/ModelOrganism mappings, batch remediation API) has addressed specific gaps but no holistic audit exists. The codebase has 102 test files but unknown effective coverage of critical KG paths. Multiple TODO/FIXME markers indicate incomplete features (text-to-Cypher, relationship crystallization, medical assistant Phase 2E, validation engine queries, auto-promotion scanner). This design describes how to execute a systematic audit and produce an actionable recommendations document.

## Goals / Non-Goals

**Goals:**

- Produce a complete structural integrity report for the Neo4j and Graphiti graph data (orphans, dangling rels, layer violations, unmapped types)
- Document all backend abstraction mismatches with concrete examples and severity ratings
- Catalog every incomplete feature (TODO/FIXME/HACK/XXX) with file location, description, dependency chain, and rough effort sizing (S/M/L/XL)
- Generate a test coverage gap matrix mapping critical KG operations to existing tests
- Assess production-readiness across observability, error handling, health checks, and deployment configuration
- Deliver a single prioritized recommendations document (P0–P3) that can be directly converted into OpenSpec changes

**Non-Goals:**

- Fixing any issues found — this audit produces the report, not the remediation
- Performance benchmarking or load testing (separate effort)
- Auditing the frontend (Astro/React) or CLI interface code
- Reviewing LLM prompt engineering or agent conversation quality
- Auditing authentication/authorization (no auth system exists yet)
- Database migration or schema changes — audit recommends but does not execute

## Decisions

### D1: Audit methodology — Static analysis + live graph queries

**Decision**: Combine static code analysis (grep for TODOs, interface comparison, test mapping) with live Cypher queries against Neo4j and Graphiti to assess actual graph state.

**Rationale**: Static analysis alone cannot detect orphan nodes, layer violations, or unmapped types in the live graph. Live queries alone cannot detect code-level issues like abstraction leaks or incomplete feature implementations. Both are needed for a complete picture.

**Alternatives considered**:
- Static-only audit: Faster but misses data-level issues. Rejected because the proposal explicitly requires graph integrity analysis.
- Full automated test suite approach: Would require writing new tests first, defeating the purpose of an audit that should inform what tests to write.

### D2: Audit scope boundary — All 4 backends, but live queries only against Neo4j

**Decision**: Review all 4 backend implementations for code-level issues. Execute live integrity queries only against Neo4j (and Graphiti's underlying Neo4j). Skip live queries against FalkorDB and InMemory.

**Rationale**: Neo4j is the production backend holding the canonical graph. Graphiti uses Neo4j underneath so the same queries apply. FalkorDB is a secondary/episodic backend without persistent production data. InMemory is test-only. Querying all backends would quadruple the effort without proportional value.

**Alternatives considered**:
- Query all backends: Comprehensive but impractical — FalkorDB may not be running, InMemory has no persistent state.
- Neo4j only (ignore Graphiti): Misses episodic memory layer issues. Rejected since Graphiti nodes are in the same Neo4j instance.

### D3: Recommendations format — Tiered priority with OpenSpec change mapping

**Decision**: Use a 4-tier priority system (P0: critical/blocking, P1: high/next-sprint, P2: medium/planned, P3: low/backlog). Each recommendation maps to a proposed OpenSpec change name so the roadmap is directly actionable.

**Rationale**: A flat list of findings is hard to act on. Priority tiers with pre-named changes let the team immediately create OpenSpec changes from the audit output, bridging the gap between "audit finding" and "actionable work item."

**Alternatives considered**:
- Flat severity list: Simpler but lacks actionability. Teams would still need to triage.
- JIRA/GitHub issues: External tool dependency. OpenSpec changes keep everything in-repo.

### D4: Feature inventory approach — Automated grep + manual classification

**Decision**: Use automated `grep -rn` for TODO/FIXME/HACK/XXX across `src/` to build the raw inventory, then manually classify each into categories (incomplete feature, technical debt, known bug, missing test) and estimate effort.

**Rationale**: Automated scanning ensures completeness. Manual classification adds the judgment needed for prioritization — a TODO in a critical path is very different from a TODO in a utility function.

### D5: Test coverage analysis — Coverage report + manual critical-path mapping

**Decision**: Run `pytest --cov=src --cov-report=html` for quantitative line coverage, then manually map critical KG operations (layer transitions, entity resolution, crystallization, remediation, agent escalation) to their test files to identify qualitative gaps.

**Rationale**: Line coverage numbers are misleading without understanding what's being tested. A service could have 90% line coverage but miss the critical error path. Combining quantitative coverage with manual critical-path analysis gives a true picture.

### D6: Ontology drift detection — Registry-vs-graph comparison queries

**Decision**: Query distinct `type` values from the Neo4j graph and diff against the unified ontology registry's known types. Any graph type not in the registry is "drifted" and needs classification.

**Rationale**: The registry defines what types should exist. The graph contains what types actually exist. The diff between them is the precise measure of ontology drift — more accurate than reviewing code alone.

## Risks / Trade-offs

**[Live graph queries require running Neo4j]** → Ensure docker-compose services are up before executing audit queries. Document all queries so they can be re-run later if services are unavailable during initial audit.

**[TODO grep may produce false positives]** → Filter to `src/` directory only. Exclude third-party code, generated files, and `node_modules`. Manual classification step catches remaining noise.

**[Audit findings may be overwhelming in volume]** → The P0–P3 tiering mitigates this. Cap P0 at max 5 items, P1 at max 10. Anything beyond goes to P2/P3. This forces ruthless prioritization.

**[Effort estimates are inherently imprecise]** → Use T-shirt sizes (S/M/L/XL) rather than hours/days. Anchor: S = single file change, M = multi-file same-service, L = cross-service, XL = architectural change. Good enough for sprint planning without false precision.

**[Audit may become stale quickly]** → Timestamp all findings. Design the integrity queries as reusable Cypher scripts that can be re-executed periodically, enabling future automated audits.

**[Backend comparison may reveal Graphiti as redundant]** → This is a valid finding, not a risk. If Graphiti adds no value over direct Neo4j, recommend evaluating its removal — but that decision is out of scope for this audit.

## Open Questions

- **Q1**: Should the audit include the evaluation framework (`eval/` endpoints and test harness) or treat it as a separate concern?
- **Q2**: Is there a preferred format for the recommendations document beyond markdown? (e.g., should it integrate with any project management tooling?)
- **Q3**: Are there specific areas the team already suspects are problematic and wants prioritized in the audit? (This would help focus the P0 tier.)
