# Quick Start Guide - Neurosymbolic Medical Chat

Get started with the intelligent medical chat system in 5 minutes.

---

## Prerequisites

1. **Neo4j Running**: `bolt://localhost:7687`
2. **Environment Variables**: `.env` file with:
   ```bash
   OPENAI_API_KEY=sk-...
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   ```
3. **Data Loaded**: Medical entities and DDA metadata in Neo4j

---

## Quick Start

### 1. Launch Interactive Chat

```bash
cd /Users/pformoso/Documents/code/Notebooks
uv run python demos/demo_intelligent_chat.py
```

### 2. Try Example Questions

```
You: What treatments are available for Crohn's Disease?
```

```
You: Which data tables contain information about autoimmune diseases?
```

```
You: What is the relationship between vitamin D and lupus?
```

```
You: Show me columns related to patient treatments
```

### 3. Use Special Commands

```
/help       - Show available commands
/context    - View knowledge graph statistics
/sources    - Show sources from last answer
/reasoning  - Show reasoning trail
/confidence - Show confidence breakdown
/reset      - Clear conversation history
/quit       - Exit
```

---

## Example Session

```
======================================================================
  Intelligent Medical Chat - Neurosymbolic Q&A
======================================================================

Initializing services...
✓ Chat service initialized

Type /help for available commands
Ask any question about medical concepts or data structures

You: /context

----------------------------------------------------------------------
  Knowledge Graph Context
----------------------------------------------------------------------

Medical Entities:     234
Data Entities:        2,378
SEMANTIC Links:       10
Total Relationships:  2,710
Total Entities:       2,612

This unified Neo4j graph enables intelligent queries across both
medical knowledge and data catalog metadata.

You: What treatments are available for Crohn's Disease?

🤔 Thinking...

----------------------------------------------------------------------
  Answer
----------------------------------------------------------------------

Based on the medical knowledge graph, several treatments are available
for Crohn's Disease:

**Biologic Therapies** [Source: autoimmune_diseases.pdf]
- Anti-TNF agents like Infliximab and Adalimumab
- These target inflammatory pathways in IBD

**Immunosuppressants** [Source: ibd_treatment_guidelines.pdf]
- Azathioprine, 6-Mercaptopurine
- Used for maintenance therapy

**Data Catalog Context**:
Our system contains treatment data in:
- `immunology_schema.patient_treatments` table
- Columns: medication_name, dosage, frequency

Related concepts: Inflammatory Bowel Disease, Ulcerative Colitis, Anti-TNF Therapy

Confidence: 0.92 (HIGH)

Query time: 3.45s

You: /sources

----------------------------------------------------------------------
  Sources
----------------------------------------------------------------------

1. PDF: autoimmune_diseases.pdf
2. PDF: ibd_treatment_guidelines.pdf
3. Table: patient_treatments

You: /quit

👋 Goodbye!
```

---

## Verify Your Setup

### Check Neo4j Connection

```bash
uv run python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    auth=(os.getenv('NEO4J_USERNAME', 'neo4j'), os.getenv('NEO4J_PASSWORD', ''))
)

with driver.session() as session:
    result = session.run('MATCH (n) RETURN count(n) as count')
    print(f'✓ Neo4j connected: {result.single()[\"count\"]} nodes')

driver.close()
"
```

### Check Medical Entities

```bash
uv run python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    auth=(os.getenv('NEO4J_USERNAME', 'neo4j'), os.getenv('NEO4J_PASSWORD', ''))
)

with driver.session() as session:
    result = session.run('MATCH (n:MedicalEntity) RETURN count(n) as count')
    print(f'Medical entities: {result.single()[\"count\"]}')

driver.close()
"
```

Expected: ~234 medical entities

### Check Cross-Graph Links

```bash
uv run python -c "
from src.application.services.cross_graph_query_builder import CrossGraphQueryBuilder

builder = CrossGraphQueryBuilder()
stats = builder.get_cross_graph_statistics()

print(f'Medical entities: {stats.records[0][\"medical_count\"]}')
print(f'Data entities: {stats.records[0][\"data_count\"]}')
print(f'SEMANTIC links: {stats.records[0][\"semantic_links\"]}')
"
```

