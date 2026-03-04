#!/usr/bin/env python3
"""Generate SynapseFlow Architecture PDF documentation."""

from fpdf import FPDF
import os

class SynapseFlowPDF(FPDF):
    """Custom PDF class for SynapseFlow documentation."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, "SynapseFlow - Architecture & Hypergraph Documentation", align="C")
            self.ln(5)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def chapter_title(self, title, level=1):
        if level == 1:
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(30, 60, 120)
            self.ln(5)
            self.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(30, 60, 120)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(6)
        elif level == 2:
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(50, 80, 140)
            self.ln(4)
            self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
            self.ln(3)
        elif level == 3:
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(70, 100, 160)
            self.ln(3)
            self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def code_block(self, code, title=None):
        if title:
            self.set_font("Helvetica", "BI", 9)
            self.set_text_color(80, 80, 80)
            self.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        self.set_fill_color(245, 245, 250)
        self.set_font("Courier", "", 8)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        y = self.get_y()
        # Calculate height
        lines = code.strip().split("\n")
        h = len(lines) * 4.5 + 4
        # Check if we need a page break
        if y + h > 270:
            self.add_page()
            y = self.get_y()
        self.rect(x, y, 190, h, style="F")
        self.set_xy(x + 3, y + 2)
        for line in lines:
            # Truncate long lines
            if len(line) > 100:
                line = line[:97] + "..."
            self.cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT")
            self.set_x(x + 3)
        self.set_y(y + h + 3)

    def bullet(self, text, indent=0):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        x = 15 + indent * 5
        self.set_x(x)
        bullet_char = "-" if indent == 0 else ">"
        self.multi_cell(190 - indent * 5, 5.5, f"  {bullet_char}  {text}")
        self.ln(1)

    def table_header(self, cols, widths):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(30, 60, 120)
        self.set_text_color(255, 255, 255)
        for i, col in enumerate(cols):
            self.cell(widths[i], 7, col, border=1, fill=True, align="C")
        self.ln()

    def table_row(self, cols, widths, fill=False):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        if fill:
            self.set_fill_color(240, 243, 250)
        for i, col in enumerate(cols):
            self.cell(widths[i], 6, col, border=1, fill=fill, align="L")
        self.ln()

    def ascii_diagram(self, text):
        self.set_font("Courier", "", 7.5)
        self.set_text_color(30, 60, 120)
        self.set_fill_color(250, 250, 255)
        lines = text.strip().split("\n")
        h = len(lines) * 4 + 4
        y = self.get_y()
        if y + h > 270:
            self.add_page()
            y = self.get_y()
        self.rect(10, y, 190, h, style="F")
        self.set_xy(12, y + 2)
        for line in lines:
            if len(line) > 105:
                line = line[:105]
            self.cell(0, 4, line, new_x="LMARGIN", new_y="NEXT")
            self.set_x(12)
        self.set_y(y + h + 3)


def build_pdf():
    pdf = SynapseFlowPDF()
    pdf.alias_nb_pages()

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(30, 60, 120)
    pdf.cell(0, 15, "SynapseFlow", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Neurosymbolic Multi-Agent Knowledge Management", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(30, 60, 120)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(50, 80, 140)
    pdf.cell(0, 10, "Architecture, Hypergraph Bridge & Promotion System", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(30)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Version 2.0  |  March 2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "Generated from source code and architecture documentation", align="C", new_x="LMARGIN", new_y="NEXT")

    # =========================================================================
    # TABLE OF CONTENTS
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("Table of Contents")
    toc = [
        ("1.", "Project Overview & Clean Architecture"),
        ("2.", "4-Layer Knowledge Graph (DIKW Pyramid)"),
        ("3.", "Multi-Agent System"),
        ("4.", "Hypergraph Bridge Architecture"),
        ("   4.1", "Why Hypergraphs?"),
        ("   4.2", "Domain Models (FactUnit, HyperEdge, etc.)"),
        ("   4.3", "Neo4j Storage Schema"),
        ("   4.4", "Bridge Operations"),
        ("   4.5", "Confidence Aggregation"),
        ("5.", "Promotion System (Layer Transitions)"),
        ("   5.1", "LayerTransitionService"),
        ("   5.2", "AutomaticLayerTransitionService"),
        ("   5.3", "PromotionGate"),
        ("   5.4", "Promotion Criteria by Layer"),
        ("6.", "Inference-Time Behavior"),
        ("   6.1", "Query Routing (DIKW Router)"),
        ("   6.2", "Reasoning Engine & Strategies"),
        ("   6.3", "Medical Safety Rules"),
        ("   6.4", "Cross-Layer Confidence Propagation"),
        ("   6.5", "Temporal Scoring"),
        ("7.", "Integration: Hypergraph + Promotion + Inference"),
    ]
    for num, title in toc:
        pdf.set_font("Helvetica", "B" if not num.startswith(" ") else "", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(15, 6, num)
        pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")

    # =========================================================================
    # 1. PROJECT OVERVIEW
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("1. Project Overview & Clean Architecture")

    pdf.body_text(
        "SynapseFlow is a neurosymbolic multi-agent system for intelligent knowledge management. "
        "It combines symbolic AI (rule-based reasoning, ontology mapping) with neural AI (LLM inference, "
        "embeddings) using a multi-agent architecture with domain-driven design."
    )

    pdf.chapter_title("Key Capabilities", 2)
    for cap in [
        "Domain-Driven Architecture (DDA) modeling from Markdown specifications",
        "ODIN metadata management: data catalog with lineage and governance",
        "Neurosymbolic reasoning: symbolic rules + LLM inference with confidence tracking",
        "Patient medical memory: 3-layer architecture (Redis + Mem0 + Neo4j)",
        "RAG-enhanced chat with FAISS vector search",
        "Hypergraph Bridge: neurosymbolic layer connecting Document Graph and Knowledge Graph",
    ]:
        pdf.bullet(cap)

    pdf.chapter_title("Clean Architecture (Onion Architecture)", 2)
    pdf.ascii_diagram("""
