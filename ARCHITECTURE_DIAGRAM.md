# System Architecture Diagram

**Medical Knowledge Management System - Complete Architecture**

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                       │
│                         USER BROWSER                                  │
│                     http://localhost:4321                             │
│                                                                       │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                    HTTP/WebSocket Requests
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      FRONTEND LAYER (Port 4321)                       │
│                                                                       │
│  ┌────────────────┐           ┌────────────────┐                     │
│  │  Astro.js      │  ←─────→  │  Vite Proxy    │                     │
│  │  Static Pages  │           │  /api → 8000   │                     │
│  └────────────────┘           │  /ws  → 8000   │                     │
│           │                   └────────────────┘                     │
│           ↓                                                          │
│  ┌────────────────────────────────────────┐                         │
│  │     React Islands (Client-side)         │                         │
│  │  • ChatInterface.tsx                    │                         │
│  │  • KnowledgeGraphViewer.tsx             │                         │
│  │  • AdminDashboard.tsx                   │                         │
│  │  • DDAUploader.tsx                      │                         │
│  └────────────────────────────────────────┘                         │
│                                                                       │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                    Proxied to Backend
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND LAYER (Port 8000)                        │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                FastAPI Application                              │ │
│  │                                                                  │ │
│  │  REST API Endpoints:                 WebSocket Endpoints:       │ │
│  │  • GET  /api/graph/data              • /ws/chat/{patient}/{id} │ │
│  │  • GET  /api/patients/{id}/context   • /ws/admin/monitor       │ │
│  │  • GET  /api/admin/metrics                                      │ │
│  │  • POST /api/dda/upload                                         │ │
│  │  • GET  /api/metadata/catalogs                                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                │                                      │
│                                ↓                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              Application Services                               │ │
│  │  • IntelligentChatService (reasoning + patient context)        │ │
│  │  • PatientMemoryService (3-layer memory)                       │ │
│  │  • ToolService (command execution)                             │ │
│  │  • ModelingWorkflow (DDA processing)                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                │                                      │
│                                ↓                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Domain Layer                                 │ │
│  │  • Command Bus (decoupled command handling)                    │ │
│  │  • Event Bus (distributed events)                              │ │
│  │  • Agent System (4 specialized agents)                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                    Database Connections
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER (Docker)                            │
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   Neo4j          │  │   Redis          │  │   Qdrant         │  │
│  │   (7474, 7687)   │  │   (6379)         │  │   (6333, 6334)   │  │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤  │
│  │ • Knowledge      │  │ • Sessions       │  │ • Vector         │  │
│  │   Graph          │  │   (24h TTL)      │  │   Embeddings     │  │
│  │ • Patient        │  │ • Cache          │  │ • Mem0 Storage   │  │
│  │   Medical Data   │  │ • Pub/Sub        │  │                  │  │
│  │ • DDA Metadata   │  │                  │  │                  │  │
│  │ • Audit Logs     │  │                  │  │                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                       │
│  ┌──────────────────┐                                                │
│  │   FalkorDB       │                                                │
│  │   (3000)         │                                                │
│  ├──────────────────┤                                                │
│  │ • Alternative    │                                                │
│  │   Graph DB       │                                                │
│  │ • Experimental   │                                                │
│  └──────────────────┘                                                │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### 1. Patient Chat Flow

```
User sends message in browser
         ↓
Frontend (ChatInterface.tsx)
         ↓ WebSocket
Backend WebSocket Handler (/ws/chat/{patient}/{session})
         ↓
PatientMemoryService.get_patient_context()
         ↓ queries
Neo4j (patient medical history)
Redis (cached session data)
Mem0/Qdrant (intelligent memories)
         ↓ returns context
IntelligentChatService.query()
         ↓ applies
Reasoning Engine (9 rules: 5 general + 4 patient safety)
         ↓ generates
LLM Response (with reasoning trail)
         ↓ stores
PatientMemoryService.store_message()
         ↓ saves to
Neo4j (full message log)
Mem0 (extracted facts)
Redis (session update)
         ↓ WebSocket response
Frontend displays message with:
  • Confidence score
  • Sources
  • Reasoning trail
  • Safety warnings (if any)
```

---

### 2. Knowledge Graph Visualization Flow

