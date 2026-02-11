# RLHF Feedback Collection & Training Data Pipeline

This guide documents the complete workflow for collecting user feedback, exporting training data, and retraining models in SynapseFlow.

## Overview

The RLHF (Reinforcement Learning with Human Feedback) system in SynapseFlow enables:
- **Real-time feedback collection** from chat interactions
- **Automatic entity confidence adjustment** based on user ratings
- **Preference pair generation** for DPO training
- **Correction examples** for supervised fine-tuning
- **Layer-specific performance analysis** for targeted improvements

The feedback system integrates with the 4-layer Knowledge Graph architecture, tracking which layers (PERCEPTION, SEMANTIC, REASONING, APPLICATION) were involved in each response.

---

## 1. Collecting Feedback (End Users)

### Chat Interface Feedback

When using the Medical Assistant chat at `/chat/patient:{id}`, users can provide feedback on assistant responses:

#### Thumbs Up/Down
- Click the **thumbs up** (👍) or **thumbs down** (👎) icons on any assistant message
- Quick way to indicate if a response was helpful
- Automatically maps to rating: thumbs up = 5, thumbs down = 1

#### Corrections
1. Click the **"Correct"** button on an assistant message
2. A modal opens where you can provide the correct response
3. Submit the correction with your improved version
4. This creates a **preference pair**: your correction is "chosen", original is "rejected"

### What Happens When You Submit Feedback

```
User Submits Feedback
        ↓
┌───────────────────────────────────┐
│  1. Store UserFeedback in Neo4j   │
│     - feedback_id, rating, type   │
│     - entities_involved           │
│     - layers_traversed            │
└───────────────────────────────────┘
        ↓
┌───────────────────────────────────┐
│  2. Adjust Entity Confidence      │
│     - Positive: boost confidence  │
│     - Negative: reduce confidence │
└───────────────────────────────────┘
        ↓
┌───────────────────────────────────┐
│  3. Generate Preference Pairs     │
│     (if correction provided)      │
│     - prompt: original query      │
│     - chosen: user's correction   │
│     - rejected: original response │
└───────────────────────────────────┘
        ↓
┌───────────────────────────────────┐
│  4. Check Layer Demotion          │
│     (on repeated negative)        │
│     APPLICATION → REASONING →     │
│     SEMANTIC → PERCEPTION         │
└───────────────────────────────────┘
```

---

## 2. Admin Dashboard (`/admin/feedback`)

Navigate to the RLHF Feedback Dashboard from Admin → RLHF Feedback.

### Overview Tab

Displays aggregate statistics:
- **Total Feedbacks**: All feedback submissions
- **Positive/Negative Ratio**: Thumbs up vs thumbs down breakdown
- **Corrections Count**: Number of user-submitted corrections
- **Feedback by Type**: Distribution of helpful, unhelpful, incorrect, etc.

### Preferences Tab

View preference pairs ready for DPO training:
- **Rating Gap**: Difference between chosen and rejected ratings (higher = stronger signal)
- **Prompt**: The original user query
- **Chosen Response**: The better response (user correction or higher-rated)
- **Rejected Response**: The worse response

Click "Expand" on any card to see the full prompt/chosen/rejected content.

### Corrections Tab

View SFT (Supervised Fine-Tuning) examples:
- **Query**: Original user question
- **Original Response**: What the assistant said
- **Correction**: What the user provided as the correct answer
- **Feedback Type**: Why the response was incorrect

### Export Tab

Export training data for model improvement:

1. **Select Format**: Choose from DPO, SFT, Alpaca, ShareGPT, OpenAI, or Raw
2. **Generate Export**: Click to generate the data
3. **Preview**: Review the formatted output
4. **Download**: Save as JSON file

---

## 3. Export Formats

| Format | Use Case | Structure |
|--------|----------|-----------|
| **DPO** | Direct Preference Optimization | `{prompt, chosen, rejected}` |
| **SFT** | Supervised Fine-Tuning | `{prompt, completion}` |
| **Alpaca** | Instruction tuning (Stanford) | `{instruction, input, output}` |
| **ShareGPT** | Conversation format | `{conversations: [{from, value}]}` |
| **OpenAI** | OpenAI Fine-tuning API | `{messages: [{role, content}]}` |
| **Raw** | Custom processing | Full feedback records |

### Format Details

#### DPO Format
```json
{
  "format": "dpo",
  "preference_pairs": [
    {
      "prompt": "What medications treat Crohn's disease?",
      "chosen": "Biologics like infliximab (Remicade) and adalimumab (Humira) are first-line treatments...",
      "rejected": "Crohn's disease can be treated with various medications...",
      "rating_gap": 3.5,
      "source": "correction",
      "layers_involved": ["SEMANTIC", "REASONING"]
    }
  ]
}
```

