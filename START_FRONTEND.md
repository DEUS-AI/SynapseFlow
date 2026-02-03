# Starting the Frontend Development Environment

**Quick Start Guide** for running the Medical Knowledge Management System frontend.

---

## 🚀 Automated Startup (Recommended)

**Use the automated startup script that checks all prerequisites:**

```bash
./start_frontend.sh
```

This script will:
- ✅ Check if backend API is running (port 8000)
- ✅ Check if Neo4j is running (port 7474)
- ✅ Check if Redis is running (port 6379)
- ✅ Check if Qdrant is running (port 6333)
- ✅ Install npm dependencies if needed
- ✅ Clear Vite cache
- ✅ Start frontend development server

**If any service is missing, it will show you exactly what to start.**

---

## 📋 Manual Startup (Step-by-Step)

If you prefer to start services manually:

### 1. Database Services (Docker)

```bash
# Check if services are running
docker ps

# If not running, start them:
docker-compose -f docker-compose.memory.yml up -d

# Verify all services
./check_services.sh
```

### 2. Backend API

```bash
# Start FastAPI backend
uv run uvicorn src.application.api.main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**Verify backend:**
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health (if endpoint exists)

---

### Terminal 2: Start Frontend Dev Server

```bash
# From project root
cd /Users/pformoso/Documents/code/Notebooks/frontend

# Start Astro dev server
npm run dev
```

**Expected output:**
```
 astro  v4.x.x ready in XXX ms

┃ Local    http://localhost:4321/
┃ Network  use --host to expose

watching for file changes...
```

**Verify frontend is running:**
- Home page: http://localhost:4321

---

## Verify Everything Works

### 1. Check Home Page
Navigate to: http://localhost:4321

**Expected:** 4 feature cards (Patient Chat, Knowledge Graph, Admin Dashboard, DDA Management)

---

### 2. Test WebSocket Connection (Patient Chat)
Navigate to: http://localhost:4321/chat/patient:demo

**Expected:**
- ✅ Green "Connected" status indicator in top right
- Chat input enabled
- Patient context sidebar loads (may be empty initially)

**If Disconnected:**
1. Check backend terminal - should show WebSocket connection log
2. Check browser console (F12) for errors
3. Verify URL format: `ws://localhost:4321/ws/chat/patient:demo/session:...`
4. Run test script: `uv run python test_websocket.py`

---

### 3. Test Knowledge Graph
Navigate to: http://localhost:4321/graph

**Expected:**
- If database empty: "No graph data available" message ✅ (correct)
- If database has data: Interactive D3 graph with nodes and edges

**To populate test data:**
```bash
# Option 1: Via Neo4j Browser (http://localhost:7474)
CREATE (e1:Entity {id: 'test1', name: 'Test Entity 1', layer: 'semantic'})
CREATE (e2:Entity {id: 'test2', name: 'Test Entity 2', layer: 'perception'})
CREATE (e1)-[:RELATES_TO {label: 'relates to'}]->(e2)

# Option 2: Upload DDA via UI
# Go to http://localhost:4321/dda and upload a markdown file
```

---

### 4. Test Admin Dashboard
Navigate to: http://localhost:4321/admin

**Expected:**
- System metrics display (queries, sessions, patients)
- Agent status cards
- "View Patients" button

---

### 5. Test DDA Management
Navigate to: http://localhost:4321/dda

**Expected:**
- File upload section
- Data catalog browser (empty initially)

---

## Troubleshooting

### Issue: "WebSocket Disconnected"

**Symptoms:** Red indicator in chat interface, "Disconnected" status

**Solutions:**

1. **Backend not running:**
   ```bash
   # Check if port 8000 is in use
   lsof -i :8000

   # If nothing, start backend:
   uv run uvicorn src.application.api.main:app --reload --port 8000
   ```

2. **WebSocket proxy not working:**
   - Check `frontend/astro.config.mjs` has WebSocket proxy configured (line 20-23)
   - Restart frontend dev server: `Ctrl+C` then `npm run dev`

3. **CORS issues:**
   - Check backend terminal for CORS errors
   - Verify backend allows WebSocket connections from localhost:4321

