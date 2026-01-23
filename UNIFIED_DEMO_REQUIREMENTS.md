# Unified End-to-End Demo Requirements

**Date**: January 20, 2026
**Purpose**: Demonstrate complete neurosymbolic knowledge management system for data engineering at scale
**Target Domain**: Autoimmune chronic diseases (medical/pharmaceutical research)

---

## Executive Summary

The demo showcases an **intelligent data engineering system** that combines:
1. **Knowledge ingestion** from medical PDFs
2. **Data architecture understanding** from DDAs (Data Domain Architectures)
3. **Neurosymbolic processing** across all DIKW layers
4. **Interactive querying** via CLI chat interface
5. **Visual graph exploration** in Neo4j/FalkorDB browser

**End Goal**: Demonstrate automated data engineering agents capable of understanding domain knowledge and creating data relationships at scale for pharmaceutical/medical trial use cases.

---

## Two-Flow Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  FLOW 1: KNOWLEDGE INGESTION                                   │
│  ────────────────────────────                                   │
│                                                                  │
│  Medical PDFs (Autoimmune Diseases)                            │
│         ↓                                                        │
│  [Entity Extraction via Graphiti]                              │
│         ↓                                                        │
│  Knowledge Base (Domain Understanding)                          │
│         ↓                                                        │
│  Semantic Layer Enrichment                                      │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
                            ↓
                   Feeds into ↓
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  FLOW 2: DATA ENGINEERING                                      │
│  ─────────────────────────                                      │
│                                                                  │
│  DDAs (Data Domain Architecture documents)                     │
│         ↓                                                        │
│  [Data Architect Agent] - Understands structure                │
│         ↓                                                        │
│  [Data Engineer Agent] - Creates relationships                 │
│         ↓                                                        │
│  Neurosymbolic Processing (All DIKW layers)                    │
│         ↓                                                        │
│  Persistent Graph (FalkorDB/Neo4j)                            │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
                            ↓
                    Queryable via ↓
                            ↓
                   [Interactive CLI Chat]
```

---

## Scope & Components

### 1. Knowledge Ingestion (PDF Processing)

**Input**: Medical PDFs on autoimmune chronic diseases
- Crohn's Disease
- Type 1 Diabetes
- Autoimmune Disease (general)
- Clinical Trials data
- Telemedicine protocols

**Process**:
1. Parse PDF content (text extraction)
2. Entity extraction via **Graphiti** (LLM-powered)
   - Medical entities (diseases, symptoms, treatments)
   - Relationships (causes, treats, prevents)
   - Clinical concepts (trials, protocols, outcomes)
3. Semantic normalization (medical abbreviations)
4. Store in knowledge base for context

**Output**: Enriched semantic layer with domain knowledge

### 2. Data Engineering (DDA Processing)

**Input**: All available DDAs in `examples/` directory
- `crohns_disease_dda.md`
- `autoimmune_disease_telemedicine_dda.md`
- `autoimmune_disease_clinical_trials_dda.md`
- `type_1_diabetes_management_dda.md`
- `sample_dda.md`
- Any others in examples/

**Process**:
1. **Data Architect Agent**:
   - Parse DDA structure
   - Identify tables, columns, relationships
   - Understand domain context (using PDF knowledge)

2. **Data Engineer Agent**:
   - Create metadata graph
   - Infer relationships between entities
   - Apply type inference

3. **Neurosymbolic Processing** (All 3 Phases):
   - Phase 1: Entity resolution, normalization, deduplication
   - Phase 2: Confidence scoring, semantic grounding, validation
   - Phase 3: Layer transitions (PERCEPTION → SEMANTIC → REASONING → APPLICATION)

**Output**: Complete knowledge graph in persistent storage

### 3. Interactive Querying

**Interface**: CLI Chat
- Natural language questions
- Cypher query generation
- Graph traversal
- Metrics and statistics

**Example Queries**:
- "What tables are related to Crohn's Disease?"
- "Show me all clinical trial data structures"
- "What quality rules apply to patient data?"
- "Visualize the relationships between treatment and outcome tables"

---

## Technical Architecture

### Backend Strategy (Repository Pattern)

```python
# Repository Pattern Implementation
class GraphBackendRepository:
    """
    Abstraction layer for graph backends.
    Allows switching between Neo4j, FalkorDB, or In-Memory.
    """

    def __init__(self, backend_type="falkordb"):
        if backend_type == "neo4j":
            self.backend = Neo4jBackend()
        elif backend_type == "falkordb":
            self.backend = FalkorDBBackend()
        else:
            self.backend = InMemoryBackend()

    # Common interface
    def create_node(self, ...): pass
    def create_relationship(self, ...): pass
    def query(self, ...): pass
```

### Processing Pipeline

```
1. PDF Ingestion (Graphiti)
   ├─→ Extract entities & relationships
   ├─→ Store in temporary knowledge base
   └─→ Build domain context

