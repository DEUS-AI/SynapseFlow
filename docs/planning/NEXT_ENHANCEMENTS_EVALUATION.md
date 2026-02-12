# Next Enhancements Evaluation

## Overview

Three major enhancements to evaluate:
1. **Adding Memory** - Patient context persistence across sessions
2. **Voice Interaction** - Speech-to-text and text-to-speech channels
3. **Improving Reasoning** - Enhanced knowledge generation for chat queries

---

## 1. Adding Memory (Patient Context)

### Concept

Store patient-specific information across chat sessions to provide personalized medical guidance.

### Use Case Example

```
Session 1:
Patient: "I was diagnosed with Crohn's disease last year"
Assistant: [stores: diagnosis=Crohn's, diagnosed_date=2025]

Patient: "I'm currently on Humira"
Assistant: [stores: current_medication=Humira (Adalimumab)]

Session 2 (next week):
Patient: "How are biologics working for my condition?"
Assistant: "Based on your Crohn's disease diagnosis and current
           treatment with Humira (a biologic anti-TNF medication)..."
           [retrieves stored context automatically]
```

### Architecture Design

#### Option A: Session-based Memory (Simpler)

**Storage**: In-memory dict or Redis cache
**Scope**: Current session only
**Persistence**: Lost when app restarts

```python
class SessionMemory:
    def __init__(self):
        self._sessions = {}  # session_id -> context

    def store(self, session_id: str, key: str, value: Any):
        if session_id not in self._sessions:
            self._sessions[session_id] = {}
        self._sessions[session_id][key] = value

    def retrieve(self, session_id: str) -> Dict[str, Any]:
        return self._sessions.get(session_id, {})
```

**Pros**:
- Simple to implement
- No database needed
- Fast access

**Cons**:
- Lost on restart
- No cross-device persistence
- Limited to single instance

#### Option B: Persistent Patient Memory (Production-ready) ⭐ Recommended

**Storage**: Neo4j (Patient nodes linked to conversation history)
**Scope**: Cross-session, cross-device
**Persistence**: Permanent with consent

```cypher
// Patient entity structure
CREATE (p:Patient {
  patient_id: "uuid",
  created_at: "2026-01-21",
  consent_given: true
})

// Medical context
CREATE (dx:Diagnosis {
  condition: "Crohn's Disease",
  diagnosed_date: "2025-01",
  icd_code: "K50.0"
})
CREATE (p)-[:HAS_DIAGNOSIS]->(dx)

// Treatment history
CREATE (tx:Treatment {
  medication: "Humira",
  generic_name: "Adalimumab",
  started_date: "2025-02",
  dosage: "40mg every 2 weeks"
})
CREATE (p)-[:CURRENT_TREATMENT]->(tx)

// Conversation history
CREATE (conv:Conversation {
  conv_id: "uuid",
  started_at: "2026-01-21T10:00:00",
  summary: "Discussed biologics and Crohn's management"
})
CREATE (p)-[:HAD_CONVERSATION]->(conv)

// Individual messages
CREATE (msg:Message {
  role: "user",
  content: "How are biologics working?",
  timestamp: "2026-01-21T10:05:00"
})
CREATE (conv)-[:HAS_MESSAGE]->(msg)
```

**Implementation**:

