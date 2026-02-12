# Hypergraph Bridge Architecture

## Overview

The Hypergraph Bridge is a neurosymbolic layer that connects the **Document Graph** (neural/dense representations from text extraction) with the **Knowledge Graph** (symbolic/sparse ontology-aligned concepts). It uses **FactUnits** as hyperedges to represent multi-entity relationships extracted from shared contexts.

---

## Why Hypergraphs?

Traditional knowledge graphs use binary edges (source → relationship → target), but real-world facts often involve multiple entities simultaneously:

> "Metformin 500mg is prescribed for Type 2 Diabetes in patients with obesity and kidney function > 30 mL/min"

This single statement involves:
- **Drug**: Metformin 500mg
- **Condition**: Type 2 Diabetes
- **Comorbidity**: Obesity
- **Constraint**: Kidney function > 30 mL/min
- **Relationship**: Treatment prescription

A hypergraph represents this as a single **hyperedge** (FactUnit) connecting all entities, preserving the full context.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           HYPERGRAPH BRIDGE                                 │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────┐                    ┌─────────────────────────┐   │
│   │    DOCUMENT GRAPH   │                    │   KNOWLEDGE GRAPH       │   │
│   │    (Neural Layer)   │                    │   (Symbolic Layer)      │   │
│   ├─────────────────────┤                    ├─────────────────────────┤   │
│   │ • PDF Chunks        │                    │ • Disease (SNOMED)      │   │
│   │ • ExtractedEntity   │                    │ • Drug (RxNorm)         │   │
│   │ • Embeddings        │                    │ • Treatment protocols   │   │
│   │ • Co-occurrences    │                    │ • Ontology classes      │   │
│   │ • Source text       │                    │ • Validated concepts    │   │
│   └─────────┬───────────┘                    └────────────┬────────────┘   │
│             │                                              │                │
│             │         ┌─────────────────────────┐          │                │
│             └────────►│      BRIDGE LAYER       │◄─────────┘                │
│                       │       (FactUnit)        │                           │
│                       ├─────────────────────────┤                           │
│                       │ • Hyperedges (N-ary)    │                           │
│                       │ • Multi-source conf.    │                           │
│                       │ • Provenance tracking   │                           │
│                       │ • Ontology mappings     │                           │
│                       │ • Participant roles     │                           │
│                       └─────────────────────────┘                           │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Domain Models

### FactUnit

The primary hyperedge structure representing a factual unit extracted from text.

```python
@dataclass
class FactUnit:
    """A hyperedge representing a factual unit extracted from text."""

    id: str                              # Deterministic hash from participants
    fact_type: FactType                  # RELATIONSHIP, CAUSATION, TREATMENT, etc.
    source_chunk_id: str                 # Original text chunk
    source_document_id: str              # Source document

    # Participating entities with their roles
    participants: List[EntityMention]    # All entities in this fact
    participant_roles: Dict[str, str]    # entity_id -> role (SUBJECT, TREATMENT, etc.)

    # The extracted fact as text
    fact_text: str                       # Natural language representation

    # Multi-source confidence
    confidence_scores: List[ConfidenceScore]  # From different sources
    aggregate_confidence: float               # Weighted combination

    # Embedding for neural operations
    embedding: Optional[List[float]]

    # Provenance
    extraction_method: str               # co_occurrence, rule_based, llm
    validated: bool                      # Human or system validated
    validation_count: int                # Number of validations

    # Links to symbolic layer
    inferred_relationships: List[str]    # Created relationship IDs
    ontology_mappings: Dict[str, str]    # entity_id -> ontology_class
```

### FactType Enumeration

```python
class FactType(str, Enum):
    RELATIONSHIP = "relationship"    # Entity1 relates to Entity2
    ATTRIBUTE = "attribute"          # Entity has property
    CAUSATION = "causation"          # Entity1 causes Entity2
    TREATMENT = "treatment"          # Drug treats Disease
    ASSOCIATION = "association"      # General co-occurrence
    TEMPORAL = "temporal"            # Time-based relationship
    HIERARCHICAL = "hierarchical"    # IS_A, PART_OF relationships
```

### EntityMention

```python
@dataclass
class EntityMention:
    """An entity mention within a specific context (chunk)."""

    entity_id: str                       # Resolved entity ID
    entity_name: str                     # Surface form
    entity_type: str                     # Disease, Drug, Symptom, etc.
    chunk_id: str                        # Source chunk

    position_start: Optional[int]        # Text position
    position_end: Optional[int]

    extraction_confidence: float         # NER confidence
    embedding: Optional[List[float]]     # Entity embedding
```

### ConfidenceScore

