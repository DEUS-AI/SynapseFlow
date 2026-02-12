# Manual Testing Guide: Feature Flags & Connections

This guide provides step-by-step checklists for verifying all system connections and feature flag behavior after enabling dual-write or switching to PostgreSQL as primary storage.

---

## Prerequisites

### Required Services Running

```bash
# Start all required services
docker-compose -f docker-compose.services.yml up -d   # Neo4j, RabbitMQ
docker-compose -f docker-compose.memory.yml up -d     # Redis, Qdrant

# Verify services are up
docker ps | grep -E "(neo4j|redis|qdrant|rabbitmq)"
```

### Backend Running

```bash
# Start backend API
uv run uvicorn application.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Running (if testing UI)

```bash
cd frontend && npm run dev
```

---

## Phase 1: Connection Verification

### 1.1 Neo4j Connection

```bash
# Check health endpoint
curl -s http://localhost:8000/health | jq '.neo4j'
```

**Expected**: `"healthy"` or similar status

**Manual verification**:
```bash
# Direct Neo4j check
curl -s -u neo4j:password http://localhost:7474/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"RETURN 1"}]}'
```

- [ ] Neo4j responds to health check
- [ ] Neo4j browser accessible at http://localhost:7474

---

### 1.2 PostgreSQL Connection

```bash
# Check dual-write health (includes PostgreSQL status)
curl -s http://localhost:8000/api/admin/dual-write-health | jq '.'
```

**Expected**: Response with `sessions`, `feedback`, `documents` sections

**If PostgreSQL not configured**: Will show warnings but API should still work

- [ ] PostgreSQL connection succeeds (or graceful fallback)
- [ ] Dual-write health endpoint returns data

---

### 1.3 Redis Connection

```bash
# Check health endpoint
curl -s http://localhost:8000/health | jq '.redis'
```

**Manual verification**:
```bash
redis-cli -p 6380 ping
```

**Expected**: `PONG`

- [ ] Redis responds to ping
- [ ] Health endpoint shows Redis healthy

---

### 1.4 Qdrant Connection

```bash
# Check Qdrant directly
curl -s http://localhost:6333/collections | jq '.result.collections | length'
```

**Expected**: Number (collections count)

- [ ] Qdrant API responds
- [ ] Collections endpoint accessible

---

## Phase 2: Feature Flag Verification

### 2.1 View Current Feature Flags

```bash
curl -s http://localhost:8000/api/admin/feature-flags | jq '.'
```

**Expected output structure**:
```json
{
  "dual_write_sessions": {"enabled": false, "source": "default"},
  "dual_write_feedback": {"enabled": false, "source": "default"},
  "dual_write_documents": {"enabled": false, "source": "default"},
  "use_postgres_sessions": {"enabled": false, "source": "default"},
  "use_postgres_feedback": {"enabled": false, "source": "default"},
  "use_postgres_documents": {"enabled": false, "source": "default"}
}
```

- [ ] All expected flags are present
- [ ] Default values are `false`
- [ ] Source shows `"default"` (no overrides yet)

---

### 2.2 Test Environment Override

```bash
# Set environment variable and restart backend
export FEATURE_FLAG_DUAL_WRITE_SESSIONS=true
uv run uvicorn application.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Then verify:
```bash
curl -s http://localhost:8000/api/admin/feature-flags | jq '.dual_write_sessions'
```

**Expected**:
```json
{"enabled": true, "source": "environment"}
```

- [ ] Environment override works
- [ ] Source changes to `"environment"`

---

### 2.3 Test API Flag Toggle

```bash
# Toggle a flag via API
curl -X PUT http://localhost:8000/api/admin/feature-flags/dual_write_feedback \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

**Expected**: `{"success": true}` or updated flag status

- [ ] API toggle endpoint works
- [ ] Flag value changes

---

## Phase 3: Dual-Write Testing

### 3.1 Session Dual-Write

**Step 1**: Enable dual-write for sessions
```bash
export FEATURE_FLAG_DUAL_WRITE_SESSIONS=true
# Restart backend
```

**Step 2**: Create a session via chat
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "test-patient-001",
    "message": "Hello, this is a test message"
  }'
```

**Step 3**: Verify in Neo4j
```cypher
MATCH (s:ConversationSession {patient_id: "test-patient-001"})
RETURN s.id, s.created_at
```

**Step 4**: Verify in PostgreSQL (if configured)
```sql
SELECT id, patient_id, created_at FROM sessions
WHERE patient_id = 'test-patient-001';
```

- [ ] Session created in Neo4j
- [ ] Session created in PostgreSQL (if dual-write enabled)
- [ ] Data matches between both stores

---

### 3.2 Feedback Dual-Write

**Step 1**: Enable dual-write for feedback
```bash
export FEATURE_FLAG_DUAL_WRITE_FEEDBACK=true
# Restart backend
```

**Step 2**: Submit feedback
```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "response_id": "test-response-001",
    "query_text": "What is ibuprofen?",
    "response_text": "Ibuprofen is a pain reliever...",
    "rating": 4,
    "feedback_type": "helpful"
  }'
```

**Step 3**: Verify in Neo4j
```cypher
MATCH (f:UserFeedback {response_id: "test-response-001"})
RETURN f
```

**Step 4**: Verify in PostgreSQL
```sql
SELECT * FROM feedback WHERE response_id = 'test-response-001';
```

- [ ] Feedback created in Neo4j
- [ ] Feedback created in PostgreSQL (if dual-write enabled)
- [ ] Rating and feedback_type match

---

### 3.3 Document Dual-Write

**Step 1**: Enable dual-write for documents
```bash
export FEATURE_FLAG_DUAL_WRITE_DOCUMENTS=true
# Restart backend
```