#### SFT Format
```json
{
  "format": "sft",
  "examples": [
    {
      "prompt": "What are the contraindications for methotrexate?",
      "completion": "Methotrexate is contraindicated in pregnancy, severe liver disease...",
      "rating": 4.5,
      "source": "high_rated"
    }
  ]
}
```

#### Alpaca Format
```json
{
  "instruction": "Answer the following medical question",
  "input": "What is the mechanism of action of adalimumab?",
  "output": "Adalimumab is a fully human monoclonal antibody that binds to TNF-alpha..."
}
```

#### ShareGPT Format
```json
{
  "conversations": [
    {"from": "human", "value": "What treats IBD?"},
    {"from": "gpt", "value": "Inflammatory bowel disease treatments include..."}
  ]
}
```

#### OpenAI Format
```json
{
  "messages": [
    {"role": "system", "content": "You are a medical knowledge assistant."},
    {"role": "user", "content": "What treats IBD?"},
    {"role": "assistant", "content": "Inflammatory bowel disease treatments include..."}
  ]
}
```

---

## 4. API Reference

### Submit Feedback

**POST** `/api/feedback`

```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "response_id": "abc123-def456",
    "query_text": "What treats Crohn'\''s disease?",
    "response_text": "Crohn'\''s disease can be treated with...",
    "rating": 2,
    "feedback_type": "incorrect",
    "correction_text": "The primary treatments for Crohn'\''s disease are biologics...",
    "severity": "high"
  }'
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `response_id` | string | Yes | UUID of the response being rated |
| `query_text` | string | Yes | The original user question |
| `response_text` | string | Yes | The assistant's response |
| `rating` | integer | Yes | 1-5 rating (1=worst, 5=best) |
| `feedback_type` | string | No | `helpful`, `unhelpful`, `incorrect`, `partially_correct`, `missing_info` |
| `correction_text` | string | No | User-provided correct response |
| `severity` | string | No | `critical`, `high`, `medium`, `low` |

**Response:**
```json
{
  "feedback_id": "fb-789xyz",
  "message": "Feedback submitted successfully",
  "confidence_adjusted": true
}
```

---

### Thumbs Feedback

**POST** `/api/feedback/thumbs`

```bash
curl -X POST http://localhost:8000/api/feedback/thumbs \
  -H "Content-Type: application/json" \
  -d '{
    "response_id": "abc123-def456",
    "query_text": "What is adalimumab?",
    "response_text": "Adalimumab is a TNF-alpha inhibitor...",
    "thumbs_up": true
  }'
```

**Response:**
```json
{
  "feedback_id": "fb-123abc",
  "message": "Feedback recorded",
  "demotion_count": 0
}
```

---

### Get Statistics

**GET** `/api/feedback/stats`

```bash
curl http://localhost:8000/api/feedback/stats
```

**Response:**
```json
{
  "total_feedbacks": 1250,
  "positive_feedbacks": 890,
  "negative_feedbacks": 360,
  "corrections_count": 145,
  "avg_rating": 3.8,
  "feedback_by_type": {
    "helpful": 650,
    "unhelpful": 280,
    "incorrect": 145,
    "partially_correct": 120,
    "missing_info": 55
  },
  "recent_trend": [
    {"period": "2025-01-20", "count": 45, "avg_rating": 4.1},
    {"period": "2025-01-21", "count": 52, "avg_rating": 3.9}
  ]
}
```

---

### Get Preference Pairs

**GET** `/api/feedback/preference-pairs`

```bash
curl "http://localhost:8000/api/feedback/preference-pairs?limit=50&min_rating_gap=2"
```

**Parameters:**
- `limit`: Maximum pairs to return (default: 100)
- `min_rating_gap`: Minimum rating difference (default: 2)

---

### Get Corrections

**GET** `/api/feedback/corrections`

```bash
curl "http://localhost:8000/api/feedback/corrections?limit=50&feedback_type=incorrect"
```

**Parameters:**
- `limit`: Maximum corrections to return (default: 100)
- `feedback_type`: Filter by type (optional)

---

### Export Training Data

**GET** `/api/feedback/export`

```bash
# DPO format for all layers
curl "http://localhost:8000/api/feedback/export?format=dpo"

# SFT format for SEMANTIC layer only
curl "http://localhost:8000/api/feedback/export?format=sft&layer=SEMANTIC"

