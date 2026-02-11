# Storage Architecture Migration Plan

**Version:** 1.0
**Date:** 2026-01-28
**Status:** Planning

---

## Executive Summary

This document outlines the migration from a Neo4j-centric storage architecture to a purpose-driven multi-database architecture that separates concerns between:

- **Neo4j**: Knowledge Graph (entities, relationships, layers)
- **PostgreSQL**: Relational data (sessions, feedback, metrics, audit)
- **Qdrant**: Vector embeddings (document chunks, semantic search)
- **Redis**: Caching and real-time state

---

## 1. Current State Analysis

### 1.1 Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Neo4j                                │
│  (Currently handling ALL data)                              │
├─────────────────────────────────────────────────────────────┤
│  • Knowledge Graph entities (MedicalEntity, Disease, etc.)  │
│  • 4-Layer hierarchy (PERCEPTION → APPLICATION)             │
│  • Patient data (Patient, Diagnosis, Medication, Allergy)   │
│  • Session management (ConversationSession, Message)        │
│  • Feedback storage (UserFeedback)                          │
│  • Document metadata                                         │
│  • Audit trails (LayerTransition)                           │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐
│       Redis          │  │       Qdrant         │
│  (patient_memory)    │  │  (Mem0 embeddings)   │
├──────────────────────┤  ├──────────────────────┤
│  • Session state     │  │  • Patient memories  │
│  • Short-term cache  │  │  • Conversation ctx  │
└──────────────────────┘  └──────────────────────┘
```

### 1.2 Current Data Volumes (Estimated)

| Data Type | Current Count | Growth Rate |
|-----------|---------------|-------------|
| Knowledge Graph Nodes | ~600 | +50/week |
| Relationships | ~700 | +60/week |
| Sessions | ~50 | +20/day |
| Messages | ~500 | +200/day |
| Feedback | ~10 | +50/day (target) |
| Documents | ~20 | +5/week |

### 1.3 Current Pain Points

1. **Performance Contention**: Graph traversals compete with relational queries
2. **Aggregation Overhead**: Neo4j not optimized for COUNT, AVG, GROUP BY
3. **Agent Conflicts**: Multiple agents querying same instance
4. **Missing Vector Search**: No semantic similarity for documents
5. **Schema Rigidity**: Graph schema changes require migrations

---

## 2. Target Architecture

### 2.1 Purpose-Driven Storage

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Target Architecture                                │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│       Neo4j         │  │    PostgreSQL       │  │       Qdrant        │
│   (Graph Store)     │  │  (Relational Store) │  │   (Vector Store)    │
├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤
│ Knowledge Graph:    │  │ Operational Data:   │  │ Embeddings:         │
│ • MedicalEntity     │  │ • sessions          │  │ • document_chunks   │
│ • Disease           │  │ • messages          │  │ • entity_embeddings │
│ • Treatment         │  │ • feedback          │  │ • query_cache       │
│ • Symptom           │  │ • document_meta     │  │                     │
│ • Drug              │  │ • quality_metrics   │  │ Payload Filtering:  │
│                     │  │ • audit_logs        │  │ • layer             │
│ Relationships:      │  │ • users             │  │ • document_id       │
│ • TREATS            │  │ • preferences       │  │ • entity_type       │
│ • CAUSES            │  │                     │  │ • quality_score     │
│ • CONTRAINDICATED   │  │ Analytics:          │  │                     │
│                     │  │ • feedback_stats    │  │                     │
│ Patient Links:      │  │ • query_patterns    │  │                     │
│ • Patient→Entity    │  │ • agent_metrics     │  │                     │
│   references only   │  │                     │  │                     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                    ┌─────────────────────────┐
                    │         Redis           │
                    │   (Cache & State)       │
                    ├─────────────────────────┤
                    │ • Session state         │
                    │ • Query result cache    │
                    │ • Rate limiting         │
                    │ • Distributed locks     │
                    │ • Real-time pub/sub     │
                    └─────────────────────────┘
```

### 2.2 Data Ownership Matrix

