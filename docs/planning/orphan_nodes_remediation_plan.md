# SynapseFlow — Implementation Plan: Orphan Node Remediation & Relationship Extraction Fix

## Project Context

SynapseFlow uses a NeuroSymbolic RAG architecture with:
- **Redis**: Vector similarity (entity and chunk embeddings)
- **Mem0**: Entity extraction, relationship mapping, scoring (Relevance + Importance + Recency)
- **Neo4j**: DIKW Knowledge Graph (PERCEPTION → SEMANTIC → REASONING → APPLICATION)
- **Graphiti + FalkorDB**: Episodic memory (conversations, temporal events)

**Core Problem**: The graph quality dashboard reveals a critical structural failure in document knowledge extraction:

| Metric | Value | Diagnosis |
|--------|-------|-----------|
| Graph Entities | 10,000 | — |
| Orphan Nodes | 10,000 | **100% of entities are disconnected** |
| Relationships | 31,493 | Concentrated in a small subset of nodes |
| Ontology Coverage | 22.8% | 7,722 entities without type mapping |
| Context Precision | 93% | Good individual matching |
| Context Recall | 32% | **Related context not being retrieved** |
| Retrieval Quality | 48% | **Degraded by missing edges** |
| Entity Extraction | 69% | Acceptable |
| Ontology Score | 0.72 | — |
| Avg Document Score | 0.66 | — |

**Root Cause Diagnosis**: The extraction pipeline extracts entities reasonably well (69%) but fails to establish relationships between them. Entities arrive in Neo4j as isolated nodes because:
1. Relationship extraction is underperforming relative to entity extraction
2. 7,722 entities lack type mapping → cannot participate in hierarchical relationships
3. Types without ontology mapping (Data Product, Institute, Product, Journal, Plant) don't generate `IS_A`, `BELONGS_TO`, `PART_OF` edges
4. Binary decomposition of multi-entity facts loses intermediate edges

**Connection to ongoing initiatives**: This plan directly complements:
- **Hypergraph Integration Analysis**: Hyperedges would eliminate orphans by construction by capturing n-ary facts as atomic units
- **SLM Migration**: The fine-tuned SLM for extraction needs high-quality training data — we must fix the current extraction first
- **Crystallization Pipeline**: Entities crystallized from Graphiti → Neo4j DIKW will inherit the orphan problem if base extraction isn't fixed

**References**: See `Hypergraph_Integration_Analysis.docx`, `SLM_Training_Research_Report.docx`, `synapseflow_implementation_plan.md`

---

## Execution Order

| Phase | Name | Priority | Dependencies |
|-------|------|----------|--------------|
| 0 | Extraction Pipeline Audit | CRITICAL | None |
| 1 | Ontology Coverage Fix | CRITICAL | Phase 0 |
| 2 | Relationship Extraction Redesign | CRITICAL | Phase 0 |
| 3 | Orphan Node Linker (Retroactive) | HIGH | Phases 1-2 |
| 4 | Quality Monitoring & Feedback Loop | HIGH | Phase 3 |
| 5 | Hypergraph Extraction Layer (Bridge to Hypergraph Plan) | MEDIUM | Phases 2-3 |

---

## PHASE 0: Extraction Pipeline Audit

### Objective
Before fixing anything, we need to understand exactly how the current extraction fails. This phase is a code analysis of the existing codebase — the Data Architect agent, the Engineer agent, and the Knowledge Manager — to map the full flow: document → chunks → extraction → Neo4j.

### Architectural Decisions

**This is a read-only phase, not a coding phase.** Claude Code must read and analyze the existing files before modifying anything. The output is a diagnostic report that guides subsequent phases.

**Key files to examine**: Pablo will provide access to the relevant agents. Claude Code must examine:

### Files to Examine (Read Only)

#### 0.1 Document Ingestion Pipeline

```
Find and read the files responsible for:
1. Document loading (PDF, text)
2. Chunking strategy (chunk size, overlap)
3. Embedding generation (model, dimensions)
4. Redis storage

Questions to answer:
- What is the chunk size? Is there enough overlap to maintain cross-chunk context?
- Do chunks preserve sentence/paragraph boundaries or cut arbitrarily?
- If a fact spans 2 chunks, is the relationship lost?
```

#### 0.2 Extraction Prompts

```
Find and read the prompts the LLM uses to extract entities and relationships.
These are the MOST CRITICAL files in this audit.

Questions to answer:
- Is extraction one-step (entities + relationships together) or two-step
  (entities first, relationships second)?
- Does the prompt explicitly request relationships or only entities?
- Does the output format require each relationship to have source and target entity?
- Is there a defined schema/ontology guiding entity and relationship types?
- Does the prompt include few-shot examples of correct relationships?
- Does it ask the LLM to extract multi-entity facts or only binary pairs?
```

#### 0.3 Neo4j Write Logic

```
Find and read the code that writes entities and relationships to Neo4j.

Questions to answer:
- Are MERGE or CREATE used for entities? (MERGE prevents duplicates)
- Are relationships created in the same transaction as entities?
- Is there a deduplication step before writing?
- Is there validation that both endpoints of a relationship exist before creating it?
- Is there error handling if relationship creation fails?
- Are properties like confidence, source_id, chunk_id written on relationships?
```

#### 0.4 Ontology/Schema Definition

