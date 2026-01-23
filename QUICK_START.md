# Quick Start Guide

**Get the Medical Knowledge Management System up and running in 3 steps.**

---

## TL;DR (Too Long; Didn't Read)

```bash
# 1. Start databases
./manage_services.sh start-db

# 2. Start backend (Terminal 1)
uv run uvicorn src.application.api.main:app --reload --port 8000

# 3. Start frontend (Terminal 2)
cd frontend && npm run dev

# 4. Open browser
open http://localhost:4321
```

---

## Step-by-Step

### 1️⃣ Start Database Services

```bash
./manage_services.sh start-db
```

This starts:
- ✅ Neo4j (port 7474, 7687)
- ✅ Redis (port 6379)
- ✅ Qdrant (port 6333)
- ✅ FalkorDB (port 3000) - optional

**Verify:** Wait 10-15 seconds, then run:
```bash
./check_services.sh
```

---

### 2️⃣ Start Backend API

Open a new terminal window and run:

```bash
uv run uvicorn src.application.api.main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

**Verify:** Open http://localhost:8000/docs

---

### 3️⃣ Start Frontend

Open another terminal window and run:

```bash
cd frontend
npm run dev
```

**Expected output:**
```
astro  v4.x.x ready in XXX ms

┃ Local    http://localhost:4321/
```

**Verify:** Open http://localhost:4321

---

## What You Should See

### Home Page (http://localhost:4321)
Four feature cards:
- 💬 Patient Chat
- 🔗 Knowledge Graph
- 👨‍💼 Admin Dashboard
- 📁 DDA Management

### Patient Chat (http://localhost:4321/chat/patient:demo)
- ✅ **Green "Connected"** indicator (top right)
- Chat input enabled
- Patient context sidebar (may be empty initially)

### Knowledge Graph (http://localhost:4321/graph)
- "No graph data available" message (expected when empty)
- Upload DDA to populate data

### Admin Dashboard (http://localhost:4321/admin)
- System metrics
- Agent status cards

---

## Troubleshooting

### Issue: Services Not Running

**Check status:**
```bash
./check_services.sh
```

**Start missing services:**
```bash
./manage_services.sh start-db
```

---

### Issue: WebSocket Shows "Disconnected"

**Cause:** Backend not running

**Solution:**
```bash
# Terminal check
lsof -i :8000

# If nothing, start backend:
uv run uvicorn src.application.api.main:app --reload --port 8000
```

---

### Issue: Port Already in Use

**Find what's using the port:**
```bash
lsof -i :4321  # or :8000
```

**Kill the process:**
```bash
kill -9 <PID>
```

---

### Issue: Database Connection Failed

**Restart databases:**
```bash
./manage_services.sh restart-db
```

**Check logs:**
```bash
./manage_services.sh logs neo4j
```

---

## Stopping Services

### Stop Everything
```bash
./manage_services.sh stop-all
```

### Stop Databases Only
```bash
./manage_services.sh stop-db
```

### Stop Backend/Frontend
Just press `Ctrl+C` in their terminal windows.

---

## Useful Commands

```bash
# Check all services
./check_services.sh

# View database logs
./manage_services.sh logs neo4j

# Restart databases
./manage_services.sh restart-db

# Get help
./manage_services.sh help
```

---

## Next Steps

Once everything is running:

1. **Test Chat:**
   - Go to http://localhost:4321/chat/patient:demo
   - Send a message
   - Verify green "Connected" status

2. **Upload DDA:**
   - Go to http://localhost:4321/dda
   - Upload a markdown file with domain model
   - View in Knowledge Graph

3. **Explore Admin:**
   - Go to http://localhost:4321/admin
   - View system metrics
   - Check agent status

---

## Documentation

- **[SERVICES_GUIDE.md](SERVICES_GUIDE.md)** - Complete service documentation
- **[START_FRONTEND.md](START_FRONTEND.md)** - Detailed frontend setup
- **[FIXES_APPLIED.md](FIXES_APPLIED.md)** - Recent fixes and solutions
- **[FRONTEND_COMPLETE.md](FRONTEND_COMPLETE.md)** - Frontend features overview

---

## Port Reference

| Service | Port | URL |
|---------|------|-----|
| Frontend | 4321 | http://localhost:4321 |
| Backend | 8000 | http://localhost:8000/docs |
| Neo4j | 7474 | http://localhost:7474 |
| FalkorDB | 3000 | http://localhost:3000 |
| Redis | 6379 | localhost:6379 |
| Qdrant | 6333 | http://localhost:6333 |

---

## Getting Help

Run these commands to diagnose issues:

```bash
# Check service status
./check_services.sh

# View logs
docker logs neo4j
docker logs redis

# Test WebSocket
uv run python test_websocket.py

# Check backend health
curl http://localhost:8000/docs
```

---

**Ready to go! 🚀**

For detailed information, see [SERVICES_GUIDE.md](SERVICES_GUIDE.md)