**Step 2**: Upload a document
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@examples/sample_dda.md"
```

**Step 3**: Verify in Neo4j
```cypher
MATCH (d:Document)
RETURN d.filename, d.status, d.created_at
ORDER BY d.created_at DESC LIMIT 5
```

**Step 4**: Verify in PostgreSQL
```sql
SELECT filename, status, created_at FROM documents
ORDER BY created_at DESC LIMIT 5;
```

- [ ] Document metadata in Neo4j
- [ ] Document metadata in PostgreSQL (if dual-write enabled)
- [ ] Status and counts match

---

## Phase 4: Sync Health Verification

### 4.1 Check Dual-Write Health

```bash
curl -s http://localhost:8000/api/admin/dual-write-health | jq '.'
```

**Expected structure**:
```json
{
  "sessions": {
    "neo4j_count": 10,
    "postgres_count": 10,
    "in_sync": true,
    "drift": 0
  },
  "feedback": {
    "neo4j_count": 5,
    "postgres_count": 5,
    "in_sync": true,
    "drift": 0
  },
  "documents": {
    "neo4j_count": 3,
    "postgres_count": 3,
    "in_sync": true,
    "drift": 0
  },
  "overall_health": "healthy",
  "recommendations": []
}
```

- [ ] All sections show `in_sync: true`
- [ ] Drift is 0 for all data types
- [ ] Overall health is `"healthy"`
- [ ] No critical recommendations

---

### 4.2 Migration Status

```bash
curl -s http://localhost:8000/api/admin/migration-status | jq '.'
```

**Expected**:
```json
{
  "phase": "dual_write",
  "flags": {
    "dual_write_sessions": true,
    "dual_write_feedback": true,
    "dual_write_documents": true,
    "use_postgres_sessions": false,
    "use_postgres_feedback": false,
    "use_postgres_documents": false
  },
  "ready_for_cutover": true
}
```

- [ ] Phase shows current migration stage
- [ ] Flags reflect actual configuration
- [ ] Ready for cutover indicates if PostgreSQL can become primary

---

## Phase 5: Frontend Verification

### 5.1 Chat Interface

1. Open http://localhost:4321 (or frontend URL)
2. Start a new chat session
3. Send a message

- [ ] Chat interface loads
- [ ] Messages appear in UI
- [ ] Session is created (check via API)

---

### 5.2 Admin Dashboard

1. Open http://localhost:4321/admin

- [ ] Admin page loads
- [ ] Document list shows
- [ ] Feedback section accessible

---

### 5.3 Knowledge Graph Viewer

1. Open http://localhost:4321/graph

- [ ] Graph visualization loads
- [ ] Entities are visible
- [ ] Zoom/pan works

---

## Phase 6: Agent Services Verification

### 6.1 Medical Assistant Agent

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "test-agent-001",
    "message": "What are the side effects of ibuprofen?"
  }'
```

- [ ] Response received
- [ ] Response contains medical information
- [ ] No errors in backend logs

---

### 6.2 Knowledge Manager Agent

```bash
# Trigger a knowledge graph query
curl -X POST http://localhost:8000/api/graph/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What drugs treat inflammation?",
    "trace_layers": true
  }'
```

- [ ] Query executes
- [ ] Results include layer information
- [ ] Provenance data included

---

### 6.3 Neurosymbolic Query

```bash
curl -X POST http://localhost:8000/api/graph/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Drug interactions for ibuprofen",
    "strategy": "SYMBOLIC_ONLY"
  }'
```

- [ ] Query uses symbolic-only strategy
- [ ] Safety-critical queries work correctly

---

## Troubleshooting

### Common Issues

| Symptom | Possible Cause | Solution |
|---------|----------------|----------|
| Health check fails | Service not running | `docker-compose up -d` |
| Dual-write not happening | Flag not enabled | Check `FEATURE_FLAG_*` env vars |
| Drift detected | Write failed to one store | Check logs, re-sync data |
| Frontend not loading | Backend not reachable | Check CORS, verify ports |
| Agent errors | Missing dependencies | Run `uv sync` |

### Log Inspection

```bash
# Backend logs
tail -f backend.log

# Neo4j logs
docker logs neo4j --tail 100

# PostgreSQL logs (if using Docker)
docker logs postgres --tail 100
```

### Reset Test Data

```bash
# Clear test sessions from Neo4j
# (Use with caution)
MATCH (s:ConversationSession) WHERE s.patient_id STARTS WITH 'test-'
DETACH DELETE s

# Clear test feedback
MATCH (f:UserFeedback) WHERE f.response_id STARTS WITH 'test-'
DETACH DELETE f
```

---

## Checklist Summary

### Pre-Flip Verification
- [ ] All services running (Neo4j, PostgreSQL, Redis, Qdrant)
- [ ] Backend health check passes
- [ ] Feature flags visible via API
- [ ] Environment override works

### Dual-Write Testing
- [ ] Session dual-write verified
- [ ] Feedback dual-write verified
- [ ] Document dual-write verified
- [ ] Sync health shows no drift

### Application Testing
- [ ] Frontend loads and works
- [ ] Chat sessions work
- [ ] Knowledge graph queries work
- [ ] Agent responses are correct

### Ready for PostgreSQL Primary
- [ ] All dual-write tests pass
- [ ] No drift between stores
- [ ] Migration status shows ready
- [ ] Rollback plan documented

---

## Post-Cutover Verification

After flipping `use_postgres_*` flags to `true`:

1. Verify reads come from PostgreSQL
2. Verify writes still go to both stores
3. Monitor for any performance changes
4. Keep Neo4j synced for rollback capability

```bash
# Enable PostgreSQL as primary for sessions
export FEATURE_FLAG_USE_POSTGRES_SESSIONS=true
# Restart and test...
```

---

**Last Updated**: 2026-01-29