2. DDA Processing (All DDAs)
   ├─→ Parse each DDA
   ├─→ Extract tables, columns, constraints
   ├─→ Apply semantic normalization (using PDF context)
   ├─→ Resolve entities (deduplicate)
   └─→ Enrich with business concepts

3. Neurosymbolic Integration
   ├─→ Confidence scoring (neural + symbolic)
   ├─→ Validation (SHACL shapes)
   ├─→ Cross-layer reasoning
   └─→ Layer transitions

4. Persistence
   ├─→ Write to FalkorDB (local dev)
   └─→ Or Neo4j (production)

5. Visualization & Querying
   ├─→ FalkorDB browser for graph visualization
   ├─→ CLI chat for interactive queries
   └─→ Export metrics and reports
```

---

## Demo Flow (Interactive)

### Stage 1: Introduction (2 minutes)
```
🎯 Welcome to SynapseFlow: Intelligent Data Engineering

This demo showcases:
✓ Automated knowledge ingestion from medical PDFs
✓ Intelligent data architecture understanding
✓ Neurosymbolic reasoning across DIKW layers
✓ Interactive knowledge graph querying

Domain: Autoimmune Chronic Diseases
Goal: Automated data engineering for pharmaceutical research

Press ENTER to begin...
```

### Stage 2: Knowledge Ingestion - PDF Processing (5-10 minutes)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STAGE 1: KNOWLEDGE INGESTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 Processing Medical PDFs...

  1. Crohn's Disease Documentation
     [████████████████████████████] 100%
     ✓ Extracted 47 medical entities
     ✓ Identified 23 relationships
     ✓ Confidence: 0.92

  2. Type 1 Diabetes Research
     [████████████████████████████] 100%
     ✓ Extracted 52 medical entities
     ✓ Identified 31 relationships
     ✓ Confidence: 0.89

  3. Clinical Trials Protocols
     [████████████████████████████] 100%
     ✓ Extracted 38 clinical entities
     ✓ Identified 19 relationships
     ✓ Confidence: 0.94

📊 Knowledge Base Summary:
   • Total Entities: 137
   • Total Relationships: 73
   • Domains Covered: 3
   • Semantic Concepts: 45

🎓 Domain knowledge ready for data engineering!

[Press ENTER to continue to DDA processing...]
```

### Stage 3: Data Architecture - DDA Processing (10-15 minutes)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STAGE 2: DATA ENGINEERING - DDA PROCESSING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏗️  Processing DDAs with intelligent agents...

DDA 1/5: crohns_disease_dda.md
  ├─ 📋 Data Architect Agent
  │  ├─ Parsing structure... ✓
  │  ├─ Identified: 8 tables, 47 columns
  │  └─ Recognized domain: Crohn's Disease (from PDF knowledge)
  │
  ├─ 🔧 Data Engineer Agent
  │  ├─ Building metadata graph... ✓
  │  ├─ Inferring relationships... ✓
  │  ├─ Applied type inference... ✓
  │  └─ Created 8 nodes, 15 relationships
  │
  └─ 🧠 Neurosymbolic Processing
     ├─ Phase 1: Semantic Layer
     │  ├─ Normalized 12 abbreviations
     │  ├─ Resolved 3 duplicate entities
     │  └─ Created 5 canonical concepts
     ├─ Phase 2: Neural-Symbolic Integration
     │  ├─ Enriched with 7 business concepts
     │  ├─ Average confidence: 0.87
     │  └─ Validated with SHACL: ✓ Pass
     └─ Phase 3: Layer Transitions
        ├─ PERCEPTION → SEMANTIC: 8 entities
        ├─ SEMANTIC → REASONING: 5 quality rules
        └─ REASONING → APPLICATION: 3 query patterns

DDA 2/5: type_1_diabetes_management_dda.md
  [Similar detailed output...]

DDA 3/5: autoimmune_disease_clinical_trials_dda.md
  [Similar detailed output...]

DDA 4/5: autoimmune_disease_telemedicine_dda.md
  [Similar detailed output...]

DDA 5/5: sample_dda.md
  [Similar detailed output...]

📊 Complete Knowledge Graph:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   PERCEPTION Layer:    42 entities
   SEMANTIC Layer:      38 concepts
   REASONING Layer:     27 quality rules
   APPLICATION Layer:   15 query patterns
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Total Nodes:         122
   Total Relationships: 187
   Graph Density:       0.328
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Graph persisted to FalkorDB!

🌐 Open browser: http://localhost:6379
   Graph name: knowledge_graph

