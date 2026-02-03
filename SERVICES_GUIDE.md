# Services Management Guide

**Complete guide** for managing all services in the Medical Knowledge Management System.

---

## Service Overview

The system consists of **7 services** across 3 layers:

### Layer 1: Databases (Docker)
1. **Neo4j** - Main graph database
2. **FalkorDB** - Alternative graph database
3. **Redis** - Session cache & pub/sub
4. **Qdrant** - Vector database for Mem0

### Layer 2: Backend (Python)
5. **FastAPI Backend** - Main API server

### Layer 3: Frontend (Node.js)
6. **Astro Dev Server** - Frontend development server
7. **Vite HMR** - Hot module replacement (bundled with Astro)

---

## Quick Start (Recommended Order)

### Option A: Full Stack Development

```bash
# 1. Start all databases (one command)
docker-compose -f docker-compose.memory.yml up -d

# 2. Start backend (Terminal 1)
uv run uvicorn src.application.api.main:app --reload --port 8000

# 3. Start frontend (Terminal 2)
cd frontend && npm run dev
```

### Option B: Backend Development Only

```bash
# 1. Start only required databases
docker-compose -f docker-compose.memory.yml up -d neo4j redis

# 2. Start backend
uv run uvicorn src.application.api.main:app --reload --port 8000
```

---

## Detailed Service Management

### 1. Neo4j (Graph Database)

**Purpose:** Main knowledge graph storage

**Port Mapping:**
- `7474` - Browser interface (HTTP)
- `7687` - Bolt protocol (database connection)

**Start:**
```bash
# Via Docker Compose (recommended)
docker-compose -f docker-compose.memory.yml up -d neo4j

# Or standalone
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

**Verify:**
```bash
# Check container
docker ps | grep neo4j

# Access browser
open http://localhost:7474

# Connect via CLI
docker exec -it neo4j cypher-shell -u neo4j -p password
```

**Status Check:**
```bash
curl http://localhost:7474
```

**Logs:**
```bash
docker logs neo4j -f
```

**Stop:**
```bash
docker stop neo4j
```

**Data Location:** `./data/neo4j` (if volume mounted)

---

### 2. FalkorDB (Alternative Graph Database)

**Purpose:** Experimental/alternative graph storage

**Port:** `3000` (HTTP API)

**Start:**
```bash
docker-compose -f docker-compose.memory.yml up -d falkordb
```

**Verify:**
```bash
curl http://localhost:3000
```

**Note:** Port 3000 is why we changed frontend to 4321

**Stop:**
```bash
docker stop falkordb
```

---

### 3. Redis (Cache & Session Store)

**Purpose:**
- Session caching (24h TTL)
- Pub/sub for multi-instance backend
- Patient context cache

**Port:** `6379` (TCP)

**Start:**
```bash
docker-compose -f docker-compose.memory.yml up -d redis
```

**Verify:**
```bash
# Test connection
redis-cli ping
# Expected: PONG

# Check keys
redis-cli KEYS "*"

# Monitor activity
redis-cli MONITOR
```

**Status Check:**
```bash
docker exec -it redis redis-cli INFO | grep uptime
```

**Stop:**
```bash
docker stop redis
```

---

### 4. Qdrant (Vector Database)

**Purpose:** Vector embeddings for Mem0 memory system

**Port Mapping:**
- `6333` - HTTP API
- `6334` - gRPC

**Start:**
```bash
docker-compose -f docker-compose.memory.yml up -d qdrant
```

**Verify:**
```bash
curl http://localhost:6333/health
# Expected: {"status":"ok"}

# List collections
curl http://localhost:6333/collections
```

**Dashboard:**
```bash
open http://localhost:6333/dashboard
```

**Stop:**
```bash
docker stop qdrant
```

---

### 5. FastAPI Backend

**Purpose:** Main application server with WebSocket support

**Port:** `8000`

**Start:**
```bash
# Development mode (auto-reload)
uv run uvicorn src.application.api.main:app --reload --port 8000

# Production mode
uv run uvicorn src.application.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Verify:**
```bash
# API docs
open http://localhost:8000/docs

# Health check
curl http://localhost:8000/api/health

# Test graph endpoint
curl http://localhost:8000/api/graph/data?limit=10
```

**Environment Variables:**
```bash
# Required
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=password
export OPENAI_API_KEY=sk-...

# Optional
export REDIS_HOST=localhost
export REDIS_PORT=6379
export QDRANT_URL=http://localhost:6333
```

**Logs:** Displayed in terminal

**Stop:** `Ctrl+C`

---

### 6. Astro Dev Server (Frontend)

**Purpose:** Frontend development server with HMR