```python
@dataclass
class ConfidenceScore:
    """Multi-source confidence score with provenance."""

    value: float                          # 0.0 - 1.0
    source: ConfidenceSource              # Where this score came from
    evidence: str                         # Supporting evidence
    timestamp: datetime                   # When scored

class ConfidenceSource(str, Enum):
    EMBEDDING_SIMILARITY = "embedding_similarity"
    EXTRACTION_MODEL = "extraction_model"
    CO_OCCURRENCE = "co_occurrence"
    ONTOLOGY_MATCH = "ontology_match"
    USER_VALIDATION = "user_validation"
    RULE_INFERENCE = "rule_inference"
```

---

## Confidence Aggregation

FactUnits aggregate confidence from multiple sources with weighted combination:

```python
# Weight by source reliability
CONFIDENCE_WEIGHTS = {
    ConfidenceSource.USER_VALIDATION: 1.0,      # Human validation
    ConfidenceSource.ONTOLOGY_MATCH: 0.9,       # Ontology alignment
    ConfidenceSource.RULE_INFERENCE: 0.85,      # Rule-based inference
    ConfidenceSource.EXTRACTION_MODEL: 0.8,     # NER/LLM extraction
    ConfidenceSource.EMBEDDING_SIMILARITY: 0.7, # Vector similarity
    ConfidenceSource.CO_OCCURRENCE: 0.6,        # Simple co-occurrence
}

def _compute_aggregate_confidence(confidence_scores):
    weighted_sum = sum(
        score.value * CONFIDENCE_WEIGHTS[score.source]
        for score in confidence_scores
    )
    total_weight = sum(
        CONFIDENCE_WEIGHTS[score.source]
        for score in confidence_scores
    )
    return weighted_sum / total_weight
```

---

## Neo4j Schema

### FactUnit Node

```cypher
// FactUnit node structure
(:FactUnit:Bridge {
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
})
```

### Participation Edges

```cypher
// Entity participation in FactUnit
(e:Entity)-[:PARTICIPATES_IN {
    role: "treatment",
    position: 0,
    confidence: 0.9
}]->(f:FactUnit)
```

### Inferred Relationships

```cypher
// High-confidence facts create knowledge graph relationships
(e1:Entity)-[:INFERRED_FROM_FACT {
    fact_id: "fact_abc123",
    confidence: 0.85,
    inferred_at: datetime()
}]->(e2:Entity)
```

---

## Bridge Operations

### 1. Build Bridge Layer

Scans chunks for entity co-occurrences and creates FactUnits:

```python
async def build_bridge_layer(limit: int = 10000, min_confidence: float = 0.5):
    """Build the bridge layer from existing co-occurrences."""

    # 1. Get co-occurrence contexts from chunks
    contexts = await self._get_co_occurrence_contexts(limit)

    for context in contexts:
        # 2. Analyze context for fact candidates
        context.analyze()

        if not context.is_fact_candidate:
            continue

        if context.avg_extraction_confidence < min_confidence:
            continue

        # 3. Create FactUnit
        fact = context.to_fact_unit()
        await self._create_fact_unit(fact)

    # 4. Enrich with ontology mappings
    await self._enrich_with_ontology(stats)

    return stats
```

### 2. Propagate to Knowledge Graph

Promotes high-confidence facts to explicit KG relationships:

```python
async def propagate_to_knowledge_graph(confidence_threshold: float = 0.7):
    """Create INFERRED_FROM_FACT relationships for high-confidence facts."""

    query = """
    MATCH (e1)-[:PARTICIPATES_IN]->(f:FactUnit)<-[:PARTICIPATES_IN]-(e2)
    WHERE f.aggregate_confidence >= $threshold
      AND e1 <> e2
      AND NOT (e1)-[:RELATED_TO]-(e2)
    WITH e1, e2, f,
         CASE f.fact_type
           WHEN 'treatment' THEN 'MAY_TREAT'
           WHEN 'causation' THEN 'MAY_CAUSE'
           ELSE 'RELATED_TO'
         END as rel_type
    MERGE (e1)-[r:INFERRED_FROM_FACT]->(e2)
    SET r.fact_id = f.id
    SET r.confidence = f.aggregate_confidence
    SET r.inferred_at = datetime()
    RETURN count(r) as created_relationships
    """

    return await self.backend.query_raw(query, {"threshold": confidence_threshold})
```

### 3. Find Fact Chains

Discovers transitive relationships through bridge entities:

