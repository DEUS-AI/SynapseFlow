# PDF Ingestion Issues Analysis

**Date**: January 20, 2026
**Analysis of**: Background task bc83c8f (full re-ingestion with enhanced normalization)

---

## Executive Summary

The PDF ingestion process is running successfully but has identified **3 major categories of issues** that are causing data loss:

1. **LLM Extraction Inconsistencies** (~40-50% of relationships skipped)
2. **Cypher Label Syntax Errors** (spaces in entity types)
3. **PDF Conversion Warnings** (non-critical)

**Impact**: Estimated **30-40% of potential relationships are not being persisted** to the knowledge graph.

---

## Issue 1: LLM Relationship Extraction Inconsistency ⚠️ HIGH PRIORITY

### Problem Description

The LLM extracts relationships between entities, but the **target entity names don't match** the entity names in the entities list. This causes the relationship lookup to fail.

### Examples

**Document**: `autoimmune_diseases_and_your_environment_508.pdf`

Extracted relationships reference entities that **were never extracted as entities**:

1. **Relationship**: `Rheumatoid arthritis -> Stressful life events`
   **Issue**: "Stressful life events" was extracted as a relationship target but NOT as an entity
   **Available entities**: Autoimmune Diseases, Type 1 Diabetes, Lupus, Rheumatoid Arthritis, etc.

2. **Relationship**: `NIEHS -> Autoimmune Diseases`
   **Issue**: "NIEHS" (abbreviation) doesn't match "National Institute Of Environmental Health Sciences" (full name)
   **Available entities**: "National Institute of Environmental Health Sciences" (title case normalized)

3. **Relationship**: `EXACT-PLAN -> Autoimmune Diseases`
   **Issue**: "EXACT-PLAN" (abbreviation) doesn't match full entity name

### Root Cause

The LLM prompt asks for entities AND relationships in a single call. When creating relationships, the LLM:
- Sometimes uses **abbreviations** (NIEHS, NIH, EXACT-PLAN, EBV)
- Sometimes references **concepts not in the entity list** (e.g., "Stressful life events", "Agricultural chemicals", "Syphilis")
- Sometimes uses **different capitalization** than the normalized form

### Impact

**Quantitative**: In first 3 documents analyzed:
- Document 1: 13 relationships extracted, **6 skipped** (46% loss)
- Document 2: 7 relationships extracted, **2 skipped** (29% loss)
- Document 3: 19 relationships extracted, **13 skipped** (68% loss!)

**Average**: ~40-50% of relationships are being skipped due to entity name mismatches.

### Current Workaround

The entity lookup map tries multiple variations:
```python
entity_map[entity_name] = entity_id           # Normalized name
entity_map[entity_name_raw] = entity_id       # Original from LLM
entity_map[entity_name.lower()] = entity_id   # Lowercase
```

This helps but **doesn't catch abbreviations** or **completely different names**.

---

## Issue 2: Cypher Label Syntax Error ❌ CRITICAL

### Problem Description

Entity types with **spaces** cause Cypher syntax errors because they're used as node labels.

### Example

**Document**: `1745495737-en.pdf`

```
Failed to add entity Environmental Factor:Smoking:
errMsg: Invalid input 'F': expected a label, '{', a parameter or ')'
line: 1, column: 24, offset: 23
errCtx: MERGE (n:Environmental Factor {id: $id})
```

### Root Cause

The Cypher query attempts:
```cypher
MERGE (n:Environmental Factor {id: $id})
          ^^^^^^^^^^^^^^^^
          This is invalid! Labels cannot have spaces
```

Valid Cypher would be:
```cypher
MERGE (n:EnvironmentalFactor {id: $id})  # No spaces
```

or

```cypher
MERGE (n:`Environmental Factor` {id: $id})  # Backticks for spaces
```

### Impact

**All entities and relationships with multi-word types fail to persist**:
- "Environmental Factor" → 4 entities lost
- All relationships involving these entities → 4 relationships lost

This appears in **at least 1 document** so far (1745495737-en.pdf), but likely affects others.

### Affected Entity Types

From logs:
- `Environmental Factor` (spaces)

Potentially affected (common multi-word types):
- `Multiple Sclerosis` (if used as entity type instead of disease name)
- Any other LLM-generated types with spaces