**Port:** `4321` (changed from 3000)

**Start:**
```bash
cd frontend
npm run dev

# Or with specific host
npm run dev -- --host 0.0.0.0
```

**Verify:**
```bash
# Home page
open http://localhost:4321

# Chat interface
open http://localhost:4321/chat/patient:demo

# Knowledge graph
open http://localhost:4321/graph
```

**Build for Production:**
```bash
cd frontend
npm run build
# Output: frontend/dist/
```

**Preview Production Build:**
```bash
cd frontend
npm run preview
```

**Logs:** Displayed in terminal

**Stop:** `Ctrl+C`

---

## Port Summary Table

| Service | Port(s) | Protocol | URL |
|---------|---------|----------|-----|
| Neo4j Browser | 7474 | HTTP | http://localhost:7474 |
| Neo4j Bolt | 7687 | TCP | bolt://localhost:7687 |
| FalkorDB | 3000 | HTTP | http://localhost:3000 |
| Redis | 6379 | TCP | localhost:6379 |
| Qdrant API | 6333 | HTTP | http://localhost:6333 |
| Qdrant gRPC | 6334 | gRPC | localhost:6334 |
| **Backend API** | **8000** | HTTP/WS | **http://localhost:8000** |
| **Frontend** | **4321** | HTTP | **http://localhost:4321** |

---

## Docker Compose Management

### Start All Services
```bash
docker-compose -f docker-compose.memory.yml up -d
```

### Start Specific Services
```bash
# Only Neo4j and Redis
docker-compose -f docker-compose.memory.yml up -d neo4j redis

# Only databases (no FalkorDB)
docker-compose -f docker-compose.memory.yml up -d neo4j redis qdrant
```

### Check Status
```bash
docker-compose -f docker-compose.memory.yml ps
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.memory.yml logs -f

# Specific service
docker-compose -f docker-compose.memory.yml logs -f neo4j
```

### Stop All Services
```bash
docker-compose -f docker-compose.memory.yml down
```

### Stop and Remove Volumes (⚠️ Deletes data)
```bash
docker-compose -f docker-compose.memory.yml down -v
```

### Restart a Service
```bash
docker-compose -f docker-compose.memory.yml restart neo4j
```

---

## Service Dependencies

```
Frontend (4321)
    ↓ depends on
Backend (8000)
    ↓ depends on
Neo4j (7687) + Redis (6379) + Qdrant (6333)

FalkorDB (3000) - Independent/experimental
```

**Minimum Required for Frontend:**
1. Neo4j (for graph data)
2. Redis (for sessions)
3. Backend API (for endpoints)
4. Frontend dev server

**Minimum Required for Backend Testing:**
1. Neo4j (required)
2. Redis (optional, but recommended)

---

## Health Check Commands

### Quick Health Check All Services
```bash
#!/bin/bash
echo "Checking all services..."

# Neo4j
echo -n "Neo4j (7474): "
curl -s http://localhost:7474 > /dev/null && echo "✅" || echo "❌"

# FalkorDB
echo -n "FalkorDB (3000): "
curl -s http://localhost:3000 > /dev/null && echo "✅" || echo "❌"

# Redis
echo -n "Redis (6379): "
redis-cli ping > /dev/null 2>&1 && echo "✅" || echo "❌"

# Qdrant
echo -n "Qdrant (6333): "
curl -s http://localhost:6333/health > /dev/null && echo "✅" || echo "❌"

# Backend
echo -n "Backend (8000): "
curl -s http://localhost:8000/docs > /dev/null && echo "✅" || echo "❌"

# Frontend
echo -n "Frontend (4321): "
curl -s http://localhost:4321 > /dev/null && echo "✅" || echo "❌"
```

Save as `check_services.sh`, make executable, and run:
```bash
chmod +x check_services.sh
./check_services.sh
```

---

## Common Operations

### Start Everything (Development)
```bash
# Terminal 1: Start databases
docker-compose -f docker-compose.memory.yml up -d

# Terminal 2: Start backend
uv run uvicorn src.application.api.main:app --reload --port 8000

# Terminal 3: Start frontend
cd frontend && npm run dev
```

### Stop Everything
```bash
# Stop frontend (Terminal 3)
Ctrl+C

# Stop backend (Terminal 2)
Ctrl+C

# Stop databases (Terminal 1 or new terminal)
docker-compose -f docker-compose.memory.yml down
```

### Restart Backend Only
```bash
# Terminal 2 (after Ctrl+C)
uv run uvicorn src.application.api.main:app --reload --port 8000
```

### Restart Frontend Only
```bash
# Terminal 3 (after Ctrl+C)
cd frontend && npm run dev
```