| Data Type | Primary Store | Secondary | Cache |
|-----------|---------------|-----------|-------|
| Knowledge entities | Neo4j | - | Redis |
| Entity relationships | Neo4j | - | Redis |
| 4-Layer hierarchy | Neo4j | - | - |
| Patient profiles | Neo4j | PostgreSQL | Redis |
| Sessions | PostgreSQL | - | Redis |
| Messages | PostgreSQL | - | - |
| Feedback | PostgreSQL | - | - |
| Document metadata | PostgreSQL | - | - |
| Document chunks | - | - | Qdrant |
| Quality metrics | PostgreSQL | - | - |
| Audit logs | PostgreSQL | - | - |
| Entity embeddings | - | - | Qdrant |

---

## 3. Migration Phases

### Phase 0: Preparation (Week 1)

**Objective:** Set up infrastructure without disrupting production

#### Tasks

- [ ] **0.1** Add PostgreSQL to docker-compose
- [ ] **0.2** Create PostgreSQL schema (see Section 4)
- [ ] **0.3** Add SQLAlchemy models to codebase
- [ ] **0.4** Create repository pattern for PostgreSQL
- [ ] **0.5** Expand Qdrant collections for documents
- [ ] **0.6** Set up connection pooling (asyncpg)
- [ ] **0.7** Create feature flags for gradual rollout

#### Docker Compose Addition

```yaml
# docker-compose.services.yml - Add this service
  postgres:
    image: postgres:16-alpine
    container_name: synapseflow_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-synapseflow}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
      POSTGRES_DB: ${POSTGRES_DB:-synapseflow}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U synapseflow"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - synapseflow_network

# Add to volumes section
volumes:
  postgres_data:
```

#### Environment Variables

```bash
# .env additions
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=synapseflow
POSTGRES_PASSWORD=password
POSTGRES_DB=synapseflow
DATABASE_URL=postgresql+asyncpg://synapseflow:password@localhost:5432/synapseflow

# Feature flags
ENABLE_POSTGRES_SESSIONS=false
ENABLE_POSTGRES_FEEDBACK=false
ENABLE_QDRANT_DOCUMENTS=false
```

#### Verification Checklist
- [ ] PostgreSQL container starts and is healthy
- [ ] Can connect from application
- [ ] Schema created successfully
- [ ] Qdrant collections created

---

### Phase 1: Dual-Write Sessions (Week 2)

**Objective:** Write sessions to both Neo4j and PostgreSQL

#### Tasks

- [ ] **1.1** Implement PostgresSessionRepository
- [ ] **1.2** Create DualWriteSessionService wrapper
- [ ] **1.3** Enable dual-write via feature flag
- [ ] **1.4** Monitor for write failures
- [ ] **1.5** Verify data consistency between stores

#### Implementation Pattern

```python
# src/infrastructure/postgres/session_repository.py
class PostgresSessionRepository:
    """PostgreSQL repository for session data."""

    async def create_session(self, session: SessionCreate) -> Session:
        query = """
        INSERT INTO sessions (id, patient_id, title, status, created_at)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """
        return await self.pool.fetchrow(query, ...)

# src/application/services/dual_write_session_service.py
class DualWriteSessionService:
    """Writes to both Neo4j and PostgreSQL during migration."""

    def __init__(self, neo4j_repo, postgres_repo, feature_flags):
        self.neo4j = neo4j_repo
        self.postgres = postgres_repo
        self.flags = feature_flags

    async def create_session(self, data: SessionCreate) -> Session:
        # Always write to Neo4j (primary)
        session = await self.neo4j.create_session(data)

        # Dual-write to PostgreSQL if enabled
        if self.flags.is_enabled("ENABLE_POSTGRES_SESSIONS"):
            try:
                await self.postgres.create_session(data)
            except Exception as e:
                logger.error(f"PostgreSQL write failed: {e}")
                # Don't fail the request - Neo4j is still primary

        return session
```

#### Rollback Plan
- Disable `ENABLE_POSTGRES_SESSIONS` flag
- PostgreSQL data can be truncated
- Neo4j remains source of truth

---

### Phase 2: Migrate Existing Sessions (Week 3)

**Objective:** Backfill PostgreSQL with existing Neo4j session data

#### Tasks

