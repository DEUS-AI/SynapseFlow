# Unified Neo4j Architecture for Neurosymbolic AI

## Overview

This document describes the consolidated Neo4j-based architecture for medical knowledge graphs and DDA metadata, implementing the DIKW hierarchy for neurosymbolic AI validation workflows.

---

## Architecture Decision

**Status**: ✅ Implemented (as of latest migration)

**Decision**: Use Neo4j as the unified backend for ALL knowledge graphs:
- Medical Knowledge Graph (from PDF ingestion)
- DDA Metadata Graphs (from DDA processing)
- Cross-Graph SEMANTIC relationships

**Previously**: Medical KG in FalkorDB, DDA metadata in Neo4j (split architecture)

**Rationale**:
1. Enables seamless cross-graph queries
2. Simplifies entity linking (single database)
3. Supports neurosymbolic validation workflows
4. Reduces operational complexity

**Future**: Repository pattern for backend abstraction (Neo4j/FalkorDB selection via config)

---

## DIKW Knowledge Layers

The system implements a four-layer hierarchy for neurosymbolic reasoning:

```
┌─────────────────────────────────────────────────────┐
│  APPLICATION LAYER                                  │
│  - Query patterns                                   │
│  - Actionable insights                              │
│  - User-facing knowledge                            │
└─────────────────────────────────────────────────────┘
                      ▲
                      │
┌─────────────────────────────────────────────────────┐
│  REASONING LAYER                                    │
│  - Validated facts                                  │
│  - Inferred knowledge                               │
│  - Confidence-scored assertions                     │
└─────────────────────────────────────────────────────┘
                      ▲
                      │
┌─────────────────────────────────────────────────────┐
│  SEMANTIC LAYER                                     │
│  - Cross-graph relationships                        │
│  - Entity links (medical ↔ data)                    │
│  - Ontology mappings                                │
└─────────────────────────────────────────────────────┘
                      ▲
                      │
┌─────────────────────────────────────────────────────┐
│  PERCEPTION LAYER                                   │
│  - Raw entities from sources                        │
│  - Medical entities (from PDFs)                     │
│  - Data entities (from DDAs)                        │
└─────────────────────────────────────────────────────┘
```

### Layer Usage in Validation Workflow

Each layer serves a specific purpose in neurosymbolic reasoning:

1. **PERCEPTION Layer**: Raw facts extracted by neural models (LLMs)
   - No validation yet
   - Confidence scores from extraction model
   - Source attribution

2. **SEMANTIC Layer**: Relationships validated by symbolic rules
   - Entity linking strategies (exact, description, semantic, LLM)
   - Cross-graph bridges
   - Confidence ≥ 0.75 threshold

3. **REASONING Layer**: Inferred knowledge from hybrid (neural + symbolic)
   - ReasoningEngine applies rules
   - ValidationEngine checks constraints
   - Provenance tracking

4. **APPLICATION Layer**: Query patterns and actionable insights
   - User-facing knowledge
   - Optimized for retrieval
   - Derived from validated reasoning

---

## Entity Structure

### Medical Entities (from PDF Ingestion)

**Labels**: `MedicalEntity` + type-specific label (e.g., `Disease`, `Treatment`, `Drug`)

**Properties**:
```cypher
CREATE (n:MedicalEntity:Disease {
  name: "Crohn's Disease",
  type: "Disease",
  description: "Inflammatory bowel disease...",
  confidence: 0.92,
  source_document: "autoimmune_diseases.pdf",
  category: "general",
  layer: "PERCEPTION",
  created_at: "2026-01-21T10:30:00"
})
```

**Entity Types**:
- `Disease`: Medical conditions, syndromes
- `Treatment`: Therapies, procedures
- `Drug`: Medications, compounds
- `Symptom`: Clinical manifestations
- `Test`: Diagnostic tests, biomarkers
- `Gene`: Genetic markers
- `Pathway`: Biological pathways
- `Organization`: Research institutions
- `Study`: Clinical trials

### Data Entities (from DDA Processing)

**Labels**: `Table`, `Column`, `BusinessConcept`, `DataEntity`

**Properties** (Table example):
```cypher
CREATE (t:Table {
  name: "patient_treatments",
  description: "Patient treatment history",
  business_context: "Tracks medications prescribed...",
  domain: "immunology_schema",
  layer: "PERCEPTION",
  created_at: "2026-01-20T14:00:00"
})
```

**Entity Types**:
- `Table`: Database tables
- `Column`: Table columns with data types
- `BusinessConcept`: Domain concepts extracted by LLM
- `dq_rule`: Data quality rules

