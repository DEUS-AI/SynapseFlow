# Enabling RAG and Reasoning in Chat Service

## Current Status

✅ **You already have**:
- `DocumentService` with FAISS vector search and embeddings
- `ReasoningEngine` with neurosymbolic capabilities
- `ValidationEngine` for fact checking
- All necessary infrastructure

⚠️ **What's disabled**:
1. RAG retrieval (returns empty list)
2. Reasoning engine (returns fallback due to unrecognized "chat_query" action)

---

## Step 1: Enable RAG Retrieval

### What to Do

Initialize `DocumentService` and pass it to `RAGService` in the `IntelligentChatService.__init__()` method.

### Implementation

**File**: `src/application/services/intelligent_chat_service.py`

**Current code** (line 154-156):
```python
# Initialize sub-services
self.query_builder = CrossGraphQueryBuilder()
self.rag_service = RAGService(model=model)  # document_service is None!
```

**Updated code**:
```python
# Initialize document service for RAG
from application.services.document_service import DocumentService

doc_service = DocumentService(
    kg_backend=neo4j_backend,
    chunk_size=1500,
    chunk_overlap=300,
    faiss_index_path="data/faiss_index"
)

# Initialize sub-services
self.query_builder = CrossGraphQueryBuilder()
self.rag_service = RAGService(
    document_service=doc_service,
    kg_backend=neo4j_backend,
    model=model
)
```

### Then Re-enable RAG retrieval

**File**: `src/application/services/intelligent_chat_service.py`

**Current code** (line 382-399):
```python
async def _retrieve_documents(self, question: str) -> List[Dict[str, Any]]:
    """Retrieve relevant document chunks using RAG."""
    # TODO: RAG service requires document_service initialization
    # For now, skip RAG retrieval and rely on graph-based context
    logger.debug("RAG retrieval skipped (document_service not initialized)")
    return []

    # Disabled until document_service is properly initialized:
    # ...
```

**Updated code**:
```python
async def _retrieve_documents(self, question: str) -> List[Dict[str, Any]]:
    """Retrieve relevant document chunks using RAG."""
    try:
        # Use RAG service to find relevant chunks
        rag_result = await self.rag_service.query(
            question=question,
            top_k=3,  # Top 3 most relevant chunks
            include_graph_context=False  # We handle graph context separately
        )

        # Extract chunks from RAG result
        chunks = []
        if hasattr(rag_result, 'sources'):
            for source in rag_result.sources[:3]:
                chunks.append({
                    "text": source.get("chunk_id", "")[:500],  # Limit length
                    "source": f"[Source: PDF Document]",
                    "relevance": source.get("score", 0.0)
                })

        return chunks

    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return []
```

### Prerequisites

You need to have PDFs ingested first. Check if you have any:

```bash
# Check if FAISS index exists
ls -lh data/faiss_index.* 2>/dev/null || echo "No FAISS index found"

# Count chunks in index
uv run python -c "
import pickle
try:
    with open('data/faiss_index.meta', 'rb') as f:
        data = pickle.load(f)
        print(f'FAISS index has {len(data.get(\"chunk_ids\", []))} chunks')
except:
    print('No FAISS index found - need to ingest PDFs first')
"
```

**If no index exists**, ingest your PDFs:

```bash
# Create script to ingest PDFs
cat > ingest_pdfs.py << 'EOF'
import asyncio
from pathlib import Path
from src.application.services.document_service import DocumentService
from src.infrastructure.neo4j_backend import Neo4jBackend
from dotenv import load_dotenv
import os

load_dotenv()

async def ingest_all_pdfs():
    # Initialize backend
    backend = Neo4jBackend(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "")
    )

    # Initialize document service
    doc_service = DocumentService(
        kg_backend=backend,
        faiss_index_path="data/faiss_index"
    )

    # Find all PDFs
    pdf_dir = Path("PDFs")
    pdfs = list(pdf_dir.rglob("*.pdf"))

    print(f"Found {len(pdfs)} PDFs to ingest\n")

    for pdf_path in pdfs:
        try:
            doc = await doc_service.ingest_document(
                str(pdf_path),
                source_name=pdf_path.name
            )
            print(f"✓ Ingested: {pdf_path.name}\n")
        except Exception as e:
            print(f"✗ Failed to ingest {pdf_path.name}: {e}\n")

asyncio.run(ingest_all_pdfs())
EOF

uv run python ingest_pdfs.py
```