```python
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from domain.roles import Role


@dataclass
class PatientContext:
    """Patient-specific medical context."""
    patient_id: str
    diagnoses: List[Dict[str, Any]]
    treatments: List[Dict[str, Any]]
    allergies: List[str]
    preferences: Dict[str, Any]
    last_updated: datetime


class PatientMemoryService:
    """Manages patient context and conversation history."""

    def __init__(self, neo4j_backend):
        self.backend = neo4j_backend

    async def get_or_create_patient(
        self,
        patient_id: Optional[str] = None,
        consent_given: bool = True
    ) -> str:
        """Get existing patient or create new one."""
        if not patient_id:
            patient_id = f"patient:{uuid.uuid4().hex[:12]}"

        # Check if patient exists
        existing = await self.backend.get_node(patient_id)

        if not existing:
            # Create new patient
            await self.backend.add_entity(
                patient_id,
                {
                    "created_at": datetime.now().isoformat(),
                    "consent_given": consent_given,
                    "patient_type": "anonymous"  # or "registered"
                },
                labels=["Patient"]
            )

        return patient_id

    async def store_diagnosis(
        self,
        patient_id: str,
        condition: str,
        diagnosed_date: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store patient diagnosis."""
        diagnosis_id = f"dx:{uuid.uuid4().hex[:12]}"

        await self.backend.add_entity(
            diagnosis_id,
            {
                "condition": condition,
                "diagnosed_date": diagnosed_date or "unknown",
                "recorded_at": datetime.now().isoformat(),
                **(metadata or {})
            },
            labels=["Diagnosis"]
        )

        await self.backend.add_relationship(
            patient_id,
            "HAS_DIAGNOSIS",
            diagnosis_id,
            {"recorded_at": datetime.now().isoformat()}
        )

    async def store_treatment(
        self,
        patient_id: str,
        medication: str,
        started_date: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store current treatment."""
        treatment_id = f"tx:{uuid.uuid4().hex[:12]}"

        await self.backend.add_entity(
            treatment_id,
            {
                "medication": medication,
                "started_date": started_date or "unknown",
                "recorded_at": datetime.now().isoformat(),
                **(metadata or {})
            },
            labels=["Treatment"]
        )

        await self.backend.add_relationship(
            patient_id,
            "CURRENT_TREATMENT",
            treatment_id,
            {"started_at": datetime.now().isoformat()}
        )

    async def get_patient_context(
        self,
        patient_id: str
    ) -> PatientContext:
        """Retrieve full patient context."""
        query = """
        MATCH (p:Patient {id: $patient_id})
        OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(dx:Diagnosis)
        OPTIONAL MATCH (p)-[:CURRENT_TREATMENT]->(tx:Treatment)
        OPTIONAL MATCH (p)-[:HAS_ALLERGY]->(allergy)
        RETURN
            p,
            collect(DISTINCT dx) as diagnoses,
            collect(DISTINCT tx) as treatments,
            collect(DISTINCT allergy.name) as allergies
        """

        result = await self.backend.query(query, {"patient_id": patient_id})

        # Parse result into PatientContext
        # ...

    async def store_conversation(
        self,
        patient_id: str,
        messages: List[Dict[str, str]],
        summary: Optional[str] = None
    ):
        """Store conversation history."""
        conv_id = f"conv:{uuid.uuid4().hex[:12]}"

        await self.backend.add_entity(
            conv_id,
            {
                "started_at": datetime.now().isoformat(),
                "summary": summary or "",
                "message_count": len(messages)
            },
            labels=["Conversation"]
        )

        await self.backend.add_relationship(
            patient_id,
            "HAD_CONVERSATION",
            conv_id,
            {}
        )

        # Store individual messages
        for i, msg in enumerate(messages):
            msg_id = f"{conv_id}:msg{i}"

            await self.backend.add_entity(
                msg_id,
                {
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg.get("timestamp", datetime.now().isoformat()),
                    "sequence": i
                },
                labels=["Message"]
            )

            await self.backend.add_relationship(
                conv_id,
                "HAS_MESSAGE",
                msg_id,
                {"sequence": i}
            )
```

**Integration with Chat Service**:

```python
class IntelligentChatService:
    def __init__(self, ..., patient_memory: Optional[PatientMemoryService] = None):
        # ... existing initialization
        self.patient_memory = patient_memory

    async def query(
        self,
        question: str,
        conversation_history: Optional[List[Message]] = None,
        patient_id: Optional[str] = None  # NEW
    ) -> ChatResponse:
        # Retrieve patient context if available
        patient_context = None
        if patient_id and self.patient_memory:
            patient_context = await self.patient_memory.get_patient_context(patient_id)

        # Include patient context in retrieval
        medical_context = await self._retrieve_medical_knowledge(
            entities,
            question,
            patient_context=patient_context  # NEW
        )

        # ... rest of query processing

        # Store conversation after response
        if patient_id and self.patient_memory:
            await self.patient_memory.store_conversation(
                patient_id,
                messages=[
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer}
                ]
            )
```

**Privacy & Security**:

1. **Consent Management**:
   ```python
   # Before storing any patient data
   if not patient.consent_given:
       raise PermissionError("Patient consent required for memory storage")
   ```

2. **Data Anonymization**:
   ```python
   # Never store PII (names, addresses, etc.)
   # Only store medical context
   ```

