# Neurosymbolic Reasoning - Quick Reference

## 5 Reasoning Rules for Chat Queries

### 1. Medical Context Validation (High Priority)
**Purpose**: Validate extracted medical entities

**When it runs**: Always (if medical entities found)

**What it does**:
- Checks confidence of each medical entity
- High confidence (≥0.8): Marks as validated
- Low confidence (<0.6): Flags for verification

**Example Output**:
```
Validated 3 high-confidence medical entities:
  • Crohn's Disease (Disease, 0.95 confidence)
  • Infliximab (Drug, 0.95 confidence)
  • Treatment (concept, 0.95 confidence)
```

---

### 2. Cross-Graph Inference (High Priority)
**Purpose**: Find links between medical and data entities

**When it runs**: When both medical entities and data entities present

**What it does**:
- Checks if medical entity names appear in table/column names
- Examples:
  - "diabetes" in "diabetes_patients" table → link
  - "lupus" in "lupus_medications" column → link

**Example Output**:
```
Inferred 2 potential cross-graph relationships:
  • Crohn's Disease → crohns_treatment_data (table, 0.75 confidence)
  • Infliximab → medication_name (column, 0.70 confidence)
```

**Note**: Only triggers when DDA tables have medical-related names.

---

### 3. Treatment Recommendation Check (Medium Priority)
**Purpose**: Safety check for medical advice queries

**When it runs**: When question contains treatment keywords

**Keywords**:
- "should i take"
- "recommend"
- "prescribe"
- "best treatment"
- "what medication"
- "which drug"
- "how to treat"
- "cure for"

**What it does**:
- Flags query as treatment recommendation
- Sets `disclaimer_required = True`
- Warns system to provide educational info only

**Example Output**:
```
⚠️ Treatment recommendation detected - educational info only
  Disclaimer required: Yes
  Confidence: 0.95
```

---

### 4. Data Availability Assessment (Medium Priority)
**Purpose**: Score quality of available context

**When it runs**: Always

**Scoring Logic**:
```python
Base score: 0.5

Medical entities: +0.1 per entity (up to 3) → max +0.3
Relationships:    +0.1 per relationship (up to 2) → max +0.2
Data tables:      +0.1 per table (up to 2) → max +0.2
Data columns:     +0.05 if present → max +0.05

Total: 0.0 - 1.0
```

**Quality Levels**:
- **High (≥0.8)**: Strong data availability
- **Medium (0.6-0.8)**: Moderate data availability
- **Low (<0.6)**: Limited data availability

**Example Output**:
```
Strong data availability (score: 0.85)
  Context: 3 medical entities, 5 relationships, 2 data tables
```

---

### 5. Confidence Scoring (Low Priority)
**Purpose**: Calculate overall answer confidence

**When it runs**: Always (last step)

**Scoring Logic**:
```python
Base: 0.5

Validated entities: +0.1 per entity (up to 3) → max +0.3
Relationships:      +0.05 per relationship (up to 2) → max +0.1
Cross-graph links:  +0.1 if present → max +0.1
Warnings:           -5% if present

Total: 0.0 - 1.0
```

**Example Output**:
```
Confidence: 0.90 (HIGH)
  Factors:
    - 3 validated entities
    - 5 relationships
    - Cross-graph context present
    - 0 warnings
```

---

## Reasoning Strategies

### Collaborative (Default) ⭐ Recommended
- Runs all rules in priority order
- Combines symbolic + neural reasoning
- Best for production use

### Symbolic-First
- Runs symbolic rules first
- LLM fills gaps if needed
- Good for deterministic behavior

### Neural-First
- LLM generates hypotheses
- Symbolic rules validate
- Good for creative inference

---

## How to Use

### In Code
```python
from application.services.intelligent_chat_service import IntelligentChatService

# Initialize
chat = IntelligentChatService(openai_api_key="your-key")

# Query (reasoning runs automatically)
response = await chat.query("What treatments exist for lupus?")

# Access reasoning trail
print(f"Reasoning steps: {len(response.reasoning_trail)}")
for step in response.reasoning_trail:
    print(f"  {step}")

# Check confidence
print(f"Confidence: {response.confidence:.2f}")
if response.confidence >= 0.8:
    print("HIGH confidence")
```

### Via CLI Demo
```bash
# Interactive chat (reasoning runs automatically)
uv run python demos/demo_intelligent_chat.py

# Test suite
uv run python test_improved_reasoning.py

# Quick demo
uv run python test_reasoning_demo.py
```

---

## Interpreting Results

### Confidence Levels
- **HIGH (0.8-1.0)**: Strong evidence, trust the answer
- **MEDIUM (0.6-0.8)**: Moderate evidence, answer with caveats
- **LOW (0.0-0.6)**: Limited evidence, incomplete answer