```
Find files that define:
- Allowed entity types
- Allowed relationship types
- Ontology mappings (SNOMED-CT, ICD-10, or domain-specific)
- Any schema validation prior to writing to Neo4j

Questions to answer:
- Is there a defined ontology or are types free-form?
- Are the 5 unmapped types (Data Product, Institute, Product, Journal, Plant)
  expected or extraction noise?
- Is there constraint validation that rejects unknown types?
```

### Diagnostic Report to Generate

#### 0.5 Create `analysis/extraction_audit_report.md`

```
Report structure:

# Extraction Pipeline Audit Report

## 1. Pipeline Flow
Diagram of the full flow: document → chunk → prompt → LLM → parse → Neo4j

## 2. Extraction Prompt Analysis
- Type: one-step vs two-step
- Does it explicitly request relationships?
- Schema enforcement: does it exist?
- Few-shot examples: present? quality?
- Output format: JSON? free-form?

## 3. Relationship Extraction Gap
- Root cause identified for why relationships fail
- Sample chunks where relationships are lost
- Estimated percentage of relationships that should exist vs those extracted

## 4. Ontology Gap Analysis
- Complete list of entity types found
- Which have ontology mapping and which don't
- Recommendation: which are legitimate types vs extraction noise

## 5. Neo4j Write Analysis
- Are relationships created correctly when the LLM returns them?
- Is there a bug in the write code that discards relationships?
- Does deduplication break relationships?

## 6. Root Cause Summary
Prioritized list of orphan node causes

## 7. Recommendations
Mapping to phases 1-5 of this plan, adjusted based on findings
```

### Diagnostic Cypher Queries

```cypher
-- Orphan node distribution by type
MATCH (n)
WHERE NOT (n)--()
RETURN n.entity_type AS type, count(n) AS orphan_count
ORDER BY orphan_count DESC

-- Connected node distribution by type
MATCH (n)
WHERE (n)--()
RETURN n.entity_type AS type, count(n) AS connected_count
ORDER BY connected_count DESC

-- Top entity types without ontology mapping
MATCH (n)
WHERE n.ontology_code IS NULL
RETURN n.entity_type AS type, count(n) AS count
ORDER BY count DESC
LIMIT 20

-- Existing relationships by type
MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(r) AS count
ORDER BY count DESC

-- Nodes with the most relationships (identify the connected subset)
MATCH (n)
WITH n, size([(n)-[]-() | 1]) AS degree
WHERE degree > 0
RETURN n.name, n.entity_type, degree
ORDER BY degree DESC
LIMIT 50

-- Documents with the most orphans (to identify patterns)
MATCH (n)
WHERE NOT (n)--() AND n.source_id IS NOT NULL
RETURN n.source_id, count(n) AS orphan_count
ORDER BY orphan_count DESC
LIMIT 20

-- Confidence distribution in existing relationships
MATCH ()-[r]->()
RETURN
  CASE
    WHEN r.confidence >= 0.9 THEN 'high (>=0.9)'
    WHEN r.confidence >= 0.7 THEN 'medium (0.7-0.9)'
    WHEN r.confidence >= 0.5 THEN 'low (0.5-0.7)'
    ELSE 'very_low (<0.5)'
  END AS confidence_band,
  count(r) AS count
ORDER BY count DESC
```

---

## PHASE 1: Ontology Coverage Fix

### Objective
Resolve the problem of 7,722 entities without type mapping. Add ontology mappings for missing types (Data Product, Institute, Product, Journal, Plant, and any others the Phase 0 audit reveals). This enables these entities to participate in hierarchical relationships and be classifiable.

### Architectural Decisions

**Legitimate type vs noise**: The Phase 0 audit will determine which unmapped types are legitimate domain categories and which are extraction errors. Legitimate ones are added to the ontology; noisy ones are corrected or removed.

**Hierarchy rules**: Each ontology type needs predefined relationship rules. For example: an `Institute` can have `PUBLISHES`, `EMPLOYS`, `RESEARCHES` relationships; a `Journal` can have `PUBLISHES`, `CONTAINS`, `CITED_BY`.

**Retroactivity**: New mappings must apply both to future entities and to the 7,722 existing unmapped ones.

### Files to Create

#### 1.1 `synapseflow/config/ontology_mappings.py`

