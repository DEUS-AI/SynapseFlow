# DIKW-Aligned Knowledge Graph Architecture Plan

## Executive Summary

This document analyzes the current system architecture, proposes a DIKW-aligned revision, and identifies gaps based on neurosymbolic AI research. The goal is to align our 4-layer knowledge graph with the DIKW pyramid (Data → Information → Knowledge → Wisdom) while maintaining the existing codebase structure.

---

## Part 1: Current State Analysis

### 1.1 Current Flow Diagrams

#### FLOW 1: DDA Processing (Data Domain Architecture)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DDA PROCESSING FLOW                              │
│                                                                         │
│  User/API                                                               │
│     │                                                                   │
│     ▼                                                                   │
│  POST /api/dda/upload                                                   │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ MarkdownDDAParser (infrastructure/parsers/markdown_parser.py)   │   │
│  │   • Extracts: domain, stakeholders, data_owner                  │   │
│  │   • Extracts: entities with attributes, primary keys            │   │
│  │   • Extracts: relationships between entities                    │   │
│  │   • Extracts: business rules, governance, access patterns       │   │
│  │   • Returns: DDADocument model                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Neo4j Storage (main.py lines 534-635)                           │   │
│  │   • Catalog node (domain metadata)                              │   │
│  │   • Schema node (linked to Catalog)                             │   │
│  │   • Table nodes (from DDA entities)                             │   │
│  │   • Column nodes (from entity attributes)                       │   │
│  │   • RELATES_TO relationships between tables                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  CURRENT ISSUES:                                                        │
│  ❌ No layer assignment (should be PERCEPTION initially)               │
│  ❌ Business rules stored as text, not executable                      │
│  ❌ Data Engineer agent not invoked (direct Neo4j write)               │
│  ❌ Knowledge Manager validation skipped                               │
└─────────────────────────────────────────────────────────────────────────┘
```

#### FLOW 2: User Query / Chat

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER QUERY FLOW                                 │
│                                                                         │
│  User                                                                   │
│     │                                                                   │
│     ├──────────────────────┬────────────────────────────────────────┐   │
│     ▼                      ▼                                        │   │
│  WebSocket              POST /api/query                             │   │
│  /ws/chat/{patient_id}  (NeurosymbolicQueryService)                 │   │
│     │                      │                                        │   │
│     ▼                      ▼                                        │   │
│  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │ IntelligentChatService                                      │   │   │
│  │   1. Extract entities from question                         │   │   │
│  │   2. Load patient context (PatientMemoryService)            │   │   │
│  │   3. Query medical knowledge (Neo4j)                        │   │   │
│  │   4. Query data catalog context                             │   │   │
│  │   5. Find cross-graph relationships                         │   │   │
│  │   6. RAG document retrieval (FAISS)                         │   │   │
│  │   7. Apply neurosymbolic reasoning                          │   │   │
│  │   8. Validate facts (ValidationEngine)                      │   │   │
│  │   9. Generate LLM answer                                    │   │   │
│  │  10. Store conversation in patient memory                   │   │   │
│  └─────────────────────────────────────────────────────────────┘   │   │
│     │                                                               │   │
│     ▼                                                               │   │
│  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │ NeurosymbolicQueryService                                   │   │   │
│  │   • Detect query type (drug_interaction, symptom, etc.)     │   │   │
│  │   • Select strategy (SYMBOLIC_ONLY, NEURAL_FIRST, etc.)     │   │   │
│  │   • Traverse layers: APP → REASONING → SEMANTIC → PERCEPTION│   │   │
│  │   • Aggregate confidence across layers                      │   │   │
│  │   • Track response for RLHF feedback                        │   │   │
│  └─────────────────────────────────────────────────────────────┘   │   │
│                                                                     │   │
│  CURRENT ISSUES:                                                    │   │
│  ❌ Medical Assistant writes directly to Neo4j (no KM validation)  │   │
│  ❌ REASONING layer rarely populated (no automatic inference)      │   │
│  ❌ APPLICATION layer empty (no query pattern caching)             │   │
│  ❌ Cross-graph linking incomplete (TODO in code)                  │   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### FLOW 3: PDF Processing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PDF PROCESSING FLOW                             │
│                                                                         │
│  User                                                                   │
│     │                                                                   │
│     ▼                                                                   │
│  POST /api/admin/documents/upload                                       │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ DocumentTracker (JSON registry)                                 │   │
│  │   • Save PDF to PDFs/{category}/                                │   │
│  │   • Register in tracking file                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼                                                                   │
│  POST /api/admin/documents/{doc_id}/ingest (Background Job)            │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ SimplePDFIngestionService                                       │   │
│  │   1. PDFToMarkdownConverter (markitdown library)                │   │
│  │   2. MarkdownCleaner (normalize, extract metadata)              │   │
│  │   3. GraphitiEntityExtractor (LLM extraction)                   │   │
│  │      • Entities: Disease, Treatment, Symptom, Drug, Gene...     │   │
│  │      • Relationships: TREATS, CAUSES, INDICATES...              │   │
│  │   4. FalkorDB/Neo4j persistence                                 │   │
│  │      • layer = PERCEPTION                                       │   │
│  │      • source_document, confidence                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  CURRENT ISSUES:                                                        │
│  ❌ TODO: "Query Graphiti's internal graph" returns empty              │
│  ❌ No validation through Knowledge Manager                            │
│  ❌ No connection to DDA metadata (medical ↔ data catalog)            │
│  ❌ No feedback loop from chat quality to ingestion                    │
│  ❌ Auto-ingestion disabled (TODO)                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Current Agent Responsibilities

| Agent | Intended Role | Actually Does | Gap |
|-------|--------------|---------------|-----|
| **Data Architect** | High-level design, DDA parsing | Defined but not called from API | API bypasses agent |
| **Data Engineer** | Metadata graphs, type inference | Defined with handlers | Not integrated in main flow |
| **Knowledge Manager** | Validation, reasoning, conflicts | Full implementation exists | Not called by other flows |
| **Medical Assistant** | Patient chat, memory | Direct Neo4j access | Should route through KM |

### 1.3 Current Layer Usage

| Layer | Purpose | Current Content | Status |
|-------|---------|-----------------|--------|
| **PERCEPTION** | Raw extracted data | PDF entities | ⚠️ Partially used |
| **SEMANTIC** | Validated concepts | DDA metadata (no layer tag) | ❌ Not tagged |
| **REASONING** | Inferred knowledge | Empty | ❌ Not populated |
| **APPLICATION** | Query patterns | Empty | ❌ Not populated |

---

## Part 2: DIKW-Aligned Architecture Proposal

### 2.1 DIKW Pyramid Mapping

```
                    ┌─────────────────┐
                    │     WISDOM      │  ← APPLICATION Layer
                    │  (Expertise +   │    User conversations + Memory
                    │   Experience)   │    Query patterns + Cached insights
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   KNOWLEDGE     │  ← REASONING Layer
                    │  (Processed +   │    Inferred relationships
                    │   Organized)    │    Business rules execution
                    └────────┬────────┘    Ontology reasoning
                             │
                    ┌────────▼────────┐
                    │  INFORMATION    │  ← SEMANTIC Layer
                    │  (Contextualized│    Validated entities
                    │   Data)         │    ODIN metadata structure
                    └────────┬────────┘    Ontology mappings
                             │
                    ┌────────▼────────┐
                    │      DATA       │  ← PERCEPTION Layer
                    │  (Raw Facts)    │    Raw PDF extractions
                    └─────────────────┘    Unvalidated DDA entities