```
User opens /graph page
         ↓
Frontend (KnowledgeGraphViewer.tsx)
         ↓ HTTP GET
Backend /api/graph/data?limit=100
         ↓ queries
Neo4j:
  MATCH (n:Entity)
  OPTIONAL MATCH (n)-[r]->(m)
  RETURN n, r, m
         ↓ returns
JSON: { nodes: [...], edges: [...] }
         ↓ renders
D3.js Force Simulation:
  • forceLink (edges)
  • forceManyBody (repulsion)
  • forceCenter (centering)
  • forceCollide (overlap prevention)
         ↓ displays
Interactive Graph:
  • Color-coded by layer (4 colors)
  • Draggable nodes
  • Zoom/pan controls
  • Click → Entity details panel
```

---

### 3. DDA Upload & Processing Flow

```
User uploads .md file
         ↓
Frontend (DDAUploader.tsx)
         ↓ HTTP POST /api/dda/upload
Backend receives file
         ↓
Validates extension (.md, .markdown)
         ↓
Saves to temp file
         ↓
MarkdownDDAParser.parse_file()
         ↓ extracts
• Catalogs (## Catalog: {name})
• Schemas (### Schema: {name})
• Tables (#### Table: {name})
• Columns (table rows)
         ↓ creates nodes in
Neo4j:
  CREATE (c:Catalog {name: "Sales"})
  CREATE (s:Schema {name: "public"})
  CREATE (t:Table {name: "customers"})
  CREATE (col:Column {name: "id", type: "INTEGER"})
         ↓ creates relationships
  (c)-[:CONTAINS_SCHEMA]->(s)
  (s)-[:CONTAINS_TABLE]->(t)
  (t)-[:HAS_COLUMN]->(col)
         ↓ returns statistics
{
  entities_count: 15,
  relationships_count: 30,
  catalogs: ["Sales", "Marketing"],
  schemas: ["public", "staging"],
  tables: ["customers", "orders"]
}
         ↓ Frontend displays
Success message with details
         ↓ Now visible in
/graph page (knowledge graph visualization)
/dda/metadata page (hierarchical browser)
```

---

### 4. Three-Layer Memory System (Patient Context)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEMORY ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────┘

Layer 1: SHORT-TERM (Redis - 24h TTL)
┌──────────────────────────────────────┐
│ Active Session State                 │
│ • session:abc123 → {                 │
│     patient_id: "patient:demo",      │
│     started_at: "2026-01-23",        │
│     last_activity: "10:30:45",       │
│     conversation_count: 5            │
│   }                                  │
└──────────────────────────────────────┘
         ↓ Expires after 24h
         ↓ Cache for fast access

Layer 2: INTELLIGENT (Mem0 + Qdrant)
┌──────────────────────────────────────┐
│ Automatic Fact Extraction            │
│ • "Patient has severe allergy to     │
│    Ibuprofen" (extracted from chat)  │
│ • "Patient started Humira 40mg"      │
│ • Vector embeddings in Qdrant        │
│ • Graph relationships in Neo4j       │
│ • Semantic search enabled            │
└──────────────────────────────────────┘
         ↓ Permanent storage
         ↓ Intelligent retrieval

