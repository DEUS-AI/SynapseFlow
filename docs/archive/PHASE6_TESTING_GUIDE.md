# Phase 6: Conversational Agent Personality Layer - Testing Guide

## Overview

This guide will help you test the conversational personality layer to ensure the agent responds naturally with memory-aware context.

## Prerequisites

### 1. Environment Variables

Make sure your `.env` file has:

```bash
# Required
OPENAI_API_KEY=sk-...
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Memory layer
QDRANT_URL=http://localhost:6333
REDIS_HOST=localhost
REDIS_PORT=6379

# Conversational layer (Phase 6)
ENABLE_CONVERSATIONAL_LAYER=true  # Enable/disable conversational layer
AGENT_PERSONA=default              # default | clinical | friendly
```

### 2. Start Backend Services

```bash
# Start Neo4j, RabbitMQ, Redis, Qdrant
docker-compose -f docker-compose.services.yml up -d
docker-compose -f docker-compose.memory.yml up -d

# Verify services are running
docker ps
```

You should see:
- Neo4j (port 7687, 7474)
- Redis (port 6379)
- Qdrant (port 6333)

---

## Test 1: Unit Tests (Offline)

Run the unit test script to verify components work without backend:

```bash
uv run python tests/test_conversational_layer.py
```

**Expected Output:**

```
TEST 1: Intent Classification
======================================================================
✅ 'Hello' -> greeting (confidence: 0.90)
✅ 'Hey, I'm back' -> greeting_return (confidence: 0.90)
✅ 'My knee hurts' -> symptom_report (confidence: 0.90)
   Topic: knee
   Urgency: medium
✅ 'What is ibuprofen?' -> medical_query (confidence: 0.70)
✅ 'Thanks' -> acknowledgment (confidence: 0.90)
✅ 'Goodbye' -> farewell (confidence: 0.90)

TEST 2: Memory Context Building (Mock)
======================================================================
✅ Mock memory context created:
   Patient: Pablo
   Recent topics: knee pain, ibuprofen, physical therapy
   Days since last session: 2
   Has history: True
   Is returning user: True
   Time context: It's been 2 days

TEST 3: Response Modulation
======================================================================
✅ Using persona: Medical Assistant (warm_professional)

--- Test 3a: Greeting Return with Memory ---
✅ Generated greeting:
   Hey Pablo, welcome back! It's been a couple of days - how's your knee
   feeling? Did you get a chance to try the physical therapy exercises?

--- Test 3b: New User Greeting (No Memory) ---
✅ Generated greeting:
   Hello! I'm your medical assistant. I'm here to help answer your health
   questions and provide guidance. What can I help you with today?

--- Test 3c: Medical Query with Persona Wrapping ---
✅ Wrapped medical response:
   Let me help you with that. Ibuprofen is a nonsteroidal anti-inflammatory
   drug (NSAID) used to reduce pain and inflammation. Given your current knee
   pain, this medication could help manage your symptoms. Let me know if you
   have any questions!

TEST 4: Different Personas
======================================================================
--- Medical Assistant (warm_professional) ---
   Use patient name: True
   Proactive followups: True
   Show empathy: True

--- Clinical Assistant (clinical) ---
   Use patient name: False
   Proactive followups: False
   Show empathy: False

--- Health Buddy (friendly) ---
   Use patient name: True
   Proactive followups: True
   Show empathy: True
```

---

## Test 2: Backend Integration (With Services)

### 2.1 Start the API

```bash
uv run uvicorn application.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected startup messages:**

```
🔄 Initializing Patient Memory Service...
  ✅ Mem0 initialized
  ✅ Neo4j backend initialized
  ✅ Redis session cache initialized
✅ Patient Memory Service initialized
✅ IntelligentChatService initialized (conversational_layer=True)
Conversational personality layer enabled
```

### 2.2 Test via API (cURL)

#### Test 1: Create Patient & Session

```bash
# Create a patient
curl -X POST http://localhost:8000/api/patients \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "test_pablo", "consent_given": true}'

