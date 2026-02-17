# Backend Consistency Analysis Report

**Date**: 2026-02-17
**Backends Analyzed**: Neo4jBackend, GraphitiBackend, FalkorBackend, InMemoryGraphBackend
**Abstract Interface**: `KnowledgeGraphBackend` (src/domain/kg_backends.py)

---

## Executive Summary

The four backend implementations have **significant interface violations** and **incompatible serialization behaviors**. Two backends (Neo4j, InMemory) add extra parameters to `add_entity()`, Neo4j adds parameters to `query()`, and each backend serializes complex types differently. There is one **Cypher injection vulnerability** in Neo4j's `delete_relationship()`. FalkorDB's async wrapper risks thread pool exhaustion. Label handling is inconsistent across all backends.

---

## 1. Interface Method Coverage

### Abstract Interface (4 required methods)

| Method | Neo4j | Graphiti | Falkor | InMemory |
|--------|-------|----------|--------|----------|
| `add_entity(entity_id, properties)` | EXTENDED | OK | OK | EXTENDED |
| `add_relationship(source, type, target, props)` | OK | OK | OK | OK |
| `rollback()` | NO-OP | NO-OP | Functional | Functional |
| `query(query_str)` | EXTENDED | OK | OK | OK |

### Additional Methods (beyond interface)

- **Neo4jBackend**: 16 additional methods (get_entity, update_entity_properties, list_entities, list_relationships, delete_entity, delete_relationship, add_entity_with_layer, promote_entity, get_promotion_candidates, list_entities_by_layer, get_layer_statistics, create_layer_indexes, query_raw, close, __aenter__, __aexit__)
- **InMemoryGraphBackend**: 1 additional method (list_relationships)
- **GraphitiBackend**: 0 additional methods
- **FalkorBackend**: 0 additional methods

---

## 2. Signature Mismatches (CRITICAL)

### add_entity() — labels parameter added
- **Abstract**: `add_entity(self, entity_id: str, properties: Dict[str, Any]) -> None`
- **Neo4jBackend**: adds `labels: List[str] = None`
- **InMemoryGraphBackend**: adds `labels: List[str] = None`
- **Impact**: Callers passing labels will fail on Graphiti and Falkor backends. Violates Liskov Substitution Principle.

### query() — parameters parameter added
- **Abstract**: `query(self, query: str) -> Any`
- **Neo4jBackend**: adds `parameters: Optional[Dict[str, Any]] = None`, returns `Dict[str, Any]`
- **Impact**: Parameterized queries only work on Neo4j. Other backends silently ignore parameters.

---

## 3. Serialization Behavior Differences

| Type | Neo4j | Graphiti | Falkor | InMemory |
|------|-------|----------|--------|----------|
| dict | Direct (Neo4j handles) | JSON string | JSON string | Direct (Python) |
| list | Direct | JSON string | JSON string | Direct |
| Enum | `.value` extracted | Not handled | `str(.value)` | Not handled |
| None | Preserved as null | Preserved | **Filtered out** | Preserved |
| datetime | Mixed (ISO + Cypher) | Python object | `str()` | Python object |

**Key Risk**: Swapping backends causes data loss (None filtering in Falkor) and type mismatches (JSON strings vs. native types).

---

## 4. Cypher Abstraction Leaks

| Location | Pattern | Severity |
|----------|---------|----------|
| neo4j_backend.py:443 | `% relationship_type` string interpolation in DELETE query | **CRITICAL** (injection) |
| neo4j_backend.py:97-100 | f-string with `{label_str}` for label interpolation | HIGH |
| neo4j_backend.py:126 | f-string with `{safe_rel_type}` for relationship type | HIGH |
| falkor_backend.py:88 | f-string `MERGE (n:{label}` | HIGH |
| falkor_backend.py:145-147 | f-string for source/target labels | HIGH |
| falkor_backend.py:182,188 | f-string for label in MATCH queries | HIGH |

**Neo4j sanitization** (line 126): `replace(":", "_").replace(" ", "_").upper()` — minimal, doesn't cover all injection vectors.
**Falkor sanitization**: None.

---

## 5. FalkorDB Async Pattern Risk

- **Pattern**: `await loop.run_in_executor(None, lambda: self.graph.query(...))` used 4 times
- **max_workers**: NOT CONFIGURED (defaults to 5 * CPU_count)
- **Thread pool exhaustion risk**: HIGH — no queue depth management, no backpressure
- **Additional issues**:
  - Repeated `get_event_loop()` calls instead of caching
  - Lambda closures create unnecessary overhead
  - Should use `asyncio.to_thread()` (Python 3.9+) instead

---

## 6. Label Handling Inconsistencies

| Aspect | Neo4j | Graphiti | Falkor | InMemory |
|--------|-------|----------|--------|----------|
| Default label | `:Entity` | `:Entity` | From entity_id convention | None |
| Custom labels | Via `labels` param | Not supported | Via `label:id` format | Via `labels` param |
| Query by label | Inconsistent (some `:Entity`, some any) | Always `:Entity` | Always from convention | Not supported |
| Promotion labels | Discards original, only `:Entity` | N/A | N/A | N/A |

---

## Severity Matrix

| Issue | Neo4j-Graphiti | Neo4j-Falkor | Neo4j-InMemory | Graphiti-Falkor |
|-------|---------------|--------------|----------------|-----------------|
| Signature mismatch | **CRITICAL** | CRITICAL | MEDIUM | OK |
| Serialization | HIGH | HIGH | LOW | MEDIUM |
| Label handling | HIGH | HIGH | MEDIUM | MEDIUM |
| Rollback behavior | MEDIUM | MEDIUM | MEDIUM | OK |
| Cypher exposure | N/A | HIGH | N/A | N/A |

---

## Recommendations

**P0 (Critical)**:
1. Fix Cypher injection in `neo4j_backend.py:443` — use parameterized queries
2. Standardize `add_entity()` signature — add `labels` to abstract interface or remove from implementations

**P1 (High)**:
3. Standardize `query()` signature — add `parameters` to abstract interface
4. Add label sanitization to FalkorBackend
5. Configure `max_workers` for FalkorBackend thread pool
6. Implement serialization adapters for backend portability

**P2 (Medium)**:
7. Make rollback consistent (either all functional or document no-op behavior)
8. Add cross-backend compatibility test suite
9. Consolidate datetime handling in Neo4jBackend