[Press ENTER to start interactive querying...]
```

### Stage 4: Interactive Querying (Open-ended)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STAGE 3: INTERACTIVE KNOWLEDGE EXPLORATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 SynapseFlow Chat
   Ask questions about your knowledge graph!
   Type 'help' for examples, 'exit' to quit

You: What tables are related to Crohn's Disease?

🤖 Analyzing query...
   ├─ Intent: Table discovery
   ├─ Domain: Crohn's Disease
   └─ Generating Cypher...

📊 Found 8 tables related to Crohn's Disease:

   1. patients (CrohnsDiseasePatients)
      ├─ Columns: patient_id, diagnosis_date, severity
      └─ Relationships: → treatments (RECEIVES)

   2. treatments (CrohnsTreatment)
      ├─ Columns: treatment_id, medication, dosage
      └─ Relationships: → outcomes (RESULTS_IN)

   3. clinical_observations
      ├─ Columns: observation_id, symptom, severity_score
      └─ Relationships: → patients (OBSERVED_IN)

   [... more tables ...]

   💡 Visualization available in FalkorDB browser

You: Show me quality rules for patient data

🤖 Analyzing query...
   ├─ Intent: Quality rule discovery
   ├─ Target: Patient data
   └─ Querying REASONING layer...

📋 Quality Rules for Patient Data:

   1. ✓ email_required
      └─ Patients must have valid contact info
      └─ Confidence: 0.92

   2. ✓ unique_patient_id
      └─ Patient ID must be unique
      └─ Confidence: 0.98

   3. ✓ diagnosis_date_not_future
      └─ Diagnosis date cannot be in the future
      └─ Confidence: 0.95

   [... more rules ...]

You: What's the relationship between treatments and outcomes?

🤖 Analyzing query...
   └─ Generating graph traversal...

🔗 Relationship Chain:

   treatments
      ├─ [RESULTS_IN] → outcomes
      ├─ [PRESCRIBED_FOR] → patients
      └─ [FOLLOWS] → protocols

   Confidence: 0.89
   Source: Inferred from DDAs + PDF knowledge

   📊 Path visualization:
      treatments ──RESULTS_IN──> outcomes
                 └──PRESCRIBED_FOR──> patients
                                      └──DIAGNOSED_WITH──> conditions

You: exit

👋 Session Summary:
   • Queries processed: 3
   • Nodes explored: 45
   • Relationships traversed: 67
   • Average response time: 1.2s

   📊 Graph available at: http://localhost:6379
   📁 Export logs: ./demo_output/session_log.json

Thank you for using SynapseFlow!
```

---

## Technical Requirements

### 1. PDF Processing Component

**New Service**: `PDFKnowledgeIngestionService`

```python
class PDFKnowledgeIngestionService:
    """
    Ingests knowledge from PDF documents using Graphiti.

    Workflow:
    1. Extract text from PDF
    2. Chunk into semantic segments
    3. Extract entities & relationships via Graphiti
    4. Store in temporary knowledge base
    5. Make available for DDA processing
    """

    def __init__(self, graphiti_client: Graphiti):
        self.graphiti = graphiti_client
        self.knowledge_base = {}

    async def ingest_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Ingest knowledge from a PDF."""
        pass

    async def extract_entities(self, text: str) -> List[Entity]:
        """Extract entities using Graphiti."""
        pass

    def get_domain_context(self, domain: str) -> Dict[str, Any]:
        """Get accumulated knowledge for a domain."""
        pass
```

**Location**: `src/application/services/pdf_knowledge_service.py`

### 2. Backend Repository Pattern

**Update**: Ensure repository pattern is properly implemented

```python
# src/infrastructure/backend_repository.py

class GraphBackendRepository:
    """
    Repository pattern for graph backends.
    Allows seamless switching between Neo4j, FalkorDB, In-Memory.
    """

    @staticmethod
    def create(backend_type: str, **config):
        if backend_type == "neo4j":
            return Neo4jBackend(**config)
        elif backend_type == "falkordb":
            return FalkorDBBackend(**config)
        elif backend_type == "in-memory":
            return InMemoryBackend()
        else:
            raise ValueError(f"Unknown backend: {backend_type}")
```

### 3. Interactive CLI Chat

**New Service**: `InteractiveChatService`

```python
class InteractiveChatService:
    """
    Interactive CLI for querying knowledge graph.

    Features:
    - Natural language question parsing
    - Intent recognition
    - Cypher query generation
    - Result formatting
    - Session management
    """

    def __init__(self, backend: GraphBackendRepository):
        self.backend = backend
        self.session_history = []

    async def process_query(self, question: str) -> Dict[str, Any]:
        """Process natural language query."""
        pass

    def format_results(self, results: List[Dict]) -> str:
        """Format query results for display."""
        pass
```

**Location**: `src/interfaces/interactive_chat.py`

### 4. Demo Orchestrator

**Main Demo Script**: `demos/e2e_neurosymbolic_demo.py`