```

### 2.2 Proposed Agent Responsibilities (DIKW-Aligned)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DIKW-ALIGNED AGENT ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ DATA LAYER (PERCEPTION)                                         │   │
│  │                                                                  │   │
│  │  Data Architect Agent                Data Engineer Agent         │   │
│  │  ┌──────────────────────┐           ┌──────────────────────┐    │   │
│  │  │ • Parse DDAs         │           │ • Parse PDFs          │    │   │
│  │  │ • Extract entities   │           │ • Extract entities    │    │   │
│  │  │ • Define structure   │           │ • Type inference      │    │   │
│  │  │ • Business rules     │           │ • Raw metadata        │    │   │
│  │  │   (as text)          │           │                       │    │   │
│  │  └──────────┬───────────┘           └──────────┬────────────┘    │   │
│  │             │                                   │                 │   │
│  │             └───────────────┬───────────────────┘                 │   │
│  │                             ▼                                     │   │
│  │                    PERCEPTION Layer                               │   │
│  │                    (Neo4j: layer='PERCEPTION')                    │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ INFORMATION LAYER (SEMANTIC)                                    │   │
│  │                                                                  │   │
│  │  Knowledge Manager Agent (Ontologist Role)                       │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ • Validate entities against ODIN schema                  │   │   │
│  │  │ • Map to standard ontologies (SNOMED-CT, ICD-10)         │   │   │
│  │  │ • Apply SHACL constraints                                │   │   │
│  │  │ • Resolve conflicts and duplicates                       │   │   │
│  │  │ • Link medical entities to metadata entities             │   │   │
│  │  │ • Promote valid entities: PERCEPTION → SEMANTIC          │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                             │                                    │   │
│  │                             ▼                                    │   │
│  │                    SEMANTIC Layer                                │   │
│  │                    (Neo4j: layer='SEMANTIC')                     │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ KNOWLEDGE LAYER (REASONING)                                     │   │
│  │                                                                  │   │
│  │  Knowledge Manager Agent (Reasoner Role)                         │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ • Execute business rules from DDAs                       │   │   │
│  │  │ • Apply inference rules (transitive, analogical)         │   │   │
│  │  │ • Generate derived relationships                         │   │   │
│  │  │ • Cross-reference medical + data catalog                 │   │   │
│  │  │ • Compute contraindications, interactions                │   │   │
│  │  │ • Promote: SEMANTIC → REASONING (with provenance)        │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                             │                                    │   │
│  │                             ▼                                    │   │
│  │                    REASONING Layer                               │   │
│  │                    (Neo4j: layer='REASONING')                    │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ WISDOM LAYER (APPLICATION)                                      │   │
│  │                                                                  │   │
│  │  Medical Assistant Agent                                         │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ • User conversation interface                            │   │   │
│  │  │ • Query pattern caching                                  │   │   │
│  │  │ • Patient memory + context                               │   │   │
│  │  │ • RLHF feedback collection                               │   │   │
│  │  │ • Wisdom accumulation (expertise from experience)        │   │   │
│  │  │ • Promote: REASONING → APPLICATION (high-frequency)      │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                             │                                    │   │
│  │                             ▼                                    │   │
│  │                    APPLICATION Layer                             │   │
│  │                    (Neo4j: layer='APPLICATION')                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Revised Flow Proposals

#### REVISED FLOW 1: DDA Processing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    REVISED DDA PROCESSING FLOW                          │
│                                                                         │
│  User/API                                                               │
│     │                                                                   │
│     ▼                                                                   │
│  POST /api/dda/upload                                                   │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 1. DATA LAYER: Data Architect Agent                             │   │
│  │    • Parse DDA markdown                                         │   │
│  │    • Extract entities, relationships, business rules            │   │
│  │    • Create PERCEPTION layer nodes (unvalidated)                │   │
│  │    • Tag: layer='PERCEPTION', status='pending_validation'       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ Event: entity_created                                            │
│     │                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 2. DATA LAYER: Data Engineer Agent                              │   │
│  │    • Build ODIN metadata graph structure                        │   │
│  │    • Apply type inference to columns                            │   │
│  │    • Enrich with LLM descriptions                               │   │
│  │    • Tag: layer='PERCEPTION', enriched=true                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ Event: entity_enriched                                           │
│     │                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 3. INFORMATION LAYER: Knowledge Manager (Ontologist)            │   │
│  │    • Validate against ODIN schema (SHACL)                       │   │
│  │    • Check naming conventions, constraints                      │   │
│  │    • Resolve duplicates with existing catalog                   │   │
│  │    • PROMOTE: PERCEPTION → SEMANTIC                             │   │
│  │    • Tag: layer='SEMANTIC', validated=true                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ Event: entity_promoted                                           │
│     │                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 4. KNOWLEDGE LAYER: Knowledge Manager (Reasoner)                │   │
│  │    • Parse business rules from DDA                              │   │
│  │    • Convert to executable rule format                          │   │
│  │    • Create REASONING layer rule nodes                          │   │
│  │    • Link rules to SEMANTIC entities                            │   │
│  │    • Tag: layer='REASONING', rule_type='business_rule'          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### REVISED FLOW 2: PDF Processing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    REVISED PDF PROCESSING FLOW                          │
│                                                                         │
│  User/API                                                               │
│     │                                                                   │
│     ▼                                                                   │
│  POST /api/admin/documents/upload + ingest                              │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 1. DATA LAYER: Data Engineer Agent                              │   │
│  │    • Convert PDF → Markdown                                     │   │
│  │    • Extract entities via LLM (GraphitiEntityExtractor)         │   │
│  │    • Create PERCEPTION layer nodes                              │   │
│  │    • Tag: layer='PERCEPTION', source_document, confidence       │   │
│  │    • Store in RAG index (FAISS)                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ Event: pdf_entities_extracted                                    │
│     │                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 2. INFORMATION LAYER: Knowledge Manager (Ontologist)            │   │
│  │    • Validate medical entities against ontologies               │   │
│  │    • Map to SNOMED-CT, ICD-10, RxNorm codes                     │   │
│  │    • Link to existing DDA metadata (if applicable)              │   │
│  │    • PROMOTE: PERCEPTION → SEMANTIC (confidence >= 0.85)        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ Event: medical_entity_validated                                  │
│     │                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 3. KNOWLEDGE LAYER: Knowledge Manager (Reasoner)                │   │
│  │    • Apply inference rules (e.g., Drug X treats Disease Y)      │   │
│  │    • Compute transitive relationships                           │   │
│  │    • Generate contraindication warnings                         │   │
│  │    • Cross-reference with data catalog (which table has this?)  │   │
│  │    • PROMOTE: SEMANTIC → REASONING (inference applied)          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### REVISED FLOW 3: User Query

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    REVISED USER QUERY FLOW                              │
│                                                                         │
│  User                                                                   │
│     │                                                                   │
│     ▼                                                                   │
│  WebSocket / POST /api/query                                            │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 1. WISDOM LAYER: Medical Assistant Agent                        │   │
│  │    • Check APPLICATION layer cache first                        │   │
│  │    • Load patient context from memory                           │   │
│  │    • Route query through Knowledge Manager                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ Query routed to Knowledge Manager                                │
│     │                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 2. KNOWLEDGE LAYER: Knowledge Manager (Query Handler)           │   │
│  │    • Detect query type (safety-critical vs general)             │   │
│  │    • Select strategy (SYMBOLIC_ONLY for contraindications)      │   │
│  │    • Traverse layers: APP → REASONING → SEMANTIC → PERCEPTION   │   │
│  │    • Apply business rules from REASONING layer                  │   │
│  │    • Aggregate confidence with provenance                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ Response with entities, reasoning trail                          │
│     │                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 3. WISDOM LAYER: Medical Assistant Agent                        │   │
│  │    • Generate natural language response (LLM)                   │   │
│  │    • Store conversation in patient memory                       │   │
│  │    • Track response for RLHF feedback                           │   │
│  │    • If low confidence: show thumbs up/down UI                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ User provides feedback                                           │
│     │                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 4. FEEDBACK LOOP: FeedbackTracerService                         │   │
│  │    • Propagate feedback to entity confidence                    │   │
│  │    • Check demotion criteria (repeated negative → demote)       │   │
│  │    • High-frequency positive queries → APPLICATION layer        │   │
│  │    • Generate preference pairs for RLHF training                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Gap Analysis

### 3.1 Comparison with Research & Best Practices

#### Neurosymbolic AI Approaches

| Approach | Description | Our Implementation | Gap |
|----------|-------------|-------------------|-----|
| **Neural-Symbolic Integration** | Combine neural networks with symbolic reasoning | ✅ NeurosymbolicQueryService exists | ⚠️ Symbolic rules not populated |
| **Knowledge Graph Embeddings** | Vector representations of KG entities | ❌ Not implemented | Need embeddings for similarity |
| **Rule Learning from Data** | Extract rules from successful patterns | ✅ FeedbackIntegrator suggests rules | ⚠️ Not connected to reasoning engine |
| **Confidence Calibration** | Align predicted vs actual confidence | ✅ CalibrationReport exists | ⚠️ Not used for model adjustment |

#### DIKW Implementation Patterns

| Pattern | Best Practice | Our Implementation | Gap |
|---------|--------------|-------------------|-----|
| **Data → Information** | Validation + Contextualization | ⚠️ Partial (SHACL exists but not called) | Connect validation pipeline |
| **Information → Knowledge** | Inference + Rule Application | ❌ Reasoning engine defined but empty | Populate business rules |
| **Knowledge → Wisdom** | Experience + Feedback Loop | ✅ RLHF infrastructure ready | Connect to layer promotion |
| **Bidirectional Flow** | Feedback affects lower layers | ✅ Demotion logic exists | ⚠️ Promotion logic incomplete |

#### Similar Projects & Research

1. **IBM's Neuro-Symbolic Concept Learner (2019)**
   - Combines perception (neural) with reasoning (symbolic)
   - Our parallel: PDF extraction (neural) → Knowledge Manager (symbolic)
   - Gap: We don't have explicit concept learning from feedback

2. **DeepMind's AlphaFold (Confidence Scoring)**
   - Per-residue confidence scores with calibration
   - Our parallel: Per-entity confidence with feedback adjustment
   - Gap: No systematic calibration pipeline

3. **Google's Knowledge Vault**
   - Multi-source knowledge extraction with confidence
   - Our parallel: PDF + DDA sources with provenance
   - Gap: No cross-source consistency checking

4. **OpenAI's RLHF Pipeline**
   - Preference learning from human feedback
   - Our parallel: Thumbs up/down → preference pairs
   - Gap: No actual model fine-tuning step

### 3.2 Specific Implementation Gaps

#### Gap 1: Agent Integration

**Current State:**
```python
# main.py line 507
@app.post("/api/dda/upload")
async def upload_dda(file, kg_backend):
    # Writes directly to Neo4j, bypassing agents
    parser = MarkdownDDAParser()
    result = await parser.parse(tmp_path)
    await kg_backend.query_raw(...)  # Direct write