Layer 3: LONG-TERM (Neo4j - Permanent)
┌──────────────────────────────────────┐
│ Complete Medical Record              │
│ Patient Node:                        │
│   • Diagnoses (Crohn's Disease)      │
│   • Medications (Humira)             │
│   • Allergies (Ibuprofen)            │
│   • Full conversation logs           │
│   • Audit trail                      │
│   • Consent records                  │
└──────────────────────────────────────┘
         ↓ Permanent, queryable
         ↓ GDPR compliant
```

---

## Agent System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT ECOSYSTEM                               │
└─────────────────────────────────────────────────────────────────┘

              ┌─────────────────┐
              │   Command Bus   │
              │  (Coordinator)  │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Data Architect│ │Data Engineer │ │Knowledge Mgr │
│    Agent     │ │    Agent     │ │    Agent     │
├──────────────┤ ├──────────────┤ ├──────────────┤
│• Domain      │ │• Metadata    │ │• Graph Ops   │
│  Modeling    │ │  Generation  │ │• Reasoning   │
│• DDA Parsing │ │• Type        │ │• Validation  │
│              │ │  Inference   │ │• Conflict    │
│              │ │              │ │  Resolution  │
└──────────────┘ └──────────────┘ └──────────────┘
        ↓              ↓              ↓
        └──────────────┼──────────────┘
                       ↓
              ┌─────────────────┐
              │Medical Assistant│
              │     Agent       │
              ├─────────────────┤
              │• Patient Memory │
              │• Medical History│
              │• Contraindication│
              │  Checking       │
              └─────────────────┘
                       ↓
              Communication Channel
                       ↓
              Event Bus (Async Messaging)
```

---

## Security & Privacy Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                               │
└─────────────────────────────────────────────────────────────────┘

Frontend Security:
├─ Input Validation (XSS prevention)
├─ CSRF Protection (tokens)
└─ Content Security Policy

Backend Security:
├─ CORS Configuration
├─ Rate Limiting
├─ Input Sanitization
└─ SQL Injection Prevention (parameterized queries)

Data Privacy:
├─ Patient Consent Management
│  └─ Neo4j: Patient.consent_given = true/false
├─ PII Anonymization
│  └─ No real names/SSN stored
├─ Audit Logging
│  └─ Every data access logged
└─ GDPR Compliance
   ├─ Right to be Forgotten (PatientMemoryService.delete_patient_data())
   ├─ Data Portability
   └─ 7-year retention policy

Database Security:
├─ Neo4j Authentication (neo4j/password)
├─ Redis AUTH (if configured)
├─ Encrypted connections (TLS in production)
└─ Network isolation (Docker network)
```

---

## Deployment Architecture

### Development
```
Developer Machine
├─ Docker Desktop
│  ├─ Neo4j Container
│  ├─ Redis Container
│  ├─ Qdrant Container
│  └─ FalkorDB Container
├─ Terminal 1: Backend (uvicorn --reload)
└─ Terminal 2: Frontend (npm run dev)
```

### Production (Recommended)
```
Load Balancer (Nginx/HAProxy)
         ↓
┌────────┴────────┐
│                 │
Frontend Pods     Backend Pods
(Astro Static)    (FastAPI + Gunicorn)
│                 │
│                 ↓
│        ┌────────┴────────┐
│        │                 │
│    Neo4j Cluster    Redis Cluster
│    (3 nodes)        (Master+Replicas)
│        │
│    Qdrant Cluster
│    (3 nodes)
```

---

## Performance Characteristics

### Response Times
- Frontend Load: < 1s
- API Response: < 500ms
- WebSocket Latency: 50-100ms
- Graph Query (100 nodes): < 2s
- Patient Context Load: < 1s

### Throughput
- Concurrent Users: 100+ (single backend instance)
- Messages/second: 50+ (WebSocket)
- Graph Queries/second: 20+
- DDA Processing: 1 file/5 seconds (50KB)

### Scalability
- Frontend: Infinitely scalable (static files)
- Backend: Horizontal scaling (stateless)
- Neo4j: Vertical + read replicas
- Redis: Cluster mode (sharding)

---

## Monitoring Points

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                                 │
└─────────────────────────────────────────────────────────────────┘

Metrics:
├─ System Metrics (Admin Dashboard)
│  ├─ Total Queries
│  ├─ Avg Response Time
│  ├─ Active Sessions
│  └─ Total Patients
├─ Neo4j Metrics
│  ├─ Node Count
│  ├─ Relationship Count
│  └─ Query Performance
└─ Redis Metrics
   ├─ Memory Usage
   ├─ Hit Rate
   └─ Connected Clients

Logs:
├─ Backend Logs (uvicorn)
├─ Frontend Logs (browser console)
├─ Database Logs (docker logs)
└─ Audit Logs (Neo4j)

Health Checks:
├─ check_services.sh (manual)
├─ /api/health endpoint (automated)
└─ Docker health checks
```

---

**This architecture supports:**
- ✅ Real-time patient chat with context
- ✅ Interactive knowledge graph visualization
- ✅ Medical data management with privacy
- ✅ Intelligent reasoning with patient safety
- ✅ Scalable, production-ready deployment
- ✅ GDPR/HIPAA compliance foundations

For implementation details, see [SERVICES_GUIDE.md](SERVICES_GUIDE.md)