3. **HIPAA Compliance** (if needed):
   - Encrypt at rest (Neo4j encryption)
   - Encrypt in transit (TLS)
   - Audit logging
   - Right to be forgotten (delete patient data)

**New Role: Medical Assistant**

```python
# In domain/roles.py
class Role(str, Enum):
    DATA_ARCHITECT = "data_architect"
    DATA_ENGINEER = "data_engineer"
    KNOWLEDGE_MANAGER = "knowledge_manager"
    MEDICAL_ASSISTANT = "medical_assistant"  # NEW
    SYSTEM_ADMIN = "system_admin"
```

**Capabilities**:
- Store patient context
- Retrieve patient history
- Summarize conversations
- Manage consent

### Implementation Effort

- **Complexity**: Medium
- **Time**: 2-3 days
- **Dependencies**: None (uses existing Neo4j backend)
- **Files to create**:
  1. `src/application/services/patient_memory_service.py`
  2. `src/domain/patient_context.py`
  3. `tests/test_patient_memory.py`

### Benefits

✅ Personalized medical guidance
✅ Context-aware conversations
✅ Cross-session continuity
✅ Better patient experience
✅ Foundation for longitudinal tracking

### Risks

⚠️ Privacy concerns (requires consent)
⚠️ Data retention policies needed
⚠️ HIPAA compliance if healthcare setting

---

## 2. Voice Interaction Channel

### Concept

Enable speech-to-text (STT) and text-to-speech (TTS) for hands-free medical chat.

### Use Cases

- **Accessibility**: Patients with visual impairments
- **Convenience**: Hands-free interaction while doing tasks
- **Elderly patients**: Easier than typing
- **Medical emergencies**: Faster than typing

### Architecture Design

```
Voice Input → STT → Text → Chat Service → Text Response → TTS → Voice Output
```

#### Speech-to-Text Options

**Option A: OpenAI Whisper API** ⭐ Recommended

**Pros**:
- High accuracy (multilingual)
- Works well with medical terminology
- Already using OpenAI

**Cons**:
- Costs: $0.006 per minute
- Requires audio upload

**Implementation**:
```python
from openai import AsyncOpenAI

class VoiceInputService:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def transcribe(self, audio_file_path: str) -> str:
        """Transcribe audio to text using Whisper."""
        with open(audio_file_path, "rb") as audio_file:
            transcript = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"  # or auto-detect
            )
        return transcript.text
```

**Option B: Local Whisper (faster-whisper)**

**Pros**:
- Free (no API costs)
- Privacy (local processing)
- Fast with GPU

**Cons**:
- Requires GPU for real-time
- Need to download models (~1GB)

**Implementation**:
```python
from faster_whisper import WhisperModel

class LocalVoiceInputService:
    def __init__(self, model_size: str = "base"):
        # model_size: tiny, base, small, medium, large
        self.model = WhisperModel(model_size, device="cuda")

    async def transcribe(self, audio_file_path: str) -> str:
        segments, info = self.model.transcribe(audio_file_path)
        return " ".join([segment.text for segment in segments])
```

#### Text-to-Speech Options

**Option A: OpenAI TTS API** ⭐ Recommended

**Pros**:
- Very natural voice
- Multiple voices (alloy, echo, fable, onyx, nova, shimmer)
- Good pronunciation of medical terms

**Cons**:
- Costs: $0.015 per 1K characters

**Implementation**:
```python
class VoiceOutputService:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def synthesize(
        self,
        text: str,
        voice: str = "nova",  # Professional, clear voice
        output_path: str = "output.mp3"
    ) -> str:
        """Convert text to speech."""
        response = await self.client.audio.speech.create(
            model="tts-1",  # or "tts-1-hd" for higher quality
            voice=voice,
            input=text
        )

        response.stream_to_file(output_path)
        return output_path
```

**Option B: Local TTS (Coqui TTS)**

**Pros**:
- Free
- Multiple voices
- Good quality

**Cons**:
- Slower than API
- Requires setup

#### Full Voice Chat Integration

