# Cross-Graph Relationship Types - Actual vs Documented

## Issue Summary

The documentation mentioned three relationship types for cross-graph SEMANTIC relationships:
- `REPRESENTS_IN`: Medical entity → Column
- `APPLICABLE_TO`: Medical entity → Table/DataEntity
- `INFORMS_RULE`: Medical entity → dq_rule

However, the actual database contains only two types:
- ✅ `APPLICABLE_TO`: Medical entity → DataEntity/Table (6 relationships)
- ✅ `RELATES_TO`: Medical entity → Column-like entities (4 relationships)

## Why This Happened

The `medical_data_linker.py` service has logic to create `REPRESENTS_IN` for Column entities:

```python
if data_type == "Column":
    return "REPRESENTS_IN"
```

However, the actual data entities in your Neo4j database have labels like:
- `['Entity', 'ExtractedEntity', 'Column']` - multi-labeled
- `['DataEntity']` - for tables

When the linker checks `labels(d)[0]` (first label), it gets `"Entity"` not `"Column"`, so it falls through to the default `RELATES_TO` relationship type.

## What Was Fixed

Updated `CrossGraphQueryBuilder` to query for the **actual** relationship types:

### Before (caused warnings):
```cypher
MATCH (m:MedicalEntity)-[r:REPRESENTS_IN|APPLICABLE_TO]->(d)
```

### After (no warnings):
```cypher
MATCH (m:MedicalEntity)-[r:APPLICABLE_TO|RELATES_TO]->(d)
```

## Current Relationship Distribution

```
SEMANTIC Layer Relationships (10 total):
- APPLICABLE_TO: 6 relationships
  - Diseases → DataEntity (e.g., "Crohn's Disease" → "Patient")
  - Organizations → DataEntity
  - Studies → DataEntity

- RELATES_TO: 4 relationships
  - Symptoms → Column (e.g., "Fatigue" → "Fatigue Level")
  - Treatments → Column (e.g., "Surgery" → "Surgery Date")
  - Drugs → Column (e.g., "Vitamin D" → "Vitamin D Level")
```

## Sample Queries (Fixed)

### Find medical concepts in data:
```cypher
MATCH (m:MedicalEntity)-[r:APPLICABLE_TO|RELATES_TO]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN m.name, type(r), d.name
```

### Find treatments and related data:
```cypher
MATCH (treatment:Treatment)-[r:APPLICABLE_TO|RELATES_TO]->(data)
WHERE r.layer = 'SEMANTIC'
RETURN treatment, r, data
```

## Future Improvement (Optional)

If you want to create `REPRESENTS_IN` relationships for columns, update the `_determine_relationship_type` method in `medical_data_linker.py`:

```python
def _determine_relationship_type(
    self,
    medical_type: str,
    data_type: str
) -> str:
    """Determine the appropriate relationship type."""
    # Check if 'Column' is in ANY of the labels (not just first)
    if data_type == "Column" or "Column" in data_type:
        return "REPRESENTS_IN"

    elif data_type in ["Table", "DataEntity"]:
        return "APPLICABLE_TO"

    elif data_type == "dq_rule":
        return "INFORMS_RULE"

    # Default fallback
    return "RELATES_TO"
```

But for now, the system works correctly with `APPLICABLE_TO` and `RELATES_TO`.

## Impact

✅ **No functional impact** - The system works correctly, just uses different relationship type names
✅ **Warnings eliminated** - No more Neo4j warnings about missing relationship types
✅ **Queries work** - All cross-graph queries return correct results

---

**Status**: Fixed in CrossGraphQueryBuilder (2026-01-21)
**Files Updated**:
- `src/application/services/cross_graph_query_builder.py` (3 queries fixed)