### Expected Result

After enabling RAG:
- ✅ Document chunks retrieved from PDFs
- ✅ Answers include PDF content context
- ✅ Sources list includes PDF references
- ✅ Confidence boost for answers with document support

---

## Step 2: Enable Reasoning Engine

### Option A: Skip Reasoning (Simplest) ✅ Recommended

**Current approach**: Reasoning returns fallback values because "chat_query" isn't a recognized action.

**Keep it this way** - the chat works great with:
- Medical KG context
- DDA metadata context
- Cross-graph SEMANTIC relationships
- RAG document retrieval

No action needed! The fallback confidence (0.7) is reasonable.

### Option B: Add Custom Chat Reasoning

If you want reasoning provenance in chat responses, extend the `ReasoningEngine` to recognize "chat_query":

**File**: `src/application/agents/knowledge_manager/reasoning_engine.py`

**Add to `_initialize_reasoning_rules()` method**:

```python
def _initialize_reasoning_rules(self) -> Dict[str, List[Dict[str, Any]]]:
    """Initialize reasoning rules for different operations."""
    return {
        "create_entity": [...],  # Existing
        "create_relationship": [...],  # Existing

        # NEW: Add chat_query support
        "chat_query": [
            {
                "name": "medical_context_validation",
                "reasoner": self._validate_medical_context,
                "priority": "high"
            },
            {
                "name": "cross_graph_inference",
                "reasoner": self._infer_cross_graph_relationships,
                "priority": "medium"
            },
            {
                "name": "confidence_scoring",
                "reasoner": self._score_answer_confidence,
                "priority": "low"
            }
        ]
    }
```

**Then add the reasoner methods**:

```python
async def _validate_medical_context(
    self,
    event: KnowledgeEvent,
    reasoning_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate medical entities in the chat context."""
    entities = event.data.get("medical_entities", [])

    validated = []
    for entity in entities:
        # Check if entity has high confidence from extraction
        if entity.get("confidence", 0) >= 0.8:
            validated.append(entity)
            reasoning_result["inferences"].append({
                "type": "medical_entity_validated",
                "entity": entity.get("name"),
                "confidence": 0.9
            })

    reasoning_result["provenance"].append(
        f"Validated {len(validated)} medical entities"
    )

    return reasoning_result

async def _infer_cross_graph_relationships(
    self,
    event: KnowledgeEvent,
    reasoning_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Infer relationships between medical and data entities."""
    medical_entities = event.data.get("medical_entities", [])
    data_tables = event.data.get("data_tables", [])

    if medical_entities and data_tables:
        reasoning_result["inferences"].append({
            "type": "cross_graph_context",
            "medical_count": len(medical_entities),
            "data_count": len(data_tables),
            "confidence": 0.85
        })

        reasoning_result["provenance"].append(
            f"Found cross-graph context: {len(medical_entities)} medical × {len(data_tables)} data entities"
        )

    return reasoning_result

async def _score_answer_confidence(
    self,
    event: KnowledgeEvent,
    reasoning_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Score confidence based on available context."""
    # Calculate base confidence from available context
    base_confidence = 0.5

    # Boost for medical entities
    if event.data.get("medical_entities"):
        base_confidence += 0.1

    # Boost for data context
    if event.data.get("data_tables") or event.data.get("data_columns"):
        base_confidence += 0.1

    # Boost for relationships
    if event.data.get("medical_relationships"):
        base_confidence += 0.1

    reasoning_result["confidence"] = min(1.0, base_confidence)
    reasoning_result["provenance"].append(
        f"Confidence scored at {reasoning_result['confidence']:.2f} based on context quality"
    )

    return reasoning_result
```