+-----------------------------------------------------------+
|                   Interfaces Layer                         |
|          (CLI, REST API, Composition Root)                 |
+-----------------------------------------------------------+
|                 Infrastructure Layer                       |
|     (Neo4j, Redis, Mem0, RabbitMQ, Parsers)               |
+-----------------------------------------------------------+
|                  Application Layer                         |
|       (Services, Agents, Commands, Workflows)              |
+-----------------------------------------------------------+
|                    Domain Layer                            |
|        (Models, Interfaces, Business Rules)                |
|               [NO DEPENDENCIES]                            |
+-----------------------------------------------------------+
    """)

    pdf.body_text(
        "Dependency Rule: Dependencies point inward only. The Domain layer has zero dependencies on "
        "outer layers. All external integrations (Neo4j, Redis, etc.) implement domain interfaces."
    )

    pdf.chapter_title("Design Patterns", 2)
    widths = [45, 70, 75]
    pdf.table_header(["Pattern", "Implementation", "Example"], widths)
    patterns = [
        ["Repository", "KnowledgeGraphBackend", "Neo4j, FalkorDB, Graphiti"],
        ["Strategy", "Resolution/Reasoning modes", "EXACT, FUZZY, EMBEDDING"],
        ["Factory", "Agent Registry", "composition_root.py"],
        ["Observer", "EventBus pub/sub", "entity_created events"],
        ["Command (CQRS)", "CommandBus", "ModelingCommand"],
        ["Decorator", "Confidence/provenance", "Audit logging"],
    ]
    for i, row in enumerate(patterns):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    # =========================================================================
    # 2. 4-LAYER KNOWLEDGE GRAPH
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("2. 4-Layer Knowledge Graph (DIKW Pyramid)")

    pdf.body_text(
        "All entities in SynapseFlow carry a 'layer' property corresponding to the DIKW knowledge "
        "pyramid. Entities are automatically promoted upward as they gain confidence, validation, "
        "and usage."
    )

    pdf.ascii_diagram("""
+------------------------------------------------------------------+
|  Layer 4: APPLICATION                                             |
|  - Query patterns, cached results, user feedback                  |
|  - Proven utility: 10+ queries/24h, 50%+ cache hit               |
+------------------------------------------------------------------+
|  Layer 3: REASONING                                               |
|  - Inferred knowledge, business rules, drug interactions          |
|  - conf >= 0.90, inference rule fired, 5+ references              |
+------------------------------------------------------------------+
|  Layer 2: SEMANTIC                                                |
|  - Validated concepts with ontology mappings (SNOMED, ICD-10)     |
|  - conf >= 0.85, SNOMED match, or 3+ validations                 |
+------------------------------------------------------------------+
|  Layer 1: PERCEPTION                                              |
|  - Raw extracted data from PDFs, DDAs, documents                  |
|  - Entry point, confidence ~ 0.7                                  |
+------------------------------------------------------------------+
    """)

    pdf.chapter_title("Layer Properties", 2)
    widths = [35, 55, 50, 50]
    pdf.table_header(["Layer", "Required Properties", "Confidence", "Transition Trigger"], widths)
    layers = [
        ["PERCEPTION", "source, origin", "~0.70", "Entry point"],
        ["SEMANTIC", "description, domain", ">= 0.85", "Ontology match, 3+ vals"],
        ["REASONING", "confidence, reasoning", ">= 0.90", "Rule fires, 5+ refs"],
        ["APPLICATION", "usage_context, access", "N/A", "10+ queries/24h"],
    ]
    for i, row in enumerate(layers):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.chapter_title("Data Flow Between Layers", 2)
    pdf.ascii_diagram("""
                     +----------------------+
                     |   APPLICATION        |
                     |   (Patient Chat)     |
                     +----------+-----------+
                                | queries
                     +----------v-----------+
                     |   REASONING          |
                     |   (Inference Engine) |
                     +----------+-----------+
                                | reasons over
          +---------------------+---------------------+
          |                     |                     |
+---------v---------+ +---------v---------+ +---------v---------+
| SEMANTIC          | | SEMANTIC          | | SEMANTIC          |
| (Medical Ontology)| | (DDA Metadata)    | | (Business Context)|
+---------+---------+ +---------+---------+ +---------+---------+
          |                     |                     |