### Clear Redis Cache
```bash
redis-cli FLUSHDB
```

### Reset Neo4j Database
```bash
# Connect to Neo4j
docker exec -it neo4j cypher-shell -u neo4j -p password

# Delete all nodes and relationships
MATCH (n) DETACH DELETE n;
```

---

## Troubleshooting

### Port Already in Use

**Problem:** "Address already in use" error

**Solution:**
```bash
# Find process using port (e.g., 8000)
lsof -i :8000

# Kill process
kill -9 <PID>

# Or for multiple processes
lsof -ti:8000 | xargs kill -9
```

### Docker Container Won't Start

**Problem:** Container exits immediately

**Solution:**
```bash
# Check logs
docker logs <container_name>

# Remove container and try again
docker rm <container_name>
docker-compose -f docker-compose.memory.yml up -d <service_name>

# Check for port conflicts
docker ps -a
```

### Backend Can't Connect to Neo4j

**Problem:** "Failed to connect to bolt://localhost:7687"

**Solution:**
```bash
# 1. Verify Neo4j is running
docker ps | grep neo4j

# 2. Check Neo4j logs
docker logs neo4j | tail -20

# 3. Test connection
docker exec -it neo4j cypher-shell -u neo4j -p password

# 4. Restart Neo4j
docker restart neo4j
```

### Frontend Shows "Disconnected"

**Problem:** WebSocket not connecting

**Solution:**
```bash
# 1. Verify backend is running
curl http://localhost:8000/docs

# 2. Test WebSocket
uv run python test_websocket.py

# 3. Check browser console (F12)
# Look for WebSocket connection errors

# 4. Restart both backend and frontend
```

### Redis Connection Refused

**Problem:** "Connection refused" to Redis

**Solution:**
```bash
# 1. Check if Redis is running
docker ps | grep redis

# 2. Test connection
redis-cli ping

# 3. Restart Redis
docker restart redis

# 4. Check Redis logs
docker logs redis
```

---

## Production Deployment

### Using Docker (Recommended)

```bash
# Build production frontend
cd frontend
npm run build

# Build Docker image
docker build -t medical-knowledge-system .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

### Manual Deployment

```bash
# 1. Build frontend
cd frontend
npm run build

# 2. Copy frontend/dist/ to backend static directory
cp -r frontend/dist/* /var/www/static/

# 3. Run backend with gunicorn
gunicorn src.application.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

---

## Monitoring

### View All Container Stats
```bash
docker stats
```

### Monitor Redis Activity
```bash
redis-cli MONITOR
```

### Monitor Neo4j Queries
```bash
# In Neo4j Browser: :queries
# Or via CLI:
docker exec -it neo4j cypher-shell -u neo4j -p password
# Then run: CALL dbms.listQueries();
```

### Monitor Backend Logs
```bash
# If using systemd
journalctl -u medical-knowledge-backend -f

# If running in terminal
# Logs are displayed automatically
```

---

## Backup & Restore

### Backup Neo4j
```bash
# Create backup
docker exec neo4j neo4j-admin backup \
  --backup-dir=/backups --name=graph-$(date +%Y%m%d)

# Copy from container
docker cp neo4j:/backups ./neo4j-backups/
```

### Backup Redis
```bash
# Trigger save
redis-cli SAVE

# Copy dump file
docker cp redis:/data/dump.rdb ./redis-backup.rdb
```

### Restore Neo4j
```bash
# Stop Neo4j
docker stop neo4j

# Restore from backup
docker exec neo4j neo4j-admin restore \
  --from=/backups/graph-20260123 --database=neo4j

# Start Neo4j
docker start neo4j
```

---

## Performance Tuning

### Neo4j Memory Settings
```yaml
# docker-compose.memory.yml
environment:
  - NEO4J_dbms_memory_heap_initial__size=1G
  - NEO4J_dbms_memory_heap_max__size=2G
  - NEO4J_dbms_memory_pagecache_size=512M
```

### Backend Workers
```bash
# Production: Use multiple workers
gunicorn --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Redis Persistence
```yaml
# docker-compose.memory.yml
command: redis-server --appendonly yes --appendfsync everysec
```

---

## Quick Reference

### Essential Commands
```bash
# Start all services
docker-compose -f docker-compose.memory.yml up -d
uv run uvicorn src.application.api.main:app --reload --port 8000
cd frontend && npm run dev

# Check all services
./check_services.sh

# Stop all services
docker-compose -f docker-compose.memory.yml down
```

### Essential URLs
- Frontend: http://localhost:4321
- Backend API: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474
- Qdrant Dashboard: http://localhost:6333/dashboard

---

**Keep this guide handy for service management! 🚀**