# With train/val/test split
curl "http://localhost:8000/api/feedback/export?format=dpo&split_dataset=true"
```

**Parameters:**
| Parameter | Values | Description |
|-----------|--------|-------------|
| `format` | `dpo`, `sft`, `alpaca`, `sharegpt`, `openai`, `raw` | Output format |
| `layer` | `PERCEPTION`, `SEMANTIC`, `REASONING`, `APPLICATION` | Filter by layer |
| `min_rating_gap` | number | Minimum gap for DPO pairs (default: 2) |
| `min_rating_for_sft` | number | Minimum rating for SFT examples (default: 4) |
| `split_dataset` | boolean | Include train/val/test splits |

**Response includes:**
- `preference_pairs` or `sft_examples`: Training data
- `layer_analysis`: Per-layer performance metrics
- `extraction_metadata`: Counts and format info

---

## 5. Retraining Workflow

### Step 1: Collect Feedback

**Minimum recommendations:**
- 100-500 feedback examples for initial training
- Balanced positive/negative ratio (aim for ~60/40)
- Include corrections for strongest training signal

**Quality over quantity:**
- Corrections create the most valuable preference pairs
- Medical domain corrections are especially important
- Mark severity for safety-critical issues

### Step 2: Export Training Data

```bash
# Export DPO format with train/val/test splits
curl -X GET "http://localhost:8000/api/feedback/export?format=dpo&split_dataset=true" \
  -o training_data_dpo.json

# Export SFT format for high-rated responses
curl -X GET "http://localhost:8000/api/feedback/export?format=sft&min_rating_for_sft=4" \
  -o training_data_sft.json

# Export layer-specific data (e.g., fix SEMANTIC layer issues)
curl -X GET "http://localhost:8000/api/feedback/export?format=dpo&layer=SEMANTIC" \
  -o semantic_layer_training.json
```

### Step 3: Prepare Data

```python
import json

# Load exported data
with open('training_data_dpo.json') as f:
    data = json.load(f)

# Access preference pairs
preference_pairs = data['preference_pairs']
print(f"Total pairs: {len(preference_pairs)}")

# Access layer analysis
layer_analysis = data.get('layer_analysis', {})
for layer, stats in layer_analysis.items():
    print(f"{layer}: avg_rating={stats['avg_rating']:.2f}, negative_rate={stats['negative_rate']:.2%}")

# If split_dataset=true, access splits
train_data = data.get('train', [])
val_data = data.get('validation', [])
test_data = data.get('test', [])
```

### Step 4: Run Training

#### DPO Training (using TRL library)

```python
from trl import DPOTrainer, DPOConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import Dataset

# Load model
model = AutoModelForCausalLM.from_pretrained("your-base-model")
tokenizer = AutoTokenizer.from_pretrained("your-base-model")

# Load preference pairs
with open('training_data_dpo.json') as f:
    data = json.load(f)

# Convert to HuggingFace dataset
dataset = Dataset.from_list(data['preference_pairs'])

# Configure DPO training
config = DPOConfig(
    beta=0.1,
    learning_rate=1e-6,
    batch_size=4,
    gradient_accumulation_steps=4,
)

# Train
trainer = DPOTrainer(
    model=model,
    ref_model=None,  # Will create automatically
    tokenizer=tokenizer,
    train_dataset=dataset,
    args=config,
)
trainer.train()
trainer.save_model("./dpo-finetuned-model")
```

#### SFT Training

```python
from transformers import Trainer, TrainingArguments
from datasets import Dataset

# Load SFT examples
with open('training_data_sft.json') as f:
    data = json.load(f)

# Prepare dataset
def format_prompt(example):
    return {
        "text": f"### Question:\n{example['prompt']}\n\n### Answer:\n{example['completion']}"
    }

dataset = Dataset.from_list(data['sft_examples'])
dataset = dataset.map(format_prompt)

# Train
training_args = TrainingArguments(
    output_dir="./sft-finetuned-model",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    learning_rate=2e-5,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
)
trainer.train()
```

### Step 5: Deploy & Monitor

1. **Deploy** the fine-tuned model
2. **Update** the model endpoint in SynapseFlow configuration
3. **Continue** collecting feedback on the improved model
4. **Compare** layer performance before/after training
5. **Iterate** with new feedback data

---

## 6. Best Practices

### Feedback Collection

| Do | Don't |
|----|-------|
| ✅ Submit corrections for incorrect medical information | ❌ Submit duplicate feedback for same response |
| ✅ Use severity ratings for safety-critical issues | ❌ Rate all responses the same |
| ✅ Provide detailed corrections when possible | ❌ Submit vague or unhelpful corrections |
| ✅ Rate confidence appropriately (1-5 scale) | ❌ Use extreme ratings (1 or 5) for average responses |

### Export Quality

- **Filter by `min_rating_gap >= 2`** for clearer preference signal in DPO
- **Include layer analysis** to identify which layers need improvement
- **Use `split_dataset=true`** for ready-to-use train/val/test splits
- **Export regularly** (weekly) to capture recent feedback

### Training Data Quality

```python
# Check for quality issues
def analyze_training_data(pairs):
    issues = []

    for pair in pairs:
        # Check for empty responses
        if not pair['chosen'].strip() or not pair['rejected'].strip():
            issues.append(f"Empty response in pair: {pair['prompt'][:50]}...")

        # Check for identical responses
        if pair['chosen'] == pair['rejected']:
            issues.append(f"Identical responses: {pair['prompt'][:50]}...")

        # Check rating gap
        if pair['rating_gap'] < 1.5:
            issues.append(f"Low rating gap ({pair['rating_gap']}): {pair['prompt'][:50]}...")

    return issues