```python
async def find_fact_chains(entity_id: str, limit: int = 10):
    """Find chains: Entity1 --[fact1]--> Bridge --[fact2]--> Entity2"""

    query = """
    MATCH path = (e1)-[:PARTICIPATES_IN]->(f1:FactUnit)
                 <-[:PARTICIPATES_IN]-(bridge)
                 -[:PARTICIPATES_IN]->(f2:FactUnit)
                 <-[:PARTICIPATES_IN]-(e2)
    WHERE e1.id = $entity_id
      AND e1 <> e2
      AND f1 <> f2
    RETURN
        e1.name as source,
        bridge.name as bridge_entity,
        e2.name as target,
        f1.fact_type as fact1_type,
        f2.fact_type as fact2_type,
        (f1.aggregate_confidence + f2.aggregate_confidence) / 2 as chain_confidence
    ORDER BY chain_confidence DESC
    LIMIT $limit
    """

    return await self.backend.query_raw(query, {"entity_id": entity_id, "limit": limit})
```

### 4. Get Facts for Entity

Query all FactUnits involving a specific entity:

```python
async def get_facts_for_entity(entity_id: str, limit: int = 20):
    """Get all FactUnits involving an entity."""

    query = """
    MATCH (e)-[:PARTICIPATES_IN]->(f:FactUnit)
    WHERE e.id = $entity_id OR e.name = $entity_id
    OPTIONAL MATCH (other)-[:PARTICIPATES_IN]->(f)
    WHERE other <> e
    RETURN
        f as fact,
        collect(DISTINCT {
            id: coalesce(other.id, other.name),
            name: other.name,
            type: labels(other)[0]
        }) as co_participants
    ORDER BY f.aggregate_confidence DESC
    LIMIT $limit
    """

    results = await self.backend.query_raw(query, {"entity_id": entity_id, "limit": limit})

    return [{
        "fact_id": row["fact"]["id"],
        "fact_type": row["fact"]["fact_type"],
        "fact_text": row["fact"]["fact_text"],
        "confidence": row["fact"]["aggregate_confidence"],
        "co_participants": row["co_participants"]
    } for row in results]
```

---

## CoOccurrenceContext

Analyzes entity co-occurrence within a chunk to determine fact candidacy:

```python
@dataclass
class CoOccurrenceContext:
    chunk_id: str
    document_id: str
    entities: List[EntityMention]
    chunk_text: str

    # Computed statistics
    entity_count: int = 0
    type_diversity: int = 0  # Number of unique entity types
    avg_extraction_confidence: float = 0.0

    # Derived signals
    is_fact_candidate: bool = False
    suggested_fact_type: Optional[FactType] = None

    def analyze(self):
        """Analyze the co-occurrence context."""
        self.entity_count = len(self.entities)
        self.type_diversity = len(set(e.entity_type for e in self.entities))

        if self.entities:
            self.avg_extraction_confidence = sum(
                e.extraction_confidence for e in self.entities
            ) / len(self.entities)

        # Determine if this is a fact candidate
        self.is_fact_candidate = (
            self.entity_count >= 2 and
            self.avg_extraction_confidence >= 0.6 and
            self.type_diversity >= 1
        )

        self._suggest_fact_type()

    def _suggest_fact_type(self):
        """Suggest a fact type based on participating entity types."""
        types = set(e.entity_type.lower() for e in self.entities)

        if {"drug", "disease"} & types and {"treatment", "medication"} & types:
            self.suggested_fact_type = FactType.TREATMENT
        elif {"cause", "effect"} & types or "causes" in self.chunk_text.lower():
            self.suggested_fact_type = FactType.CAUSATION
        elif self.type_diversity == 1:
            self.suggested_fact_type = FactType.HIERARCHICAL
        else:
            self.suggested_fact_type = FactType.ASSOCIATION
```

---

## NeurosymbolicLink

Bridges neural (embedding) and symbolic (ontology) representations:

```python
@dataclass
class NeurosymbolicLink:
    entity_id: str
    entity_name: str

    # Neural representation
    embedding: Optional[List[float]]
    embedding_model: str = "text-embedding-3-small"
    cluster_id: Optional[str]

    # Symbolic representation
    ontology_class: Optional[str]        # SNOMED-CT, ICD-10, etc.
    ontology_domain: str = "unknown"     # Gastroenterology, Cardiology, etc.
    dikw_layer: str = "PERCEPTION"       # Current DIKW layer
    external_ids: Dict[str, str]         # ICD-10, SNOMED, RxNorm codes

    # Bridge metrics
    embedding_ontology_alignment: float = 0.0  # How well embedding matches ontology
    symbolic_coverage: float = 0.0             # % of properties covered by ontology
```

---

## Statistics and Reporting

