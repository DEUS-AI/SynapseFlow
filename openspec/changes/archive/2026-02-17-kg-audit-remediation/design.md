## Context

The knowledge graph audit (2026-02-17) found 5 P0-critical issues blocking production readiness. This design covers Sprint 1: Security & Data Quality Foundation.

**Current state:**
- `neo4j_backend.py:443` — `delete_relationship()` uses `% relationship_type` string interpolation in Cypher, allowing injection
- `.env` is committed with a real OpenAI API key (`sk-proj-...`), eval key, and Neo4j Aura credentials in comments
- `composition_root.py` defaults Neo4j password to `"password"` (lines 219, 292); 4+ services fall back to empty string
- 30 remediation queries exist but **cytokine** and **chemical** have no mapping (9 and ~20 entities respectively)
- `EntityResolver` has 5 strategies (exact, fuzzy, embedding, graph, hybrid) but only resolves during entity creation — no batch deduplication pipeline exists
- 0% of entities have `_ontology_mapped=true` — remediation has never been executed on the live graph

## Goals / Non-Goals

**Goals:**
- Eliminate the Cypher injection vector in Neo4j backend
- Remove all committed secrets and enforce startup validation for required env vars
- Expand remediation queries to cover all entity types present in the graph
- Execute remediation against the live graph, achieving >80% ontology mapping
- Provide a batch deduplication pipeline to merge the 131 detected duplicate pairs

**Non-Goals:**
- Rewriting the backend interface (P1-1, separate change)
- Fixing the 74% orphan node problem (P0-3 — requires deduplication and remediation first)
- Adding health checks, metrics, or error handling overhaul (Sprint 3)
- Implementing relationship crystallization (Sprint 4)
- Modifying the FalkorDB or Graphiti backends

## Decisions

### D1: Cypher injection fix — input validation, not parameterization

Neo4j does not support parameterized relationship types in Cypher (`$rel_type` is not valid in `[r:$type]` patterns). Instead of parameterization:

- **Chosen approach**: Validate `relationship_type` against an allowlist regex (`^[A-Za-z_][A-Za-z0-9_]*$`) before interpolation. Reject any input containing backticks, brackets, braces, or Cypher keywords.
- **Alternative considered**: Using APOC `apoc.merge.relationship()` which accepts dynamic types — rejected because it adds an APOC dependency and changes query semantics.
- **Alternative considered**: Querying all relationship types first and matching against them — rejected as it adds a round-trip and race condition.

**Location**: `src/infrastructure/neo4j_backend.py`, `delete_relationship()` method (line 443). Audit all other methods for similar patterns.

### D2: Secrets management — .gitignore + env validation module

- **Remove `.env` from tracking**: Add `.env` to `.gitignore`, create `.env.example` with placeholder values, `git rm --cached .env`
- **Startup validation**: New module `src/infrastructure/config_validation.py` that validates required env vars at import time. Required vars: `NEO4J_URI`, `NEO4J_PASSWORD`, `OPENAI_API_KEY`. Optional with warnings: `REDIS_HOST`, `QDRANT_URL`.
- **Remove hardcoded defaults**: Replace `os.getenv("NEO4J_PASSWORD", "password")` with `os.environ["NEO4J_PASSWORD"]` (fail-fast) in `composition_root.py`. Keep empty-string fallbacks in services that receive password via constructor injection (they get it from composition root).
- **Rotate compromised keys**: Document that the exposed OpenAI key must be rotated immediately (out of scope for code changes but flagged in tasks).

### D3: Remediation query expansion — add cytokine and chemical mappings

Research shows most types the audit flagged as missing are actually covered:
- bacteria → organism (exists)
- species → organism (exists)
- cell → cell_type (exists via "cell type" alias)
- pathway → pathway (exists)
- study → study (exists)
- compound → drug (exists)

**Truly missing:**
- `cytokine` — add `cytokine_mapping` query + MEDICAL_TYPE_ALIASES entry mapping to new `cytokine` registry type (or map to `protein` if preferred — cytokines are signaling proteins)
- `chemical` — add `chemical_mapping` query + alias mapping to `drug` (chemicals in medical context are typically pharmaceutical compounds)

**Decision**: Map `cytokine → protein` (cytokines are a subclass of proteins) and `chemical → drug` (aligns with existing compound→drug mapping). Add both as MEDICAL_TYPE_ALIASES entries and REMEDIATION_QUERIES.

### D4: Batch deduplication — new service wrapping EntityResolver

The existing `EntityResolver` only resolves during entity creation (single-entity mode). For batch deduplication of the 131 audit-detected pairs:

- **New service**: `DeduplicationService` in `src/application/services/deduplication_service.py`
- **Approach**: Query Neo4j for all entities grouped by type, run case-insensitive exact match within each group, produce a merge plan
- **Merge strategy**: Keep the entity with (1) more relationships, (2) higher confidence, (3) earlier creation date. Transfer all relationships from the merged entity. Mark merged entity with `_merged_into=<winning_id>` before deletion (audit trail).
- **API**: `POST /api/ontology/deduplication/dry-run` (preview merge plan) and `POST /api/ontology/deduplication/execute` (execute merges)
- **Scope**: Start with exact case-insensitive matches only (131 pairs from audit). Fuzzy deduplication (Levenshtein ≥0.90) deferred to a follow-up change due to higher false-positive risk.

### D5: Remediation execution — dry-run first, then execute with backup

- Run `POST /api/ontology/remediation/dry-run` to validate all queries and preview impact
- Review no-op queries (queries matching zero entities) to confirm they're expected
- Export a pre-remediation graph snapshot via Cypher `CALL apoc.export.json.all()` or property backup query
- Run `POST /api/ontology/remediation/execute`
- Verify coverage improvement with `ontology_mapped_stats.cypher` from audit
- Document the `batch_id` for potential rollback

This is an operational step, not a code change — but requires the query expansion (D3) to be complete first.

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Relationship type allowlist too restrictive | Could reject valid types with unusual characters | Audit existing relationship types in graph first; use allowlist based on actual data |
| `.env` removal breaks developer workflow | Developers lose their local config | Provide `.env.example` with clear setup instructions; document in README |
| Cytokine→protein mapping is lossy | Loses specificity (cytokines are a protein subclass) | Add `_original_type` preservation in remediation query; can be refined later |
| Batch deduplication merges wrong entity | Data loss if merge direction is incorrect | Dry-run mode is mandatory before execute; merged entities marked not deleted immediately |
| Remediation execution on live graph | Could corrupt data if queries have bugs | Dry-run validation first; graph snapshot before execute; batch_id enables rollback |
| Exposed OpenAI key already compromised | Unauthorized API usage/billing | Flag for immediate rotation (task, not code) |

## Migration Plan

**Order of operations** (matches dependency chain from audit):
1. Fix Cypher injection (D1) — no data impact, pure code fix
2. Secure secrets (D2) — `.gitignore` + validation module + remove cached `.env`
3. Expand remediation queries (D3) — add cytokine/chemical mappings and aliases
4. Execute remediation (D5) — dry-run → snapshot → execute on live graph
5. Run deduplication (D4) — dry-run → review → execute after remediation stabilizes

**Rollback**: Each step is independently reversible. Remediation has built-in rollback via `batch_id`. Deduplication dry-run is non-destructive.

## Open Questions

- Should `cytokine` get its own registry entry in MEDICAL_ONTOLOGY_REGISTRY or just alias to `protein`? (Design assumes alias to protein)
- Should the deduplication API be added to the existing ontology router or a new dedicated router?
- Is the exposed OpenAI key still active? Rotation should happen before this change ships.