+---------v---------------------v---------------------v---------+
|                     PERCEPTION                                 |
|         (PDF Extractions, Raw Data, Documents)                 |
+----------------------------------------------------------------+
    """)

    # =========================================================================
    # 3. MULTI-AGENT SYSTEM
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("3. Multi-Agent System")

    pdf.body_text(
        "SynapseFlow uses specialized agents that communicate via message passing and escalation. "
        "Each agent has defined capabilities and handles specific types of knowledge operations."
    )

    pdf.chapter_title("Agent Hierarchy", 2)
    widths = [38, 65, 45, 42]
    pdf.table_header(["Agent", "Responsibilities", "Capabilities", "Escalates To"], widths)
    agents = [
        ["DataArchitect", "Design, planning, simple KG", "design, planning", "KnowledgeMgr"],
        ["DataEngineer", "Implementation, full KG ops", "kg_ops, data_proc", "-"],
        ["KnowledgeMgr", "Validation, reasoning, conflicts", "reasoning, audit", "-"],
        ["MedicalAssist", "Patient care, medical memory", "medical, memory", "KnowledgeMgr"],
    ]
    for i, row in enumerate(agents):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.chapter_title("Escalation Pattern", 2)
    pdf.ascii_diagram("""
DataArchitectAgent
    | (creates simple entity)
    | SUCCESS -> direct execution
    |
    | (creates complex relationship)
    | ESCALATE -> KnowledgeManagerAgent
                     | Advanced validation
                     | Conflict resolution
                     | Reasoning engine
                     | Execute or reject
                     | Send feedback to requester
    """)

    pdf.chapter_title("Agent Communication", 2)
    pdf.body_text(
        "Agents communicate via an EventBus (pub/sub) and direct message passing through "
        "CommunicationChannels. In development, InMemoryCommunicationChannel is used; "
        "in production, RabbitMQ distributes messages across pods."
    )

    # =========================================================================
    # 4. HYPERGRAPH BRIDGE ARCHITECTURE
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("4. Hypergraph Bridge Architecture")

    pdf.body_text(
        "The Hypergraph Bridge is a neurosymbolic layer that connects the Document Graph "
        "(neural/dense representations from text extraction) with the Knowledge Graph "
        "(symbolic/sparse ontology-aligned concepts). It uses FactUnits as hyperedges to "
        "represent multi-entity relationships extracted from shared contexts."
    )

    pdf.chapter_title("4.1 Why Hypergraphs?", 2)
    pdf.body_text(
        "Traditional knowledge graphs use binary edges (source -> relationship -> target), but "
        "real-world facts often involve multiple entities simultaneously. For example:"
    )
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 5.5,
        'Metformin 500mg is prescribed for Type 2 Diabetes in patients with obesity '
        'and kidney function > 30 mL/min'
    )
    pdf.ln(3)
    pdf.body_text("This single statement involves 5 entities simultaneously:")
    for item in [
        "Drug: Metformin 500mg",
        "Condition: Type 2 Diabetes",
        "Comorbidity: Obesity",
        "Constraint: Kidney function > 30 mL/min",
        "Relationship: Treatment prescription",
    ]:
        pdf.bullet(item)

    pdf.body_text(
        "A hypergraph represents this as a single hyperedge (FactUnit) connecting ALL entities, "
        "preserving the full context that would be lost with pairwise binary edges."
    )

    pdf.chapter_title("Architecture Overview", 2)
    pdf.ascii_diagram("""
+---------------------+                    +-------------------------+
|   DOCUMENT GRAPH    |                    |   KNOWLEDGE GRAPH       |
|   (Neural Layer)    |                    |   (Symbolic Layer)      |
+---------------------+                    +-------------------------+
| - PDF Chunks        |                    | - Disease (SNOMED)      |
| - ExtractedEntity   |                    | - Drug (RxNorm)         |
| - Embeddings        |                    | - Treatment protocols   |
| - Co-occurrences    |                    | - Ontology classes      |
+----------+----------+                    +------------+------------+
           |                                            |
           |         +-------------------------+        |
           +-------->|      BRIDGE LAYER       |<-------+
                     |       (FactUnit)        |
                     +-------------------------+
                     | - Hyperedges (N-ary)    |
                     | - Multi-source conf.    |
                     | - Provenance tracking   |
                     | - Ontology mappings     |
                     | - Participant roles     |
                     +-------------------------+
    """)

    # 4.2 Domain Models
    pdf.add_page()
    pdf.chapter_title("4.2 Domain Models", 2)
    pdf.body_text("All models live in src/domain/hypergraph_models.py with zero external dependencies.")

    pdf.chapter_title("FactUnit (Primary Hyperedge)", 3)
    pdf.body_text(
        "The primary hyperedge structure. Unlike a binary edge connecting exactly 2 nodes, "
        "a FactUnit connects N entities that share a factual context."
    )
    pdf.code_block("""@dataclass