```python
class VoiceChatService:
    """Voice-enabled chat service."""

    def __init__(
        self,
        chat_service: IntelligentChatService,
        voice_input: VoiceInputService,
        voice_output: VoiceOutputService
    ):
        self.chat = chat_service
        self.stt = voice_input
        self.tts = voice_output

    async def voice_query(
        self,
        audio_input_path: str,
        patient_id: Optional[str] = None
    ) -> tuple[str, str]:
        """Process voice input and return voice output.

        Returns:
            (text_answer, audio_output_path)
        """
        # 1. Transcribe audio to text
        question = await self.stt.transcribe(audio_input_path)
        print(f"User said: {question}")

        # 2. Get chat response
        response = await self.chat.query(question, patient_id=patient_id)

        # 3. Convert answer to speech
        audio_path = await self.tts.synthesize(response.answer)

        return response.answer, audio_path
```

#### Web Interface (Optional)

**Using WebRTC for browser-based voice**:

```javascript
// Client-side (JavaScript)
let mediaRecorder;
let audioChunks = [];

async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
    };

    mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

        // Send to backend
        const formData = new FormData();
        formData.append('audio', audioBlob);

        const response = await fetch('/api/voice-chat', {
            method: 'POST',
            body: formData
        });

        const audioResponse = await response.blob();
        const audioUrl = URL.createObjectURL(audioResponse);

        // Play response
        const audio = new Audio(audioUrl);
        audio.play();
    };

    mediaRecorder.start();
}

function stopRecording() {
    mediaRecorder.stop();
}
```

### Cost Analysis

**At 1,000 queries/day**:
- STT (Whisper): Avg 30 sec/query = 500 min/day = $3/day = $90/month
- TTS: Avg 500 chars/response = 500K chars/day = $7.50/day = $225/month
- **Total**: ~$315/month for voice

**Compared to text-only**: $21.60/month
**Increase**: 14.6x more expensive!

**Recommendation**: Offer voice as premium feature or use local models.

### Implementation Effort

- **Complexity**: Low-Medium
- **Time**: 1-2 days (using APIs)
- **Dependencies**: OpenAI API or local Whisper/TTS
- **Files to create**:
  1. `src/application/services/voice_input_service.py`
  2. `src/application/services/voice_output_service.py`
  3. `src/application/services/voice_chat_service.py`
  4. `demos/demo_voice_chat.py`

### Benefits

✅ Accessibility for visually impaired
✅ Hands-free interaction
✅ Better elderly user experience
✅ Faster for some users
✅ Natural conversation flow

### Risks

⚠️ 14x cost increase (mitigate with local models)
⚠️ Audio quality issues
⚠️ Accent/dialect challenges
⚠️ Background noise

---

## 3. Improving Reasoning & Knowledge Generation

### Current State

- Reasoning engine returns fallback because "chat_query" isn't a recognized action
- No reasoning provenance (0 steps)
- Confidence calculation doesn't benefit from reasoning

### Goal

Enable proper neurosymbolic reasoning for chat queries with:
1. Symbolic rule application
2. Neural inference (LLM)
3. Confidence tracking
4. Provenance trail

### Implementation

**Step 1: Add chat_query support to ReasoningEngine**