```python
class UnifiedDemo:
    """
    Complete end-to-end demonstration.

    Stages:
    1. Introduction
    2. PDF knowledge ingestion
    3. DDA processing (all phases)
    4. Interactive querying
    """

    def __init__(self, backend_type="falkordb"):
        self.backend = GraphBackendRepository.create(backend_type)
        self.pdf_service = PDFKnowledgeIngestionService(graphiti_client)
        self.chat_service = InteractiveChatService(self.backend)

    async def run(self):
        """Run complete demo."""
        await self.stage1_introduction()
        await self.stage2_pdf_ingestion()
        await self.stage3_dda_processing()
        await self.stage4_interactive_chat()
```

---

## Data Sources

### Medical PDFs (To Be Provided)
- [ ] Crohn's Disease documentation
- [ ] Type 1 Diabetes research papers
- [ ] Clinical trials protocols
- [ ] Autoimmune disease overview
- [ ] Telemedicine procedures

**Note**: If PDFs not available, we can:
1. Use public medical literature
2. Generate sample medical documents
3. Use existing DDA content as knowledge source

### DDAs (Existing)
- ✓ `examples/crohns_disease_dda.md`
- ✓ `examples/type_1_diabetes_management_dda.md`
- ✓ `examples/autoimmune_disease_clinical_trials_dda.md`
- ✓ `examples/autoimmune_disease_telemedicine_dda.md`
- ✓ `examples/sample_dda.md`
- ✓ Any others in `examples/` directory

---

## Output & Visualization

### 1. Terminal Output
- ✓ Progress bars and status indicators
- ✓ Colored output (green/yellow/blue/red)
- ✓ Real-time statistics
- ✓ Interactive prompts

### 2. FalkorDB Browser
- ✓ Graph visualization at http://localhost:6379
- ✓ Node/relationship exploration
- ✓ Cypher query console
- ✓ Visual graph analysis

### 3. Session Logs
- ✓ Complete processing log (JSON)
- ✓ Metrics and statistics (CSV)
- ✓ Query history
- ✓ Error/warning reports

### 4. Optional Exports
- PDF report (summary)
- HTML dashboard (metrics)
- GraphML export (for external tools)

---

## Non-Functional Requirements

### Performance
- Process all DDAs in reasonable time (< 5 minutes total)
- Interactive queries respond in < 2 seconds
- Handle large PDFs (50+ pages)

### Reliability
- Graceful error handling
- Resume capability if interrupted
- Validation at each stage

### Usability
- Clear progress indicators
- Helpful error messages
- Intuitive CLI interface
- Easy visualization access

### Extensibility
- Easy to add new backends
- Pluggable PDF processors
- Customizable queries
- Configurable processing steps

---

## Success Criteria

✅ **Knowledge Ingestion**
- Successfully extract entities from medical PDFs
- Build coherent domain knowledge base
- Context improves DDA processing quality

✅ **Data Engineering**
- Process all DDAs successfully
- Create complete knowledge graph
- All three phases execute correctly
- Layer transitions work properly

✅ **Persistence**
- Graph stored in FalkorDB
- Data retrievable via Cypher
- Visualizable in browser

✅ **Querying**
- Natural language queries work
- Results are accurate and relevant
- Fast response times
- Intuitive UX

✅ **End-to-End**
- Complete workflow executes without manual intervention
- Demonstrates value for pharmaceutical/medical use cases
- Shows automation of data engineering tasks

---

## Implementation Phases

### Phase A: Core Components (Week 1)
1. PDF ingestion service
2. Backend repository pattern validation
3. Interactive chat service
4. Demo orchestrator framework

### Phase B: Integration (Week 1-2)
1. Connect PDF knowledge to DDA processing
2. Wire up all three neurosymbolic phases
3. Implement FalkorDB persistence
4. Create visualization helpers

### Phase C: Polish (Week 2)
1. Enhanced CLI output formatting
2. Error handling and recovery
3. Session management
4. Documentation and examples

---

## Questions for Clarification

1. **PDF Sources**: Do you have specific PDFs, or should I use public medical literature?
2. **FalkorDB Setup**: Is FalkorDB already running locally, or do we need setup instructions?
3. **Graphiti API**: Do you have Graphiti API keys configured?
4. **Query Complexity**: How sophisticated should the natural language parsing be? (Simple keyword matching vs. full NLP)
5. **Demo Automation**: Should demo run fully automated first, then interactive chat? Or interleaved?

---

## Next Steps

Once requirements are approved:
1. Create PDF ingestion service
2. Implement backend repository pattern (if not already done)
3. Build interactive chat interface
4. Create unified demo orchestrator
5. Test end-to-end with sample data
6. Polish and document

---

**Ready to proceed?** Please review and let me know:
- Any changes to requirements
- Answers to clarification questions
- Priority adjustments
- Additional features needed