```
Responsibility: Define all recognized entity types, their hierarchical relationships,
and the automatic relationship rules derived from type.

ONTOLOGY_REGISTRY = {
    # Existing types (already have mapping)
    "medication": {
        "parent_type": "medical_concept",
        "auto_relationships": ["TREATS", "INTERACTS_WITH", "CONTRAINDICATED_FOR"],
        "ontology_system": "SNOMED-CT",
        "hierarchy_path": ["medical_concept", "treatment", "medication"]
    },
    "condition": {
        "parent_type": "medical_concept",
        "auto_relationships": ["TREATED_BY", "DIAGNOSED_BY", "SYMPTOM_OF"],
        "ontology_system": "ICD-10",
        "hierarchy_path": ["medical_concept", "condition"]
    },
    # ...other existing types...

    # NEW types (currently unmapped — those reported by the dashboard)
    "data_product": {
        "parent_type": "artifact",
        "auto_relationships": ["PRODUCED_BY", "CONTAINS", "DERIVED_FROM", "USED_BY"],
        "ontology_system": "custom",
        "hierarchy_path": ["artifact", "data_product"]
    },
    "institute": {
        "parent_type": "organization",
        "auto_relationships": ["PUBLISHES", "EMPLOYS", "RESEARCHES", "LOCATED_IN"],
        "ontology_system": "custom",
        "hierarchy_path": ["organization", "institute"]
    },
    "product": {
        "parent_type": "artifact",
        "auto_relationships": ["PRODUCED_BY", "CONTAINS", "USED_FOR"],
        "ontology_system": "custom",
        "hierarchy_path": ["artifact", "product"]
    },
    "journal": {
        "parent_type": "publication",
        "auto_relationships": ["PUBLISHES", "PUBLISHED_BY", "CONTAINS", "CITED_BY"],
        "ontology_system": "custom",
        "hierarchy_path": ["publication", "journal"]
    },
    "plant": {
        "parent_type": "organism",
        "auto_relationships": ["USED_IN", "PRODUCES", "RELATED_TO", "STUDIED_BY"],
        "ontology_system": "custom",
        "hierarchy_path": ["organism", "plant"]
    }
}

# Type aliases for normalization
TYPE_ALIASES = {
    "data product": "data_product",
    "dataproduct": "data_product",
    "research institute": "institute",
    "university": "institute",
    "academia": "institute",
    "scientific journal": "journal",
    "publication": "journal",
    # ... expand based on audit
}

def resolve_entity_type(raw_type: str) -> str:
    """Normalize and resolve an entity type to its canonical type."""
    normalized = raw_type.lower().strip().replace("-", "_").replace(" ", "_")
    return TYPE_ALIASES.get(normalized, normalized)

def get_ontology_config(entity_type: str) -> dict:
    """Get ontology configuration for an entity type."""
    resolved = resolve_entity_type(entity_type)
    return ONTOLOGY_REGISTRY.get(resolved, {
        "parent_type": "unknown",
        "auto_relationships": [],
        "ontology_system": "none",
        "hierarchy_path": ["unknown"]
    })

def is_known_type(entity_type: str) -> bool:
    """Check if an entity type has a mapping in the ontology."""
    resolved = resolve_entity_type(entity_type)
    return resolved in ONTOLOGY_REGISTRY
```

#### 1.2 `synapseflow/services/ontology_mapper.py`

```
Responsibility: Apply ontology mappings to entities, both new and existing.

Class: OntologyMapper
  - __init__(neo4j_backend, ontology_config)

  - async map_entity(entity: dict) -> dict
      1. Resolve entity_type via resolve_entity_type()
      2. Look up in ONTOLOGY_REGISTRY
      3. If found: add ontology_code, hierarchy_path, parent_type
      4. If not found: flag as "unmapped", log for review
      5. Return enriched entity

  - async backfill_unmapped_entities() -> BackfillResult
      Batch process for the 7,722 existing entities without mapping:
      1. Query Neo4j: MATCH (n) WHERE n.ontology_code IS NULL RETURN n
      2. For each entity: attempt resolve_entity_type(n.entity_type)
      3. If resolved: UPDATE SET n.ontology_code = ..., n.hierarchy_path = ...
      4. If not resolved: add to review list
      5. Return stats: {mapped: int, unmapped: int, review_needed: list}

  - async create_hierarchy_relationships() -> int
      Once entities have hierarchy_path, create IS_A relationships:
      1. Query: MATCH (n) WHERE n.hierarchy_path IS NOT NULL AND NOT (n)-[:IS_A]->()
      2. For each entity: create IS_A edge to its parent_type
      3. This immediately connects entities to the hierarchy
      4. Return count of relationships created

  - async suggest_new_mappings(unmapped_types: list) -> list
      For unknown types, use embedding similarity against known types
      to suggest the most likely mapping:
      1. Embed the unknown type name
      2. Compare against embeddings of known types
      3. Return top-3 suggestions with similarity score
```

### Key Cypher Queries

```cypher
-- Backfill: update entities with new mapping
MATCH (n)
WHERE n.entity_type = $raw_type AND n.ontology_code IS NULL
SET n.entity_type = $resolved_type,
    n.ontology_code = $ontology_code,
    n.ontology_system = $ontology_system,
    n.hierarchy_path = $hierarchy_path,
    n.mapped_at = datetime()
RETURN count(n) AS updated

-- Create IS_A relationships to connect entities to hierarchy
MATCH (n)
WHERE n.hierarchy_path IS NOT NULL
  AND NOT (n)-[:IS_A]->()
WITH n, n.hierarchy_path[-2] AS parent_type
MERGE (p:TypeNode {name: parent_type})
MERGE (n)-[:IS_A]->(p)
RETURN count(n) AS connected

-- Verify impact post-backfill
MATCH (n)
RETURN
  CASE WHEN (n)--() THEN 'connected' ELSE 'orphan' END AS status,
  count(n) AS count
```

### Tests to Create

```
tests/test_ontology_mapper.py
  - test_resolve_known_type
  - test_resolve_type_alias
  - test_resolve_unknown_type_returns_unknown
  - test_backfill_maps_entities
  - test_hierarchy_relationships_created
  - test_suggest_new_mappings_returns_similar
  - test_is_known_type_true_for_registered
  - test_is_known_type_false_for_unknown
```

---

## PHASE 2: Relationship Extraction Redesign

### Objective
Redesign extraction to reliably produce relationships. This is the highest-impact change — moving from entity-first extraction to fact-first extraction, where each fact is a unit (entities + relationship) extracted atomically.

### Architectural Decisions