```python
# File: src/application/agents/knowledge_manager/reasoning_engine.py

def _initialize_reasoning_rules(self) -> Dict[str, List[Dict[str, Any]]]:
    """Initialize reasoning rules for different operations."""
    return {
        "create_entity": [...],  # Existing
        "create_relationship": [...],  # Existing

        # NEW: Chat query reasoning
        "chat_query": [
            {
                "name": "medical_context_validation",
                "reasoner": self._validate_medical_context,
                "priority": "high"
            },
            {
                "name": "cross_graph_inference",
                "reasoner": self._infer_cross_graph_relationships,
                "priority": "high"
            },
            {
                "name": "treatment_recommendation_check",
                "reasoner": self._check_treatment_recommendations,
                "priority": "medium"
            },
            {
                "name": "data_availability_assessment",
                "reasoner": self._assess_data_availability,
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

**Step 2: Implement reasoning methods**

```python
async def _validate_medical_context(
    self,
    event: KnowledgeEvent,
    reasoning_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate medical entities in chat context."""
    entities = event.data.get("medical_entities", [])

    high_confidence_entities = []
    low_confidence_entities = []

    for entity in entities:
        confidence = entity.get("confidence", 0)

        if confidence >= 0.8:
            high_confidence_entities.append(entity)
            reasoning_result["inferences"].append({
                "type": "validated_medical_entity",
                "entity": entity.get("name"),
                "entity_type": entity.get("type"),
                "confidence": 0.9,
                "source": entity.get("source_document", "knowledge_graph")
            })
        elif confidence < 0.6:
            low_confidence_entities.append(entity)
            reasoning_result["warnings"].append(
                f"Low confidence entity: {entity.get('name')} ({confidence:.2f})"
            )

    reasoning_result["provenance"].append(
        f"Validated {len(high_confidence_entities)} high-confidence medical entities"
    )

    if low_confidence_entities:
        reasoning_result["provenance"].append(
            f"Found {len(low_confidence_entities)} low-confidence entities - may need verification"
        )

    return reasoning_result


async def _infer_cross_graph_relationships(
    self,
    event: KnowledgeEvent,
    reasoning_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Infer implicit relationships between medical and data entities."""
    medical_entities = event.data.get("medical_entities", [])
    data_tables = event.data.get("data_tables", [])
    data_columns = event.data.get("data_columns", [])

    if not medical_entities:
        return reasoning_result

    # Check for implicit data-medical connections
    potential_connections = []

    for med_entity in medical_entities:
        med_name = med_entity.get("name", "").lower()

        # Check if medical entity name appears in data entity names
        for table in data_tables:
            table_name = table.get("name", "").lower()
            if med_name in table_name or table_name in med_name:
                potential_connections.append({
                    "medical": med_entity.get("name"),
                    "data": table.get("name"),
                    "type": "table",
                    "confidence": 0.75
                })

        for column in data_columns:
            col_name = column.get("name", "").lower()
            if med_name in col_name or col_name in med_name:
                potential_connections.append({
                    "medical": med_entity.get("name"),
                    "data": column.get("name"),
                    "type": "column",
                    "confidence": 0.70
                })

    if potential_connections:
        reasoning_result["inferences"].extend([
            {
                "type": "inferred_cross_graph_link",
                "medical_entity": conn["medical"],
                "data_entity": conn["data"],
                "data_type": conn["type"],
                "confidence": conn["confidence"]
            }
            for conn in potential_connections
        ])

        reasoning_result["provenance"].append(
            f"Inferred {len(potential_connections)} potential cross-graph relationships"
        )

    return reasoning_result


async def _check_treatment_recommendations(
    self,
    event: KnowledgeEvent,
    reasoning_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Check if question involves treatment recommendations (sensitive)."""
    question = event.data.get("question", "").lower()

    treatment_keywords = [
        "should i take",
        "recommend",
        "prescribe",
        "best treatment",
        "what medication",
        "should i use"
    ]

    if any(keyword in question for keyword in treatment_keywords):
        reasoning_result["warnings"].append(
            "Question involves treatment recommendations - provide educational info only"
        )

        reasoning_result["inferences"].append({
            "type": "treatment_recommendation_detected",
            "disclaimer_required": True,
            "confidence": 0.95
        })

        reasoning_result["provenance"].append(
            "Detected treatment recommendation query - added medical disclaimer requirement"
        )

    return reasoning_result


async def _assess_data_availability(
    self,
    event: KnowledgeEvent,
    reasoning_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Assess data availability for answering the question."""
    medical_entities = event.data.get("medical_entities", [])
    relationships = event.data.get("medical_relationships", [])
    data_tables = event.data.get("data_tables", [])

    # Score data availability
    availability_score = 0.5  # Base score

    if medical_entities:
        availability_score += 0.1 * min(len(medical_entities), 3)

    if relationships:
        availability_score += 0.1 * min(len(relationships), 2)

    if data_tables:
        availability_score += 0.1 * min(len(data_tables), 2)

    availability_score = min(1.0, availability_score)

    reasoning_result["inferences"].append({
        "type": "data_availability_assessment",
        "score": availability_score,
        "confidence": 0.85
    })

    if availability_score >= 0.8:
        reasoning_result["provenance"].append(
            f"Strong data availability (score: {availability_score:.2f}) - high-confidence answer possible"
        )
    elif availability_score >= 0.6:
        reasoning_result["provenance"].append(
            f"Moderate data availability (score: {availability_score:.2f}) - answer with caveats"
        )
    else:
        reasoning_result["provenance"].append(
            f"Limited data availability (score: {availability_score:.2f}) - answer may be incomplete"
        )

    return reasoning_result


async def _score_answer_confidence(
    self,
    event: KnowledgeEvent,
    reasoning_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate overall confidence score for the answer."""
    # Base confidence from context quality
    base_confidence = 0.5

    # Boost for validated entities
    validated_entities = [
        inf for inf in reasoning_result.get("inferences", [])
        if inf.get("type") == "validated_medical_entity"
    ]
    if validated_entities:
        base_confidence += 0.1 * min(len(validated_entities), 3)

    # Boost for cross-graph connections
    cross_graph = [
        inf for inf in reasoning_result.get("inferences", [])
        if inf.get("type") == "inferred_cross_graph_link"
    ]
    if cross_graph:
        base_confidence += 0.05 * min(len(cross_graph), 2)

    # Penalize for warnings
    if reasoning_result.get("warnings"):
        base_confidence *= 0.95

    # Incorporate data availability
    data_availability = next(
        (inf for inf in reasoning_result.get("inferences", [])
         if inf.get("type") == "data_availability_assessment"),
        None
    )
    if data_availability:
        # Weight 50% from base, 50% from data availability
        base_confidence = (base_confidence + data_availability["score"]) / 2

    reasoning_result["confidence"] = min(1.0, base_confidence)
    reasoning_result["provenance"].append(
        f"Calculated confidence: {reasoning_result['confidence']:.2f} "
        f"(validated entities: {len(validated_entities)}, "
        f"cross-graph links: {len(cross_graph)})"
    )

    return reasoning_result
```

### Expected Improvements

**Before (current)**:
```
Reasoning trail: 0 steps
Confidence: 0.65
```

**After (with reasoning)**:
```
Reasoning trail: 5 steps
  1. Validated 4 high-confidence medical entities
  2. Inferred 2 potential cross-graph relationships
  3. Detected treatment recommendation query - added medical disclaimer requirement
  4. Strong data availability (score: 0.82) - high-confidence answer possible
  5. Calculated confidence: 0.85 (validated entities: 4, cross-graph links: 2)

Confidence: 0.85
```

### Implementation Effort

- **Complexity**: Medium
- **Time**: 2-3 days
- **Dependencies**: None (extends existing ReasoningEngine)
- **Files to modify**:
  1. `src/application/agents/knowledge_manager/reasoning_engine.py`

### Benefits

✅ Transparent reasoning process
✅ Better confidence calculation
✅ Safety checks (treatment recommendations)
✅ Data quality assessment
✅ Provenance for debugging
✅ Foundation for explainable AI

---

## Implementation Priority & Roadmap

### Phase 1: Reasoning (Highest Impact) ⭐
**Priority**: 🔥 High
**Effort**: 2-3 days
**ROI**: High (better answers, explainability)

**Why first**:
- Improves core functionality
- No new dependencies
- Foundation for other features

### Phase 2: Memory (High Value) ⭐
**Priority**: 🔥 High
**Effort**: 2-3 days
**ROI**: High (personalization, UX)

**Why second**:
- High user value
- Uses existing infrastructure
- Enables longitudinal tracking

### Phase 3: Voice (Optional)
**Priority**: 🟡 Medium
**Effort**: 1-2 days
**ROI**: Medium (accessibility, UX)

**Why last**:
- Nice-to-have feature
- 14x cost increase (use local models)
- Niche use case currently

---

## Recommended Implementation Order

1. **Week 1**: Improve reasoning (2-3 days)
   - Add chat_query support
   - Implement 5 reasoning methods
   - Test with existing chat

2. **Week 2**: Add memory (2-3 days)
   - Create PatientMemoryService
   - Add Patient nodes to Neo4j
   - Integrate with chat service
   - Add Medical Assistant role

3. **Week 3 (if needed)**: Add voice (1-2 days)
   - Implement VoiceInputService (Whisper)
   - Implement VoiceOutputService (TTS)
   - Create VoiceChatService
   - Demo CLI with voice

---

## Next Steps

Which enhancement would you like to start with?

**Option A**: Improve reasoning (highest impact, ready now)
**Option B**: Add memory (high value, patient-centric)
**Option C**: Both reasoning + memory (1 week sprint)
**Option D**: Wait for PDF ingestion to complete, then decide

I'm ready to implement any of these! What's your preference?
