# SynapseFlow Reasoning Architecture

## Overview

SynapseFlow implements a **neurosymbolic reasoning system** that combines symbolic AI (rule-based reasoning, ontology mapping) with neural AI (LLM inference, embeddings) to create a robust knowledge management platform. This document details how reasoning flows through the system.

---

## Core Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              SYNAPSEFLOW REASONING SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────────┐                    ┌──────────────────────────────────────────┐│
│  │  User Query     │──────────────────► │           DIKW ROUTER                    ││
│  │  "¿Puedo tomar  │                    │  ┌─────────────────────────────────────┐ ││
│  │   ibuprofeno?"  │                    │  │ Intent Classification:               │ ││
│  └─────────────────┘                    │  │ • FACTUAL → SEMANTIC/PERCEPTION     │ ││
│                                         │  │ • RELATIONAL → SEMANTIC              │ ││
│                                         │  │ • INFERENTIAL → REASONING            │ ││
│                                         │  │ • ACTIONABLE → APPLICATION           │ ││
│                                         │  └─────────────────────────────────────┘ ││
│                                         └──────────────────────────────────────────┘│
│                                                        │                             │
│                                                        ▼                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐│
│  │                    NEUROSYMBOLIC QUERY SERVICE                                   ││
│  │                                                                                  ││
│  │   Strategy Selection:                                                            ││
│  │   ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐   ││
│  │   │ SYMBOLIC_ONLY  │ │ SYMBOLIC_FIRST │ │  NEURAL_FIRST  │ │ COLLABORATIVE  │   ││
│  │   │ Drug interact. │ │ Data catalog   │ │ Symptom interp.│ │ Treatment recs │   ││
│  │   │ Contraindic.   │ │ Structured     │ │ Context-heavy  │ │ General queries│   ││
│  │   └────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘   ││
│  └──────────────────────────────────────────────────────────────────────────────────┘│
│                                                        │                             │
│                                                        ▼                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐│
│  │                         REASONING ENGINE                                         ││
│  │                                                                                  ││
│  │   ┌────────────────────────────────────────────────────────────────────────────┐││
│  │   │                      REASONING STRATEGIES                                  │││
│  │   │                                                                            │││
│  │   │  NEURAL-FIRST                    SYMBOLIC-FIRST                            │││
│  │   │  ┌─────────┐                     ┌─────────┐                               │││
│  │   │  │   LLM   │────► Hypotheses ────►│  Rules  │────► Validation              │││
│  │   │  └─────────┘      (tentative)    └─────────┘      (certain)                │││
│  │   │                                                                            │││
│  │   │  COLLABORATIVE                                                             │││
│  │   │  ┌─────────┐ ┌─────────┐                                                   │││
│  │   │  │   LLM   │ │  Rules  │ ────► Parallel Execution ────► Confidence        │││
│  │   │  └─────────┘ └─────────┘                                   Weighting       │││
│  │   └────────────────────────────────────────────────────────────────────────────┘││
│  │                                                                                  ││
│  │   ┌────────────────────────────────────────────────────────────────────────────┐││
│  │   │                      REASONING RULES                                       │││
│  │   │                                                                            │││
│  │   │  create_entity:                  chat_query:                               │││
│  │   │  • ontology_mapping (HIGH)       • contraindication_check (CRITICAL)       │││
│  │   │  • property_inference (HIGH)     • medical_context_validation (HIGH)       │││
│  │   │  • entity_classification (MED)   • cross_graph_inference (HIGH)            │││
│  │   │  • relationship_suggestion (LOW) • treatment_history_analysis (HIGH)       │││
│  │   │  • llm_semantic_inference (LOW)  • symptom_tracking (MED)                  │││
│  │   │  • semantic_linking (LOW)        • medication_adherence (LOW)              │││
│  │   │                                  • data_availability_assessment (MED)      │││
│  │   │  create_relationship:            • confidence_scoring (LOW)                │││
│  │   │  • relationship_validation (HIGH)                                          │││
│  │   │  • inverse_relationship (MED)                                              │││
│  │   │  • transitive_closure (LOW)                                                │││
│  │   └────────────────────────────────────────────────────────────────────────────┘││
│  └──────────────────────────────────────────────────────────────────────────────────┘│
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. ReasoningEngine (`src/application/agents/knowledge_manager/reasoning_engine.py`)