**Fact-first extraction**: Instead of extracting entities first and then searching for relationships between them, the prompt asks the LLM to extract "facts" — each fact contains the entities involved AND the relationship between them. This is conceptually the same approach as the hyperedge extraction from the Hypergraph Analysis (Section 7.2), but starting with binary and ternary facts before scaling to n-ary.

**Dual output**: The new prompt produces both binary triples (for compatibility with the existing graph) and fact descriptions (which will serve as training data for hyperedges in Phase 5 and eventually for the SLM).

**Parallel deployment**: The new extractor runs in parallel with the existing one during validation. Nothing is replaced until improvement is confirmed.

**Ontology-guided**: The prompt includes entity types and relationship types from the ontology registry as context, guiding the LLM to use valid categories.

### Files to Create

#### 2.1 `synapseflow/extraction/fact_extraction_prompt.py`

```
Responsibility: Define the prompt template for fact-first extraction.

FACT_EXTRACTION_SYSTEM_PROMPT = """
You are a fact and relationship extractor from documents. Your task is to identify
facts (knowledge units) in the provided text.

Each fact MUST contain:
- The entities involved (minimum 2)
- The relationship type between them
- A natural language description of the complete fact
- A confidence level (0.0 to 1.0)

RECOGNIZED ENTITY TYPES:
{entity_types}

RECOGNIZED RELATIONSHIP TYPES:
{relationship_types}

If an entity doesn't fit any known type, use "other" and describe the type
in the description field.

CRITICAL RULES:
1. Every mentioned entity MUST participate in at least one fact/relationship
2. DO NOT extract standalone entities without a relationship — if you cannot identify
   a relationship, don't extract the entity
3. If a fact involves more than 2 entities, include all of them in entity_refs
4. Preserve temporal context if it exists (dates, periods)
5. If the same entity appears with name variations, normalize to the most
   complete name
"""

FACT_EXTRACTION_USER_PROMPT = """
Text to analyze:
---
{chunk_text}
---

Document context: {document_context}
Chunk: {chunk_index} of {total_chunks}

Respond ONLY with valid JSON following this exact schema:
{output_schema}
"""

FACT_EXTRACTION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Complete natural language description of the fact"
                    },
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "description": {"type": "string"}
                            },
                            "required": ["name", "type"]
                        },
                        "minItems": 2
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string", "description": "source entity name"},
                                "target": {"type": "string", "description": "target entity name"},
                                "type": {"type": "string"},
                                "description": {"type": "string"}
                            },
                            "required": ["source", "target", "type"]
                        },
                        "minItems": 1
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "temporal_context": {
                        "type": "string",
                        "description": "Temporal context if present (date, period)"
                    }
                },
                "required": ["description", "entities", "relationships", "confidence"]
            }
        },
        "cross_chunk_candidates": {
            "type": "array",
            "description": "Entities that likely connect with adjacent chunks",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "likely_connection": {"type": "string"}
                }
            }
        }
    },
    "required": ["facts"]
}
```

#### 2.2 `synapseflow/extraction/fact_extractor.py`

```
Responsibility: Execute fact-first extraction on document chunks.

Class: FactExtractor
  - __init__(llm_client, ontology_config, neo4j_backend)

  - async extract_from_chunk(
      chunk_text: str,
      document_context: str,
      chunk_index: int,
      total_chunks: int
    ) -> FactExtractionResult
      1. Build prompt with entity_types and relationship_types from ontology registry
      2. Include the output_schema as format guidance
      3. Call LLM with temperature=0.0 for reproducibility
      4. Parse JSON response
      5. Validate: each entity in relationships.source/target must exist in entities
      6. Resolve entity types via ontology_mapper
      7. Return FactExtractionResult

  - async extract_from_document(
      chunks: List[str],
      document_id: str,
      document_metadata: dict
    ) -> DocumentExtractionResult
      1. For each chunk: extract_from_chunk()
      2. Cross-chunk entity resolution:
         a. Unify entities with same normalized name across chunks
         b. Process cross_chunk_candidates: find matches between adjacent chunks
         c. Create cross-chunk relationships when continuity is detected
      3. Deduplicate entities and relationships at document level
      4. Return unified result

  - async write_to_neo4j(result: DocumentExtractionResult) -> WriteResult
      1. Atomic transaction for each fact:
         a. MERGE each entity in the fact
         b. CREATE relationship(s) between fact entities
         c. Both operations in the SAME transaction → no orphans
      2. If relationship fails: rollback including entities →
         don't create partial orphans
      3. Metadata on each node and relationship:
         source_id, chunk_id, confidence, fact_description
      4. Return stats: {entities_created, relationships_created, facts_written}

  - _validate_fact(fact: dict) -> ValidationResult
      Verify that:
      - Each relationship source/target exists in entities
      - Entity types are known or resolved via ontology
      - Confidence >= minimum threshold (configurable, default 0.5)
      - At least one relationship per fact

  - _resolve_cross_chunk_entities(
      chunk_results: List[FactExtractionResult]
    ) -> List[EntityMerge]
      1. Index all entities by normalized_name + type
      2. For entities with same name in adjacent chunks: merge
      3. For cross_chunk_candidates: search for match by name
      4. Return list of merges to apply
```

#### 2.3 `synapseflow/extraction/extraction_models.py`