```

**Required Change:**
```python
@app.post("/api/dda/upload")
async def upload_dda(file, data_architect_agent):
    # Route through Data Architect Agent
    result = await data_architect_agent.process_dda(file)
    # Agent handles validation, layer assignment, event publishing
```

#### Gap 2: Layer Assignment

**Current State:**
- DDA entities: No `layer` property
- PDF entities: `layer='PERCEPTION'` but never promoted

**Required Change:**
- All entities must have `layer` property
- Automatic promotion triggers via events
- Demotion on negative feedback (already implemented)

#### Gap 3: Business Rules Execution

**Current State:**
```python
# DDA stores business rules as text
Table {
    business_rules: "Patient age must be > 0"  # Just a string
}
```

**Required Change:**
```python
# REASONING layer stores executable rules
BusinessRule {
    layer: 'REASONING',
    rule_type: 'constraint',
    subject_entity: 'Patient',
    condition: 'age > 0',
    action: 'reject',
    source_dda: 'clinical_trials_dda'
}
```

#### Gap 4: Medical Assistant → Knowledge Manager Routing

**Current State:**
```python
# intelligent_chat_service.py
async def query(self, question, patient_id):
    # Direct queries to Neo4j
    medical_context = await self._get_medical_context(question)
```

**Required Change:**
```python
async def query(self, question, patient_id):
    # Route through Knowledge Manager for validation
    result = await self.knowledge_manager.query(
        question=question,
        patient_context=patient_context,
        require_validation=True  # Safety-critical queries
    )