The core reasoning component that applies symbolic logic and neural inference to knowledge graph operations.

**Responsibilities:**
- Applies reasoning rules to KnowledgeEvents
- Tracks confidence and provenance for all inferences
- Supports three reasoning strategies: neural-first, symbolic-first, collaborative
- Manages medical safety rules (contraindications, drug interactions)
- Cross-layer reasoning across DIKW hierarchy

**Reasoning Strategies:**

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `neural_first` | LLM generates hypotheses → symbolic validation | Symptom interpretation, context-heavy queries |
| `symbolic_first` | Rules first → LLM fills gaps | Data catalog queries, structured information |
| `collaborative` | Both run in parallel → confidence weighting | Treatment recommendations, general queries |

**Code Flow:**
```python
# ReasoningEngine.apply_reasoning()
async def apply_reasoning(event: KnowledgeEvent, strategy: str = "collaborative"):
    # 1. Get rules for this action type (create_entity, chat_query, etc.)
    rules = self._reasoning_rules.get(event.action, [])

    # 2. Sort by priority (critical > high > medium > low)
    sorted_rules = sorted(rules, key=lambda r: priority_order[r["priority"]])

    # 3. Execute based on strategy
    if strategy == "neural_first":
        # LLM first, then validate with symbolic rules
        neural_result = await self._llm_semantic_inference(event)
        for rule in sorted_rules:
            rule_result = await rule["reasoner"](event)
            # Mark neural inferences as "tentative", symbolic as "certain"

    elif strategy == "symbolic_first":
        # Rules first, LLM fills gaps if needed
        for rule in sorted_rules:
            rule_result = await rule["reasoner"](event)
        if len(inferences) < 2:
            neural_result = await self._llm_semantic_inference(event)

    else:  # collaborative
        # Both in parallel, confidence weighting
        for rule in sorted_rules:
            rule_result = await rule["reasoner"](event)
            # Assign confidence based on source (neural vs symbolic)

    # 4. Track provenance for each inference
    # 5. Return results with confidence scores
```

### 2. KnowledgeManagerAgent (`src/application/agents/knowledge_manager/agent.py`)

The orchestrating agent that coordinates complex knowledge graph operations.

**Key Components:**
- **ReasoningEngine**: Applies symbolic and neural reasoning
- **ValidationEngine**: Validates events before processing
- **ConflictResolver**: Detects and resolves conflicts between sources

**Flow:**
```python
async def _handle_knowledge_event(event: KnowledgeEvent):
    # 1. Advanced validation
    validation_result = await self.validation_engine.validate_event(event)
    if not validation_result["is_valid"]:
        return await self._send_validation_feedback(event, validation_result)

    # 2. Check for conflicts
    conflicts = await self.conflict_resolver.detect_conflicts(event)
    if conflicts:
        await self._handle_conflicts(event, conflicts)
        if not await self._can_proceed_after_conflicts(event, conflicts):
            return

    # 3. Apply reasoning
    reasoning_result = await self.reasoning_engine.apply_reasoning(event)

    # 4. Execute the operation
    await self.knowledge_service.handle_event(event)

    # 5. Send success feedback with reasoning results
    await self._send_success_feedback(event, reasoning_result)
```

### 3. NeurosymbolicQueryService (`src/application/services/neurosymbolic_query_service.py`)

Executes queries across knowledge graph layers using neurosymbolic reasoning.

**Query Type → Strategy Mapping:**

| Query Type | Strategy | Reason |
|------------|----------|--------|
| Drug Interaction | SYMBOLIC_ONLY | Safety-critical, no hallucination risk |
| Contraindication | SYMBOLIC_ONLY | Must be deterministic |
| Symptom Interpretation | NEURAL_FIRST | Requires context understanding |
| Treatment Recommendation | COLLABORATIVE | Hybrid knowledge needed |
| Disease Information | COLLABORATIVE | Balance accuracy and completeness |
| Data Catalog | SYMBOLIC_FIRST | Structured data, rules primary |

