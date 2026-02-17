## 1. Cypher Injection Fix

- [x] 1.1 Create `validate_cypher_identifier()` utility in `src/infrastructure/cypher_utils.py` — regex allowlist `^[A-Za-z_][A-Za-z0-9_]*$`, reject empty/backtick/keywords, raise `ValueError`
- [x] 1.2 Fix `delete_relationship()` in `neo4j_backend.py:443` — call `validate_cypher_identifier(relationship_type)` before `%` interpolation
- [x] 1.3 Audit all other Cypher string interpolation in `neo4j_backend.py` — scan for `%s`, `.format(`, f-strings in query strings; add validation to each
- [x] 1.4 Write tests for `validate_cypher_identifier()` — valid types, injection attempts, empty strings, backticks, reserved words
- [x] 1.5 Write tests for `delete_relationship()` with malicious input — verify `ValueError` is raised before any query execution

## 2. Secrets Management

- [x] 2.1 Add `.env` to `.gitignore` and run `git rm --cached .env` to stop tracking the file (already done — .env is in .gitignore and not tracked)
- [x] 2.2 Create `.env.example` with placeholder values for all required and optional variables
- [x] 2.3 Create `src/infrastructure/config_validation.py` — validate required vars (`NEO4J_URI`, `NEO4J_PASSWORD`, `OPENAI_API_KEY`) at import time; warn on missing optional vars (`REDIS_HOST`, `QDRANT_URL`)
- [x] 2.4 Remove hardcoded `"password"` defaults from `composition_root.py` (lines 219, 292) — use `os.environ["NEO4J_PASSWORD"]` (fail-fast)
- [x] 2.5 Import `config_validation` in `composition_root.py` so validation runs before service initialization
- [x] 2.6 Write tests for config validation — missing required var exits, missing optional var warns, all present succeeds
- [x] 2.7 Add task note: rotate the exposed OpenAI API key (`sk-proj-lQX...`) immediately — this is an operational step, not a code change

## 3. Ontology Alias Expansion

- [x] 3.1 Add `"cytokine" → "protein"` and `"cytokines" → "protein"` to `MEDICAL_TYPE_ALIASES` in `src/domain/ontologies/odin_medical.py`
- [x] 3.2 Add `"chemical" → "drug"` and `"chemicals" → "drug"` to `MEDICAL_TYPE_ALIASES`
- [x] 3.3 Write tests verifying `resolve_medical_type("Cytokine")` returns `"protein"` and `resolve_medical_type("Chemical")` returns `"drug"`

## 4. Remediation Query Expansion

- [x] 4.1 Add `cytokine_mapping` query to `REMEDIATION_QUERIES` in `remediation_service.py` — match `type IN ['Cytokine', 'cytokine', 'Cytokines', 'cytokines']` or label `Cytokine`, set `_canonical_type='protein'`, `_original_type=n.type`
- [x] 4.2 Add `chemical_mapping` query to `REMEDIATION_QUERIES` — match `type IN ['Chemical', 'chemical', 'Chemicals', 'chemicals']` or label `Chemical`, set `_canonical_type='drug'`, `_original_type=n.type`
- [x] 4.3 Write tests for both new remediation queries — verify correct property assignments and skip-when-already-mapped behavior

## 5. Entity Deduplication Service

- [x] 5.1 Create `src/application/services/deduplication_service.py` with `DeduplicationService` class — constructor takes Neo4j backend dependency
- [x] 5.2 Implement `detect_duplicates()` — query all entities grouped by type, find case-insensitive name matches, return list of pairs with entity IDs, names, relationship counts, confidence scores
- [x] 5.3 Implement `create_merge_plan()` — for each pair, select winner (most relationships > highest confidence > earliest created), return structured plan
- [x] 5.4 Implement `execute_merge(plan)` — transfer relationships from loser to winner (skip duplicate relationships), set `_merged_into` and `_merged_date` on loser, delete loser node, return summary
- [x] 5.5 Add `POST /api/ontology/deduplication/dry-run` endpoint to ontology router — calls `detect_duplicates()` + `create_merge_plan()`, returns plan
- [x] 5.6 Add `POST /api/ontology/deduplication/execute` endpoint — calls full pipeline, returns `total_merged`, `total_relationships_transferred`, `batch_id`
- [x] 5.7 Write tests for duplicate detection — case-insensitive matches, different-type exclusion, already-merged exclusion
- [x] 5.8 Write tests for merge execution — relationship transfer, duplicate relationship handling, `_merged_into` audit trail

## 6. Remediation Execution (Operational)

- [x] 6.1 **[OPERATIONAL]** Run `POST /api/ontology/remediation/dry-run` against live graph — review output, confirm no-op queries are expected, verify new cytokine/chemical queries match entities
- [x] 6.2 **[OPERATIONAL]** Export pre-remediation graph snapshot (property backup query or `CALL apoc.export.json.all()`)
- [x] 6.3 **[OPERATIONAL]** Run `POST /api/ontology/remediation/execute` — record `batch_id`, verify `coverage_after` > 80%
- [x] 6.4 **[OPERATIONAL]** Run `audit/queries/ontology_mapped_stats.cypher` to confirm coverage improvement
- [x] 6.5 **[OPERATIONAL]** Run deduplication dry-run, review merge plan, then execute deduplication
- [x] 6.6 **[OPERATIONAL]** Document final graph statistics (total nodes, orphan %, ontology mapping %, duplicate count) in audit report addendum