```python
async def get_bridge_report():
    """Generate a comprehensive bridge layer report."""

    stats = await self._get_database_statistics()

    # Get fact type distribution
    type_results = await self.backend.query_raw("""
        MATCH (f:FactUnit)
        RETURN f.fact_type as type, count(f) as count
        ORDER BY count DESC
    """)

    # Get confidence distribution
    conf_results = await self.backend.query_raw("""
        MATCH (f:FactUnit)
        RETURN
            CASE
                WHEN f.aggregate_confidence >= 0.8 THEN 'high'
                WHEN f.aggregate_confidence >= 0.5 THEN 'medium'
                ELSE 'low'
            END as confidence_level,
            count(f) as count
    """)

    # Generate recommendations
    recommendations = []
    if stats["fact_count"] == 0:
        recommendations.append("Run build_bridge_layer() to create FactUnits")
    if stats["avg_confidence"] < 0.5:
        recommendations.append("Low average confidence - review extraction quality")
    if confidence_dist.get("high", 0) > fact_count * 0.3:
        recommendations.append("Good high-confidence ratio - ready for KG propagation")

    return {
        "generated_at": datetime.now().isoformat(),
        "statistics": {
            "total_fact_units": stats["fact_count"],
            "total_hyperedges": stats["edge_count"],
            "entities_with_facts": stats["entities_with_facts"],
            "avg_fact_confidence": stats["avg_confidence"],
        },
        "facts_by_type": facts_by_type,
        "confidence_distribution": confidence_dist,
        "recommendations": recommendations,
    }
```

---

## Usage Example

```python
from application.services.hypergraph_bridge_service import HypergraphBridgeService
from infrastructure.neo4j_backend import Neo4jBackend

# Initialize
backend = Neo4jBackend(uri, user, password)
service = HypergraphBridgeService(backend)

# Build bridge layer from document extractions
stats = await service.build_bridge_layer(limit=5000, min_confidence=0.6)
print(f"Created {stats.total_fact_units} FactUnits with {stats.total_hyperedges} hyperedges")

# Get facts for a specific entity
facts = await service.get_facts_for_entity("metformin")
for fact in facts:
    print(f"  {fact['fact_type']}: {fact['fact_text']} (conf: {fact['confidence']:.2f})")
    print(f"    Co-participants: {[p['name'] for p in fact['co_participants']]}")

# Propagate high-confidence facts to knowledge graph
created = await service.propagate_to_knowledge_graph(confidence_threshold=0.75)
print(f"Propagated {created} relationships to Knowledge Graph")

# Find fact chains for transitive reasoning
chains = await service.find_fact_chains("diabetes")
for chain in chains:
    print(f"  {chain['source']} --[{chain['fact1_type']}]--> "
          f"{chain['bridge']} --[{chain['fact2_type']}]--> {chain['target']}")

# Generate report
report = await service.get_bridge_report()
print(f"\nBridge Report:")
print(f"  Total FactUnits: {report['statistics']['total_fact_units']}")
print(f"  Avg Confidence: {report['statistics']['avg_fact_confidence']:.2%}")
```

---

## Integration with Reasoning System

The Hypergraph Bridge integrates with the ReasoningEngine for:

1. **Fact Validation**: FactUnits are validated against medical rules before promotion
2. **Cross-Graph Inference**: Bridge enables inference across document and knowledge graphs
3. **Confidence Propagation**: Aggregate confidence flows into reasoning confidence model
4. **Provenance Tracking**: Full lineage from source text to knowledge graph

```python
# In ReasoningEngine
async def _infer_cross_graph_relationships(event: KnowledgeEvent):
    """Use Hypergraph Bridge to infer cross-graph relationships."""

    medical_entities = event.data.get("medical_entities", [])

    for entity in medical_entities:
        # Get facts from bridge layer
        facts = await self.bridge_service.get_facts_for_entity(entity["id"])

        for fact in facts:
            if fact["confidence"] >= 0.7:
                inferences.append({
                    "type": "bridge_inferred_relationship",
                    "source_entity": entity["name"],
                    "related_entities": fact["co_participants"],
                    "fact_type": fact["fact_type"],
                    "confidence": fact["confidence"],
                    "source": "hypergraph_bridge"
                })

    return {"inferences": inferences}
```

---

## Related Documentation

- [REASONING_ARCHITECTURE.md](./REASONING_ARCHITECTURE.md) - Main reasoning system
- [KNOWLEDGE_GRAPH_LAYERS_ARCHITECTURE.md](./KNOWLEDGE_GRAPH_LAYERS_ARCHITECTURE.md) - DIKW layers
- [synapseflow_crystallization_architecture.mermaid](./synapseflow_crystallization_architecture.mermaid) - Visual architecture