**Layer Traversal:**
```
APPLICATION (cached results)
    ↓
REASONING (inferred knowledge)
    ↓
SEMANTIC (validated concepts)
    ↓
PERCEPTION (raw extracted data)
```

### 4. DIKWRouter (`src/application/services/dikw_router.py`)

Routes queries to appropriate DIKW layers based on intent classification.

**Intent → Layer Mapping:**

| Intent | Example Query | Target Layers |
|--------|---------------|---------------|
| FACTUAL | "¿cuándo fue mi última cita?" | SEMANTIC, PERCEPTION |
| RELATIONAL | "¿qué medicamentos tomo para X?" | SEMANTIC |
| INFERENTIAL | "¿debería preocuparme?" | REASONING |
| ACTIONABLE | "¿qué debo hacer?" | APPLICATION |
| EXPLORATORY | Open-ended questions | All layers |

**Intent Detection Patterns:**
```python
INTENT_PATTERNS = {
    QueryIntent.FACTUAL: {
        "question_words": ["cuándo", "cuál", "qué es", "dónde"],
        "patterns": ["última vez", "fecha de", "nombre de"]
    },
    QueryIntent.INFERENTIAL: {
        "question_words": ["por qué", "debería", "puede ser"],
        "patterns": ["riesgo de", "posible que", "significa que"]
    },
    QueryIntent.ACTIONABLE: {
        "question_words": ["qué hacer", "cómo puedo"],
        "patterns": ["siguiente paso", "recomienda", "debería hacer"]
    }
}
```

---

## Confidence Model

### Confidence Sources

```python
class ConfidenceSource(str, Enum):
    SYMBOLIC_RULE = "symbolic_rule"   # From rule-based reasoning (high trust)
    NEURAL_MODEL = "neural_model"     # From LLM inference (variable trust)
    HYBRID = "hybrid"                 # Combined neural + symbolic
    USER_INPUT = "user_input"         # Direct from user
    VALIDATION = "validation"         # From validation process
    HEURISTIC = "heuristic"           # From heuristic rules
```

### Cross-Layer Confidence Propagation

Confidence is adjusted when traversing between DIKW layers:

```python
LAYER_WEIGHTS = {
    KnowledgeLayer.APPLICATION: 1.0,   # Most trusted (validated by usage)
    KnowledgeLayer.REASONING: 0.9,     # Inferred with rules
    KnowledgeLayer.SEMANTIC: 0.8,      # Validated against ontologies
    KnowledgeLayer.PERCEPTION: 0.6,    # Raw extraction, needs validation
}

CROSS_LAYER_DECAY = {
    # Downward traversal (higher decay)
    (APPLICATION, REASONING): 0.95,
    (REASONING, SEMANTIC): 0.90,
    (SEMANTIC, PERCEPTION): 0.85,

    # Upward traversal (lower decay)
    (PERCEPTION, SEMANTIC): 0.98,
    (SEMANTIC, REASONING): 0.95,
    (REASONING, APPLICATION): 0.92,
}
```

### Confidence Resolution

When layers conflict:
1. Higher layer wins (APPLICATION > REASONING > SEMANTIC > PERCEPTION)
2. Unless confidence gap > threshold, then prefer higher confidence
3. Flag for human review if unclear

```python
def resolve_conflict(layer1, confidence1, layer2, confidence2):
    weight1 = self.get_layer_weight(layer1)
    weight2 = self.get_layer_weight(layer2)

    adjusted1 = confidence1.score * weight1
    adjusted2 = confidence2.score * weight2

    gap = abs(adjusted1 - adjusted2)

    if gap > self.conflict_threshold:
        # Go with higher confidence
        return winner_by_confidence
    else:
        # Higher layer wins
        return winner_by_layer
```

---

## Medical Reasoning Rules

### Safety-Critical Rules (Priority: CRITICAL)