Expected: 234 medical, 2378 data, 10 semantic links

---

## Troubleshooting

### Issue: "Neo4j connection failed"

**Solution**: Check that Neo4j is running:
```bash
# Check if Neo4j is running
ps aux | grep neo4j

# Or check Neo4j Browser at http://localhost:7474
```

### Issue: "OPENAI_API_KEY not found"

**Solution**: Add to `.env` file:
```bash
echo "OPENAI_API_KEY=sk-your-key-here" >> .env
```

### Issue: "No medical entities found"

**Solution**: Run migration script:
```bash
uv run python demos/migrate_medical_entities_to_neo4j.py
```

### Issue: "Chat service takes too long"

**Potential causes**:
- Large graph traversals
- First query (cold start)
- OpenAI API latency

**Solutions**:
- Reduce `max_depth` in query builder
- Add graph indexes: `CREATE INDEX ON :MedicalEntity(name)`
- Use `gpt-3.5-turbo` for faster responses

### Issue: "Low confidence answers"

**Potential causes**:
- Few cross-graph links
- Limited document coverage
- Validation failures

**Solutions**:
- Lower confidence threshold in entity linking
- Add more PDFs to knowledge base
- Process more DDAs for data coverage

---

## Next Steps

1. **Explore the knowledge graph** in Neo4j Browser:
   ```cypher
   MATCH (m:MedicalEntity)-[r]->(d)
   WHERE r.layer = 'SEMANTIC'
   RETURN m, r, d
   LIMIT 50
   ```

2. **Add more PDFs** to expand medical knowledge:
   ```bash
   # Place PDFs in PDFs/ directory
   uv run python demos/demo_pdf_ingestion.py
   ```

3. **Process more DDAs** to expand data catalog:
   ```bash
   # Place DDAs in examples/ directory
   uv run python demos/demo_batch_dda_processing.py
   ```

4. **Create more cross-graph links**:
   ```bash
   uv run python demos/demo_medical_data_linking.py --confidence-threshold 0.70
   ```

5. **Read the full documentation**:
   - [UNIFIED_NEO4J_ARCHITECTURE.md](UNIFIED_NEO4J_ARCHITECTURE.md)
   - [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
   - [NEO4J_QUERIES.md](NEO4J_QUERIES.md)

---

## Tips for Best Results

### Asking Good Questions

✅ **Good questions**:
- "What treatments are available for Crohn's Disease?"
- "Which tables contain patient treatment data?"
- "What is the relationship between vitamin D and autoimmune diseases?"
- "Show me columns related to inflammation markers"

❌ **Unclear questions**:
- "Tell me about stuff"
- "What do you know?"
- "Anything about tables?"

### Understanding Confidence Scores

- **HIGH (0.9+)**: Strong evidence from multiple sources
- **MEDIUM (0.7-0.9)**: Good evidence but some uncertainty
- **LOW (<0.7)**: Limited evidence or conflicting information

### Using Commands Effectively

- Use `/context` first to understand what's in the knowledge base
- Use `/sources` to verify information provenance
- Use `/reasoning` to understand how the answer was derived
- Use `/confidence` to assess answer reliability

---

## Support

**Documentation**:
- Full architecture: [UNIFIED_NEO4J_ARCHITECTURE.md](UNIFIED_NEO4J_ARCHITECTURE.md)
- Implementation details: [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
- Neo4j queries: [NEO4J_QUERIES.md](NEO4J_QUERIES.md)

**Code**:
- Chat service: [src/application/services/intelligent_chat_service.py](src/application/services/intelligent_chat_service.py)
- Query builder: [src/application/services/cross_graph_query_builder.py](src/application/services/cross_graph_query_builder.py)
- Interactive demo: [demos/demo_intelligent_chat.py](demos/demo_intelligent_chat.py)

---

**Ready to chat?**

```bash
uv run python demos/demo_intelligent_chat.py
```

🚀 Enjoy exploring your neurosymbolic medical knowledge system!