---

## Relationship Structure

### Medical Relationships (PERCEPTION Layer)

Between medical entities:

```cypher
(treatment:Treatment)-[:TREATS {
  description: "Anti-TNF therapy for IBD",
  layer: "PERCEPTION",
  created_at: "2026-01-21T10:30:00"
}]->(disease:Disease)
```

**Relationship Types**:
- `TREATS`: Treatment → Disease
- `CAUSES`: Factor → Disease
- `INDICATES`: Symptom → Disease
- `ASSOCIATED_WITH`: General association
- `TARGETS`: Drug → Pathway/Gene

### Cross-Graph Relationships (SEMANTIC Layer)

Between medical and data entities:

```cypher
(disease:MedicalEntity)-[:APPLICABLE_TO {
  confidence: 0.95,
  linking_strategy: "exact",
  reasoning: "Exact name match: 'Crohn's Disease' in 'crohns_data'",
  layer: "SEMANTIC",
  created_at: "2026-01-21T11:00:00"
}]->(table:Table)
```

**Relationship Types**:
- `REPRESENTS_IN`: Medical entity represented in column
- `APPLICABLE_TO`: Medical concept applies to table/domain
- `INFORMS_RULE`: Medical knowledge informs data quality rule

### DDA Metadata Relationships (Multi-Layer)

Between data entities:

```cypher
(table:Table)-[:HAS_COLUMN {
  layer: "PERCEPTION"
}]->(column:Column)

(table:Table)-[:TRANSFORMS_INTO {
  layer: "SEMANTIC"
}]->(target_table:Table)
```

---

## Data Ingestion Workflows

### 1. PDF → Medical KG (Neo4j)

**Service**: `Neo4jPDFIngestionService`

**Workflow**:
```
PDF File
  ↓ markitdown
Markdown
  ↓ LLM extraction (gpt-4o-mini)
Entities + Relationships (JSON)
  ↓ persist_to_neo4j()
Neo4j (MedicalEntity nodes, PERCEPTION layer)
```

**Code**:
```python
from application.services.neo4j_pdf_ingestion import Neo4jPDFIngestionService

service = Neo4jPDFIngestionService(
    pdf_directory=Path("PDFs"),
    openai_api_key=api_key
)

# Discover and process PDFs
documents = service.discover_pdfs()

for doc in documents:
    # Convert to markdown
    result = service.converter.convert(str(doc.path))

    # Extract knowledge
    extraction = await service.extract_knowledge(result.text_content, doc)

    # Persist to Neo4j with PERCEPTION layer
    await service.persist_to_neo4j(extraction)
```

### 2. DDA → Metadata Graph (Neo4j)

**Services**: `Data Architect Agent` → `Data Engineer Agent`

**Workflow**:
```
DDA Markdown File
  ↓ MarkdownDDAParser
DDADocument (parsed structure)
  ↓ ModelingCommand (Data Architect)
Architecture Graph (PERCEPTION layer)
  ↓ GenerateMetadataCommand (Data Engineer)
Metadata Graph (all 4 layers)
  ↓ LLM Enrichment
BusinessConcept nodes (SEMANTIC layer)
```

**Code**:
```python
from application.commands.modeling_command import ModelingCommand
from application.commands.metadata_command import GenerateMetadataCommand

# Parse DDA
parser = MarkdownDDAParser()
dda_doc = await parser.parse(str(dda_path))

# Phase 1: Architecture modeling
modeling_cmd = ModelingCommand(
    dda_path=str(dda_path),
    domain=dda_doc.domain
)
result = await command_bus.dispatch(modeling_cmd)

# Phase 2: Metadata generation
metadata_cmd = GenerateMetadataCommand(
    dda_path=str(dda_path),
    domain=dda_doc.domain,
    architecture_graph_ref=result["architecture_graph_ref"]
)
await command_bus.dispatch(metadata_cmd)
```

### 3. Cross-Graph Entity Linking

**Service**: `MedicalDataLinker`

**Workflow**:
```
Medical Entities (Neo4j)
          +
Data Entities (Neo4j)
          ↓
Multi-Strategy Matching
  - Exact name match
  - Description match
  - Semantic similarity
  - LLM inference
          ↓
EntityLink (confidence-scored)
          ↓
Create SEMANTIC relationships
```

**Code**:
```python
from application.services.medical_data_linker import MedicalDataLinker

linker = MedicalDataLinker()

# Create cross-graph links
result = await linker.link_medical_to_data(confidence_threshold=0.75)

print(f"Created {result.links_created} links")
print(f"  - Exact: {result.exact_count}")
print(f"  - Description: {result.description_count}")
```