# Start a session
curl -X POST http://localhost:8000/api/chat/sessions/start \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "test_pablo"}'
```

#### Test 2: Send Messages (New User)

```bash
# First greeting (no history)
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type": application/json" \
  -d '{
    "question": "Hello",
    "patient_id": "test_pablo",
    "session_id": "session:xxx"
  }'
```

**Expected Response:**
```json
{
  "answer": "Hello! I'm your medical assistant. I'm here to help answer your health questions and provide guidance. What can I help you with today?",
  "confidence": 0.95,
  "sources": [],
  "related_concepts": [],
  "reasoning_trail": ["Intent: greeting"],
  "query_time_seconds": 0.3
}
```

#### Test 3: Symptom Report

```bash
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "My knee hurts when I walk",
    "patient_id": "test_pablo",
    "session_id": "session:xxx"
  }'
```

**Expected Response:**
- Intent detected: SYMPTOM_REPORT
- Empathetic response
- Follow-up questions (severity, duration)

#### Test 4: Returning User Greeting

```bash
# Wait a few seconds for Mem0 to extract facts, then:
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Hey, I'm back",
    "patient_id": "test_pablo",
    "session_id": "session:xxx"
  }'
```

**Expected Response:**
```json
{
  "answer": "Welcome back! We were discussing your knee pain. How's it feeling today?",
  "confidence": 0.95,
  "sources": [],
  "related_concepts": [],
  "reasoning_trail": ["Intent: greeting_return"],
  "query_time_seconds": 0.4
}
```

### 2.3 Test via WebSocket (Frontend)

Open [http://localhost:8000/docs](http://localhost:8000/docs) and navigate to the WebSocket test interface:

1. **Connect WebSocket:**
   ```
   ws://localhost:8000/ws/chat/test_pablo/session123
   ```

2. **Send Test Messages:**

   ```json
   {"message": "Hello"}
   ```
   → Should get generic greeting

   ```json
   {"message": "My knee hurts"}
   ```
   → Should get empathetic symptom response

   ```json
   {"message": "What is ibuprofen?"}
   ```
   → Should get medical info wrapped with persona

   ```json
   {"message": "Thanks!"}
   ```
   → Should get brief acknowledgment

---

## Test 3: Different Personas

### 3.1 Test Default Persona (Warm Professional)

```bash
export AGENT_PERSONA=default
uv run uvicorn application.api.main:app --reload
```

Expected behavior:
- Uses patient name: "Hey Pablo, ..."
- Proactive follow-ups: "How's your knee today?"
- Shows empathy: "I understand you're experiencing pain..."

### 3.2 Test Clinical Persona

```bash
export AGENT_PERSONA=clinical
uv run uvicorn application.api.main:app --reload
```

Expected behavior:
- No patient name: "Hello."
- No proactive follow-ups
- Formal tone: "Please provide additional information..."

### 3.3 Test Friendly Persona

```bash
export AGENT_PERSONA=friendly
uv run uvicorn application.api.main:app --reload
```

Expected behavior:
- Uses patient name: "Hey Pablo!"
- Very casual: "How's it going?"
- More emojis/casual language (if enabled)

---

## Test 4: Memory Context Verification

### 4.1 Check Mem0 Memories

```bash
# Query Mem0 directly to verify memories are stored
curl -X GET http://localhost:11333/api/memories/test_pablo
```

### 4.2 Check Neo4j Data

```cypher
// In Neo4j Browser (http://localhost:7474)

// Check patient
MATCH (p:Patient {id: 'test_pablo'}) RETURN p;

// Check sessions
MATCH (p:Patient {id: 'test_pablo'})-[:HAS_SESSION]->(s)
RETURN s;

// Check messages
MATCH (s:ConversationSession)-[:HAS_MESSAGE]->(m:Message)
WHERE s.patient_id = 'test_pablo'
RETURN m ORDER BY m.timestamp DESC LIMIT 10;
```

### 4.3 Check Redis Session

```bash
# Connect to Redis
docker exec -it <redis-container-id> redis-cli