```
Responsibility: Pydantic models for extraction results.

class ExtractedEntity(BaseModel):
    name: str
    type: str
    description: str = ""
    confidence: float = 0.0
    source_chunk_id: Optional[str] = None

class ExtractedRelationship(BaseModel):
    source: str          # entity name
    target: str          # entity name
    type: str            # relationship type
    description: str = ""
    confidence: float = 0.0

class ExtractedFact(BaseModel):
    description: str
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelationship]
    confidence: float
    temporal_context: Optional[str] = None
    source_chunk_id: Optional[str] = None

class FactExtractionResult(BaseModel):
    facts: List[ExtractedFact]
    cross_chunk_candidates: List[dict] = []
    chunk_id: str
    extraction_time_ms: float

class DocumentExtractionResult(BaseModel):
    document_id: str
    facts: List[ExtractedFact]
    entities: List[ExtractedEntity]       # deduplicated across chunks
    relationships: List[ExtractedRelationship]  # deduplicated
    entity_count: int
    relationship_count: int
    orphan_count: int                     # should be 0 with fact-first extraction
    extraction_time_ms: float

class WriteResult(BaseModel):
    entities_created: int
    entities_merged: int
    relationships_created: int
    facts_written: int
    orphans_created: int                  # should be 0; alert if > 0
    errors: List[str]
```

### Files to Modify

#### 2.4 Modify the existing ingestion pipeline

```
Changes (exact insertion point depends on Phase 0 audit):

1. Add FactExtractor as an alternative/parallel extractor
2. Feature flag to choose extractor:
   EXTRACTION_MODE = "fact_first"  # or "entity_first" (legacy)
3. In parallel mode: run both, compare results, log differences
4. The FactExtractor's write_to_neo4j uses atomic transactions per fact

NOTE: The exact insertion point and files to modify are determined
in Phase 0 after the audit. Claude Code must read the current pipeline
before deciding where to integrate.
```

### Key Cypher Queries

```cypher
-- Atomic fact write (entities + relationships in one transaction)
-- This is the key pattern that prevents orphans
UNWIND $facts AS fact
UNWIND fact.entities AS entity
MERGE (e:Entity {name: toLower(entity.name), entity_type: entity.type})
ON CREATE SET
  e.description = entity.description,
  e.confidence = entity.confidence,
  e.source_id = $document_id,
  e.chunk_id = fact.source_chunk_id,
  e.created_at = datetime()
ON MATCH SET
  e.confidence = CASE WHEN entity.confidence > e.confidence
                      THEN entity.confidence ELSE e.confidence END,
  e.last_seen = datetime()
WITH fact
UNWIND fact.relationships AS rel
MATCH (s:Entity {name: toLower(rel.source)})
MATCH (t:Entity {name: toLower(rel.target)})
MERGE (s)-[r:RELATES_TO {type: rel.type}]->(t)
ON CREATE SET
  r.description = rel.description,
  r.confidence = rel.confidence,
  r.source_id = $document_id,
  r.fact_description = fact.description,
  r.created_at = datetime()
RETURN count(r) AS relationships_created

-- Verify no orphans were created in this session
MATCH (n)
WHERE n.source_id = $document_id
  AND NOT (n)--()
RETURN n.name, n.entity_type
```

### Tests to Create

```
tests/test_fact_extractor.py
  - test_extract_simple_binary_fact
  - test_extract_multi_entity_fact
  - test_no_orphan_entities_in_output
  - test_cross_chunk_entity_resolution
  - test_validation_rejects_orphan_entity
  - test_ontology_type_resolution_in_extraction
  - test_write_atomic_transaction_creates_both_entities_and_relationships
  - test_write_rollback_on_relationship_failure
  - test_confidence_threshold_filtering
  - test_cross_chunk_candidate_detection
```

---

## PHASE 3: Orphan Node Linker (Retroactive)

### Objective
Address the 10,000 existing orphan nodes. We can't simply delete them — many represent legitimate entities that just weren't connected. This phase attempts to reconnect the most valuable orphans.

### Architectural Decisions

**Three-level strategy**:
1. **Type-based linking**: Entities that now have ontology mapping (Phase 1) can be automatically connected to their hierarchy
2. **Embedding-based linking**: Use vector similarity to find orphans that should be connected to existing entities
3. **Re-extraction**: For high-quality orphans (confidence > 0.7), reprocess the original chunk with the new FactExtractor to discover lost relationships

**No delete policy**: Don't delete orphans. Instead, mark those that can't be reconnected as `status: unresolvable` with the reason. They may be useful as negative training data for the SLM.

### Files to Create

#### 3.1 `synapseflow/services/orphan_linker.py`