class FactUnit:
    id: str                              # Deterministic SHA-256 hash
    fact_type: FactType                  # RELATIONSHIP, CAUSATION, TREATMENT...
    source_chunk_id: str
    source_document_id: str
    participants: List[EntityMention]    # All entities in this fact (N-ary)
    participant_roles: Dict[str, str]    # entity_id -> role
    fact_text: str
    confidence_scores: List[ConfidenceScore]
    aggregate_confidence: float          # Weighted combination
    embedding: Optional[List[float]]
    extraction_method: str               # "co_occurrence", "rule_based", "llm"
    validated: bool
    inferred_relationships: List[str]
    ontology_mappings: Dict[str, str]    # entity_id -> ontology_class""")

    pdf.chapter_title("FactType Enumeration", 3)
    widths = [40, 75, 75]
    pdf.table_header(["FactType", "Description", "Example"], widths)
    fact_types = [
        ["RELATIONSHIP", "Generic relation between entities", "Entity1 relates to Entity2"],
        ["ATTRIBUTE", "Entity has a property", "Metformin has dosage 500mg"],
        ["CAUSATION", "Entity1 causes Entity2", "Smoking causes lung cancer"],
        ["TREATMENT", "Drug treats Disease", "Metformin treats T2 Diabetes"],
        ["ASSOCIATION", "General co-occurrence", "Obesity + hypertension"],
        ["TEMPORAL", "Time-based relationship", "Diagnosis before treatment"],
        ["HIERARCHICAL", "IS_A or PART_OF", "Crohn's IS_A IBD"],
    ]
    for i, row in enumerate(fact_types):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.chapter_title("Other Key Models", 3)
    for model_name, desc in [
        ("EntityMention", "An entity within a chunk (position, confidence, embedding). The nodes that hyperedges connect."),
        ("HyperEdge", "Lightweight struct for a single PARTICIPATES_IN link between entity and FactUnit."),
        ("ConfidenceScore", "Single evidence contribution: value (0-1), source, evidence text, timestamp."),
        ("NeurosymbolicLink", "Bridges neural (embedding) and symbolic (ontology) for a single entity. Tracks dikw_layer, external_ids, alignment scores."),
        ("CoOccurrenceContext", "Analyzes entity co-occurrence within a chunk. Determines is_fact_candidate (>= 2 entities, avg conf >= 0.6)."),
        ("BridgeStatistics", "Aggregate metrics: total FactUnits, hyperedges, avg confidence, facts by type."),
    ]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(50, 80, 140)
        pdf.cell(0, 6, model_name, new_x="LMARGIN", new_y="NEXT")
        pdf.body_text(desc)

    # 4.3 Neo4j Storage
    pdf.add_page()
    pdf.chapter_title("4.3 Neo4j Storage Schema", 2)
    pdf.body_text(
        "Because Neo4j natively supports only binary edges, N-ary hyperedges are modeled using "
        "an intermediate node pattern (reification):"
    )
    pdf.ascii_diagram("""
(e1:Entity)--+
(e2:Entity)--+--[:PARTICIPATES_IN {role, position, confidence}]-->(f:FactUnit:Bridge)
(e3:Entity)--+
    """)

    pdf.chapter_title("FactUnit Node Properties", 3)
    pdf.code_block("""(:FactUnit:Bridge {
    id: "fact_abc123",
    fact_type: "treatment",
    source_chunk_id: "chunk_xyz",
    source_document_id: "doc_001",
    fact_text: "Metformin treats Type 2 Diabetes",
    aggregate_confidence: 0.85,
    extraction_method: "co_occurrence",
    participant_count: 2,
    validated: true,
    validation_count: 3,
    created_at: datetime()
})""", "Neo4j FactUnit node:")

    pdf.chapter_title("Inferred Relationships", 3)
    pdf.body_text("High-confidence facts create KG relationships via propagation:")
    pdf.code_block("""(e1:Entity)-[:INFERRED_FROM_FACT {
    fact_id: "fact_abc123",
    confidence: 0.85,
    inferred_at: datetime()
}]->(e2:Entity)""", "Cypher:")

    # 4.4 Bridge Operations
    pdf.chapter_title("4.4 Bridge Operations", 2)
    pdf.body_text("The HypergraphBridgeService (src/application/services/hypergraph_bridge_service.py) provides:")

    widths = [50, 140]
    pdf.table_header(["Method", "Purpose"], widths)
    ops = [
        ["build_bridge_layer()", "Scans chunks, creates FactUnits from co-occurrences"],
        ["get_facts_for_entity()", "Returns all FactUnits involving an entity + co-participants"],
        ["propagate_to_knowledge_graph()", "Creates INFERRED_FROM_FACT edges for high-conf facts"],
        ["find_fact_chains()", "Discovers 2-hop transitive reasoning chains"],
        ["validate_fact()", "Marks a FactUnit as human- or system-validated"],
        ["cleanup_low_confidence()", "Deletes unvalidated facts below threshold"],
        ["get_bridge_report()", "Stats + confidence distribution + recommendations"],
    ]
    for i, row in enumerate(ops):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.chapter_title("Build Bridge Layer Flow", 3)
    pdf.ascii_diagram("""
1. Query Neo4j for chunks with co-occurring entities (MENTIONS relationships)
2. For each chunk, create CoOccurrenceContext and call analyze()
3. Filter: is_fact_candidate? (>= 2 entities, avg confidence >= min_confidence)
4. Convert to FactUnit via context.to_fact_unit()
5. Persist FactUnit node + PARTICIPATES_IN edges in Neo4j
6. Enrich with ontology mappings
7. Return BridgeStatistics
    """)

    # 4.5 Confidence Aggregation
    pdf.chapter_title("4.5 Confidence Aggregation", 2)
    pdf.body_text("FactUnits aggregate confidence from multiple sources with weighted averaging:")

    widths = [55, 30, 105]
    pdf.table_header(["Confidence Source", "Weight", "Description"], widths)
    sources = [
        ["USER_VALIDATION", "1.0", "Human validation (highest trust)"],
        ["ONTOLOGY_MATCH", "0.9", "Ontology alignment (SNOMED, ICD-10, RxNorm)"],
        ["RULE_INFERENCE", "0.85", "Rule-based inference"],
        ["EXTRACTION_MODEL", "0.8", "NER/LLM extraction confidence"],
        ["EMBEDDING_SIMILARITY", "0.7", "Vector similarity score"],
        ["CO_OCCURRENCE", "0.6", "Simple co-occurrence (lowest trust)"],
    ]
    for i, row in enumerate(sources):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.code_block("""aggregate_confidence = sum(score.value * weight[score.source])
                   / sum(weight[score.source])""", "Formula:")

    # =========================================================================
    # 5. PROMOTION SYSTEM
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("5. Promotion System (Layer Transitions)")

    pdf.body_text(
        "SynapseFlow implements a sophisticated entity promotion system that automatically moves "
        "knowledge through the DIKW pyramid as it gains confidence, validation, and usage. "
        "Three services collaborate to manage this process."
    )

    pdf.chapter_title("5.1 LayerTransitionService", 2)
    pdf.body_text(
        "The foundational service (src/application/services/layer_transition.py) that validates "
        "and executes individual promotions with lineage tracking."
    )
    pdf.bullet("Validates layer hierarchy (no backward transitions)")
    pdf.bullet("Checks required properties for target layer")
    pdf.bullet("Versioning: creates new entity version on transition")
    pdf.bullet("Tracks lineage, property changes, and audit trail")
    pdf.bullet("Supports approval workflows (manual or auto)")

    pdf.chapter_title("Layer Requirements", 3)
    widths = [40, 75, 75]
    pdf.table_header(["Layer", "Required Properties", "Validation"], widths)
    reqs = [
        ["PERCEPTION", "source, origin", "Entry point (no validation)"],
        ["SEMANTIC", "description, domain", "Domain classification required"],
        ["REASONING", "confidence, reasoning", "Confidence in [0.0, 1.0]"],
        ["APPLICATION", "usage_context, access_pattern", "Usage documentation"],
    ]
    for i, row in enumerate(reqs):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.chapter_title("5.2 AutomaticLayerTransitionService", 2)
    pdf.body_text(
        "Event-driven service (src/application/services/automatic_layer_transition.py) that monitors "
        "the EventBus and promotes entities when configurable thresholds are met."
    )

    pdf.chapter_title("Event Subscriptions", 3)
    widths = [45, 50, 95]
    pdf.table_header(["Event", "Checks Layer", "Action"], widths)
    events = [
        ["entity_created", "PERCEPTION", "Check PERCEPTION -> SEMANTIC promotion"],
        ["entity_updated", "SEMANTIC/REASONING", "Check SEMANTIC -> REASONING promotion"],
        ["query_executed", "REASONING", "Track queries for APPLICATION promotion"],
    ]
    for i, row in enumerate(events):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.chapter_title("Configurable Thresholds (PromotionThresholds)", 3)
    widths = [55, 45, 90]
    pdf.table_header(["Transition", "Threshold", "Details"], widths)
    thresholds = [
        ["PERCEPTION -> SEMANTIC", "conf >= 0.85", "OR validation_count >= 3 OR ontology match"],
        ["SEMANTIC -> REASONING", "conf >= 0.90", "OR inference rule fired OR ref_count >= 5"],
        ["REASONING -> APPLICATION", "queries >= 10", "Within 24h AND cache_hit_rate >= 0.50"],
    ]
    for i, row in enumerate(thresholds):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.body_text(
        "The service also provides scan_for_promotion_candidates() and run_promotion_scan() "
        "for batch processing all eligible entities."
    )

    pdf.chapter_title("5.3 PromotionGate", 2)
    pdf.body_text(
        "Medical-domain gatekeeper (src/application/services/promotion_gate.py) that adds "
        "risk assessment and human review workflows to the promotion process."
    )

    pdf.chapter_title("Risk-Based Workflow", 3)
    widths = [30, 55, 105]
    pdf.table_header(["Risk", "Entity Types", "Workflow"], widths)
    risks = [
        ["LOW", "Demographics, Preferences", "Auto-promote when criteria met"],
        ["MEDIUM", "Symptoms, Observations, Vitals", "Log and auto-promote"],
        ["HIGH", "Medications, Diagnoses, Allergies", "Human review required (SEMANTIC+)"],
    ]
    for i, row in enumerate(risks):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.chapter_title("5.4 Promotion Criteria by Layer", 2)

    pdf.chapter_title("PERCEPTION -> SEMANTIC", 3)
    pdf.body_text("Focus: establishing validated, canonical concepts.")
    for c in [
        "Confidence >= 0.85",
        "Observation count >= 2",
        "Ontology match required (SNOMED-CT, ICD-10, RxNorm - mock lookup)",
        "No stability requirement",
        "Multi-source not required",
    ]:
        pdf.bullet(c)

    pdf.chapter_title("SEMANTIC -> REASONING", 3)
    pdf.body_text("Focus: deriving reliable inferences from validated concepts.")
    for c in [
        "Confidence >= 0.92",
        "Observation count >= 3",
        "Temporal stability >= 48 hours (no contradictions)",
        "Multi-source required (>= 3 sources)",
        "Ontology match required",
        "High-risk entities require human review",
    ]:
        pdf.bullet(c)

    pdf.chapter_title("REASONING -> APPLICATION", 3)
    pdf.body_text("Focus: proven utility through actual usage patterns.")
    for c in [
        "Confidence >= 0.95",
        "Observation count >= 5",
        "Temporal stability >= 168 hours (1 week)",
        "Multi-source required",
        "High-risk entities require human review",
        "Query frequency >= 10 in 24h (AutomaticLayerTransitionService)",
        "Cache hit rate >= 50% (AutomaticLayerTransitionService)",
    ]:
        pdf.bullet(c)

    # =========================================================================
    # 6. INFERENCE-TIME BEHAVIOR
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("6. Inference-Time Behavior")

    pdf.body_text(
        "This section describes what happens at runtime when a query arrives, from routing through "
        "reasoning to response generation."
    )

    pdf.chapter_title("6.1 Query Routing (DIKW Router)", 2)
    pdf.body_text(
        "The DIKWRouter (src/application/services/dikw_router.py) classifies query intent "
        "and routes to appropriate DIKW layers."
    )
    widths = [35, 55, 50, 50]
    pdf.table_header(["Intent", "Example", "Target Layers", "Strategy"], widths)
    intents = [
        ["FACTUAL", "When was my last visit?", "SEMANTIC, PERCEP", "SYMBOLIC_FIRST"],
        ["RELATIONAL", "What meds for X?", "SEMANTIC", "SYMBOLIC_FIRST"],
        ["INFERENTIAL", "Should I be worried?", "REASONING", "COLLABORATIVE"],
        ["ACTIONABLE", "What should I do?", "APPLICATION", "COLLABORATIVE"],
        ["EXPLORATORY", "Open-ended questions", "All layers", "NEURAL_FIRST"],
    ]
    for i, row in enumerate(intents):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.chapter_title("6.2 Reasoning Engine & Strategies", 2)
    pdf.body_text(
        "The ReasoningEngine (src/application/agents/knowledge_manager/reasoning_engine.py) "
        "is the core component that applies symbolic logic and neural inference."
    )

    pdf.chapter_title("Three Reasoning Strategies", 3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(50, 80, 140)
    pdf.cell(0, 7, "A) Neural-First", new_x="LMARGIN", new_y="NEXT")
    pdf.body_text(
        "LLM generates hypotheses (marked as 'tentative'), then symbolic rules validate them "
        "(marking validated ones as 'certain'). Used for symptom interpretation, context-heavy queries."
    )
    pdf.ascii_diagram("""
LLM Inference --> Tentative Hypotheses --> Symbolic Rules --> Validated Results
                  (neural_confidence)                        (symbolic_confidence)
    """)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(50, 80, 140)
    pdf.cell(0, 7, "B) Symbolic-First", new_x="LMARGIN", new_y="NEXT")
    pdf.body_text(
        "Rules fire first, LLM fills gaps only if fewer than 2 inferences produced. "
        "Used for data catalog queries, structured information lookups."
    )

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(50, 80, 140)
    pdf.cell(0, 7, "C) Collaborative (default)", new_x="LMARGIN", new_y="NEXT")
    pdf.body_text(
        "Both neural and symbolic run in parallel. Results are combined with confidence weighting. "
        "Used for treatment recommendations, general queries."
    )

    pdf.chapter_title("Reasoning Rules by Action", 3)
    pdf.body_text("For chat_query (the most common inference-time action):")
    widths = [55, 25, 110]
    pdf.table_header(["Rule", "Priority", "Function"], widths)
    rules = [
        ["contraindication_check", "CRITICAL", "Patient safety: drug interactions, allergies"],
        ["medical_context_validation", "HIGH", "Validate medical entities in query"],
        ["cross_graph_inference", "HIGH", "Link medical entities to data entities"],
        ["treatment_history_analysis", "HIGH", "Analyze patient treatment patterns"],
        ["symptom_tracking", "MEDIUM", "Track symptoms over time"],
        ["treatment_recommendation", "MEDIUM", "Safety check for medical advice"],
        ["data_availability_assessment", "MEDIUM", "Score data quality for context"],
        ["medication_adherence", "LOW", "Check medication compliance"],
        ["confidence_scoring", "LOW", "Calculate overall answer confidence"],
    ]
    for i, row in enumerate(rules):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.add_page()
    pdf.chapter_title("6.3 Medical Safety Rules", 2)
    pdf.body_text(
        "At inference time, the contraindication_check rule runs at CRITICAL priority before "
        "all other rules. It uses the MedicalRulesEngine to evaluate:"
    )
    for item in [
        "Allergy contraindications: patient allergies vs. mentioned substances",
        "Drug interactions: current medications vs. discussed medications",
        "Known interaction databases (expandable with real pharmacology data)",
        "Risk severity classification: CRITICAL, HIGH, MEDIUM, LOW",
    ]:
        pdf.bullet(item)

    pdf.body_text(
        "If a CRITICAL severity result is found, the system adds a safety warning to the "
        "response before any other reasoning proceeds."
    )

    pdf.chapter_title("6.4 Cross-Layer Confidence Propagation", 2)
    pdf.body_text("At inference time, confidence is adjusted when traversing DIKW layers:")

    widths = [47, 47, 48, 48]
    pdf.table_header(["Layer", "Trust Weight", "Downward Decay", "Upward Decay"], widths)
    conf_rows = [
        ["APPLICATION", "1.0", "-> REASONING: 0.95", "From REASONING: 0.92"],
        ["REASONING", "0.9", "-> SEMANTIC: 0.90", "From SEMANTIC: 0.95"],
        ["SEMANTIC", "0.8", "-> PERCEPTION: 0.85", "From PERCEPTION: 0.98"],
        ["PERCEPTION", "0.6", "-", "-"],
    ]
    for i, row in enumerate(conf_rows):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.body_text(
        "When layers conflict: higher layer wins by default. If confidence gap > threshold (0.3), "
        "the higher-confidence result wins regardless of layer. Unclear cases are flagged for review."
    )

    pdf.chapter_title("6.5 Temporal Scoring", 2)
    pdf.body_text(
        "Queries incorporate temporal relevance using exponential decay. "
        "Each entity type has a different decay rate (lambda):"
    )

    widths = [45, 30, 55, 60]
    pdf.table_header(["Entity Type", "Lambda", "Half-life", "Meaning"], widths)
    temporal = [
        ["Symptom", "0.05", "~20 hours", "Symptoms become stale quickly"],
        ["Vital sign", "0.03", "~33 hours", "Vitals relevant for ~1 day"],
        ["Medication", "0.005", "~8 days", "Meds relevant for weeks"],
        ["Diagnosis", "0.001", "~42 days", "Diagnoses persist months"],
        ["Allergy", "0.0001", "~290 days", "Almost permanent relevance"],
    ]
    for i, row in enumerate(temporal):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    pdf.ln(3)
    pdf.code_block("relevance_score = exp(-lambda * hours_since_observation)", "Formula:")

    # =========================================================================
    # COMPLETE INFERENCE-TIME FLOW
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("Complete Inference-Time Flow", 2)
    pdf.body_text("End-to-end flow when a patient query arrives:")

    pdf.ascii_diagram("""
1. User Message arrives at MedicalAssistantAgent
                |
2. PatientMemoryService.get_patient_context()
   |-- Redis: Check active session (24h TTL)
   |-- Mem0: Query relevant memories (semantic search)
   |-- Neo4j: Load patient profile (diagnoses, meds, allergies)
   |-- Aggregate -> PatientContext
                |
3. DIKWRouter classifies intent -> selects target layers + strategy
                |
4. NeurosymbolicQueryService selects execution strategy:
   Drug interaction -> SYMBOLIC_ONLY (no hallucination risk)
   Symptom interpret -> NEURAL_FIRST (context understanding)
   Treatment rec.    -> COLLABORATIVE (hybrid knowledge)
                |
5. ReasoningEngine.apply_reasoning(event, strategy)
   |-- CRITICAL: contraindication_check (allergies, drug interactions)
   |-- HIGH: medical_context_validation, cross_graph_inference
   |-- HIGH: treatment_history_analysis
   |-- MEDIUM: symptom_tracking, data_availability_assessment
   |-- LOW: medication_adherence, confidence_scoring
                |
6. Layer traversal with confidence propagation:
   APPLICATION (cached) -> REASONING (inferred) -> SEMANTIC (validated)
   -> PERCEPTION (raw), applying decay factors at each crossing
                |
7. Temporal scoring: weight results by recency (exp decay)
                |
8. Generate response via LLM with full context
                |
9. Store conversation:
   |-- Mem0: Extract + store facts (intelligent)
   |-- Neo4j: Log full message (permanent)
   |-- Redis: Update session TTL (ephemeral)
    """)

    # =========================================================================
    # 7. INTEGRATION
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("7. Integration: Hypergraph + Promotion + Inference")

    pdf.body_text(
        "The three subsystems work together in a continuous cycle of knowledge creation, "
        "validation, and consumption:"
    )

    pdf.chapter_title("Knowledge Lifecycle", 2)
    pdf.ascii_diagram("""
  DOCUMENT INGESTION          HYPERGRAPH BRIDGE            KNOWLEDGE GRAPH
  +------------------+        +-------------------+        +-----------------+
  | PDF/DDA Upload   |------->| build_bridge_layer|------->| PERCEPTION      |
  | Entity Extraction|        | Co-occ -> FactUnit|        | (conf ~0.7)     |
  | NER + Embeddings |        | N-ary hyperedges  |        |                 |
  +------------------+        +-------------------+        +---------+-------+
                                       |                             |
                              propagate_to_kg()              PROMOTION SYSTEM
                              (conf >= 0.7)           +------|-------+-------+
                                       |              |      |               |
                                       v              | Auto |  PromotionGate
                              +-------------------+   | Layer|  (Risk-based)
                              | INFERRED_FROM_FACT|   | Svc  |               |
                              | relationships     |   +------+               |
                              +-------------------+          |               |
                                                    +--------v--------+      |
                                                    | SEMANTIC        |      |
                                                    | (conf >= 0.85)  |------+
                                                    | SNOMED matched  |      |
                                                    +--------+--------+      |
                                                             |               |
                                                    +--------v--------+      |
                                                    | REASONING       |------+
                                                    | (conf >= 0.92)  |
                                                    | Rules applied   |
                                                    +--------+--------+
                                                             |
                                                    +--------v--------+
                                                    | APPLICATION     |
                                                    | Query patterns  |
                                                    | Cache results   |
                                                    +-----------------+
    """)

    pdf.chapter_title("How They Connect", 2)

    pdf.chapter_title("Hypergraph -> Promotion", 3)
    pdf.body_text(
        "When the Hypergraph Bridge propagates high-confidence FactUnits to the Knowledge Graph "
        "via INFERRED_FROM_FACT relationships, those new entities enter at the PERCEPTION layer. "
        "The AutomaticLayerTransitionService detects entity_created events and evaluates them "
        "for promotion through the DIKW hierarchy."
    )

    pdf.chapter_title("Promotion -> Inference", 3)
    pdf.body_text(
        "As entities are promoted to higher layers, they become available for higher-level "
        "reasoning. SEMANTIC entities are used in ontology-based lookups. REASONING entities "
        "participate in cross-graph inference. APPLICATION entities serve as cached query patterns "
        "that speed up repeated inference requests."
    )

    pdf.chapter_title("Inference -> Hypergraph", 3)
    pdf.body_text(
        "During inference, the cross_graph_inference rule in the ReasoningEngine can query "
        "the Hypergraph Bridge (get_facts_for_entity) to discover N-ary relationships that "
        "would not be visible in the binary Knowledge Graph. These bridge inferences feed "
        "back into the confidence scoring and may trigger new entity_updated events that "
        "drive further promotions."
    )

    pdf.chapter_title("Crystallization Pipeline", 3)
    pdf.body_text(
        "Additionally, the Crystallization Pipeline transfers knowledge from episodic memory "
        "(Graphiti/FalkorDB) to the DIKW Knowledge Graph in Neo4j. Episodic episodes are "
        "deduplicated via EntityResolver, classified into DIKW layers, and fed into the "
        "promotion pipeline. This completes the cycle: patient conversations create episodes, "
        "episodes crystallize into knowledge, knowledge is promoted through layers, and "
        "promoted knowledge improves future inference quality."
    )

    # =========================================================================
    # FILE INDEX
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("Appendix: Key File Index")

    widths = [90, 100]
    pdf.table_header(["File Path", "Role"], widths)
    files = [
        ["src/domain/hypergraph_models.py", "All hypergraph domain models"],
        ["src/application/services/hypergraph_bridge_service.py", "Build, query, propagate bridge"],
        ["src/application/services/layer_transition.py", "Core layer transition with validation"],
        ["src/application/services/automatic_layer_transition.py", "Event-driven auto-promotion"],
        ["src/application/services/promotion_gate.py", "Medical-domain promotion gatekeeper"],
        ["src/application/agents/knowledge_manager/reasoning_engine.py", "Neurosymbolic reasoning"],
        ["src/application/services/dikw_router.py", "Query intent -> DIKW layer routing"],
        ["src/application/services/neurosymbolic_query_service.py", "Strategy selection + execution"],
        ["src/application/services/remediation_service.py", "FactUnit ontology remediation"],
        ["src/domain/confidence_models.py", "Confidence tracking models"],
        ["src/domain/promotion_models.py", "Promotion domain models"],
        ["docs/architecture/HYPERGRAPH_BRIDGE_ARCHITECTURE.md", "Hypergraph architecture doc"],
        ["docs/architecture/REASONING_ARCHITECTURE.md", "Reasoning system overview"],
        ["docs/architecture/KNOWLEDGE_GRAPH_LAYERS_ARCHITECTURE.md", "DIKW layers doc"],
        ["docs/architecture/ARCHITECTURE.md", "General system architecture"],
    ]
    for i, row in enumerate(files):
        pdf.table_row(row, widths, fill=(i % 2 == 0))

    # Save
    output_path = "/home/user/SynapseFlow/docs/SynapseFlow_Architecture_Hypergraph_Promotion.pdf"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf.output(output_path)
    print(f"PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    build_pdf()