**Contraindication Check:**
```python
async def _check_contraindications(event: KnowledgeEvent):
    patient_context = event.data.get("patient_context")
    medical_entities = event.data.get("medical_entities", [])

    # Use MedicalRulesEngine for comprehensive evaluation
    if self.medical_rules_engine:
        evaluation = self.medical_rules_engine.evaluate(rules_context)

        for result in evaluation.results:
            if result.severity in ("CRITICAL", "HIGH"):
                warnings.append(f"⚠️ {result.severity}: {result.message}")

    # Fallback to built-in checks
    else:
        # Check allergy contraindications
        for entity in medical_entities:
            for allergy in patient_context.allergies:
                if allergy.lower() in entity_name:
                    warnings.append("CRITICAL: Patient allergic to this substance")

        # Check drug interactions
        for med in current_meds:
            if (entity_name, med) in known_interactions:
                warnings.append(f"WARNING: Interaction with {med}")
```

### Medical Rules Configuration

```python
MEDICAL_REASONING_RULES = [
    {
        "id": "drug_interaction_check",
        "type": "cross_entity",
        "conditions": {
            "entity_types": ["medication", "medication"],
            "relationship": "taken_by_same_patient",
        },
        "produces": {
            "entity_type": "drug_interaction_warning",
            "dikw_layer": "REASONING",
            "risk_level": "HIGH"
        }
    },
    {
        "id": "allergy_contraindication",
        "type": "cross_entity",
        "conditions": {
            "entity_types": ["allergy", "medication"],
            "relationship": "potential_reaction"
        },
        "produces": {
            "entity_type": "contraindication_alert",
            "dikw_layer": "REASONING",
            "risk_level": "HIGH"
        }
    }
]
```

---

## Cross-Layer Reasoning

The ReasoningEngine implements cross-layer reasoning rules that enable knowledge to flow between DIKW layers:

### PERCEPTION → SEMANTIC
**Infer business concepts from data attributes**

```python
async def _perception_to_semantic_reasoning(entity_data):
    # Analyze table/column structure to infer semantic concepts
    concept_patterns = {
        "customer": ["customer_id", "customer_name", "email"],
        "order": ["order_id", "order_date", "order_total"],
        "product": ["product_id", "product_name", "price"],
    }

    for concept, pattern_cols in concept_patterns.items():
        match_score = calculate_match(entity_columns, pattern_cols)
        if match_score >= 0.4:
            inferences.append({
                "type": "business_concept_inference",
                "concept": concept,
                "confidence": min(0.6 + match_score * 0.4, 1.0),
                "target_layer": "SEMANTIC"
            })
```

### SEMANTIC → REASONING
**Derive quality rules from business concept constraints**

```python
async def _semantic_to_reasoning_reasoning(entity_data):
    quality_rules = {
        "Customer": [
            {"rule": "email_required", "reason": "Customers must have contact info"},
            {"rule": "unique_email", "reason": "Email must be unique"},
        ],
        "Order": [
            {"rule": "order_date_not_future", "reason": "Cannot be future date"},
            {"rule": "total_positive", "reason": "Must be positive"},
        ],
    }

    if concept_type in quality_rules:
        for rule in quality_rules[concept_type]:
            inferences.append({
                "type": "quality_rule",
                "rule_name": rule["rule"],
                "target_layer": "REASONING"
            })
```

### REASONING → APPLICATION
**Suggest query patterns from usage statistics**

```python
async def _reasoning_to_application_reasoning(entity_data):
    if reasoning_type == "quality_rule":
        if "unique" in rule_name:
            inferences.append({
                "type": "query_pattern",
                "pattern": "duplicate_detection_query",
                "target_layer": "APPLICATION"
            })
        elif "date" in rule_name:
            inferences.append({
                "type": "query_pattern",
                "pattern": "temporal_analysis_query",
                "target_layer": "APPLICATION"
            })
```

### APPLICATION → PERCEPTION
**Request new data based on query patterns**