```
Responsibility: Reconnect orphan nodes to the existing graph.

Class: OrphanLinker
  - __init__(neo4j_backend, redis_backend, fact_extractor, ontology_mapper)

  - async link_all_orphans() -> LinkingResult
      Orchestrate the full process in 3 levels:
      1. await self.link_by_type()        # fastest, safest
      2. await self.link_by_embedding()    # medium cost, medium confidence
      3. await self.link_by_reextraction() # most expensive, most accurate
      4. Mark remaining as unresolvable
      5. Return statistics

  - async link_by_type() -> int
      For each orphan with ontology mapping (post Phase 1):
      1. Create IS_A relationship to the type node from hierarchy_path
      2. Search other entities of the same type in the same document →
         create CO_OCCURS relationship if they share source_id
      3. Return count of connected orphans

  - async link_by_embedding(similarity_threshold: float = 0.8) -> int
      For each orphan with an embedding:
      1. Search Redis for k=5 nearest neighbors among connected entities
      2. If similarity >= threshold:
         a. Verify the relationship type makes sense (ontology check)
         b. Create SIMILAR_TO or specific type relationship per ontology
         c. Confidence = similarity_score
      3. Return count of connected orphans

  - async link_by_reextraction(confidence_threshold: float = 0.7) -> int
      For high-confidence orphans that couldn't be connected by type or embedding:
      1. Retrieve the original chunk via source_id + chunk_id
      2. Re-run extraction with the new FactExtractor
      3. If re-extraction produces relationships for this entity: create in Neo4j
      4. If no relationships produced: mark as unresolvable
      5. Return count of connected orphans
      NOTE: This has LLM cost — apply only to high-value orphans

  - async mark_unresolvable(reason: str) -> int
      For orphans that couldn't be connected by any method:
      MATCH (n) WHERE NOT (n)--() AND n.status IS NULL
      SET n.status = 'unresolvable',
          n.unresolvable_reason = $reason,
          n.marked_at = datetime()
      Return count

  - async get_orphan_stats() -> dict
      Return current statistics:
      {
        "total_orphans": int,
        "by_type": {type: count},
        "by_confidence": {band: count},
        "resolvable_estimate": int,  # with type mapping or embedding match
        "unresolvable": int
      }
```

#### 3.2 `synapseflow/services/orphan_linker_config.py`

```
ORPHAN_LINKING_CONFIG = {
    "type_linking": {
        "enabled": True,
        "create_is_a": True,
        "create_co_occurs": True,
        "co_occurs_same_document_only": True
    },
    "embedding_linking": {
        "enabled": True,
        "similarity_threshold": 0.8,
        "max_neighbors": 5,
        "relationship_type": "SIMILAR_TO",
        "min_confidence": 0.7
    },
    "reextraction": {
        "enabled": True,  # False for dry run without LLM cost
        "confidence_threshold": 0.7,
        "max_orphans_to_reprocess": 1000,  # cost limit
        "batch_size": 50
    },
    "batch": {
        "size": 500,
        "pause_between_batches_seconds": 2  # don't saturate Neo4j
    }
}
```

### Key Cypher Queries

```cypher
-- Get orphans with their source info for re-extraction
MATCH (n)
WHERE NOT (n)--()
  AND n.confidence >= $confidence_threshold
  AND n.source_id IS NOT NULL
  AND n.chunk_id IS NOT NULL
  AND (n.status IS NULL OR n.status <> 'unresolvable')
RETURN n.name, n.entity_type, n.source_id, n.chunk_id, n.confidence
ORDER BY n.confidence DESC
LIMIT $batch_size

-- Create CO_OCCURS relationship for entities from the same document
MATCH (a), (b)
WHERE NOT (a)--()
  AND a.source_id = b.source_id
  AND a <> b
  AND (b)--()  -- b is already connected
MERGE (a)-[r:CO_OCCURS]->(b)
SET r.source_id = a.source_id,
    r.confidence = 0.6,
    r.method = 'orphan_linker_type',
    r.created_at = datetime()
RETURN count(r) AS links_created

-- Post-linking statistics
MATCH (n)
RETURN
  CASE
    WHEN (n)--() THEN 'connected'
    WHEN n.status = 'unresolvable' THEN 'unresolvable'
    ELSE 'orphan'
  END AS status,
  count(n) AS count
```

### Tests to Create

```
tests/test_orphan_linker.py
  - test_link_by_type_creates_is_a
  - test_link_by_type_creates_co_occurs
  - test_link_by_embedding_above_threshold
  - test_link_by_embedding_below_threshold_skips
  - test_link_by_reextraction_finds_relationship
  - test_mark_unresolvable_sets_status
  - test_orphan_stats_returns_correct_counts
  - test_batch_processing_respects_limits
```

---

## PHASE 4: Quality Monitoring & Feedback Loop

### Objective
Implement continuous graph quality monitoring to detect regressions and measure the impact of changes. The dashboard Pablo already has measures static state — this phase adds per-document monitoring and alerting.

### Architectural Decisions

**Per-document metrics**: Each processed document generates immediate metrics (orphan rate, relationship density, type coverage). If a document produces more than X% orphans, it's flagged for review.

**Trend tracking**: Daily aggregated metrics to detect regressions.

**Eval framework integration**: Quality checks can be included as state assertions in the Agent Evaluation Framework scenarios.

### Files to Create

#### 4.1 `synapseflow/services/graph_quality_monitor.py`