- [ ] **2.1** Create migration script
- [ ] **2.2** Run migration in batches (100 at a time)
- [ ] **2.3** Verify row counts match
- [ ] **2.4** Verify data integrity (spot checks)
- [ ] **2.5** Create reconciliation report

#### Migration Script

```python
# scripts/migrations/migrate_sessions_to_postgres.py
async def migrate_sessions():
    """Migrate sessions from Neo4j to PostgreSQL."""

    # 1. Get all sessions from Neo4j
    neo4j_sessions = await neo4j.query_raw("""
        MATCH (s:ConversationSession)
        OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
        RETURN s, collect(m) as messages
        ORDER BY s.created_at
    """)

    migrated = 0
    failed = 0

    for batch in chunks(neo4j_sessions, 100):
        async with postgres.transaction():
            for record in batch:
                try:
                    # Insert session
                    await postgres.execute("""
                        INSERT INTO sessions (id, patient_id, title, ...)
                        VALUES ($1, $2, $3, ...)
                        ON CONFLICT (id) DO NOTHING
                    """, ...)

                    # Insert messages
                    for msg in record['messages']:
                        await postgres.execute("""
                            INSERT INTO messages (id, session_id, ...)
                            VALUES ($1, $2, ...)
                            ON CONFLICT (id) DO NOTHING
                        """, ...)

                    migrated += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to migrate {record['s']['id']}: {e}")

    return {"migrated": migrated, "failed": failed}
```

#### Verification Queries

```sql
-- PostgreSQL: Count sessions
SELECT COUNT(*) FROM sessions;

-- Neo4j: Count sessions (run via cypher-shell)
MATCH (s:ConversationSession) RETURN count(s);

-- Compare counts should match
```

---

### Phase 3: Switch Session Reads (Week 4)

**Objective:** Read sessions from PostgreSQL, write to both

#### Tasks

- [ ] **3.1** Update ChatHistoryService to read from PostgreSQL
- [ ] **3.2** Keep dual-write active
- [ ] **3.3** Monitor query performance (should improve)
- [ ] **3.4** Verify API responses unchanged
- [ ] **3.5** Run integration tests

#### Performance Comparison

| Query | Neo4j | PostgreSQL | Expected |
|-------|-------|------------|----------|
| List sessions (patient) | ~50ms | ~10ms | 5x faster |
| Get session messages | ~30ms | ~5ms | 6x faster |
| Session count | ~100ms | ~2ms | 50x faster |
| Message search | ~200ms | ~20ms | 10x faster |

---

### Phase 4: Migrate Feedback (Week 5)

**Objective:** Move feedback storage to PostgreSQL

#### Tasks

- [ ] **4.1** Enable dual-write for feedback
- [ ] **4.2** Migrate existing feedback data
- [ ] **4.3** Update FeedbackTracerService to use PostgreSQL
- [ ] **4.4** Verify RLHF dashboard works
- [ ] **4.5** Test export endpoints

#### Benefits

```sql
-- Fast aggregations now possible
SELECT
    DATE_TRUNC('day', created_at) as day,
    COUNT(*) as total,
    AVG(rating) as avg_rating,
    COUNT(*) FILTER (WHERE rating >= 4) as positive
FROM feedback
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY day;

-- Layer performance analysis
SELECT
    unnest(layers_traversed) as layer,
    AVG(rating) as avg_rating,
    COUNT(*) as query_count
FROM feedback
GROUP BY layer;
```

---

### Phase 5: Document Quality & Embeddings (Week 6)

**Objective:** Set up document quality metrics and vector search

#### Tasks

- [ ] **5.1** Create document_quality table in PostgreSQL
- [ ] **5.2** Create document_chunks collection in Qdrant
- [ ] **5.3** Implement DocumentQualityService
- [ ] **5.4** Implement document chunking pipeline
- [ ] **5.5** Generate embeddings for existing documents

#### Qdrant Collection Setup