```python
async def _application_to_perception_reasoning(entity_data):
    if usage_pattern == "temporal_analysis":
        suggestions.append({
            "action": "collect_temporal_data",
            "recommended_columns": ["created_at", "updated_at"],
            "target_layer": "PERCEPTION"
        })

    if access_count > 100:
        inferences.append({
            "type": "data_gap_detection",
            "gap": "missing_optimized_structure",
            "target_layer": "PERCEPTION"
        })
```

---

## Hypergraph Bridge (Neurosymbolic)

The HypergraphBridgeService bridges the Document Graph (neural/dense) with the Knowledge Graph (symbolic/sparse) using FactUnits as hyperedges.

### Architecture

```
┌─────────────────┐         ┌──────────────────┐
│  DOCUMENT GRAPH │         │  KNOWLEDGE GRAPH │
│  (Neural Layer) │         │ (Symbolic Layer) │
├─────────────────┤         ├──────────────────┤
│ Chunk           │         │ Disease          │
│ ExtractedEntity │◄───────►│ Drug             │
│ Embedding       │    │    │ Treatment        │
│ Co-occurrence   │    │    │ Ontology classes │
└─────────────────┘    │    └──────────────────┘
                       │
               ┌───────┴────────┐
               │  BRIDGE LAYER  │
               │   (FactUnit)   │
               ├────────────────┤
               │ Hyperedges     │
               │ Confidence     │
               │ Provenance     │
               └────────────────┘
```

### FactUnit (Hyperedge)

Unlike traditional edges (2 nodes), a FactUnit connects N entities from the same factual context:

```python
@dataclass
class FactUnit:
    id: str
    fact_type: FactType  # RELATIONSHIP, CAUSATION, TREATMENT, etc.
    source_chunk_id: str
    source_document_id: str

    # Participating entities with roles
    participants: List[EntityMention]
    participant_roles: Dict[str, str]  # entity_id -> role

    # Multi-source confidence
    confidence_scores: List[ConfidenceScore]
    aggregate_confidence: float

    # Links to symbolic layer
    ontology_mappings: Dict[str, str]  # entity_id -> ontology_class
```

**Example:**
```
"Metformin is used to treat Type 2 Diabetes in patients with obesity"
→ FactUnit connecting: [Metformin, Type2Diabetes, Obesity, Patient]
→ With roles: [TREATMENT, CONDITION, COMORBIDITY, SUBJECT]
```

### Bridge Operations

1. **Build Bridge Layer**: Create FactUnits from co-occurrences in chunks
2. **Propagate to KG**: Promote high-confidence facts to knowledge graph relationships
3. **Find Fact Chains**: Discover transitive relationships through bridge entities

```python
# Build bridge from existing co-occurrences
stats = await service.build_bridge_layer()

# Propagate high-confidence facts to KG
created = await service.propagate_to_knowledge_graph(confidence_threshold=0.7)

# Find fact chains: Entity1 --[fact1]--> Bridge --[fact2]--> Entity2
chains = await service.find_fact_chains(entity_id="diabetes")
```

---

## Crystallization Pipeline

Transfers knowledge from episodic memory (Graphiti/FalkorDB) to the DIKW Knowledge Graph (Neo4j).

### Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CRYSTALLIZATION PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌──────────────┐               │
│  │   Graphiti  │────►│ episode_added│────►│ Crystallization│             │
│  │  FalkorDB   │     │    Event    │     │    Service    │              │
│  │  (Episodic) │     └─────────────┘     └───────┬──────┘               │
│  └─────────────┘                                  │                      │
│                                                   ▼                      │
│                                        ┌──────────────────┐              │
│                                        │ Entity Resolver  │              │
│                                        │ (Deduplication)  │              │
│                                        └────────┬─────────┘              │
│                                                 │                        │
│                                                 ▼                        │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    NEO4J DIKW KNOWLEDGE GRAPH                    │   │
│   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │   │
│   │  │ PERCEPTION  │ │  SEMANTIC   │ │  REASONING  │ │APPLICATION │ │   │
│   │  │ Raw data    │►│ Validated   │►│ Inferred    │►│ Query      │ │   │
│   │  │ conf ~0.7   │ │ conf ≥0.85  │ │ conf ≥0.92  │ │ patterns   │ │   │
│   │  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │   │
│   │                     Promotion Criteria:                          │   │
│   │                     • conf ≥ 0.85                                │   │
│   │                     • obs ≥ 2                                    │   │
│   │                     • SNOMED match                               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Promotion Rules