```
Responsibility: Monitor knowledge graph quality.

Class: GraphQualityMonitor
  - __init__(neo4j_backend, config)

  - async assess_document(document_id: str) -> DocumentQualityReport
      Post-extraction quality check for a document:
      1. Count entities created for this document
      2. Count relationships created
      3. Count orphans (entities without relationships)
      4. Calculate entity-to-relationship ratio
      5. Calculate type coverage (% with ontology mapping)
      6. If orphan_rate > threshold: emit warning event
      7. Return DocumentQualityReport

  - async assess_graph_global() -> GlobalQualityReport
      Full graph assessment (equivalent to dashboard):
      1. Total entities, relationships, orphans
      2. Ontology coverage %
      3. Relationship density (edges/node ratio)
      4. Component analysis (how many disconnected subgraphs)
      5. Orphan distribution by type
      6. Confidence distribution
      7. Return GlobalQualityReport

  - async check_extraction_health(
      result: DocumentExtractionResult
    ) -> ExtractionHealthCheck
      Validate result quality BEFORE writing to Neo4j:
      1. orphan_rate = result.orphan_count / result.entity_count
      2. relationship_ratio = result.relationship_count / result.entity_count
      3. If orphan_rate > 0.3: WARNING — extractor is failing
      4. If relationship_ratio < 0.5: WARNING — too few relationships per entity
      5. If > 20% entities with type "other": WARNING — ontology insufficient
      6. Return health check with pass/fail and warnings

  - _compute_metrics(document_id: Optional[str] = None) -> dict
      Execute the cypher metric queries and return normalized dict

class DocumentQualityReport(BaseModel):
    document_id: str
    entity_count: int
    relationship_count: int
    orphan_count: int
    orphan_rate: float              # orphan_count / entity_count
    relationship_density: float     # relationship_count / entity_count
    type_coverage: float            # % entities with ontology mapping
    health_status: str              # "good", "warning", "critical"
    warnings: List[str]
    timestamp: datetime

class ExtractionHealthCheck(BaseModel):
    passed: bool
    orphan_rate: float
    relationship_ratio: float
    unknown_type_rate: float
    warnings: List[str]
    block_write: bool               # True if quality too low to write
```

#### 4.2 `synapseflow/services/quality_alerting.py`

```
Responsibility: Emit alerts when graph quality degrades.

Class: QualityAlerter
  - __init__(event_bus, config)

  - async on_document_assessed(report: DocumentQualityReport)
      If report.health_status == "critical":
        emit event "quality_alert" with details
        log.error("Document {id} produced {orphan_rate}% orphans")
      If report.health_status == "warning":
        log.warning(...)

  - async check_trend(window_days: int = 7) -> TrendReport
      Compare metrics from the last N days against baseline:
      If orphan_rate trend is positive (worsening): alert
      If relationship_density trend is negative: alert

QUALITY_THRESHOLDS = {
    "orphan_rate_warning": 0.3,     # > 30% orphans in a document
    "orphan_rate_critical": 0.5,    # > 50% orphans
    "relationship_ratio_min": 0.5,  # at least 0.5 relationships per entity
    "type_coverage_min": 0.7,       # at least 70% entities with type mapping
    "block_write_orphan_rate": 0.8  # > 80% orphans → don't write
}
```

### Tests to Create

```
tests/test_graph_quality_monitor.py
  - test_assess_document_healthy
  - test_assess_document_warning_high_orphans
  - test_assess_document_critical
  - test_extraction_health_check_passes
  - test_extraction_health_check_blocks_on_high_orphan_rate
  - test_global_assessment_returns_all_metrics
```

---

## PHASE 5: Hypergraph Extraction Layer (Bridge to Hypergraph Plan)

### Objective
Extend the FactExtractor to produce hyperedges in addition to binary relationships. This phase is the bridge between this remediation plan and the Hypergraph Integration Analysis — it implements the n-ary extraction that feeds the hypergraph layer.

### Architectural Decisions

**Extension, not replacement**: The Phase 2 FactExtractor already extracts facts with multiple entities and relationships. This phase adds the ability to generate :Hyperedge nodes in Neo4j when a fact involves 3+ entities.

**Hypergraph Analysis schema**: Use exactly the schema from Section 4.2 of the Hypergraph Integration Analysis for :Hyperedge nodes and :CONNECTS relationships.

**Training data generation**: Each successful LLM extraction is logged as training data for the future SLM (Phase 4 of the Hypergraph plan).

### Files to Create/Modify

#### 5.1 Modify `synapseflow/extraction/fact_extractor.py`

```
Changes:
1. In write_to_neo4j(): if a fact has >= 3 entities:
   a. Create :Hyperedge node with description, confidence, entity_count,
      source_id, chunk_id
   b. Create :CONNECTS relationships from :Hyperedge to each :Entity
   c. Generate embedding for the hyperedge description → Redis
2. ALSO maintain the binary relationships for backward compatibility
3. Log the fact as a training example for SLM:
   {input: chunk_text, output: {entities, hyperedges}} → JSONL file
```

#### 5.2 Create `synapseflow/extraction/hyperedge_writer.py`

```
Responsibility: Write hyperedges to Neo4j and embeddings to Redis.

Class: HyperedgeWriter
  - __init__(neo4j_backend, redis_backend, embedding_model)

  - async write_hyperedge(fact: ExtractedFact, document_id: str) -> str
      If len(fact.entities) >= 3:
        1. Create :Hyperedge node in Neo4j
        2. Create :CONNECTS to each entity
        3. Generate embedding of fact.description → Redis
        4. Return hyperedge_id
      If len(fact.entities) < 3:
        Skip (handled by normal binary relationships)

  - async write_batch(facts: List[ExtractedFact], document_id: str) -> BatchResult
      Process all eligible facts in batch
      Return statistics

  - _log_training_example(chunk_text: str, fact: ExtractedFact, output_path: str)
      Append to the JSONL training data file for future SLM fine-tuning
```

### Key Cypher Queries

```cypher
-- Create hyperedge node (schema from Hypergraph Integration Analysis)
CREATE (he:Hyperedge {
  hyperedge_id: $hyperedge_id,
  description: $description,
  confidence: $confidence,
  entity_count: $entity_count,
  source_id: $source_id,
  chunk_id: $chunk_id,
  created_at: datetime(),
  embedding_id: $embedding_id
})
WITH he
UNWIND $entity_names AS entity_name
MATCH (e:Entity {name: toLower(entity_name)})
MERGE (he)-[:CONNECTS]->(e)
RETURN he.hyperedge_id, count(e) AS connected_entities
```