### Expected Result

After enabling reasoning:
- ✅ Reasoning trail with 2-3 steps
- ✅ Provenance explains what was validated
- ✅ Confidence scores reflect context quality
- ✅ Inferences about cross-graph relationships

---

## Step 3: Test Everything

### Test RAG Retrieval

```bash
uv run python -c "
import asyncio
from src.application.services.document_service import DocumentService

async def test_rag():
    doc_service = DocumentService(faiss_index_path='data/faiss_index')

    results = await doc_service.search_similar('What is Crohn\\'s disease?', top_k=3)

    print(f'Found {len(results)} matching chunks:')
    for i, result in enumerate(results, 1):
        print(f'\n{i}. Score: {result[\"score\"]:.3f}')
        print(f'   Text: {result[\"text\"][:200]}...')

asyncio.run(test_rag())
"
```

### Test Chat with RAG + Reasoning

```bash
uv run python demos/demo_intelligent_chat.py
```

Try these queries:
```
You: What treatments are available for Crohn's disease?
You: Which tables contain autoimmune disease data?
You: What is the relationship between vitamin D and lupus?
```

### Expected Improvements

**Before (current state)**:
```
Confidence: 0.55 (MEDIUM)
Sources: 2 sources (graph only)
Reasoning trail: 0 steps
Query time: 8.84s
```

**After (with RAG + reasoning)**:
```
Confidence: 0.85 (HIGH)
Sources: 5 sources (graph + PDFs)
Reasoning trail: 3 steps
  1. Validated 4 medical entities
  2. Found cross-graph context: 4 medical × 2 data entities
  3. Confidence scored at 0.80 based on context quality
Query time: 9.5s
```

---

## Quick Start Commands

### 1. Check if PDFs already ingested:
```bash
ls -lh data/faiss_index.* 2>/dev/null && echo "✅ FAISS index exists" || echo "❌ Need to ingest PDFs"
```

### 2. Ingest PDFs (if needed):
```bash
# See script above in Step 1 Prerequisites
```

### 3. Enable RAG in IntelligentChatService:
```bash
# Edit src/application/services/intelligent_chat_service.py
# - Add DocumentService initialization (lines ~154)
# - Uncomment RAG retrieval code (lines ~382-399)
```

### 4. Enable reasoning (optional):
```bash
# Edit src/application/agents/knowledge_manager/reasoning_engine.py
# - Add "chat_query" to _initialize_reasoning_rules()
# - Add the 3 reasoner methods shown above
```

### 5. Test:
```bash
uv run python demos/demo_intelligent_chat.py
```

---

## Summary

### Priority Order

1. **HIGH**: Enable RAG retrieval (Step 1)
   - Immediate impact on answer quality
   - Provides PDF document context
   - Boosts confidence scores

2. **MEDIUM**: Keep reasoning as-is (Step 2, Option A)
   - Current fallback works well
   - No breaking changes
   - Simpler to maintain

3. **LOW**: Add chat reasoning (Step 2, Option B)
   - Nice-to-have for provenance
   - More complexity
   - Marginal improvement over Option A

### Recommended Path

1. ✅ Check if FAISS index exists
2. ✅ Ingest PDFs if needed (one-time setup)
3. ✅ Enable RAG retrieval in chat service
4. ✅ Test with sample queries
5. ⏭️ Optionally add reasoning later if needed

---

**Ready to start?** Let me know if you want me to:
- Check if FAISS index exists
- Create the PDF ingestion script
- Make the code changes to enable RAG
- Add reasoning support

All the pieces are there - just need to wire them together! 🚀