---

## Issue 3: PDF Conversion Warnings ℹ️ LOW PRIORITY

### Problem Description

PDF parsing library (pdfminer) generates warnings about invalid color values in certain PDFs.

### Example

**Document**: `the-autoimmune-diseases-6nbsped-0128121025-9780128121023_compress.pdf`

```
WARNING - Cannot set gray non-stroke color because /'P1' is an invalid float value
WARNING - Cannot set gray non-stroke color because /'P2' is an invalid float value
... (35 warnings total)
```

### Root Cause

PDF has custom color palettes (`P1`, `P2`, etc.) that pdfminer doesn't recognize.

### Impact

**Non-critical**: Text extraction still works. These warnings don't affect the ingestion process, just clutter the logs.

---

## Issue 4: Apostrophe Normalization Still Has Edge Cases ⚠️ MEDIUM PRIORITY

### Problem Description

The apostrophe normalization fix (`'S ` → `'s `) works for most cases but still produces some variations.

### Examples From Logs

**Document**: `Bookshelf_NBK580299.pdf` shows:
- `Hashimoto'S Thyroiditis` (capital S after apostrophe - should be fixed by normalization)
- But normalized to: `Hashimoto's Thyroiditis` ✅ (normalization worked!)

**Document**: `1745495737-en.pdf` shows:
- `Crohn'S_Disease` (underscore in ID, capital S)

### Current Status

The normalization **IS working** (see line 116: `Hashimoto's thyroiditis` in entity map), but there may be edge cases.

**Verification needed**: Check final graph to confirm all apostrophe entities are properly normalized.

---

## Recommendations

### Priority 1: Fix Cypher Label Spaces (CRITICAL)

**Solution**: Sanitize entity types before using as Cypher labels.

**Implementation**:
```python
def _sanitize_label(self, entity_type: str) -> str:
    """Sanitize entity type for use as Cypher label."""
    # Remove spaces and special characters
    sanitized = entity_type.replace(" ", "").replace("-", "")
    # Ensure it starts with a letter
    if not sanitized[0].isalpha():
        sanitized = "Entity" + sanitized
    return sanitized
```

**Usage**:
```python
# Before
label = entity_type  # "Environmental Factor"

# After
label = self._sanitize_label(entity_type)  # "EnvironmentalFactor"
```

**Impact**: Prevents ~5-10% entity/relationship loss.

---

### Priority 2: Improve Relationship Matching (HIGH)

**Solution A**: Add abbreviation mapping
```python
ABBREVIATION_MAP = {
    "NIEHS": "National Institute of Environmental Health Sciences",
    "NIH": "National Institutes of Health",
    "EBV": "Epstein-Barr Virus",
    "EXACT-PLAN": "Exposome in Autoimmune Diseases Collaborating Teams Planning Awards",
    "CD": "Crohn's Disease",
    "UC": "Ulcerative Colitis",
    "MS": "Multiple Sclerosis",
    "RA": "Rheumatoid Arthritis",
    "SLE": "Systemic Lupus Erythematosus",
    # ... add more as discovered
}
```

**Solution B**: Fuzzy matching with entity names
```python
from difflib import get_close_matches

# If exact match fails, try fuzzy matching
if not source_id:
    matches = get_close_matches(
        source_name,
        entity_map.keys(),
        n=1,
        cutoff=0.8
    )
    if matches:
        source_id = entity_map[matches[0]]
```

**Solution C**: Two-pass extraction
1. **Pass 1**: Extract entities only
2. **Pass 2**: Extract relationships, but provide entity list in prompt

This would tell the LLM: "Only create relationships between these specific entities: [list]"

**Impact**: Could recover 30-40% of lost relationships.

---

### Priority 3: LLM Prompt Enhancement (MEDIUM)

**Current Issue**: LLM extracts relationships to entities it didn't include in the entity list.

**Enhanced Prompt**:
```
IMPORTANT:
1. First, extract ALL relevant entities (diseases, treatments, etc.)
2. Then, create relationships ONLY between entities you extracted
3. DO NOT reference entities in relationships that are not in your entity list
4. Use full entity names in relationships, not abbreviations
5. If an entity has an abbreviation (e.g., NIH), include both forms as separate entities or use the full name consistently
```