```python
# Create document chunks collection
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

client = QdrantClient(host="localhost", port=6333)

client.create_collection(
    collection_name="document_chunks",
    vectors_config=VectorParams(
        size=1536,  # OpenAI ada-002 dimension
        distance=Distance.COSINE
    )
)

# Payload schema
{
    "document_id": "doc-123",
    "chunk_index": 5,
    "chunk_text": "...",  # For debugging
    "layer": "SEMANTIC",
    "quality_score": 0.85,
    "entity_types": ["Disease", "Treatment"],
    "created_at": "2026-01-28T..."
}
```

---

### Phase 6: Remove Neo4j Relational Data (Week 7)

**Objective:** Clean up Neo4j, keep only graph data

#### Tasks

- [ ] **6.1** Disable Neo4j writes for sessions
- [ ] **6.2** Disable Neo4j writes for feedback
- [ ] **6.3** Archive Neo4j session/feedback data
- [ ] **6.4** Delete archived data from Neo4j
- [ ] **6.5** Update all services to use new stores

#### Cleanup Script

```cypher
// Archive before deleting (export to JSON first)
// Then delete relational data from Neo4j

// Delete session nodes and relationships
MATCH (s:ConversationSession)
DETACH DELETE s;

// Delete message nodes
MATCH (m:Message)
DETACH DELETE m;

// Delete feedback nodes (after PostgreSQL verified)
MATCH (f:UserFeedback)
DETACH DELETE f;

// Verify only graph data remains
MATCH (n)
RETURN labels(n) as type, count(n) as count
ORDER BY count DESC;
```

---

### Phase 7: Optimization & Monitoring (Week 8)

**Objective:** Fine-tune performance and set up monitoring

#### Tasks

- [ ] **7.1** Create PostgreSQL indexes
- [ ] **7.2** Set up connection pooling
- [ ] **7.3** Configure query timeouts
- [ ] **7.4** Add Prometheus metrics
- [ ] **7.5** Create Grafana dashboards

#### PostgreSQL Indexes

```sql
-- Sessions
CREATE INDEX idx_sessions_patient ON sessions(patient_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_activity ON sessions(last_activity DESC);

-- Messages
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(created_at DESC);
CREATE INDEX idx_messages_response ON messages(response_id) WHERE response_id IS NOT NULL;

-- Feedback
CREATE INDEX idx_feedback_response ON feedback(response_id);
CREATE INDEX idx_feedback_created ON feedback(created_at DESC);
CREATE INDEX idx_feedback_rating ON feedback(rating);

-- Document Quality
CREATE INDEX idx_quality_document ON document_quality(document_id);
CREATE INDEX idx_quality_score ON document_quality(composite_score DESC);

-- Full-text search (optional)
CREATE INDEX idx_messages_content_fts ON messages USING gin(to_tsvector('english', content));
```

---

## 4. PostgreSQL Schema

### 4.1 Complete Schema