### Reasoning Trail Length
- **0 steps**: Reasoning failed (fallback mode)
- **2-3 steps**: Basic reasoning (some context)
- **3-4 steps**: Full reasoning (rich context)
- **4-5 steps**: Maximum reasoning (all rules applied)

### Common Patterns

**Pattern 1: Medical Question with Good Context**
```
Reasoning:
  1. medical_context_validation (3 entities)
  2. data_availability_assessment (score: 0.85)
  3. confidence_scoring (0.92)

Confidence: HIGH
```

**Pattern 2: Treatment Recommendation Query**
```
Reasoning:
  1. medical_context_validation (2 entities)
  2. treatment_recommendation_check (⚠️ disclaimer)
  3. data_availability_assessment (score: 0.80)
  4. confidence_scoring (0.88)

Confidence: HIGH (but with disclaimer)
```

**Pattern 3: Data Catalog Query**
```
Reasoning:
  1. medical_context_validation (4 entities)
  2. cross_graph_inference (2 links) ← NEW!
  3. data_availability_assessment (score: 0.90)
  4. confidence_scoring (0.95)

Confidence: HIGH
```

---

## Troubleshooting

### "Reasoning trail: 0 steps"
**Cause**: Reasoning engine failed or chat_query not recognized
**Fix**: Check if ReasoningEngine initialized properly

### "Low confidence despite good answer"
**Cause**: Few validated entities or limited context
**Fix**: Ensure entity extraction working, check graph has relevant data

### "cross_graph_inference never triggers"
**Cause**: No DDA tables with medical-related names
**Expected**: This is normal if DDA metadata doesn't overlap with medical concepts

### "treatment_recommendation_check always triggers"
**Cause**: Question contains treatment keywords
**Expected**: This is intentional for safety

---

## Performance

### Timing Breakdown
```
Total Query Time: 12-14s
  ├─ Entity Extraction: 1-2s (LLM)
  ├─ Knowledge Retrieval: 3-4s (Neo4j)
  ├─ Reasoning: 0.1-0.2s (symbolic) ⚡
  ├─ Document Retrieval: 2-3s (FAISS)
  └─ Answer Generation: 5-6s (LLM)
```

### Cost Breakdown
```
Cost Per Query: ~$0.0015
  ├─ Entity Extraction: $0.0003 (500 tokens)
  ├─ Reasoning: $0 (symbolic) 💰
  └─ Answer Generation: $0.0012 (2000 tokens)
```

**Note**: Reasoning adds minimal latency (<200ms) and zero cost.

---

## Advanced Usage

### Custom Reasoning Rules
```python
from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine

# Add custom rule
def my_custom_rule(event):
    # Your logic here
    return {"inferences": [...]}

reasoning_engine.add_custom_reasoning_rule(
    action="chat_query",
    rule={
        "name": "my_custom_rule",
        "reasoner": my_custom_rule,
        "priority": "medium"
    }
)
```

### Change Strategy
```python
# Use symbolic-first strategy
result = await reasoning_engine.apply_reasoning(
    event=event,
    strategy="symbolic_first"  # or "neural_first" or "collaborative"
)
```

### Access Provenance
```python
# Get inference provenance
provenance = reasoning_engine.get_inference_provenance(entity_id)
```

---

## What's Next

### Phase 2: Patient Memory
- Add persistent context across sessions
- Store diagnoses, treatments, conversations
- Enable personalized reasoning

### Phase 3: Voice Interaction
- Add speech-to-text (Whisper)
- Add text-to-speech (TTS)
- Enable hands-free chat

### Future Reasoning Enhancements
- Temporal reasoning (track changes over time)
- Abductive reasoning (hypothesis generation)
- Probabilistic reasoning (Bayesian inference)
- Causal reasoning (cause-effect relationships)

---

## Resources

### Documentation
- [REASONING_IMPROVEMENT_COMPLETE.md](REASONING_IMPROVEMENT_COMPLETE.md) - Full implementation details
- [BEFORE_AFTER_COMPARISON.md](BEFORE_AFTER_COMPARISON.md) - Visual comparison
- [NEXT_ENHANCEMENTS_EVALUATION.md](NEXT_ENHANCEMENTS_EVALUATION.md) - Future phases

### Code
- `src/application/agents/knowledge_manager/reasoning_engine.py` - Reasoning rules
- `src/application/services/intelligent_chat_service.py` - Chat integration
- `test_improved_reasoning.py` - Test suite
- `test_reasoning_demo.py` - Quick demo

---

**Status**: ✅ Phase 1 Complete - Neurosymbolic Reasoning Working
**Date**: 2026-01-21
**Next**: Phase 2 (Memory) or Phase 3 (Voice)?