4. **Test WebSocket directly:**
   ```bash
   uv run python test_websocket.py
   ```

---

### Issue: "bg-background class does not exist"

**Solution:** Already fixed! Tailwind config now defines the colors directly.

If you see this error:
1. Stop frontend dev server (Ctrl+C)
2. Clear cache: `rm -rf frontend/node_modules/.vite`
3. Restart: `npm run dev`

---

### Issue: Port 4321 already in use

**Solution:**
```bash
# Find process using port 4321
lsof -i :4321

# Kill process (replace PID with actual process ID)
kill -9 <PID>

# Or change port in frontend/astro.config.mjs
```

---

### Issue: Port 3000 conflict (FalkorDB)

**Solution:** Already fixed! Frontend now uses port 4321.

---

### Issue: API calls fail (404/500 errors)

**Check:**
1. Backend is running: http://localhost:8000/docs
2. Vite proxy is configured in `astro.config.mjs`
3. Browser console (F12) shows actual error
4. Backend terminal shows request logs

**Debug API calls:**
```bash
# Test graph endpoint
curl http://localhost:8000/api/graph/data?limit=10

# Test patient context
curl http://localhost:8000/api/patients/patient:demo/context
```

---

## Port Configuration Summary

| Service | Port | URL |
|---------|------|-----|
| **Frontend** | 4321 | http://localhost:4321 |
| **Backend API** | 8000 | http://localhost:8000 |
| **FalkorDB** | 3000 | http://localhost:3000 |
| **Neo4j Browser** | 7474 | http://localhost:7474 |
| **Neo4j Bolt** | 7687 | bolt://localhost:7687 |
| **Redis** | 6379 | localhost:6379 |

---

## Quick Commands Reference

```bash
# Start backend
uv run uvicorn src.application.api.main:app --reload --port 8000

# Start frontend
cd frontend && npm run dev

# Test WebSocket
uv run python test_websocket.py

# Run E2E tests
cd frontend && npm test

# Build for production
cd frontend && npm run build

# Preview production build
cd frontend && npm run preview
```

---

## Development Workflow

### Making Frontend Changes

1. Edit files in `frontend/src/`
2. Changes auto-reload (Astro HMR)
3. Check browser console for errors (F12)
4. Check terminal for build errors

### Making Backend Changes

1. Edit files in `src/application/api/`
2. Backend auto-reloads (uvicorn --reload)
3. Check terminal for errors
4. Test endpoints: http://localhost:8000/docs

### Testing WebSocket Changes

1. Make changes to WebSocket handlers
2. Backend auto-reloads
3. Frontend reconnects automatically
4. Check both terminals for logs
5. Use browser DevTools > Network > WS to see WebSocket messages

---

## Success Checklist

Before starting development, verify:

- ✅ Neo4j is running (http://localhost:7474)
- ✅ Redis is running (`redis-cli ping` returns PONG)
- ✅ Backend is running (http://localhost:8000/docs loads)
- ✅ Frontend is running (http://localhost:4321 loads)
- ✅ WebSocket connects (green indicator in chat)
- ✅ No console errors in browser (F12)

---

## Next Steps

Once everything is running:

1. **Upload a DDA specification:**
   - Go to http://localhost:4321/dda
   - Upload a markdown file
   - View results in Knowledge Graph

2. **Test patient chat:**
   - Go to http://localhost:4321/chat/patient:demo
   - Send a message
   - Verify response appears

3. **Explore admin dashboard:**
   - Go to http://localhost:4321/admin
   - View system metrics
   - Check agent status

4. **Run E2E tests:**
   ```bash
   cd frontend
   npm test
   ```

---

## Getting Help

If you encounter issues:

1. Check both terminal outputs (backend + frontend)
2. Check browser console (F12 > Console)
3. Check Network tab (F12 > Network) for failed requests
4. Review error messages carefully
5. Check the troubleshooting section above

Common log locations:
- Backend logs: Terminal 1
- Frontend build logs: Terminal 2
- Browser logs: DevTools Console (F12)
- WebSocket logs: DevTools Network > WS (F12)

---

**Happy coding! 🚀**