```

### 3.3 Priority Matrix

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| Layer assignment for DDA entities | High | Low | **P1** |
| Route DDA through Data Architect | High | Medium | **P1** |
| Route queries through Knowledge Manager | High | Medium | **P2** |
| Business rules as executable | High | High | **P2** |
| PDF entity validation pipeline | Medium | Medium | **P3** |
| Cross-source linking | Medium | High | **P3** |
| Knowledge graph embeddings | Low | High | **P4** |

---

## Part 4: Implementation Roadmap

### Phase 1: Foundation (Low Effort, High Impact)

1. **Add layer property to all DDA entities**
   - Modify `main.py` upload endpoint
   - Default to `layer='PERCEPTION'`
   - File: `src/application/api/main.py`

2. **Wire DDA upload through Data Architect Agent**
   - Create command handler in agent
   - Publish `entity_created` events
   - File: `src/application/agents/data_architect/agent.py`

3. **Enable automatic promotion scanner**
   - Set `ENABLE_PROMOTION_SCANNER=true`
   - Configure thresholds in env
   - File: `src/application/api/dependencies.py`

### Phase 2: Knowledge Layer (Medium Effort)

4. **Route Medical Assistant through Knowledge Manager**
   - Add `knowledge_manager` dependency to chat service
   - Call `knowledge_manager.query()` instead of direct Neo4j
   - File: `src/application/services/intelligent_chat_service.py`

5. **Convert business rules to executable format**
   - Parse rule text in DDA
   - Create `BusinessRule` nodes in REASONING layer
   - Apply rules during query execution
   - Files: `src/application/agents/knowledge_manager/reasoning_engine.py`

6. **Connect feedback to promotion/demotion**
   - High positive feedback → promote to APPLICATION
   - Repeated negative → demote (already implemented)
   - File: `src/application/services/feedback_tracer.py`

### Phase 3: Wisdom Layer (Higher Effort)

7. **Query pattern caching in APPLICATION layer**
   - Track query frequency
   - Promote high-frequency patterns
   - Cache results for fast retrieval

8. **Cross-source entity linking**
   - Link medical entities (from PDF) to data catalog (from DDA)
   - Semantic similarity + LLM inference
   - File: `src/application/services/medical_data_linker.py`

9. **RLHF training data export**
   - Format preference pairs for fine-tuning
   - Integrate with training pipeline
   - File: `src/application/services/rlhf_data_extractor.py`

---

## Appendix A: DIKW Research References

### Academic Foundations

1. **Ackoff, R.L. (1989)** - "From Data to Wisdom" - Original DIKW hierarchy
2. **Rowley, J. (2007)** - "The wisdom hierarchy: representations of the DIKW hierarchy"
3. **Frické, M. (2009)** - "The knowledge pyramid: a critique of the DIKW hierarchy"

### Neurosymbolic AI

4. **Garcez & Lamb (2020)** - "Neurosymbolic AI: The 3rd Wave"
5. **Mao et al. (2019)** - "The Neuro-Symbolic Concept Learner"
6. **Hamilton et al. (2017)** - "Representation Learning on Graphs"

### Knowledge Graphs + LLMs

7. **Pan et al. (2023)** - "Unifying Large Language Models and Knowledge Graphs"
8. **Ye et al. (2022)** - "Knowledge Graph Enhanced Pre-trained Language Models"
9. **Zhang et al. (2024)** - "KG-GPT: Knowledge Graph Construction with LLMs"

### RLHF & Feedback Systems

10. **Ouyang et al. (2022)** - "Training language models to follow instructions with human feedback" (InstructGPT)
11. **Rafailov et al. (2023)** - "Direct Preference Optimization" (DPO)

---

## Appendix B: Current vs Proposed Architecture Diff

```diff
  DDA Upload Flow:
- POST /api/dda/upload → MarkdownDDAParser → Neo4j (direct)
+ POST /api/dda/upload → DataArchitectAgent → DataEngineerAgent → KnowledgeManager → Neo4j

  PDF Processing Flow:
- POST /documents/ingest → GraphitiExtractor → FalkorDB (layer=PERCEPTION, no promotion)
+ POST /documents/ingest → DataEngineerAgent → KnowledgeManager → Neo4j (layer=PERCEPTION → SEMANTIC → REASONING)

  User Query Flow:
- WebSocket → IntelligentChatService → Neo4j (direct)
+ WebSocket → MedicalAssistant → KnowledgeManager → Neo4j (validated, reasoned)

  Feedback Flow:
- Thumbs feedback → Entity confidence adjustment
+ Thumbs feedback → Entity confidence → Promotion/Demotion → Layer transition → Training data export
```
