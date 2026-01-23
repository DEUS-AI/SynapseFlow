# Restart and Test Instructions

**Date:** 2026-01-23
**Status:** Ready to test after backend restart

---

## What Was Fixed

✅ **Installed WebSocket Libraries**
- `websockets` 16.0
- `wsproto` 1.3.2

These libraries were missing from the backend, causing 404 errors on the WebSocket endpoint.

---

## Quick Restart Procedure

### 1. Restart Backend (REQUIRED)

```bash
# Stop current backend (Ctrl+C in the terminal running uvicorn)

# Start with WebSocket support
uv run uvicorn src.application.api.main:app --reload --port 8000
```

**What to Look For:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 2. Start Frontend (New Terminal)

```bash
./start_frontend.sh
```

**Expected Output:**
```
================================================
✓ All prerequisites met!
================================================

Starting frontend on http://localhost:4321
```

---

## Test the WebSocket Connection

### Option 1: Browser Test (Recommended)

1. Navigate to: <http://localhost:4321/chat/patient:demo>

2. **Check Connection Status** (top right):
   - ✅ **Green "Connected"** = Success!
   - ❌ **Red "Disconnected"** = Check backend logs

3. **Send Test Message:**
   ```
   What medications am I taking?
   ```

4. **Verify Response:**
   - "Thinking..." indicator appears
   - Assistant response appears within 2-3 seconds
   - Confidence score displays at bottom
   - Patient context sidebar loads on right

### Option 2: Direct WebSocket Test

```bash
# Install wscat if needed
npm install -g wscat

# Test connection
wscat -c ws://localhost:8000/ws/chat/patient:demo/session:test

# Send message
> {"message": "Hello"}

# Expected response:
< {"type":"status","status":"thinking"}
< {"type":"message","role":"assistant","content":"...","confidence":0.9}
```

---

## Expected Backend Logs (Success)

After frontend connects, you should see:

```
INFO:     127.0.0.1:XXXXX - "WebSocket /ws/chat/patient:demo/session:XXXXX" [accepted]
INFO:     Client patient:demo:session:XXXXX connected. Total connections: 1
```

**NOT:**
```
WARNING: No supported WebSocket library detected
INFO: ... 404 Not Found
```

---

## Troubleshooting

### Still Getting 404?

```bash
# Verify libraries are installed
uv pip list | grep -E "(websockets|wsproto)"

# Should show:
# websockets                16.0
# wsproto                   1.3.2

# If not shown, reinstall:
uv pip install 'websockets' 'wsproto'
```

### Frontend Shows "Disconnected"?

1. **Check backend is running:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"healthy"}
   ```

2. **Check backend logs** for errors

3. **Check frontend console** (F12 → Console) for WebSocket errors

### Connection Drops Immediately?

Check backend logs for errors during connection. Common issues:
- Missing dependencies in chat service
- Database not running
- Invalid patient_id format

---

## Quick Service Check

```bash
./check_services.sh
```

**Expected:**
```
✅ Neo4j Browser      (Port 7474 ): ✅ Running
✅ Redis             (Port 6379 ): ✅ Running
✅ Qdrant            (Port 6333 ): ✅ Running
✅ Backend API       (Port 8000 ): ✅ Running
✅ Frontend          (Port 4321 ): ✅ Running
```

---

## Complete Test Checklist

- [ ] Backend restarted with `uv run uvicorn ...`
- [ ] Frontend started with `./start_frontend.sh`
- [ ] Navigate to <http://localhost:4321/chat/patient:demo>
- [ ] Status shows "Connected" (green)
- [ ] Patient context sidebar loads on right
- [ ] Send test message
- [ ] "Thinking..." indicator appears
- [ ] Assistant response appears
- [ ] Confidence score displays
- [ ] No errors in browser console (F12)
- [ ] Backend logs show "Client connected"

---

## All 7 Issues Now Resolved

1. ✅ GetStaticPathsRequired error
2. ✅ Port conflict (3000 → 4321)
3. ✅ CSS classes missing
4. ✅ SSR window error
5. ✅ WebSocket disconnected
6. ✅ Vite proxy errors
7. ✅ **WebSocket libraries installed**

---

**Ready to test!** 🚀

After confirming WebSocket connection works, see `FIXES_APPLIED.md` for complete documentation.