---

## Query Patterns

### 1. Medical Knowledge Queries

**All diseases**:
```cypher
MATCH (d:MedicalEntity)
WHERE d.type = 'Disease' AND d.layer = 'PERCEPTION'
RETURN d.name, d.description
ORDER BY d.name
```

**Treatment relationships**:
```cypher
MATCH (treatment:MedicalEntity)-[r:TREATS]->(disease:MedicalEntity)
WHERE treatment.type = 'Treatment' AND disease.type = 'Disease'
RETURN treatment.name, disease.name, r.description
```

### 2. DDA Metadata Queries

**All tables in a domain**:
```cypher
MATCH (t:Table)
WHERE t.domain = 'immunology_schema'
RETURN t.name, t.description
```

**Table-column structure**:
```cypher
MATCH (t:Table)-[:HAS_COLUMN]->(c:Column)
WHERE t.name = 'patient_treatments'
RETURN t, c
```

### 3. Cross-Graph Queries

**Find tables containing data about a disease**:
```cypher
MATCH (disease:MedicalEntity {name: "Crohn's Disease"})
MATCH (disease)-[r:APPLICABLE_TO]->(table:Table)
WHERE r.layer = 'SEMANTIC'
RETURN disease.name, table.name, r.confidence, r.linking_strategy
```

**Medical concepts represented in data columns**:
```cypher
MATCH (med:MedicalEntity)-[r:REPRESENTS_IN]->(col:Column)
WHERE r.layer = 'SEMANTIC' AND r.confidence >= 0.85
MATCH (col)<-[:HAS_COLUMN]-(table:Table)
RETURN med.name, med.type, col.name, table.name
ORDER BY r.confidence DESC
```

**Full context for a medical entity**:
```cypher
MATCH path = (entity:MedicalEntity {name: "Vitamin D"})-[*1..2]-(related)
RETURN path
LIMIT 50
```

### 4. Layer-Filtered Queries

**PERCEPTION layer only** (raw extractions):
```cypher
MATCH (n)
WHERE n.layer = 'PERCEPTION'
RETURN labels(n) as type, count(n) as count
```

**SEMANTIC layer only** (validated relationships):
```cypher
MATCH ()-[r]-()
WHERE r.layer = 'SEMANTIC'
RETURN type(r) as rel_type, count(r) as count
```

**Cross-layer traversal**:
```cypher
MATCH (perception:MedicalEntity {layer: 'PERCEPTION'})
MATCH (perception)-[semantic:APPLICABLE_TO]-(data)
WHERE semantic.layer = 'SEMANTIC'
RETURN perception, semantic, data
LIMIT 25
```

---

## Current Statistics

**As of 2026-01-21**:

### Medical Knowledge Graph
- **Entities**: 234 (MedicalEntity nodes)
  - 201 migrated from FalkorDB
  - 33 newly ingested via Neo4jPDFIngestionService
- **Relationships**: 210 (TREATS, CAUSES, ASSOCIATED_WITH, etc.)
- **Layer**: PERCEPTION
- **Sources**: 18 PDFs in `PDFs/` directory

### DDA Metadata Graph
- **Entities**: 2,378 total
  - 96 Tables
  - 1,872 Columns
  - 410+ other (BusinessConcept, dq_rule, etc.)
- **Relationships**: 2,500+
- **Layers**: PERCEPTION → APPLICATION (all 4 layers)
- **Sources**: 19/20 DDAs processed from `examples/`

### Cross-Graph Integration
- **SEMANTIC Relationships**: 10
  - 8 exact name matches
  - 2 description matches
- **Confidence Range**: 0.85 - 0.95
- **Relationship Types**:
  - `REPRESENTS_IN`: Medical → Column
  - `APPLICABLE_TO`: Medical → Table

---

## Neo4j Browser Visualization

### Recommended Starting Query

```cypher
// View cross-graph integration
MATCH (m:MedicalEntity)-[r]->(d)
WHERE r.layer = 'SEMANTIC'
OPTIONAL MATCH (d)-[r2]-(related)
RETURN m, r, d, r2, related
LIMIT 100
```

This query shows:
- Medical entities (MedicalEntity nodes)
- SEMANTIC layer relationships
- Connected data entities (Table, Column)
- Related data structures

### Color-Coded Visualization

Configure Neo4j Browser:
- `MedicalEntity`: Blue
- `Table`: Green
- `Column`: Yellow
- `BusinessConcept`: Orange
- SEMANTIC relationships: Bold red lines