# Check session data
KEYS session:*
GET session:xxx
```

---

## Expected Behavior Summary

| User Input | Intent | Expected Response Style |
|------------|--------|-------------------------|
| "Hello" | GREETING | Generic welcome, offer help |
| "Hey, I'm back" | GREETING_RETURN | Personalized, mentions recent topics |
| "My knee hurts" | SYMPTOM_REPORT | Empathetic, asks clarifying questions |
| "What is ibuprofen?" | MEDICAL_QUERY | Educational, cites sources, wrapped with persona |
| "Thanks" | ACKNOWLEDGMENT | Brief, offers next steps |
| "Goodbye" | FAREWELL | Warm closing |

---

## Troubleshooting

### Issue: "Conversational layer disabled"

**Solution:** Check that:
```bash
ENABLE_CONVERSATIONAL_LAYER=true  # in .env
```

### Issue: Generic greetings even for returning users

**Solution:**
1. Verify Mem0 is storing memories:
   ```bash
   # Check Mem0 logs
   docker logs <qdrant-container>
   ```

2. Check that patient has conversation history in Neo4j

3. Ensure `days_since_last_session` is calculated correctly

### Issue: LLM classification failing

**Solution:**
- Check `OPENAI_API_KEY` is valid
- Verify network connectivity
- Check API rate limits

### Issue: Memory context not found

**Solution:**
1. Verify Redis is running: `docker ps | grep redis`
2. Check Neo4j connection: `docker ps | grep neo4j`
3. Verify Qdrant is running: `docker ps | grep qdrant`

---

## Success Criteria

✅ **Test 1: Intent Classification**
- All 6 intent types classify correctly
- Confidence scores >= 0.7

✅ **Test 2: Memory Context**
- Recent topics extracted from Mem0
- Patient profile loaded from Neo4j
- Days since last session calculated

✅ **Test 3: Personalized Greetings**
- New users get generic greeting
- Returning users get personalized greeting with recent topics

✅ **Test 4: Response Modulation**
- Medical responses wrapped with persona
- Empathetic responses for symptom reports
- Natural follow-up handling

✅ **Test 5: Different Personas**
- Default, clinical, and friendly personas behave differently
- Persona configuration loads correctly

---

## Next Steps After Testing

Once Phase 6 is verified:

1. ✅ **Phase 6 Complete** - Conversational personality works
2. 🔄 **Review Chat History Plan** - Adjust if needed based on Phase 6 learnings
3. 🚀 **Implement Chat History** - Add session retrieval and continuation

---

## Debugging Tips

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
uv run uvicorn application.api.main:app --reload
```

### Check Logs

```bash
# Backend logs
tail -f backend.log

# View intent classification
grep "Intent classified" backend.log

# View memory context
grep "Memory context built" backend.log

# View response modulation
grep "Wrapping medical response" backend.log
```

---

## Test Results Template

Use this template to document your test results:

```markdown
## Phase 6 Test Results

**Date:** 2026-01-26
**Tester:** [Your Name]

### Environment
- [ ] Neo4j running
- [ ] Redis running
- [ ] Qdrant running
- [ ] API started successfully

### Test Results

#### Unit Tests
- [ ] Intent classification: PASS/FAIL
- [ ] Memory context mock: PASS/FAIL
- [ ] Response modulation: PASS/FAIL
- [ ] Different personas: PASS/FAIL

#### Integration Tests
- [ ] New user greeting: PASS/FAIL
- [ ] Returning user greeting: PASS/FAIL
- [ ] Symptom report: PASS/FAIL
- [ ] Medical query: PASS/FAIL
- [ ] Acknowledgment: PASS/FAIL

#### Issues Found
1. [Issue description]
2. [Issue description]

### Conclusion
- [ ] Phase 6 working as expected
- [ ] Ready to proceed with Chat History implementation
```
