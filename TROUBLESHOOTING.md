# Troubleshooting Guide

Quick solutions for common issues.

---

## 🔴 WebSocket Stream Error

**Error:**
```
[ERROR] [vite] ws proxy socket error:
Error: read ECONNRESET
```

**Cause:** WebSocket connection between Vite proxy and backend is being reset.

**Solutions:**

### 1. Test Backend WebSocket First

```bash
# Test if backend WebSocket works
./test_websocket_connection.sh

# Or manually with wscat
wscat -c ws://localhost:8000/ws/chat/patient:demo/session:test
```

**If this fails:** Backend WebSocket endpoint has an issue.

**If this works:** Proxy configuration issue (continue below).

### 2. Check Backend Logs

Look for errors in the terminal running uvicorn:

```bash
# Should see:
INFO: 127.0.0.1:XXXXX - "GET /ws/chat/... HTTP/1.1" 101

# 101 = success (WebSocket upgrade)
# 500 = backend error
# 400 = bad request
```

### 3. Restart Everything

```bash
# Stop frontend (Ctrl+C)
# Stop backend (Ctrl+C)

# Clear Vite cache
cd frontend && rm -rf node_modules/.vite && cd ..

# Restart backend
uv run uvicorn src.application.api.main:app --reload --port 8000

# Wait 5 seconds, then start frontend
./start_frontend.sh
```

### 4. Check Frontend Browser Console

Open DevTools (F12) → Network → WS tab

- Look for connection to `ws://localhost:4321/ws/chat/...`
- Status should be "101 Switching Protocols"
- If "Connection Reset", check backend is accepting connections

---

## 🔴 Backend Not Running

**Symptom:** Frontend shows "Disconnected" or yellow warning banner

**Solution:**

```bash
# Check if backend is running
curl http://localhost:8000/docs

# If not running, start it
uv run uvicorn src.application.api.main:app --reload --port 8000
```

---

## 🔴 Database Connection Failed

**Symptom:** Backend crashes with database connection errors

**Solution:**

```bash
# Check databases
./check_services.sh

# If not running, start them
docker compose -f docker-compose.memory.yml up -d

# Wait 10 seconds for databases to initialize
sleep 10

# Verify
docker ps
# Should see: neo4j, redis, qdrant containers
```

---

## 🔴 Port Already in Use

**Error:**
```
Error: listen EADDRINUSE: address already in use :::4321
```

**Solution:**

```bash
# Find what's using the port
lsof -i :4321

# Kill the process
kill -9 <PID>

# Or change frontend port in astro.config.mjs
```

---

## 🔴 CSS Not Loading

**Symptom:** Page is white, no styles

**Solution:**

```bash
cd frontend

# Clear Vite cache
rm -rf node_modules/.vite

# Reinstall dependencies
npm install

# Restart dev server
npm run dev
```

---

## 🔴 Docker Compose Not Found

**Error:**
```
docker-compose: command not found
```

**Reason:** You have modern Docker which uses `docker compose` (space, not hyphen)

**Solution:**

All scripts have been updated to use `docker compose`. If you see old commands:

```bash
# Old (legacy)
docker-compose up -d

# New (modern)
docker compose up -d
```

---

## 🔴 Module Not Found

**Error:**
```
ModuleNotFoundError: No module named 'xyz'
```

**Solution:**

```bash
# Backend dependencies
uv sync

# Frontend dependencies
cd frontend && npm install && cd ..
```

---

## 🔴 Vite Build Failed

**Error:** Build errors, TypeScript errors, etc.

**Solution:**

```bash
cd frontend

# Clear everything
rm -rf node_modules/.vite
rm -rf dist

# Reinstall
npm install

# Try again
npm run dev
```

---

## 🟡 Services Check

**Quick health check:**

```bash
./check_services.sh
```

**Expected output:**
```
✅ Neo4j Browser      (Port 7474 ): ✅ Running
✅ Redis             (Port 6379 ): ✅ Running
✅ Qdrant            (Port 6333 ): ✅ Running
✅ Backend API       (Port 8000 ): ✅ Running
✅ Frontend          (Port 4321 ): ✅ Running
```

---

## 🔧 Debug Mode

### Backend Debug Logging

```bash
LOG_LEVEL=DEBUG uv run uvicorn src.application.api.main:app --reload --port 8000
```

### Frontend Network Tab

1. Open browser DevTools (F12)
2. Go to Network tab
3. Filter: `WS` for WebSocket
4. Filter: `Fetch/XHR` for API calls
5. Look for failed requests (red)

### Database Logs

```bash
# Neo4j logs
docker logs neo4j

# Redis logs
docker logs redis

# Qdrant logs
docker logs qdrant
```

---

## 🚨 Nuclear Option (Reset Everything)

If nothing works, reset completely:

```bash
# 1. Stop all services
./manage_services.sh stop-all

# 2. Remove containers and volumes
docker compose -f docker-compose.memory.yml down -v

# 3. Clear Python cache
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true

# 4. Clear frontend cache
cd frontend && rm -rf node_modules/.vite dist && cd ..

# 5. Reinstall dependencies
uv sync
cd frontend && npm install && cd ..

# 6. Start fresh
docker compose -f docker-compose.memory.yml up -d
sleep 10
uv run uvicorn src.application.api.main:app --reload --port 8000 &
./start_frontend.sh
```

---

## 📊 Diagnostic Scripts

| Script | Purpose |
|--------|---------|
| `./check_services.sh` | Check all service status |
| `./test_websocket_connection.sh` | Test WebSocket endpoint |
| `./start_frontend.sh` | Automated frontend startup with checks |
| `./manage_services.sh status` | Detailed service status |

---

## 📚 Detailed Documentation

- [WEBSOCKET_FIX.md](WEBSOCKET_FIX.md) - WebSocket error solutions
- [FIXES_APPLIED.md](FIXES_APPLIED.md) - All frontend fixes
- [SERVICES_GUIDE.md](SERVICES_GUIDE.md) - Complete service reference
- [QUICK_FRONTEND_START.md](QUICK_FRONTEND_START.md) - Quick start guide

---

## 💡 Common Mistakes

1. **Starting frontend before backend** → Use `./start_frontend.sh`
2. **Using old docker-compose** → Use `docker compose` (space)
3. **Not waiting for databases** → Wait 10-15 seconds after starting
4. **Stale Vite cache** → Clear with `rm -rf node_modules/.vite`
5. **Wrong ports** → Frontend: 4321, Backend: 8000

---

## ✅ Quick Checklist

Before starting development:

- [ ] Databases running (`docker ps`)
- [ ] Backend running (`curl http://localhost:8000/docs`)
- [ ] Frontend running (`curl http://localhost:4321`)
- [ ] WebSocket connected (green indicator in chat)
- [ ] No errors in browser console
- [ ] No errors in backend terminal

---

**Still stuck? Check the detailed guides or run diagnostic scripts above.**