### Tests to Create

```
tests/test_hyperedge_writer.py
  - test_fact_with_3_entities_creates_hyperedge
  - test_fact_with_2_entities_skips_hyperedge
  - test_connects_relationships_created
  - test_embedding_stored_in_redis
  - test_training_data_logged
  - test_batch_write_multiple_hyperedges
```

---

## File Summary

### New (create)
| File | Phase |
|------|-------|
| `analysis/extraction_audit_report.md` | 0 |
| `synapseflow/config/ontology_mappings.py` | 1 |
| `synapseflow/services/ontology_mapper.py` | 1 |
| `synapseflow/extraction/fact_extraction_prompt.py` | 2 |
| `synapseflow/extraction/fact_extractor.py` | 2 |
| `synapseflow/extraction/extraction_models.py` | 2 |
| `synapseflow/services/orphan_linker.py` | 3 |
| `synapseflow/services/orphan_linker_config.py` | 3 |
| `synapseflow/services/graph_quality_monitor.py` | 4 |
| `synapseflow/services/quality_alerting.py` | 4 |
| `synapseflow/extraction/hyperedge_writer.py` | 5 |
| `tests/test_ontology_mapper.py` | 1 |
| `tests/test_fact_extractor.py` | 2 |
| `tests/test_orphan_linker.py` | 3 |
| `tests/test_graph_quality_monitor.py` | 4 |
| `tests/test_hyperedge_writer.py` | 5 |

### Existing (modify)
| File | Phase | Change Type |
|------|-------|-------------|
| Ingestion pipeline (file TBD in Phase 0) | 2 | Integrate FactExtractor as alternative extractor |
| `synapseflow/extraction/fact_extractor.py` | 5 | Add hyperedge writing for facts with ≥3 entities |

---

## Configuration and Feature Flags

```python
# synapseflow/config/extraction_config.py

EXTRACTION_CONFIG = {
    "mode": "fact_first",              # "entity_first" (legacy) | "fact_first" | "parallel"
    "parallel_comparison": True,       # In parallel mode: compare and log differences
    "fact_extraction": {
        "temperature": 0.0,
        "min_confidence": 0.5,
        "max_entities_per_fact": 5,    # Cap per fact (HyperGraphRAG recommendation)
        "enable_cross_chunk_resolution": True,
        "enable_ontology_guided": True,
    },
    "orphan_prevention": {
        "atomic_transactions": True,    # Entities + relationships in same transaction
        "block_orphan_write": False,    # True for hard block; False for warning only
        "orphan_rate_warning": 0.3,
        "orphan_rate_critical": 0.5,
    },
    "ontology": {
        "enable_backfill": True,
        "create_hierarchy_relationships": True,
        "unknown_type_handling": "flag",  # "flag" | "reject" | "assign_other"
    },
    "hyperedge": {
        "enabled": False,              # Enable in Phase 5
        "min_entities_for_hyperedge": 3,
        "log_training_data": True,
        "training_data_path": "data/slm_training/hyperedge_examples.jsonl"
    },
    "quality_monitoring": {
        "assess_per_document": True,
        "assess_interval_hours": 24,   # Global assessment every 24h
        "alert_on_regression": True,
    }
}
```

---

## Instructions for Claude Code

**Strict execution order**: Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5.

**Phase 0 is a mandatory prerequisite**: Do not write code for phases 1-5 without completing the audit. Phase 0 findings may change decisions in subsequent phases.

**Key principle — zero orphans by design**: The Phase 2 FactExtractor uses atomic transactions: entities + relationships are created together or not at all. If the relationship fails, the entity is not created. This is the most important architectural change.

**For the audit (Phase 0)**:
1. Pablo will provide access to the agent code (Data Architect, Engineer, Knowledge Manager)
2. Read the ENTIRE extraction flow end-to-end before diagnosing
3. Execute the diagnostic cypher queries against the current Neo4j
4. The report must be specific: which file, which function, which line causes the problem
5. Include concrete samples: chunks where relationships are lost

**For each new file**:
1. Create the file with the indicated structure
2. Implement all described methods
3. Write docstrings in English
4. Use complete type hints (Python 3.10+)
5. Follow the project's existing async/await pattern
6. Write corresponding unit tests

**For each modified file**:
1. Read the current file completely before modifying
2. Identify exact insertion points
3. Maintain backward compatibility
4. Don't break existing imports
5. Add necessary imports at the top of the file

**Project conventions**:
- Pydantic v2 for models
- asyncio for async operations
- Neo4j async driver
- Logging with structlog or standard logging
- Existing in-memory event bus from the project
- Cypher for Neo4j queries
- Feature flags in config for gradual activation

**Success metrics**:
- Post Phase 1: Ontology coverage > 80% (currently 22.8%)
- Post Phase 2: Orphan rate < 10% for new documents (currently ~100%)
- Post Phase 3: Total orphans reduced > 70% (from 10,000 to < 3,000)
- Post Phase 4: Quality monitoring active with alerting
- Post Phase 5: Hyperedge generation working, training data accumulating

**Main adaptation point**:
Phase 0 will determine exactly how the FactExtractor integrates with the existing pipeline. The files to modify in Phase 2 are marked as "TBD in Phase 0" because they depend on the audit. Claude Code must adapt the integration based on findings.