**Impact**: Reduces relationship mismatches by 20-30%.

---

### Priority 4: Monitoring and Logging Enhancement (LOW)

**Add Metrics**:
```python
# At end of each document
logger.info(f"""
Document: {doc.filename}
  Entities extracted: {len(entities)}
  Entities persisted: {entities_added}
  Entities failed: {len(entities) - entities_added}
  Relationships extracted: {len(relationships)}
  Relationships persisted: {relationships_added}
  Relationships skipped: {len(relationships) - relationships_added}
  Success rate: {relationships_added / len(relationships) * 100:.1f}%
""")
```

**Impact**: Better visibility into data quality issues.

---

## Summary Statistics (From Current Run)

### Per-Document Analysis

| Document | Entities Extracted | Entities Persisted | Relationships Extracted | Relationships Persisted | Success Rate |
|----------|-------------------|-------------------|------------------------|------------------------|--------------|
| autoimmune_diseases... | 14 | 14 | 13 | 7 | 53.8% |
| the-autoimmune-diseases... | 9 | 9 | 7 | 5 | 71.4% |
| jrcollphyslond... | 23 | 23 | 19 | 6 | 31.6% |
| ijms-25-07062... | 14 | 14 | 13 | 13 | 100% ✅ |
| Bookshelf_NBK608308 | 14 | 14 | 9 | 9 | 100% ✅ |
| Bookshelf_NBK580299 | 20 | 20 | 19 | 16 | 84.2% |
| NIH-Wide-Strategic... | 11 | 11 | 10 | 4 | 40.0% |
| 1745495737-en | 15 | **11** ❌ | 14 | 10 | 71.4% |
| en_1130-0108... | 13 | 13 | 10 | 10 | 100% ✅ |

### Overall Statistics (First 9 Documents)

- **Total Entities Extracted**: 133
- **Total Entities Persisted**: **129** (4 failed due to label syntax error)
- **Entity Success Rate**: 97.0%

- **Total Relationships Extracted**: 114
- **Total Relationships Persisted**: **80**
- **Relationships Skipped**: 34
- **Relationship Success Rate**: 70.2%

**Data Loss**: ~30% of relationships are being lost due to entity name mismatches and syntax errors.

---

## Next Steps

### Immediate Actions

1. **Fix Cypher label syntax** (1-2 hours of work)
   - Add `_sanitize_label()` method
   - Update entity persistence to use sanitized labels
   - Re-test with problematic document

2. **Add abbreviation mapping** (2-3 hours of work)
   - Create comprehensive abbreviation dictionary
   - Update entity lookup to check abbreviations
   - Test with documents that have high skip rates

3. **Monitor current ingestion** (ongoing)
   - Wait for full ingestion to complete
   - Verify final statistics
   - Check for Crohn's Disease duplication status

### Future Improvements

4. **Implement fuzzy matching** (4-6 hours)
5. **Enhance LLM prompt** (1-2 hours + testing)
6. **Add metrics dashboard** (4-8 hours)
7. **Consider two-pass extraction** (8-12 hours - major refactor)

---

## Files to Modify

1. **[src/application/services/simple_pdf_ingestion.py](src/application/services/simple_pdf_ingestion.py)**
   - Add `_sanitize_label()` method (line ~306)
   - Add `ABBREVIATION_MAP` constant (line ~105)
   - Update entity lookup in `persist_to_falkordb()` (line ~352)
   - Update LLM prompt (line ~63)

2. **[src/infrastructure/falkor_backend.py](src/infrastructure/falkor_backend.py)** (may need updates)
   - Verify Cypher query generation handles sanitized labels

---

## Conclusion

The ingestion process is **functional but losing ~30% of relationships** due to:
1. **Entity name mismatches** (abbreviations, different names) - 25-30% loss
2. **Cypher syntax errors** (spaces in labels) - 3-5% loss

**Recommended action**: Implement Priority 1 (Cypher label fix) and Priority 2 (abbreviation mapping) fixes before next full ingestion.

**Current run status**: Let it complete to get full statistics, then implement fixes and re-run.

---

**Report Generated**: January 20, 2026
**Estimated Completion Time**: 30-40 minutes remaining (9/18 documents processed)