```sql
-- File: scripts/postgres/init.sql

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- ===========================================
-- Sessions & Messages
-- ===========================================

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id VARCHAR(100) NOT NULL,
    title VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'ended', 'archived')),
    device VARCHAR(50) DEFAULT 'web',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    response_id UUID,  -- Links to feedback
    confidence FLOAT,
    sources JSONB DEFAULT '[]'::jsonb,
    reasoning_trail JSONB DEFAULT '[]'::jsonb,
    related_concepts JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ===========================================
-- Feedback & RLHF
-- ===========================================

CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    response_id UUID NOT NULL,
    session_id UUID REFERENCES sessions(id),
    patient_id VARCHAR(100),
    query_text TEXT,
    response_text TEXT,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    feedback_type VARCHAR(50) CHECK (feedback_type IN (
        'helpful', 'unhelpful', 'incorrect', 'partially_correct', 'missing_info'
    )),
    severity VARCHAR(20) CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    correction_text TEXT,
    entities_involved TEXT[] DEFAULT '{}',
    layers_traversed TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE preference_pairs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prompt TEXT NOT NULL,
    chosen_response TEXT NOT NULL,
    rejected_response TEXT NOT NULL,
    chosen_feedback_id UUID REFERENCES feedback(id),
    rejected_feedback_id UUID REFERENCES feedback(id),
    rating_gap FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===========================================
-- Document Management
-- ===========================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(100) UNIQUE,  -- Original document ID
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    title VARCHAR(500),
    source VARCHAR(100),  -- 'upload', 'dda', 'pdf'
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN (
        'pending', 'processing', 'completed', 'failed'
    )),
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE document_quality (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Core metrics (0.0 - 1.0)
    information_density FLOAT,
    structural_clarity FLOAT,
    entity_coherence FLOAT,
    context_sufficiency FLOAT,
    contextual_relevancy FLOAT,

    -- Composite score
    composite_score FLOAT,

    -- Detailed breakdown
    metrics_detail JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(document_id)  -- One quality record per document
);

-- ===========================================
-- Audit & Analytics
-- ===========================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(255),
    actor VARCHAR(100),  -- 'system', 'user', agent name
    action VARCHAR(50),
    old_value JSONB,
    new_value JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE query_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64),  -- For deduplication
    strategy VARCHAR(50),
    layers_traversed TEXT[],
    execution_time_ms FLOAT,
    result_count INTEGER,
    cache_hit BOOLEAN DEFAULT FALSE,
    confidence FLOAT,
    patient_id VARCHAR(100),
    session_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===========================================
-- Materialized Views for Analytics
-- ===========================================

CREATE MATERIALIZED VIEW feedback_daily_stats AS
SELECT
    DATE_TRUNC('day', created_at) as day,
    COUNT(*) as total_feedback,
    AVG(rating) as avg_rating,
    COUNT(*) FILTER (WHERE rating >= 4) as positive_count,
    COUNT(*) FILTER (WHERE rating <= 2) as negative_count,
    COUNT(*) FILTER (WHERE correction_text IS NOT NULL) as corrections_count
FROM feedback
GROUP BY DATE_TRUNC('day', created_at);

CREATE MATERIALIZED VIEW layer_performance AS
SELECT
    unnest(layers_traversed) as layer,
    AVG(rating) as avg_rating,
    COUNT(*) as query_count,
    COUNT(*) FILTER (WHERE rating <= 2) as negative_count
FROM feedback
GROUP BY unnest(layers_traversed);

-- Refresh views (run periodically via cron or pg_cron)
-- REFRESH MATERIALIZED VIEW feedback_daily_stats;
-- REFRESH MATERIALIZED VIEW layer_performance;

-- ===========================================
-- Indexes
-- ===========================================

-- Sessions
CREATE INDEX idx_sessions_patient ON sessions(patient_id);
CREATE INDEX idx_sessions_status ON sessions(status) WHERE status = 'active';
CREATE INDEX idx_sessions_activity ON sessions(last_activity DESC);

-- Messages
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(session_id, created_at DESC);
CREATE INDEX idx_messages_response ON messages(response_id) WHERE response_id IS NOT NULL;

-- Feedback
CREATE INDEX idx_feedback_response ON feedback(response_id);
CREATE INDEX idx_feedback_created ON feedback(created_at DESC);
CREATE INDEX idx_feedback_rating ON feedback(rating);
CREATE INDEX idx_feedback_layers ON feedback USING gin(layers_traversed);

-- Documents
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_external ON documents(external_id);

-- Quality
CREATE INDEX idx_quality_score ON document_quality(composite_score DESC);

-- Analytics
CREATE INDEX idx_query_hash ON query_analytics(query_hash);
CREATE INDEX idx_query_created ON query_analytics(created_at DESC);

-- Full-text search
CREATE INDEX idx_messages_fts ON messages USING gin(to_tsvector('english', content));
```

---

## 5. Risk Mitigation

### 5.1 Risk Matrix

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Data loss during migration | High | Low | Backup before each phase, dual-write |
| Performance degradation | Medium | Medium | Feature flags, gradual rollout |
| API breaking changes | High | Low | Maintain backward compatibility |
| PostgreSQL connection issues | Medium | Medium | Connection pooling, retries |
| Inconsistent data between stores | Medium | Medium | Reconciliation scripts |

### 5.2 Rollback Procedures

**Phase 1-3 Rollback (Sessions):**
```bash
# Disable PostgreSQL writes
export ENABLE_POSTGRES_SESSIONS=false

# Restart services
docker-compose restart api

# Neo4j remains source of truth
```

