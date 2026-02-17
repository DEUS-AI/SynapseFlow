# Post-Remediation Graph Statistics

**Date**: 2026-02-17
**Batch ID**: `20260217_remediation_01`
**Executed by**: kg-audit-remediation change (Sprint 1)

---

## Before vs After

| Metric | Before Remediation | After Remediation | Change |
|--------|-------------------|-------------------|--------|
| Total nodes | 5,915 | 5,915 | -- |
| Total relationships | 2,504 | 2,578 | +74 |
| Structural nodes marked | 0 | 945 | +945 |
| Ontology-mapped entities | 0 (0%) | 522 (100% of typed) | +522 |
| Orphan nodes flagged | 0 | 4,400 (74%) | +4,400 |
| Knowledge entities (typed, non-structural) | 1,248 | 522 | Reduced after structural marking |
| Duplicate pairs (actionable) | 131 | 0 | Resolved (131 were in structural nodes) |

## Ontology Mapping Breakdown

| Canonical Type | Count |
|---------------|-------|
| drug | 91 |
| organization | 81 |
| disease | 79 |
| treatment | 61 |
| gene | 52 |
| test | 45 |
| symptom | 39 |
| study | 19 |
| pathway | 18 |
| biomarker | 14 |
| protein | 11 (includes 2 cytokines) |
| organism | 7 |
| cell_type | 3 |
| virus | 2 |
| **Total** | **522** |

## Key Findings

1. **100% ontology mapping achieved** for all typed knowledge entities (522/522)
2. **945 structural nodes** correctly classified and excluded (Chunk, Document, ExtractedEntity, ConversationSession, Message)
3. **4,400 orphan nodes** flagged (74% of graph) — mostly Graphiti episodic nodes without relationships
4. **131 duplicate pairs** from the original audit were within structural/episodic nodes — no actionable duplicates remain among knowledge entities
5. **New query coverage**: Cytokine (2 mapped to protein) and Chemical (2 mapped to drug) queries working correctly

## Remaining Issues

- **74% orphan rate** persists — requires Graphiti relationship crystallization (Sprint 4)
- **4,448 nodes without type** — episodic nodes from Graphiti that don't carry type properties
- Structural nodes should be periodically archived to reduce graph size (P2-3)

## Remediation Rollback

If needed, rollback with:
```
POST /api/ontology/remediation/rollback/20260217_remediation_01
```
Pre-remediation snapshot at: `audit/reports/pre_remediation_snapshot.csv`
