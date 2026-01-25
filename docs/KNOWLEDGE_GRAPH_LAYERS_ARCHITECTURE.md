# Knowledge Graph Layered Architecture

## Overview

This document describes the theoretical foundation and implementation approach for the 4-layer knowledge graph architecture used in the Medical Knowledge Graph system.

---

## Theoretical Foundation

### The Three Interconnected Graph Types

Based on [Enterprise Knowledge's semantic layer framework](https://enterprise-knowledge.com/graph-analytics-in-the-semantic-layer-architectural-framework-for-knowledge-intelligence/):

| Graph Type | Purpose | Our Implementation |
|------------|---------|-------------------|
| **Metadata Graph** | Data about data - lineage, ownership, security, governance | **DDAs (Data Delivery Agreements)** |
| **Knowledge Graph** | Business meaning and context - domain concepts | **PDFs (Medical Knowledge)** |
| **Analytics Graph** | Derived insights, patterns, computed relationships | **Chat/Reasoning output** |

### The Ontological Layering Model

From robotics knowledge representation research and [Blindata's ontology modeling](https://blindata.io/blog/2024/ontologies-for-semantic-modeling/):

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  How knowledge is consumed: queries, chat, recommendations   │
├─────────────────────────────────────────────────────────────┤
│                    REASONING LAYER                           │
│  Inferred knowledge: computed relationships, derived facts   │
├─────────────────────────────────────────────────────────────┤
│                    SEMANTIC LAYER                            │
│  Canonical concepts: ontology, business meaning, validated   │
├─────────────────────────────────────────────────────────────┤
│                    PERCEPTION LAYER                          │
│  Raw extracted data: PDFs, documents, sensor data            │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer Definitions

### PERCEPTION Layer (Raw Extraction)

**Purpose**: Store raw extracted data before validation and canonicalization.

**Source**: PDFs about autoimmune diseases, raw document extractions

**Content**:
- Extracted entities (Disease, Treatment, Drug, Gene, Pathway)
- Raw relationships from text
- Confidence scores from LLM extraction
- Source document metadata

**Required Properties**:
- `source` - Origin document or system
- `origin` - How the data was captured
- `confidence` - Extraction confidence (0.0-1.0)
- `extraction_timestamp` - When extracted

**Example Node**:
```cypher
(:Entity:Disease {
  name: "Crohn's disease",
  layer: "PERCEPTION",
  source_document: "ibd_treatment.pdf",
  confidence: 0.85,
  raw_text: "Crohn's disease is a chronic inflammatory...",
  extraction_timestamp: datetime()
})
```

### SEMANTIC Layer (Canonical Knowledge)

**Purpose**: Store validated, canonicalized concepts linked to standard ontologies.

**Source**:
- DDAs (Data Delivery Agreements) - business/technical metadata
- Validated PERCEPTION entities promoted after review
- Medical ontologies (SNOMED-CT, UMLS)

**Content**:
- Canonical concepts linked to standard ontologies
- Business definitions from DDAs
- Validated, deduplicated entities
- Domain relationships

**Required Properties**:
- `description` - Clear definition
- `domain` - Business/medical domain
- `validated` - Validation status
- `ontology_code` - Link to standard ontology (SNOMED, UMLS, etc.)

**Example Nodes**:
```cypher
// Medical concept from ontology
(:Concept:Disease {
  name: "Crohn's disease",
  layer: "SEMANTIC",
  snomed_code: "34000006",
  umls_cui: "C0010346",
  definition: "A chronic inflammatory bowel disease affecting the gastrointestinal tract",
  domain: "Gastroenterology",
  validated: true
})

// Data asset from DDA
(:DataAsset:Table {
  name: "patient_diagnoses",
  layer: "SEMANTIC",
  dda_source: "clinical_data_contract.md",
  business_owner: "Clinical Operations",
  contains_pii: true,
  description: "Patient diagnosis records with ICD-10 codes"
})
```

### REASONING Layer (Inferred Knowledge)

**Purpose**: Store computed/inferred knowledge derived from SEMANTIC and PERCEPTION layers.

**Source**:
- Reasoning engine computations
- Cross-domain inference rules
- Aggregated patterns

**Content**:
- Inferred relationships (drug interactions, contraindications)
- Aggregated patterns (treatment efficacy)
- Cross-domain connections
- Provenance chains

**Required Properties**:
- `confidence` - Inference confidence
- `reasoning` - Explanation of inference
- `derived_from` - Source entities/relationships
- `rule_applied` - Which inference rule produced this

**Example Node**:
```cypher
(:Inference:DrugInteraction {
  name: "Methotrexate-NSAID interaction",
  layer: "REASONING",
  derived_from: ["methotrexate", "ibuprofen"],
  confidence: 0.92,
  rule_applied: "nephrotoxicity_combination",
  reasoning: "Both drugs can cause kidney damage; combined use increases risk",
  evidence: ["study_123", "fda_warning"],
  inference_timestamp: datetime()
})
```

### APPLICATION Layer (Query Patterns)

**Purpose**: Store consumption patterns, cached results, and user interaction context.

**Source**:
- User interactions
- System queries
- Access patterns

**Content**:
- Common query patterns
- User session context
- Access patterns
- Cached reasoning results

**Required Properties**:
- `usage_context` - How/when used
- `access_pattern` - Query patterns
- `last_accessed` - Recency tracking

**Example Node**:
```cypher
(:QueryPattern {
  name: "treatment_options_for_disease",
  layer: "APPLICATION",
  cypher_template: "MATCH (d:Disease {name: $disease})-[:TREATED_BY]->(t:Treatment) RETURN t",
  usage_count: 1523,
  avg_response_time_ms: 45,
  last_accessed: datetime()
})
```

---

## Data Flow Between Layers

```
                     ┌──────────────────────┐
                     │   APPLICATION        │
                     │   (Patient Chat)     │
                     └──────────┬───────────┘
                                │ queries
                     ┌──────────▼───────────┐
                     │   REASONING          │
                     │   (Inference Engine) │
                     └──────────┬───────────┘
                                │ reasons over
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
┌─────────▼─────────┐ ┌─────────▼─────────┐ ┌─────────▼─────────┐
│ SEMANTIC          │ │ SEMANTIC          │ │ SEMANTIC          │
│ (Medical Ontology)│ │ (DDA Metadata)    │ │ (Business Context)│
└─────────┬─────────┘ └─────────┬─────────┘ └─────────┬─────────┘
          │ validated from      │ defines            │ enriches
          │                     │                     │
┌─────────▼─────────────────────▼─────────────────────▼─────────┐
│                     PERCEPTION                                 │
│         (PDF Extractions, Raw Data, Documents)                 │
└───────────────────────────────────────────────────────────────┘
```

### Promotion Rules (PERCEPTION → SEMANTIC)

Entities are promoted from PERCEPTION to SEMANTIC when:

1. **Confidence threshold met**: `confidence >= 0.85`
2. **Ontology match found**: Entity matches SNOMED-CT or UMLS concept
3. **Multiple source confirmation**: Same entity extracted from 2+ documents
4. **Manual validation**: Human reviewer approves promotion

### Inference Generation (SEMANTIC → REASONING)

Reasoning layer nodes are created when:

1. **Rule triggers**: Inference rule fires based on SEMANTIC relationships
2. **Pattern detected**: Statistical pattern identified across entities
3. **Cross-domain connection**: Link discovered between different domains
4. **Contradiction resolution**: Conflicting information reconciled

---

## DDA as Semantic Backbone

DDAs (Data Delivery Agreements) define the **SEMANTIC layer for data assets**:

```
DDA (Data Delivery Agreement)
├── Domain: Clinical Operations
├── Data Owner: Dr. Smith
├── Business Context: "Patient clinical data for IBD research"
├── Tables Delivered:
│   ├── patient_demographics
│   │   ├── Columns: patient_id, name, dob, ...
│   │   ├── Business Rules: "PII - requires consent"
│   │   └── Links to: Patient (SEMANTIC concept)
│   └── diagnoses
│       ├── Columns: diagnosis_id, icd10_code, ...
│       ├── Business Rules: "Must have valid ICD-10"
│       └── Links to: Disease (SEMANTIC concept)
└── Relationships:
    └── patient_demographics --[HAS_DIAGNOSIS]--> diagnoses
```

This creates the bridge between **technical metadata** (tables, columns) and **business knowledge** (diseases, treatments from PDFs).

---

## Medical Ontology Integration

### SNOMED-CT

According to [SNOMED CT research](https://pmc.ncbi.nlm.nih.gov/articles/PMC11494256/), SNOMED-CT contains:
- 350,000+ medical concepts
- 1.4 million relationships
- Hierarchical "is-a" relations
- Attribute relations (finding site, causative agent, etc.)

### UMLS (Unified Medical Language System)

UMLS provides a metathesaurus combining:
- Millions of biomedical concepts
- Relations under a common ontological framework
- Mappings between different terminologies

### Integration Approach

```cypher
// Link PERCEPTION entity to SEMANTIC ontology concept
MATCH (p:Entity {layer: "PERCEPTION", name: "Crohn's disease"})
MATCH (s:Concept {layer: "SEMANTIC", snomed_code: "34000006"})
MERGE (p)-[:MAPS_TO {confidence: 0.95, method: "exact_match"}]->(s)
SET p.promoted = true, p.semantic_link = elementId(s)
```

---

## Implementation Phases

### Phase 1: Establish SEMANTIC Layer Foundation
1. Import medical ontology subset (SNOMED-CT core for autoimmune diseases)
2. Process DDAs → Create SEMANTIC nodes for data assets
3. Link DDAs to ontology → Connect tables/columns to medical concepts

### Phase 2: Promote PERCEPTION to SEMANTIC
1. Match extracted entities to SNOMED-CT concepts
2. Deduplicate across PDF sources
3. Validate with confidence thresholds
4. Promote validated entities to SEMANTIC layer

### Phase 3: Enable REASONING Layer
1. Define inference rules (contraindications, treatment paths)
2. Run reasoning engine over SEMANTIC layer
3. Store inferred facts as REASONING layer nodes
4. Track provenance (which rules produced which facts)

### Phase 4: Optimize APPLICATION Layer
1. Capture query patterns from patient chat
2. Cache common reasoning chains
3. Build query templates for common questions

---

## Layer Requirements Summary

| Layer | Required Properties | Transition Criteria |
|-------|---------------------|---------------------|
| **PERCEPTION** | source, origin, confidence, extraction_timestamp | N/A (entry point) |
| **SEMANTIC** | description, domain, validated, ontology_code | confidence >= 0.85, ontology match |
| **REASONING** | confidence, reasoning, derived_from, rule_applied | Rule trigger, pattern detection |
| **APPLICATION** | usage_context, access_pattern, last_accessed | Query frequency, user demand |

---

## References

- [Graph Analytics in the Semantic Layer - Enterprise Knowledge](https://enterprise-knowledge.com/graph-analytics-in-the-semantic-layer-architectural-framework-for-knowledge-intelligence/)
- [The Metadata Knowledge Graph - Enterprise Knowledge](https://enterprise-knowledge.com/the-metadata-knowledge-graph/)
- [Enterprise Knowledge Graphs: The Importance of Semantics](https://enterprise-knowledge.com/enterprise-knowledge-graphs-the-importance-of-semantics/)
- [Best Practices for Enterprise Knowledge Graph Design](https://enterprise-knowledge.com/best-practices-for-enterprise-knowledge-graph-design/related/2/)
- [Ontologies for Semantic Modeling - Blindata](https://blindata.io/blog/2024/ontologies-for-semantic-modeling/)
- [SNOMED CT in Large Language Models - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11494256/)
- [Semantic Interoperability in Digital Health - 6B Health](https://6b.health/insight/semantic-interoperability-in-digital-health-from-terminologies-to-ontologies/)
- [From LLMs to Knowledge Graphs - Medium](https://medium.com/@claudiubranzan/from-llms-to-knowledge-graphs-building-production-ready-graph-systems-in-2025-2b4aff1ec99a)
- [Benchmark and Best Practices for Biomedical Knowledge Graph Embeddings - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7971091/)

---

## Related Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [NSL_KNOWLEDGE_MANAGEMENT_SPEC.md](../NSL_KNOWLEDGE_MANAGEMENT_SPEC.md) - Technical specification
- [NSL_KNOWLEDGE_MANAGEMENT_PRD.md](../NSL_KNOWLEDGE_MANAGEMENT_PRD.md) - Product requirements
