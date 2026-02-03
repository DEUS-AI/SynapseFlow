# Multi-Agent Knowledge Management System - Architecture Documentation

**Version**: 2.0 (with Patient Memory System)
**Date**: 2026-01-22
**Status**: Production-ready with Phase 2A complete

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architectural Principles](#2-architectural-principles)
3. [Layer Architecture](#3-layer-architecture)
4. [Core Design Patterns](#4-core-design-patterns)
5. [Domain Models](#5-domain-models)
6. [Agent System](#6-agent-system)
7. [Knowledge Graph System](#7-knowledge-graph-system)
8. [Patient Memory System (NEW)](#8-patient-memory-system)
9. [Reasoning & Validation](#9-reasoning--validation)
10. [Communication Patterns](#10-communication-patterns)
11. [Key Workflows](#11-key-workflows)
12. [Deployment Architecture](#12-deployment-architecture)

---

## 1. System Overview

### Purpose

A **neurosymbolic multi-agent system** for intelligent knowledge management that combines:
- **Symbolic AI**: Rule-based reasoning, ontology mapping, validation
- **Neural AI**: LLM-based inference, embeddings, semantic understanding
- **Multi-agent collaboration**: Specialized agents with escalation patterns
- **Domain-Driven Design**: Clean architecture with rich domain models

### Key Capabilities

1. **Domain-Driven Architecture (DDA) Modeling**
   - Parse business domain specifications from Markdown
   - Generate knowledge graphs with 4-layer architecture
   - Validate against business rules and constraints

2. **ODIN Metadata Management**
   - Catalog data assets (tables, columns, schemas)
   - Track lineage and quality metrics
   - Enforce governance policies

3. **Neurosymbolic Reasoning**
   - Symbolic rules + LLM inference
   - Confidence tracking with provenance
   - Entity resolution with multiple strategies

4. **Patient Medical Memory (NEW)**
   - 3-layer memory architecture (Redis + Mem0 + Neo4j)
   - Intelligent conversation tracking
   - Medical history management
   - GDPR-compliant data handling

5. **RAG-Enhanced Chat**
   - Document ingestion (PDFs, DOCX)
   - FAISS vector search
   - Context-aware responses

---

## 2. Architectural Principles

### Clean Architecture (Onion Architecture)

```
┌─────────────────────────────────────────────────┐
│            Interfaces Layer                     │
│   (CLI, REST API, Composition Root)             │
├─────────────────────────────────────────────────┤
│          Infrastructure Layer                   │
│  (Neo4j, Redis, Mem0, RabbitMQ, Parsers)        │
├─────────────────────────────────────────────────┤
│          Application Layer                      │
│   (Services, Agents, Commands, Workflows)       │
├─────────────────────────────────────────────────┤
│            Domain Layer                         │
│   (Models, Interfaces, Business Rules)          │
│            [NO DEPENDENCIES]                    │
└─────────────────────────────────────────────────┘
```

**Dependency Rule**: Dependencies point inward only. Domain layer has zero dependencies on outer layers.

### Domain-Driven Design (DDD)

- **Bounded Contexts**:
  - Domain Architecture Context (DDA models)
  - Data Catalog Context (ODIN models)
  - Medical Context (Patient memory)
  - Knowledge Management Context (KG operations)

- **Aggregates**:
  - `DDADocument` (root)
  - `PatientContext` (root)
  - `CanonicalConcept` (root)

- **Value Objects**:
  - `Confidence`, `EntityMatch`, `ConversationMessage`

- **Domain Events**:
  - `KnowledgeEvent` for event sourcing

- **Repositories**:
  - `KnowledgeGraphBackend` abstraction

### CQRS (Command Query Responsibility Segregation)

- **Commands**: Write operations via `CommandBus`
  - `ModelingCommand`, `GenerateMetadataCommand`, `RunAgentCommand`
- **Queries**: Read operations via services
  - `get_patient_context()`, `query()`, `search()`

### Event-Driven Architecture

- **Event Bus**: Pub/sub messaging between agents
- **Message Passing**: Async agent communication
- **Event Sourcing**: All operations logged as events

---

## 3. Layer Architecture

### 3.1 Domain Layer (`src/domain/`)

**Responsibility**: Core business logic, models, and abstractions

**Zero Dependencies**: Pure Python, no external libraries

```python
domain/
├── agent.py                  # Abstract Agent base class
├── agent_definition.py       # Agent API definition
├── command_bus.py            # CommandBus abstraction
├── communication.py          # Message & Channel abstractions
├── event.py                  # KnowledgeEvent
├── kg_backends.py            # KnowledgeGraphBackend interface
├── roles.py                  # RBAC roles
├── dda_models.py             # DDA domain models
├── odin_models.py            # ODIN metadata models
├── knowledge_layers.py       # 4-layer KG architecture
├── canonical_concepts.py     # Business concept registry
├── confidence_models.py      # Neurosymbolic confidence
└── ontologies/               # Ontology definitions
```

**Key Abstractions**:

```python
# Agent abstraction
class Agent(ABC):
    @abstractmethod
    async def process_messages() -> None

# Knowledge Graph Backend
class KnowledgeGraphBackend(ABC):
    @abstractmethod
    async def add_entity(entity_id, properties, labels)
    @abstractmethod
    async def add_relationship(source, type, target, properties)
    @abstractmethod
    async def query(query: str) -> Any
```

### 3.2 Application Layer (`src/application/`)

**Responsibility**: Orchestration, workflows, use cases

**Dependencies**: Domain layer only (via abstractions)

```python
application/
├── knowledge_management.py       # KG service with RBAC
├── event_bus.py                  # Event bus implementation
├── agent_runner.py               # Agent lifecycle
├── agents/
│   ├── data_architect/           # Design & planning agent
│   ├── data_engineer/            # Implementation agent
│   ├── knowledge_manager/        # Complex ops agent
│   └── medical_assistant/        # Patient care agent (NEW)
├── commands/                     # CQRS command handlers
│   ├── modeling_command.py
│   ├── metadata_command.py
│   └── agent_commands.py
└── services/
    ├── patient_memory_service.py # 3-layer memory (NEW)
    ├── entity_resolver.py        # Deduplication
    ├── knowledge_enricher.py     # Semantic enrichment
    ├── document_service.py       # Document ingestion
    └── rag_service.py            # RAG capabilities
```

### 3.3 Infrastructure Layer (`src/infrastructure/`)

**Responsibility**: External integrations, persistence, I/O

**Dependencies**: Domain abstractions (implements interfaces)

```python
infrastructure/
├── neo4j_backend.py              # Neo4j implementation
├── falkor_backend.py             # FalkorDB implementation
├── graphiti_backend.py           # Graphiti integration
├── redis_session_cache.py        # Redis sessions (NEW)
├── communication/
│   ├── memory_channel.py         # In-memory messaging
│   └── a2a_channel.py            # Agent-to-agent channel
├── event_bus/
│   └── rabbitmq_event_bus.py     # RabbitMQ integration
└── parsers/
    └── markdown_parser.py        # DDA Markdown parser
```

### 3.4 Interface Layer (`src/interfaces/`, `src/config/`)

**Responsibility**: User interfaces, dependency injection

```python
interfaces/
├── cli.py                        # Typer CLI
├── kg_api.py                     # FastAPI REST API
└── kg_operations_api.py          # KG operations facade

config/
├── memory_config.py              # Mem0 configuration (NEW)
└── __init__.py

composition_root.py               # DI container
```

---

## 4. Core Design Patterns

### 4.1 Repository Pattern

**Purpose**: Abstract data access

```python
# Domain abstraction
class KnowledgeGraphBackend(ABC):
    @abstractmethod
    async def add_entity(...)
    @abstractmethod
    async def add_relationship(...)
    @abstractmethod
    async def query(...)

# Implementations
- Neo4jBackend
- FalkorBackend
- GraphitiBackend
- InMemoryBackend (testing)
```

### 4.2 Agent Pattern

**Purpose**: Autonomous, specialized workers

```python
class Agent(ABC):
    agent_id: str
    command_bus: CommandBus
    communication_channel: CommunicationChannel

    async def process_messages() -> None:
        while True:
            message = await self.receive_message()
            await self.handle_message(message)
```

**Agents**:
- `DataArchitectAgent` - High-level design
- `DataEngineerAgent` - Implementation
- `KnowledgeManagerAgent` - Complex operations
- `MedicalAssistantAgent` - Patient care

### 4.3 Strategy Pattern

**Purpose**: Pluggable algorithms

```python
# Entity Resolution Strategies
class ResolutionStrategy(Enum):
    EXACT = "exact"           # String equality
    FUZZY = "fuzzy"          # Levenshtein distance
    EMBEDDING = "embedding"  # Semantic similarity
    HYBRID = "hybrid"        # Combined approach

# Reasoning Strategies
class ReasoningMode(Enum):
    NEURAL_FIRST = "neural_first"
    SYMBOLIC_FIRST = "symbolic_first"
    COLLABORATIVE = "collaborative"
```

### 4.4 Factory Pattern

**Purpose**: Object creation abstraction

```python
# Agent Registry
AGENT_REGISTRY: Dict[str, Callable[..., Agent]] = {
    "data_architect": create_data_architect_agent,
    "data_engineer": create_data_engineer_agent,
    "knowledge_manager": create_knowledge_manager_agent,
    "medical_assistant": create_medical_assistant_agent,
}

# Parser Factory
class DDAParserFactory:
    @staticmethod
    def get_parser(file_type: str) -> DDAParser:
        if file_type == "markdown":
            return MarkdownDDAParser()
```

### 4.5 Observer Pattern (Event Bus)

**Purpose**: Pub/sub messaging

```python
# Subscribe to events
event_bus.subscribe("complex_entity_operation", handler)

# Publish events
event = KnowledgeEvent(
    action="create_entity",
    data={...},
    role=Role.DATA_ARCHITECT
)
await event_bus.publish(event)
```

### 4.6 Command Pattern (CQRS)

**Purpose**: Encapsulate operations as objects

```python
@dataclass
class ModelingCommand:
    dda_path: str
    output_path: str

class ModelingCommandHandler(CommandHandler):
    async def handle(self, command: ModelingCommand):
        # Execute workflow
        pass

# Dispatch
result = await command_bus.dispatch(ModelingCommand(...))
```

### 4.7 Decorator Pattern

**Purpose**: Add cross-cutting concerns

- **Confidence Tracking**: Wrap operations with confidence metadata
- **Provenance Tracking**: Track reasoning rule applications
- **Audit Logging**: Log data access for compliance

---

## 5. Domain Models

### 5.1 Knowledge Layer Architecture

The system uses a **4-layer knowledge graph** based on the SECI model:

```
┌─────────────────────────────────────────────────┐
│  Layer 4: APPLICATION                           │
│  - Use cases, queries, views                    │
│  - Business applications                        │
├─────────────────────────────────────────────────┤
│  Layer 3: REASONING                             │
│  - Inferred knowledge, rules                    │
│  - Derived relationships                        │
├─────────────────────────────────────────────────┤
│  Layer 2: SEMANTIC                              │
│  - Business concepts, entities                  │
│  - Canonical definitions                        │
├─────────────────────────────────────────────────┤
│  Layer 1: PERCEPTION                            │
│  - Raw data (tables, columns, files)            │
│  - Data catalog metadata                        │
└─────────────────────────────────────────────────┘
```

**Layer Transitions**:
- Perception → Semantic: Entity resolution, concept mapping
- Semantic → Reasoning: Rule application, inference
- Reasoning → Application: Query generation, view creation

### 5.2 DDA Models (Domain-Driven Architecture)

**Purpose**: Specify business domains and data architecture

```python
@dataclass
class DDADocument:
    """Complete business domain specification."""
    metadata: Dict[str, Any]
    data_entities: List[DataEntity]
    relationships: List[Relationship]
    data_quality_requirements: List[DataQualityRequirement]
    access_patterns: List[AccessPattern]
    governance: Governance

@dataclass
class DataEntity:
    """Business entity with attributes and rules."""
    name: str
    description: str
    attributes: List[DataAttribute]
    business_rules: List[BusinessRule]

@dataclass
class Relationship:
    """Entity relationship (1:1, 1:N, M:N)."""
    source: str
    target: str
    cardinality: str
    description: str
```

### 5.3 ODIN Models (Open Data Integration Network)

**Purpose**: Metadata catalog for data assets

```python
@dataclass
class Catalog:
    """Top-level data catalog."""
    name: str
    schemas: List[Schema]

@dataclass
class Schema:
    """Database schema."""
    name: str
    tables: List[Table]

@dataclass
class Table:
    """Data table with columns."""
    name: str
    columns: List[Column]
    constraints: List[Constraint]

@dataclass
class Column:
    """Table column with type and constraints."""
    name: str
    data_type: str
    nullable: bool
    constraints: List[Constraint]
```

**Metadata Enrichment**:
- Lineage tracking (`LineageNode`, `LineageRelationship`)
- Quality metrics (`DataQualityScore`)
- Usage statistics (`UsageStats`)
- Governance policies (`Policy`)

### 5.4 Canonical Concepts

**Purpose**: Authoritative business concept definitions

```python
@dataclass
class CanonicalConcept:
    """Authoritative business concept."""
    concept_id: str
    name: str
    definition: str
    aliases: List[str]
    related_concepts: List[str]
    confidence: Confidence
    version: str

class ConceptRegistry:
    """Concept lookup and management."""
    def register_concept(concept: CanonicalConcept)
    def resolve_concept(name: str) -> CanonicalConcept
    def get_hierarchy() -> Dict[str, List[str]]
```

### 5.5 Confidence Models (Neurosymbolic AI)

**Purpose**: Track certainty of knowledge

```python
@dataclass
class Confidence:
    """Confidence score with provenance."""
    score: float  # [0.0, 1.0]
    source: str
    uncertainty_type: str  # "aleatory" or "epistemic"
    provenance: List[str]  # Reasoning rules applied

class ConfidenceCombination(Enum):
    """Aggregation strategies."""
    MIN = "min"
    MAX = "max"
    WEIGHTED = "weighted"
    NOISY_OR = "noisy_or"

@dataclass
class ConfidencePropagation:
    """Confidence decay through reasoning chains."""
    decay_factor: float = 0.95
    min_threshold: float = 0.3
```

### 5.6 Patient Models (NEW)

**Purpose**: Medical history and patient care

```python
@dataclass
class PatientContext:
    """Complete patient context for reasoning."""
    patient_id: str
    diagnoses: List[Dict[str, Any]]
    medications: List[Dict[str, Any]]
    allergies: List[str]
    recent_symptoms: List[Dict[str, Any]]
    conversation_summary: str
    last_updated: datetime

@dataclass
class ConversationMessage:
    """Message with patient context."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    patient_id: str
    session_id: str
    metadata: Dict[str, Any]
```

**Neo4j Schema**:
```cypher
(:Patient)-[:HAS_DIAGNOSIS]->(:Diagnosis)
(:Patient)-[:CURRENT_MEDICATION]->(:Medication)
(:Patient)-[:HAS_ALLERGY]->(:Allergy)
(:Patient)-[:HAS_SESSION]->(:ConversationSession)
(:ConversationSession)-[:HAS_MESSAGE]->(:Message)
(:Patient)-[:HAS_AUDIT_LOG]->(:AuditLog)
```

---

## 6. Agent System

### 6.1 Agent Hierarchy

```
Agent (abstract base)
│
├── DataArchitectAgent
│   Responsibilities:
│   - High-level design and planning
│   - Simple KG updates (entities only)
│   - Escalates complex operations
│   Capabilities: ["design", "planning", "simple_kg_updates"]
│
├── DataEngineerAgent
│   Responsibilities:
│   - Implementation and data processing
│   - Full KG operations (entities + relationships)
│   - Metadata generation workflow
│   Capabilities: ["implementation", "kg_operations", "data_processing"]
│
├── KnowledgeManagerAgent
│   Responsibilities:
│   - Complex KG operations
│   - Validation, reasoning, conflict resolution
│   - Handles escalated operations
│   Capabilities: ["complex_validation", "reasoning", "audit_trail"]
│
├── MedicalAssistantAgent (NEW)
│   Responsibilities:
│   - Patient interactions
│   - Medical reasoning
│   - 3-layer memory management
│   Capabilities: ["patient_care", "medical_reasoning", "memory_management"]
│
└── EchoAgent
    Responsibilities:
    - Testing/demo purposes
```

### 6.2 Agent Capabilities

Each agent declares its capabilities in the knowledge graph:

```python
await agent.register_self()
# Creates:
# (:Agent {id, capabilities: ["design", "planning"]})
```

Other agents discover by capability:

```python
km_agent_url = await agent.discover_agent("knowledge_management")
```

### 6.3 Escalation Pattern

```
DataArchitectAgent
    ↓ (creates simple entity)
    ↓ SUCCESS (direct execution)

DataArchitectAgent
    ↓ (creates complex relationship)
    ↓ ESCALATE → KnowledgeManagerAgent
                     ↓ Advanced validation
                     ↓ Conflict resolution
                     ↓ Reasoning
                     ↓ Execute or reject
                     ↓ Send feedback
```

**Escalation Logic**:
```python
if operation_requires_reasoning or has_conflicts:
    escalate_to_knowledge_manager()
else:
    execute_directly()
```

### 6.4 Agent Communication

**Message Format**:
```python
@dataclass
class Message:
    sender_id: str
    receiver_id: str
    content: Any  # Dict with type and data
    metadata: Dict[str, Any]
    timestamp: datetime
```

**Channels**:
- `InMemoryCommunicationChannel`: Single-process deployments
- `RabbitMQEventBus`: Distributed deployments

---

## 7. Knowledge Graph System

### 7.1 Backend Abstraction

```python
class KnowledgeGraphBackend(ABC):
    """Abstract KG backend interface."""

    @abstractmethod
    async def add_entity(
        entity_id: str,
        properties: Dict[str, Any],
        labels: List[str] = None
    ) -> None

    @abstractmethod
    async def add_relationship(
        source_id: str,
        relationship_type: str,
        target_id: str,
        properties: Dict[str, Any]
    ) -> None

    @abstractmethod
    async def query(query: str, parameters: Dict) -> Any

    @abstractmethod
    async def search(
        query: str,
        filters: Dict = None
    ) -> List[Dict]
```

### 7.2 Backend Implementations

#### **Neo4jBackend** (Primary production backend)

```python
class Neo4jBackend(KnowledgeGraphBackend):
    """Neo4j implementation with async driver."""

    - Cypher query execution
    - Label-based categorization
    - Property graph model
    - ACID transactions
    - Full-text search support

    Methods:
    - query(): Returns {nodes, edges, query, parameters}
    - query_raw(): Returns List[Dict] for scalar values
    - add_entity(): MERGE with dynamic labels
    - add_relationship(): MERGE nodes + CREATE relationship
```

#### **FalkorBackend** (Redis-based graph)

```python
class FalkorBackend(KnowledgeGraphBackend):
    """FalkorDB (Redis graph module) implementation."""

    - JSON property serialization
    - Sync-to-async wrapper
    - Rollback via operation history
    - Fast in-memory graph queries
```

#### **GraphitiBackend** (Episodic memory)

```python
class GraphitiBackend(KnowledgeGraphBackend):
    """Graphiti integration for episodic memory."""

    - Maps to EntityNode/EntityEdge
    - Triplet-based relationships
    - Temporal graph support
    - JSON attribute serialization
```

### 7.3 Cross-Graph Queries

The system maintains multiple graphs:

1. **ODIN Graph** (Data Catalog): Tables, columns, schemas
2. **Business Concept Graph**: Canonical concepts, relationships
3. **Patient Medical Graph**: Diagnoses, medications, history
4. **Conversation Graph**: Session logs, message history

**Cross-Graph Reasoning**:
```cypher
// Find data entities containing patient allergy information
MATCH (concept:CanonicalConcept {name: "Allergy"})
MATCH (concept)-[:SEMANTIC_LINK]->(table:Table)
MATCH (patient:Patient)-[:HAS_ALLERGY]->(allergy:Allergy)
WHERE allergy.substance IN table.columns
RETURN table, allergy
```

---

## 8. Patient Memory System

### 8.1 Three-Layer Architecture

```
┌──────────────────────────────────────────────────┐
│  Layer 1: SHORT-TERM (Redis - 24h TTL)          │
│  - Active session state                          │
│  - Last activity tracking                        │
│  - Device information                            │
│  - Temporary context cache                       │
├──────────────────────────────────────────────────┤
│  Layer 2: MID-TERM (Mem0 - Intelligent)         │
│  - Automatic fact extraction                     │
│  - Semantic memory compression                   │
│  - Graph-based memory relationships              │
│  - Vector search (Qdrant)                        │
├──────────────────────────────────────────────────┤
│  Layer 3: LONG-TERM (Neo4j - Permanent)         │
│  - Patient medical history                       │
│  - Full conversation logs                        │
│  - Diagnoses, medications, allergies             │
│  - Audit trail for compliance                    │
└──────────────────────────────────────────────────┘
```

### 8.2 Data Flow

```
User Message
    ↓
1. Redis: Check active session
    ├─ Hit: Load session metadata
    └─ Miss: Create new session
    ↓
2. Mem0: Query relevant memories
    ├─ Patient-specific facts
    ├─ Recent conversation context
    └─ Semantic memory search
    ↓
3. Neo4j: Load patient profile
    ├─ Diagnoses
    ├─ Medications
    ├─ Allergies
    └─ Medical history
    ↓
4. Aggregate → PatientContext
    ↓
5. LLM reasoning with context
    ↓
6. Generate response
    ↓
7. Store conversation
    ├─ Mem0: Extract + store facts
    ├─ Neo4j: Log full message
    └─ Redis: Update session TTL
```

### 8.3 PatientMemoryService

**Key Methods**:

```python
class PatientMemoryService:
    # Patient Profile
    async def get_or_create_patient(patient_id, consent_given=True) -> str
    async def get_patient_context(patient_id) -> PatientContext

    # Medical History
    async def add_diagnosis(patient_id, condition, icd10_code, ...) -> str
    async def add_medication(patient_id, name, dosage, frequency, ...) -> str
    async def add_allergy(patient_id, substance, reaction, severity) -> str

    # Conversation Management
    async def start_session(patient_id, device="web") -> str
    async def store_message(message: ConversationMessage) -> str
    async def get_conversation_history(session_id, limit=50) -> List[Dict]

    # Privacy & Compliance
    async def check_consent(patient_id) -> bool
    async def delete_patient_data(patient_id) -> bool  # GDPR
    async def log_audit(patient_id, action, actor, details) -> str
```

### 8.4 Privacy & Compliance

**GDPR Compliance**:
- ✅ Right to be forgotten (`delete_patient_data()`)
- ✅ Consent management
- ✅ PII anonymization (patient_id only, no real names)
- ✅ Audit logging for all data access
- ✅ Data retention policy (7 years configurable)

**HIPAA Considerations**:
- ✅ Access control via RBAC
- ✅ Audit trails for PHI access
- ✅ Encrypted storage (Neo4j encryption at rest)
- ⏸️ Redis TLS (configure for production)
- ⏸️ Data encryption in transit

---

## 9. Reasoning & Validation

### 9.1 ReasoningEngine

**Purpose**: Apply symbolic and neural reasoning to KG operations

```python
class ReasoningEngine:
    """Neurosymbolic reasoning engine."""

    reasoning_rules: Dict[str, List[ReasoningRule]]
    reasoning_mode: ReasoningMode  # neural_first, symbolic_first, collaborative
    llm_reasoner: LLMReasoner
```

**Reasoning Actions**:
- `create_entity`: Ontology mapping, property inference
- `create_relationship`: Relationship suggestions, validation
- `enrich_entity`: Semantic enrichment, concept linking
- `chat_query`: Medical context validation, safety checks (NEW)

**Reasoning Rules** (chat_query):
1. `medical_context_validation` - Validate medical entities
2. `cross_graph_inference` - Link medical entities to data entities
3. `treatment_recommendation_check` - Safety check for medical advice
4. `data_availability_assessment` - Score quality of available context
5. `confidence_scoring` - Calculate overall answer confidence

### 9.2 ValidationEngine

**Purpose**: Enforce constraints and rules

```python
class ValidationEngine:
    """Rule-based and SHACL validation."""

    async def validate_event(event: KnowledgeEvent) -> ValidationResult
```

**Validation Types**:
- **Rule-based**: Required fields, format validation, type checking
- **SHACL**: RDF shape validation, constraint checking
- **Layer constraints**: Ensure entities belong to correct layer
- **RBAC**: Role permission checking

**Validation Result**:
```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[ValidationError]  # Severity: ERROR
    warnings: List[ValidationWarning]  # Severity: WARNING
    suggestions: List[str]
```

### 9.3 ConflictResolver

**Purpose**: Detect and resolve entity conflicts

```python
class ConflictResolver:
    """Conflict detection and resolution."""

    async def detect_conflicts(event: KnowledgeEvent) -> List[Conflict]
    async def resolve_conflicts(conflicts: List[Conflict]) -> ResolutionPlan
```

**Conflict Types**:
- Duplicate entities (same name, different IDs)
- Contradictory relationships
- Property mismatches
- Schema violations

**Resolution Strategies**:
- Merge entities
- Create aliases
- Update properties
- Link instead of duplicate

### 9.4 EntityResolver

**Purpose**: Prevent duplicate entity creation

```python
class EntityResolver:
    """Multi-strategy entity resolution."""

    Resolution Strategies:
    - EXACT: String equality
    - FUZZY: Levenshtein distance (threshold: 0.85)
    - EMBEDDING: Semantic similarity (SentenceTransformers)
    - HYBRID: Combined approach with confidence weighting
```

**Resolution Result**:
```python
@dataclass
class ResolutionResult:
    action: str  # "merge", "link", "create_new"
    matched_entities: List[EntityMatch]
    confidence: float
    reasoning: str
```

---

## 10. Communication Patterns

### 10.1 Message Passing (Agent-to-Agent)

```python
# Agent A sends message to Agent B
message = Message(
    sender_id="data_architect_1",
    receiver_id="knowledge_manager_1",
    content={
        "type": "escalation_request",
        "operation": "create_relationship",
        "data": {...}
    }
)
await communication_channel.send(message)

# Agent B receives message
message = await communication_channel.receive("knowledge_manager_1")
await self.handle_message(message)
```

### 10.2 Event Bus (Pub/Sub)

```python
# Subscribe to events
event_bus.subscribe("complex_entity_operation", handler)

# Publish event
event = KnowledgeEvent(
    action="create_entity",
    data={"entity_id": "...", "properties": {...}},
    role=Role.DATA_ARCHITECT
)
await event_bus.publish(event)

# All subscribers receive event
async def handler(event: KnowledgeEvent):
    # Process event
    pass
```

### 10.3 Command Bus (CQRS)

```python
# Register command handler
command_bus.register(ModelingCommand, ModelingCommandHandler())

# Dispatch command
command = ModelingCommand(dda_path="path/to/dda.md")
result = await command_bus.dispatch(command)

# Handler executes
class ModelingCommandHandler(CommandHandler):
    async def handle(self, command: ModelingCommand):
        # Execute modeling workflow
        return ModelingResult(...)
```

---

## 11. Key Workflows

### 11.1 DDA Modeling Workflow

```
1. User: model --dda-path document.md
   ↓
2. CLI → ModelingCommand
   ↓
3. CommandBus → ModelingCommandHandler
   ↓
4. ModelingWorkflow.execute()
   ├─ Parse DDA (MarkdownDDAParser)
   ├─ Validate document (ValidationEngine)
   ├─ Create KG nodes (ArchitectureGraphWriter)
   ├─ Apply reasoning (ReasoningEngine)
   └─ Generate artifacts (JSON, diagrams)
   ↓
5. Handoff to DataEngineerAgent
   ↓
6. Generate metadata (ODIN)
```

### 11.2 Metadata Generation Workflow

```
1. GenerateMetadataCommand
   ↓
2. MetadataGenerationWorkflow
   ├─ Parse DDA → Extract entities
   ├─ Type Inference (LLM)
   ├─ Create ODIN nodes (Catalog, Schema, Table, Column)
   ├─ Semantic enrichment (KnowledgeEnricher)
   ├─ Entity resolution (EntityResolver)
   └─ Write to KG backend
   ↓
3. Validation (ValidationEngine)
   ↓
4. Reasoning (ReasoningEngine)
   ├─ Ontology mapping
   ├─ Property inference
   └─ Relationship suggestions
```

### 11.3 Patient Interaction Workflow (NEW)

```
1. User message → MedicalAssistantAgent
   ↓
2. PatientMemoryService.get_patient_context()
   ├─ Redis: Get session state
   ├─ Mem0: Get relevant memories
   └─ Neo4j: Get medical history
   ↓
3. Aggregate → PatientContext
   ↓
4. ReasoningEngine.apply_reasoning("chat_query")
   ├─ Validate medical entities
   ├─ Check for treatment recommendations (safety)
   ├─ Assess data availability
   └─ Calculate confidence
   ↓
5. Generate response with LLM + context
   ↓
6. PatientMemoryService.store_message()
   ├─ Mem0: Store with fact extraction
   ├─ Neo4j: Log full message
   └─ Redis: Update session state
```

### 11.4 Knowledge Graph Update with Escalation

```
1. Agent creates KnowledgeEvent
   ↓
2. Check operation complexity
   ├─ Simple → Execute directly
   └─ Complex → Escalate
       ↓
3. KnowledgeManagerAgent receives escalation
   ↓
4. ValidationEngine.validate_event()
   ├─ Required fields
   ├─ SHACL validation
   ├─ Role permissions
   └─ Layer constraints
   ↓
5. ConflictResolver.detect_conflicts()
   ├─ Check for duplicates
   └─ Apply auto-resolutions
   ↓
6. ReasoningEngine.apply_reasoning()
   ├─ Ontology mapping
   ├─ Property inference
   ├─ Relationship suggestions
   └─ LLM semantic inference
   ↓
7. Execute operation with confidence tracking
   ↓
8. Send feedback to requesting agent
```

---

## 12. Deployment Architecture

### 12.1 Single-Process Deployment (Development)

```
┌────────────────────────────────────────────────┐
│           Python Process                       │
├────────────────────────────────────────────────┤
│  CLI/API                                       │
│    ↓                                           │
│  Agents (in-memory communication)              │
│    ├─ DataArchitectAgent                      │
│    ├─ DataEngineerAgent                       │
│    ├─ KnowledgeManagerAgent                   │
│    └─ MedicalAssistantAgent                   │
│    ↓                                           │
│  Application Services                          │
│    ↓                                           │
│  Infrastructure Layer                          │
└────────────────────────────────────────────────┘
        ↓               ↓              ↓
    Neo4j          Redis           Qdrant
    (KG)         (Sessions)      (Vectors)
```

### 12.2 Distributed Deployment (Production)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Agent 1   │     │   Agent 2   │     │   Agent 3   │
│  (Pod/VM)   │     │  (Pod/VM)   │     │  (Pod/VM)   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       └───────────────────┴────────────────────┘
                           ↓
                   ┌──────────────┐
                   │  RabbitMQ    │
                   │  Event Bus   │
                   └──────────────┘
                           ↓
       ┌───────────────────┴────────────────────┐
       ↓                   ↓                     ↓
   ┌───────┐         ┌─────────┐          ┌─────────┐
   │ Neo4j │         │  Redis  │          │ Qdrant  │
   │Cluster│         │ Cluster │          │ Cluster │
   └───────┘         └─────────┘          └─────────┘
```

### 12.3 Technology Stack

**Backend Services**:
- **Neo4j**: Primary knowledge graph storage
- **Redis**: Session cache, short-term memory
- **Qdrant**: Vector search for embeddings
- **Mem0**: Intelligent memory layer (uses Neo4j + Qdrant)

**Communication**:
- **RabbitMQ**: Distributed agent messaging (production)
- **In-memory queues**: Single-process deployment (development)

**API Layer**:
- **FastAPI**: REST API endpoints
- **Typer**: CLI interface

**LLM Integration**:
- **OpenAI GPT-4o-mini**: Reasoning, entity extraction, type inference
- **OpenAI text-embedding-3-small**: Vector embeddings

**Libraries**:
- **SentenceTransformers**: Local embeddings
- **FAISS**: Vector similarity search
- **PyShacl**: SHACL validation
- **NetworkX**: Graph algorithms

---

## 13. Summary of Patterns & Principles

### ✅ Architectural Patterns
- **Clean Architecture**: Domain → Application → Infrastructure → Interfaces
- **Domain-Driven Design**: Aggregates, Value Objects, Domain Events, Repositories
- **CQRS**: Command Bus, separate read/write models
- **Event-Driven Architecture**: Event Bus, Message Passing, Event Sourcing

### ✅ Design Patterns
- **Repository Pattern**: KnowledgeGraphBackend abstraction
- **Agent Pattern**: Autonomous, specialized workers
- **Strategy Pattern**: Resolution strategies, reasoning modes
- **Factory Pattern**: Agent registry, parser factory, backend factory
- **Observer Pattern**: Event Bus pub/sub
- **Command Pattern**: CQRS commands
- **Decorator Pattern**: Confidence tracking, provenance, audit logging

### ✅ SOLID Principles
- **Single Responsibility**: Each class has one reason to change
- **Open/Closed**: Open for extension, closed for modification
- **Liskov Substitution**: All backends implement same interface
- **Interface Segregation**: Focused interfaces (Agent, Backend, Channel)
- **Dependency Inversion**: Depend on abstractions, not concretions

### ✅ Key Strengths
1. **Neurosymbolic AI**: Combines symbolic rules with neural LLM reasoning
2. **Multi-agent collaboration**: Specialized agents with escalation
3. **Clean architecture**: Clear boundaries, testable, maintainable
4. **Domain-rich models**: Captures complex business logic
5. **Extensible**: Easy to add new agents, backends, reasoning rules
6. **Production-ready**: RBAC, audit logging, GDPR compliance
7. **3-layer memory**: Fast (Redis) + Intelligent (Mem0) + Permanent (Neo4j)

---

**End of Architecture Documentation**

For implementation details, see:
- [PHASE_2A_COMPLETE.md](PHASE_2A_COMPLETE.md) - Patient memory implementation
- [REASONING_IMPROVEMENT_COMPLETE.md](REASONING_IMPROVEMENT_COMPLETE.md) - Neurosymbolic reasoning
- [RAG_ENABLED_SUCCESS.md](RAG_ENABLED_SUCCESS.md) - RAG capabilities

For design decisions, see:
- [/Users/pformoso/.claude/plans/memoized-dancing-moore.md](/.claude/plans/memoized-dancing-moore.md) - Phase 2 plan