**Phase 4 Rollback (Feedback):**
```bash
# Disable PostgreSQL feedback
export ENABLE_POSTGRES_FEEDBACK=false

# Update FeedbackTracerService to read from Neo4j
# (keep as commented code until migration complete)
```

**Full Rollback:**
```bash
# Disable all PostgreSQL features
export ENABLE_POSTGRES_SESSIONS=false
export ENABLE_POSTGRES_FEEDBACK=false
export ENABLE_QDRANT_DOCUMENTS=false

# Restart all services
docker-compose down
docker-compose up -d
```

---

## 6. Testing Requirements

### 6.1 Pre-Migration Tests

- [ ] All existing unit tests pass
- [ ] Integration tests pass
- [ ] Load test baseline established
- [ ] Backup verified

### 6.2 Per-Phase Tests

**Phase 1 (Dual-Write):**
- [ ] Sessions created in both stores
- [ ] Data consistency verified
- [ ] Write latency acceptable (<100ms overhead)

**Phase 2 (Migration):**
- [ ] Row counts match
- [ ] Sample data spot-checked
- [ ] No orphaned records

**Phase 3 (Read Switch):**
- [ ] API responses unchanged
- [ ] Query performance improved
- [ ] No 500 errors in logs

**Phase 4-6:**
- [ ] Feedback dashboard works
- [ ] RLHF export works
- [ ] Quality metrics calculated

### 6.3 Post-Migration Tests

- [ ] Full integration test suite
- [ ] Load test comparison
- [ ] 24-hour soak test
- [ ] User acceptance testing

---

## 7. Timeline Summary

| Week | Phase | Key Deliverable |
|------|-------|-----------------|
| 1 | 0: Preparation | PostgreSQL running, schema created |
| 2 | 1: Dual-Write Sessions | Sessions writing to both stores |
| 3 | 2: Migrate Sessions | Historical data in PostgreSQL |
| 4 | 3: Switch Reads | Sessions served from PostgreSQL |
| 5 | 4: Migrate Feedback | Feedback in PostgreSQL, RLHF working |
| 6 | 5: Documents & Vectors | Quality metrics, Qdrant embeddings |
| 7 | 6: Cleanup | Neo4j relational data removed |
| 8 | 7: Optimization | Indexes, monitoring, documentation |

---

## 8. Success Criteria

### Performance Targets

| Metric | Current | Target |
|--------|---------|--------|
| Session list query | 50ms | <10ms |
| Feedback aggregation | 200ms | <20ms |
| Semantic search | N/A | <50ms |
| Write latency overhead | N/A | <20ms |

### Data Integrity

- [ ] Zero data loss
- [ ] 100% data consistency
- [ ] All APIs backward compatible

### Operational

- [ ] No unplanned downtime
- [ ] Rollback tested and documented
- [ ] Monitoring dashboards created

---

## 9. Dependencies

### Required Packages

```toml
# pyproject.toml additions
[project.dependencies]
asyncpg = "^0.29.0"
sqlalchemy = {extras = ["asyncio"], version = "^2.0.0"}
alembic = "^1.13.0"
qdrant-client = "^1.7.0"
```

### Infrastructure

- PostgreSQL 16+
- Qdrant 1.7+
- Redis 7+ (existing)
- Neo4j 5+ (existing)

---

## Appendix A: File Structure

```
src/
├── infrastructure/
│   ├── neo4j_backend.py          # Existing (graph only)
│   ├── postgres/
│   │   ├── __init__.py
│   │   ├── connection.py         # Connection pooling
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── session_repository.py
│   │   ├── feedback_repository.py
│   │   └── document_repository.py
│   └── qdrant/
│       ├── __init__.py
│       ├── client.py             # Qdrant client wrapper
│       └── document_vectors.py   # Embedding operations
├── application/
│   └── services/
│       ├── dual_write_session_service.py
│       └── document_quality_service.py
scripts/
├── postgres/
│   └── init.sql                  # Schema
└── migrations/
    ├── migrate_sessions.py
    └── migrate_feedback.py
```

---

**Document Owner:** Engineering Team
**Review Date:** 2026-02-01
**Next Review:** After Phase 3 completion