```

### Continuous Improvement Loop

```
Week 1-4: Collect Feedback
    ↓
Weekly: Export & Analyze
    ↓
Monthly: Retrain Model
    ↓
Deploy & Continue Collecting
    ↓
(Repeat)
```

---

## 7. Layer-Specific Feedback Attribution

Feedback automatically tracks which Knowledge Graph layers were involved in generating the response:

| Layer | Typical Issues | Training Focus |
|-------|----------------|----------------|
| **PERCEPTION** | Raw extraction errors | Improve entity extraction |
| **SEMANTIC** | Ontology/concept mismatches | Better entity resolution |
| **REASONING** | Inference logic problems | Rule refinement |
| **APPLICATION** | Stale cached patterns | Cache invalidation |

### Layer-Targeted Training

```bash
# Export data for specific layer improvements
curl "http://localhost:8000/api/feedback/export?format=dpo&layer=SEMANTIC" \
  -o semantic_training.json

curl "http://localhost:8000/api/feedback/export?format=dpo&layer=REASONING" \
  -o reasoning_training.json
```

### Layer Performance Analysis

The export includes `layer_analysis`:

```json
{
  "layer_analysis": {
    "PERCEPTION": {
      "avg_rating": 3.2,
      "total_feedbacks": 150,
      "negative_rate": 0.35,
      "suggestion": "High negative rate - review extraction pipeline"
    },
    "SEMANTIC": {
      "avg_rating": 4.1,
      "total_feedbacks": 420,
      "negative_rate": 0.12,
      "suggestion": "Performing well"
    },
    "REASONING": {
      "avg_rating": 3.8,
      "total_feedbacks": 380,
      "negative_rate": 0.22,
      "suggestion": "Consider rule refinement for edge cases"
    },
    "APPLICATION": {
      "avg_rating": 4.3,
      "total_feedbacks": 300,
      "negative_rate": 0.08,
      "suggestion": "Strong performance - maintain current patterns"
    }
  }
}
```

---

## 8. Troubleshooting

### No Preference Pairs Generated

**Cause**: Not enough feedback with corrections or rating gaps.

**Solution**:
1. Encourage users to submit corrections, not just thumbs down
2. Lower `min_rating_gap` parameter (try 1.5)
3. Collect more feedback before exporting

### Low-Quality Training Data

**Cause**: Duplicate or contradictory feedback.

**Solution**:
1. Check for duplicate prompts in exports
2. Use layer filtering to target specific improvements
3. Increase `min_rating_gap` for cleaner signals

### Entity Confidence Not Updating

**Cause**: Response tracking not working.

**Solution**:
1. Verify `response_id` matches tracked responses
2. Check backend logs for feedback processing errors
3. Ensure Neo4j connection is stable

---

## Quick Reference

### Common Commands

```bash
# Get feedback statistics
curl http://localhost:8000/api/feedback/stats

# Export DPO training data
curl "http://localhost:8000/api/feedback/export?format=dpo&split_dataset=true" -o dpo_data.json

# Export SFT training data
curl "http://localhost:8000/api/feedback/export?format=sft" -o sft_data.json

# Submit test feedback
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"response_id": "test-123", "query_text": "test", "response_text": "test", "rating": 5}'
```

### Dashboard URLs

- **Chat Interface**: `http://localhost:4321/chat/patient:{id}`
- **Feedback Dashboard**: `http://localhost:4321/admin/feedback`
- **Admin Home**: `http://localhost:4321/admin`

### Related Documentation

- [Knowledge Graph Layers Architecture](./KNOWLEDGE_GRAPH_LAYERS_ARCHITECTURE.md)
- [DIKW Architecture Plan](./DIKW_ARCHITECTURE_PLAN.md)
- [Semantic Layer Quickstart](./SEMANTIC_LAYER_QUICKSTART.md)