| Transition | Min Confidence | Min Observations | Additional Criteria |
|------------|----------------|------------------|---------------------|
| PERCEPTION → SEMANTIC | 0.85 | 2 | SNOMED-CT match |
| SEMANTIC → REASONING | 0.92 | 3 | Stable 48h, domain validation |
| REASONING → APPLICATION | N/A | N/A | Validated rules applied |

---

## Layer Transition Service

Manages entity promotion between knowledge layers with validation and lineage tracking.

### Validation Flow

```python
def validate_transition(entity_data, from_layer, to_layer):
    errors = []

    # Check layer hierarchy (can't go backwards)
    if to_level < from_level:
        errors.append("Cannot transition backwards in DIKW hierarchy")

    # Check required properties for target layer
    LAYER_REQUIREMENTS = {
        Layer.PERCEPTION: ["source", "origin"],
        Layer.SEMANTIC: ["description", "domain"],
        Layer.REASONING: ["confidence", "reasoning"],
        Layer.APPLICATION: ["usage_context", "access_pattern"]
    }

    for prop in LAYER_REQUIREMENTS[to_layer]:
        if prop not in entity_props:
            errors.append(f"Missing required property '{prop}'")

    return (len(errors) == 0, errors)
```

### Lineage Tracking

Every transition creates a record with:
- Source and target layers
- Validation results
- Property changes
- Timestamp and approver
- Links to previous entity versions

---

## Integration Points

### Event Bus

The system uses an in-memory event bus for component communication:

```python
# Events emitted
"episode_added"           # Graphiti adds episode → triggers crystallization
"crystallization_complete" # Batch crystallization done → triggers promotions
"review_needed"           # High-risk entity needs human review
"conflict_resolution"     # Conflict detected → KnowledgeManager handles

# Event handlers
event_bus.subscribe("episode_added", crystallization_service._handle_episode_added)
event_bus.subscribe("crystallization_complete", promotion_gate.evaluate_candidates)
```

### Temporal Scoring

Queries incorporate temporal relevance:

```python
# Decay rates by entity type (lambda parameter)
DECAY_RATES = {
    "symptom": 0.05,      # Decays in ~20h
    "vital_sign": 0.03,   # Decays in ~33h
    "medication": 0.005,  # Decays in ~8 days
    "diagnosis": 0.001,   # Decays in ~42 days
    "allergy": 0.0001,    # Almost permanent
}

# Relevance score = exp(-lambda * hours_since_observation)
```

---

## Configuration

```python
REASONING_CONFIG = {
    # Crystallization
    "batch_interval_minutes": 5,
    "batch_threshold": 10,

    # Promotion rules
    "perception_to_semantic": {
        "min_confidence": 0.85,
        "min_observations": 2,
        "require_snomed_match": True
    },
    "semantic_to_reasoning": {
        "min_confidence": 0.92,
        "min_observations": 3,
        "min_stability_hours": 48,
        "high_risk_requires_review": True
    },

    # Temporal
    "temporal": {
        "default_decay_lambda": 0.01,
        "use_adaptive_windows": True
    },

    # Confidence
    "cross_layer_min_confidence": 0.1,
    "conflict_threshold": 0.3
}
```

---

## Related Documentation

- [KNOWLEDGE_GRAPH_LAYERS_ARCHITECTURE.md](./KNOWLEDGE_GRAPH_LAYERS_ARCHITECTURE.md) - DIKW layer details
- [synapseflow_implementation_plan.md](./synapseflow_implementation_plan.md) - Implementation phases
- [synapseflow_crystallization_architecture.mermaid](./synapseflow_crystallization_architecture.mermaid) - Visual architecture
- [LANGGRAPH_ARCHITECTURE.md](./LANGGRAPH_ARCHITECTURE.md) - LangGraph integration
