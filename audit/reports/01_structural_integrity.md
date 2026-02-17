# Graph Structural Integrity Audit Report

**Date**: 2026-02-17
**Graph**: Neo4j at bolt://localhost:7687
**Total Nodes**: 5,915 | **Total Relationships**: 2,504

---

## Executive Summary

The knowledge graph has **critical structural issues**: 74% of nodes are orphans (zero relationships), 77% of nodes have no layer assignment, and 0% of entities have been ontology-mapped. The graph contains 131 duplicate entity pairs (case-insensitive) and 4,312 LayerTransition audit records that dominate the node count. However, there are zero dangling relationships, zero invalid layers, and zero layer-confidence inconsistencies among assigned nodes.

---

## Findings

### 1. Orphan Nodes (CRITICAL)

- **Count**: 4,400 nodes (74.4% of total)
- **Primary source**: 4,312 LayerTransition records (audit trail nodes with no outgoing edges)
- **Medical orphans**: Entities like Biomarkers (C3 Complement, Immunoglobulin A), Diseases (Alzheimer's, Lupus, Cancer), etc. that were created but never linked
- **Orphan source stats**: 0 nodes have `_orphan_source` set — the orphan classification remediation has never been executed

### 2. Dangling Relationships

- **Count**: 0
- **Status**: CLEAN — no relationships reference non-existent nodes

### 3. Invalid Layer Values

- **Count**: 0 with invalid values
- **Count with NULL layer**: 4,565 nodes (77.1% of total)
- **Breakdown of assigned layers**:
  - REASONING: 841 nodes
  - PERCEPTION: 288 nodes
  - SEMANTIC: 219 nodes
  - APPLICATION: 2 nodes
- **Note**: The 4,312 LayerTransition nodes correctly have NULL layer (they are audit records, not domain entities)

### 4. Layer-Confidence Inconsistencies

- **Count**: 0
- **Status**: CLEAN — all entities with assigned layers meet confidence thresholds

### 5. Duplicate Entities

- **Count**: 131 pairs detected (case-insensitive match within same type)
- **Pattern**: Capitalized vs. lowercase variants (e.g., "Aspirin" vs. "aspirin", "Lupus" vs. "lupus")
- **Types affected**: Disease (14 pairs), Drug (24+ pairs), Compound, Cytokine, Cell Type
- **Root cause**: Entity resolution not running during ingestion, or case-insensitive matching not enforced

### 6. Type Distribution (24 distinct types)

| Type | Count | | Type | Count |
|------|-------|-|------|-------|
| Organization | 215 | | Protein | 18 |
| Drug | 194 | | Biomarker | 16 |
| Disease | 179 | | Cytokine | 9 |
| Treatment | 151 | | Food Component | 7 |
| Gene | 134 | | Cell Type | 6 |
| Test | 102 | | Organism | 6 |
| Symptom | 91 | | Chemical | 4 |
| Pathway | 52 | | Compound | 4 |
| Study | 46 | | Virus | 4 |

Plus: Model Organism (2), Genus (2), Species (2), Bacteria (2), Guideline (1), Cell (1)

### 7. Label Distribution (56 distinct labels)

Top labels: LayerTransition (4,312), ExtractedEntity (726), MedicalEntity (522), Organization (215), Drug (194), Disease (179), Treatment (151), Gene (134), Test (102), Symptom (91), Document (80), Chunk (80), Column (74), Entity (63), Pathway (52), Message (48), Study (46)

### 8. Relationship Type Distribution (80 distinct types)

Top types: MENTIONS (1,040), LINKS_TO (737), ASSOCIATEDWITH (139), TREATS (129), INDICATES (101), HAS_CHUNK (80), HAS_COLUMN (74), HAS_MESSAGE (48), CONTAINS_TABLE (41), CAUSES (35)

### 9. Ontology Mapping Status

- **Entities with `_ontology_mapped=true`**: 0
- **Status**: The remediation pipeline has never been executed against this graph

### 10. Nodes Without Type Property

- **Count**: 50 (within LIMIT 50 query)
- **Labels**: Catalog, Schema, Table, Column — these are DDA (Data Architecture) entities that use labels instead of type property

---

## Unmapped Types (Registry vs. Graph Diff)

**Graph types NOT in UNIFIED_ONTOLOGY_REGISTRY**:
- `Chemical` (4 entities) — not a registered type
- `Compound` (4 entities) — alias maps to `drug` but not direct match
- `Bacteria` (2 entities) — alias maps to `organism` but not direct match
- `Species` (2 entities) — alias maps to `organism` but not direct match
- `Cell` (1 entity) — near-match to `cell_type` but not exact

**Registry types NOT in graph**:
- `anatomy`, `observation`, `measurement` (medical PERCEPTION)
- `mechanism`, `interaction` (medical REASONING)
- `condition`, `protocol` (medical SEMANTIC/APPLICATION)
- `report`, `dashboard`, `domain`, `data_product`, `person`, `team` (data architecture SEMANTIC)
- `concept`, `business_concept`, `rule`, `data_quality_rule`, `pipeline`, `workflow` (data architecture REASONING)
- `score`, `usage`, `decision`, `metric`, `kpi`, `policy`, `sla` (data architecture APPLICATION)

---

## Severity Assessment

| Finding | Severity | Impact |
|---------|----------|--------|
| 74% orphan nodes | **CRITICAL** | Most entities are disconnected, reducing graph utility |
| 77% missing layer assignment | **CRITICAL** | DIKW pyramid non-functional for majority of data |
| 0% ontology-mapped | **HIGH** | Canonical type normalization not applied |
| 131 duplicate pairs | **HIGH** | Inflated entity counts, incorrect aggregations |
| 5 unmapped graph types | **MEDIUM** | Remediation queries won't cover these entities |
| 0 dangling relationships | LOW (positive) | Graph referential integrity is sound |
| 0 layer-confidence issues | LOW (positive) | Assigned layers are consistent |

---

## Reusable Queries

All Cypher queries saved to `audit/queries/`:
- `orphan_nodes.cypher`, `dangling_relationships.cypher`, `invalid_layers.cypher`
- `null_layers_with_type.cypher`, `layer_confidence_issues.cypher`, `duplicate_entities.cypher`
- `type_distribution.cypher`, `label_distribution.cypher`, `layer_distribution.cypher`
- `rel_type_distribution.cypher`, `nodes_without_type.cypher`
- `ontology_mapped_stats.cypher`, `orphan_source_stats.cypher`