---

## Service Components

### Ingestion Services

1. **`Neo4jPDFIngestionService`**
   - File: `src/application/services/neo4j_pdf_ingestion.py`
   - Purpose: PDF → Medical KG (Neo4j)
   - Layer: PERCEPTION
   - Status: ✅ Active (replaces FalkorDB version)

2. **`Data Architect Agent`**
   - File: `src/application/agents/data_architect/agent.py`
   - Purpose: DDA → Architecture Graph
   - Layer: PERCEPTION
   - Status: ✅ Active

3. **`Data Engineer Agent`**
   - File: `src/application/agents/data_engineer/agent.py`
   - Purpose: Architecture → Metadata Graph (with LLM enrichment)
   - Layers: PERCEPTION → APPLICATION
   - Status: ✅ Active

### Integration Services

1. **`MedicalDataLinker`**
   - File: `src/application/services/medical_data_linker.py`
   - Purpose: Create cross-graph relationships
   - Layer: SEMANTIC
   - Strategies: exact, description, semantic (TODO), LLM (TODO)
   - Status: ✅ Active

2. **`CrossGraphQueryBuilder`** (PLANNED)
   - File: `src/application/services/cross_graph_query_builder.py`
   - Purpose: Query templates for cross-graph traversal
   - Status: 🔜 Phase 3

### Reasoning Services

1. **`ReasoningEngine`**
   - File: `src/application/agents/knowledge_manager/reasoning_engine.py`
   - Purpose: Neurosymbolic inference (neural + symbolic)
   - Layer: REASONING
   - Strategies: neural-first, symbolic-first, collaborative
   - Status: ✅ Active

2. **`ValidationEngine`**
   - File: `src/application/agents/knowledge_manager/validation_engine.py`
   - Purpose: SHACL validation + layer hierarchy checks
   - Layer: REASONING
   - Status: ✅ Active

3. **`IntelligentChatService`** (PLANNED)
   - File: `src/application/services/intelligent_chat_service.py`
   - Purpose: RAG + reasoning + validation for Q&A
   - Layers: Uses all layers
   - Status: 🔜 Phase 3

---

## Migration History

### Initial State (Before Consolidation)
- Medical KG: FalkorDB (`medical_knowledge` graph)
- DDA Metadata: Neo4j

### Migration Performed
**Script**: `demos/migrate_medical_entities_to_neo4j.py`

**Actions**:
1. Connected to both FalkorDB and Neo4j
2. Queried FalkorDB for all medical entities (201 entities, 170 relationships)
3. Copied entities to Neo4j with `MedicalEntity` label
4. Copied relationships preserving types
5. Added `migrated_at` timestamp

**Result**: Medical entities now exist in BOTH databases
- FalkorDB: Original source (read-only, deprecated for new work)
- Neo4j: Active backend for all queries and new ingestions

**Note**: Medical entities were COPIED, not moved. FalkorDB graph still exists but is no longer used.

---

## Future Enhancements

### Immediate (Phase 3)
- [ ] `IntelligentChatService`: RAG-based Q&A with reasoning
- [ ] `CrossGraphQueryBuilder`: Query template library
- [ ] Interactive chat demo (`demos/demo_intelligent_chat.py`)

### Short-Term
- [ ] Semantic similarity matching (embeddings-based)
- [ ] LLM-based inference matching for entity linking
- [ ] Enhanced confidence scoring models

### Long-Term
- [ ] Repository pattern for backend abstraction (Neo4j/FalkorDB/Graphiti)
- [ ] Conversation memory across chat sessions
- [ ] Proactive query suggestions
- [ ] Visual graph explorer UI
- [ ] Feedback learning for confidence updates

---

## References

- **Neo4j Queries**: See [NEO4J_QUERIES.md](NEO4J_QUERIES.md)
- **Plan**: See [memoized-dancing-moore.md](~/.claude/plans/memoized-dancing-moore.md)
- **Migration Script**: [demos/migrate_medical_entities_to_neo4j.py](demos/migrate_medical_entities_to_neo4j.py)
- **Neo4j Ingestion**: [src/application/services/neo4j_pdf_ingestion.py](src/application/services/neo4j_pdf_ingestion.py)
- **Medical Data Linker**: [src/application/services/medical_data_linker.py](src/application/services/medical_data_linker.py)

---

**Status**: ✅ Architecture Documented
**Date**: 2026-01-21
**Next**: Phase 3 - Intelligent Chat Interface
