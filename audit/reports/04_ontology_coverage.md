# Ontology Coverage Audit Report

**Date**: 2026-02-17
**Registry**: UNIFIED_ONTOLOGY_REGISTRY (50 types, 118 aliases)
**Graph**: 24 distinct types, 1,248 typed entities

---

## Executive Summary

The ontology registry defines 50 types with 118 aliases, but only 24 types appear in the live graph. **Zero entities have been ontology-mapped** (`_ontology_mapped=true` count: 0). The remediation pipeline has never been executed. Five graph types lack direct registry entries (Chemical, Compound, Bacteria, Species, Cell), though most resolve via aliases. The registry-to-graph drift ratio is 100% — no normalization has occurred.

---

## 1. Registry Inventory

### Data Architecture Domain (27 types)
- PERCEPTION: table, file, column, field, database, schema, system
- SEMANTIC: report, dashboard, domain, data_product, person, team
- REASONING: concept, business_concept, rule, data_quality_rule, process, pipeline, workflow
- APPLICATION: score, usage, decision, metric, kpi, policy, sla

### Medical Domain (23 types)
- PERCEPTION: symptom, test, observation, measurement, biomarker
- SEMANTIC: disease, condition, drug, treatment, anatomy, protein, organism, virus, cell_type, food_component
- REASONING: pathway, gene, mechanism, interaction
- APPLICATION: guideline, protocol, study, organization

### Alias Coverage
- **Medical aliases**: 59 entries (e.g., "medication" → "drug", "syndrome" → "disease")
- **Data architecture aliases**: 59 entries (e.g., "entity" → "table", "etl" → "process")

---

## 2. Graph-to-Registry Coverage

### Types IN graph AND in registry (directly or via alias): 19/24
| Graph Type | Registry Match | Via |
|-----------|---------------|-----|
| Organization | organization | Direct |
| Drug | drug | Direct |
| Disease | disease | Direct |
| Treatment | treatment | Direct |
| Gene | gene | Direct |
| Test | test | Direct |
| Symptom | symptom | Direct |
| Pathway | pathway | Direct |
| Study | study | Direct |
| Protein | protein | Direct |
| Biomarker | biomarker | Direct |
| Cytokine | — | **UNMAPPED** |
| Food Component | food_component | Alias |
| Cell Type | cell_type | Alias |
| Organism | organism | Direct |
| Virus | virus | Direct |
| Model Organism | organism | Alias |
| Genus | organism | Alias |
| Guideline | guideline | Direct |

### Types IN graph but NOT in registry: 5
| Graph Type | Count | Nearest Match | Action Needed |
|-----------|-------|---------------|---------------|
| Chemical | 4 | drug (via alias) | Add alias `chemical → drug` or new type |
| Compound | 4 | drug (via alias) | Already aliased in MEDICAL_TYPE_ALIASES |
| Bacteria | 2 | organism (via alias) | Already aliased |
| Species | 2 | organism (via alias) | Already aliased |
| Cell | 1 | cell_type (near-match) | Add alias `cell → cell_type` |
| Cytokine | 9 | — | Add as new type or alias to protein |

### Registry types NOT in graph: 26+
- Medical: anatomy, observation, measurement, mechanism, interaction, condition, protocol
- Data Architecture: ALL 27 types (no DDA entities have been ingested with type property)

---

## 3. Ontology Mapping Status

- **Entities with `_ontology_mapped=true`**: 0 out of 1,248 typed entities
- **Entities with `_canonical_type` set**: 0
- **Entities with `_orphan_source` set**: 0
- **Post-remediation drift**: N/A (remediation never executed)

---

## 4. Stale/Broken Alias Analysis

### Stale Aliases (source type not in graph)
The following alias source types have no matching entities in the graph:
- `medical condition`, `disorder`, `syndrome`, `illness` → disease
- `medication`, `pharmaceutical`, `medicine` → drug
- `therapy`, `procedure`, `intervention` → treatment
- `sign`, `manifestation`, `clinical sign` → symptom
- `diagnostic test`, `lab test`, `laboratory test` → test
- `genetic marker` → gene
- `biological pathway` → pathway
- `clinical trial`, `research study`, `trial` → study
- `institution`, `research institution`, `pharma company`, `university`, `hospital` → organization

**Assessment**: These are not truly "stale" — they are normalization aliases that will match during entity extraction. No action needed.

### Broken Aliases (target type not in registry)
- None found. All alias targets resolve to valid registry entries.

---

## 5. Drift Metrics

| Metric | Value |
|--------|-------|
| Total typed entities | 1,248 |
| Ontology-mapped entities | 0 |
| **Drift ratio** | **100%** (0/1,248 mapped) |
| Types with direct registry match | 19/24 (79%) |
| Types needing alias addition | 2 (Cytokine, Cell) |
| Types resolvable via existing aliases | 3 (Compound, Bacteria, Species) |

---

## Recommendations

**P0**: Execute remediation pipeline dry-run to preview normalization impact
**P1**: Add missing aliases: `cytokine → protein` (or register as new type), `cell → cell_type`, `chemical → drug`
**P1**: Run full remediation execute to normalize all 1,248 typed entities
**P2**: Add normalization consistency check to ingestion pipeline (prevent drift at source)
