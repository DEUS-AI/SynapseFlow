# WebSocket Stream Error Fix

**Issue:** `ws proxy socket error: Error: read ECONNRESET`

**Date:** 2026-01-23

---

## Problem

WebSocket proxy is experiencing connection resets between Vite dev server and FastAPI backend.

### Error Message

```
[ERROR] [vite] ws proxy socket error:
Error: read ECONNRESET
    at TCP.onStreamRead (node:internal/stream_base_commons:216:20)
```

---

## Root Cause

The WebSocket connection between Vite's proxy and the FastAPI backend is being reset. This can happen due to:

1. **Backend not accepting WebSocket connections properly**
2. **Missing CORS/headers for WebSocket upgrade**
3. **Connection timeout or keep-alive issues**
4. **Backend dependency injection failing**

---

## Solutions Applied

### 1. Enhanced Vite Proxy Configuration

**File:** `frontend/astro.config.mjs`

**Changes:**
```javascript
'/ws': {
  target: 'ws://localhost:8000',
  ws: true,
  changeOrigin: true,
  secure: false,
  rewrite: (path) => path,
  configure: (proxy, options) => {
    proxy.on('error', (err, req, res) => {
      console.log('WebSocket proxy error:', err.message);
    });
    proxy.on('proxyReq', (proxyReq, req, res) => {
      console.log('Proxying WebSocket request:', req.url);
    });
    proxy.on('open', (proxySocket) => {
      console.log('WebSocket proxy connection opened');
      proxySocket.on('error', (err) => {
        console.error('WebSocket proxy socket error:', err.message);
      });
    });
  },
}
```

**Benefits:**
- Better error logging
- Connection lifecycle tracking
- Easier debugging

### 2. Updated Docker Compose Commands

**Changed:** `docker-compose` → `docker compose`

**Files Updated:**
- `start_frontend.sh`
- `check_services.sh`
- `manage_services.sh`
- All documentation files

**Reason:** `docker-compose` is legacy, modern Docker uses `docker compose` (space, not hyphen)

---

## Backend Verification Checklist

### 1. Check WebSocket Endpoint Exists

```bash
curl http://localhost:8000/docs
# Look for /ws/chat/{patient_id}/{session_id}
```

### 2. Verify Backend Dependencies

The backend needs the chat service dependency. Check if this is defined:

**File:** `src/application/api/main.py`

```python
from src.application.services.intelligent_chat_service import IntelligentChatService

def get_chat_service() -> IntelligentChatService:
    # Should return initialized chat service
    pass

@app.websocket("/ws/chat/{patient_id}/{session_id}")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    patient_id: str,
    session_id: str,
    chat_service: IntelligentChatService = Depends(get_chat_service)
):
    await websocket.accept()
    # ... rest of implementation
```

### 3. Test WebSocket Connection Directly

**Without Frontend (Direct Test):**

```bash
# Install wscat if needed
npm install -g wscat

# Test connection
wscat -c ws://localhost:8000/ws/chat/patient:demo/session:test

# You should see:
# Connected (press CTRL+C to quit)

# Send a test message
> {"message": "Hello"}

# Expect response
< {"type":"status","status":"thinking"}
< {"type":"message","role":"assistant","content":"..."}
```

If this fails, the backend WebSocket implementation needs fixing.

---

## Debugging Steps

### 1. Check Backend Logs

```bash
# In the terminal running uvicorn, look for:
INFO:     127.0.0.1:XXXXX - "GET /ws/chat/patient:demo/session:test HTTP/1.1" 101
```

`101` status code = WebSocket upgrade successful

If you see `500` or `400`, there's a backend error.

### 2. Check Frontend Browser Console

```javascript
// Open DevTools → Network → WS tab
// Look for connection to: ws://localhost:4321/ws/chat/...

// Check status:
// - 101 Switching Protocols = success
// - 400/500 = backend error
// - Connection reset = this issue
```

### 3. Enable Verbose Logging

**Backend:**
```bash
# Start with debug logging
LOG_LEVEL=DEBUG uv run uvicorn src.application.api.main:app --reload --port 8000
```

**Frontend:**
```bash
# Vite already logs proxy events with new config
cd frontend && npm run dev
```

---

## Temporary Workaround

If the WebSocket proxy continues to fail, you can bypass it temporarily:

### Option 1: Connect Directly to Backend

**File:** `frontend/src/components/chat/ChatInterface.tsx`

```typescript
// Temporarily bypass proxy (for debugging only)
const wsURL = typeof window !== 'undefined'
  ? `ws://localhost:8000/ws/chat/${patientId}/${sessionId}` // Direct connection
  : '';
```

**Note:** This only works in development. Remove before production.

### Option 2: Use Polling Instead

If WebSocket is too problematic, temporarily use polling:

```typescript
// Poll for messages every 3 seconds
useEffect(() => {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/chat/${sessionId}/messages`);
    const messages = await response.json();
    setMessages(messages);
  }, 3000);

  return () => clearInterval(interval);
}, [sessionId]);
```

**Note:** This is inefficient but works as a fallback.

---

## Production Considerations

### 1. WebSocket Keep-Alive

Add ping/pong to prevent timeouts:

**Backend:**
```python
@app.websocket("/ws/chat/{patient_id}/{session_id}")
async def chat_websocket_endpoint(websocket: WebSocket, ...):
    await websocket.accept()

    # Send periodic pings
    async def send_ping():
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})

    ping_task = asyncio.create_task(send_ping())

    try:
        # ... handle messages
        pass
    finally:
        ping_task.cancel()
```

**Frontend:**
```typescript
// Respond to pings
if (data.type === 'ping') {
  sendMessage({ type: 'pong' });
}
```

### 2. Reverse Proxy Configuration

For Nginx in production:

```nginx
location /ws/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    # Prevent timeouts
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
}
```

---

## Common Fixes

### Fix 1: Backend Not Handling WebSocket Properly

**Symptom:** Connection resets immediately

**Solution:** Check backend accepts connection:

```python
@app.websocket("/ws/chat/{patient_id}/{session_id}")
async def chat_websocket_endpoint(websocket: WebSocket, ...):
    await websocket.accept()  # ← This is critical!

    try:
        while True:
            data = await websocket.receive_json()
            # Process message
            await websocket.send_json(response)
    except WebSocketDisconnect:
        logger.info(f"Client disconnected")
```

### Fix 2: CORS Issues

**Symptom:** Connection refused

**Solution:** Add WebSocket CORS:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Fix 3: Dependency Injection Failing

**Symptom:** 500 error when connecting

**Solution:** Ensure dependencies are injectable:

```python
# Make sure this is defined and works
def get_chat_service() -> IntelligentChatService:
    return IntelligentChatService(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        # ... other dependencies
    )
```

---

## Testing the Fix

### 1. Start Backend

```bash
uv run uvicorn src.application.api.main:app --reload --port 8000
```

### 2. Test WebSocket Directly

```bash
wscat -c ws://localhost:8000/ws/chat/patient:demo/session:test
```

**Expected:** Connection succeeds, you can send/receive messages

### 3. Start Frontend

```bash
./start_frontend.sh
```

### 4. Test in Browser

1. Open http://localhost:4321/chat/patient:demo
2. Check status indicator:
   - ✅ Green "Connected" = Success
   - ❌ Red "Disconnected" = Still broken
3. Try sending a message
4. Check browser DevTools → Network → WS tab

---

## Next Steps

1. **Verify backend WebSocket endpoint is working:**
   ```bash
   wscat -c ws://localhost:8000/ws/chat/patient:demo/session:test
   ```

2. **Check backend logs for errors**

3. **If still failing, try direct connection (bypass proxy) for debugging**

4. **Check if backend dependencies are properly initialized**

---

## References

- [Vite WebSocket Proxy Docs](https://vitejs.dev/config/server-options.html#server-proxy)
- [FastAPI WebSocket Docs](https://fastapi.tiangolo.com/advanced/websockets/)
- [WebSocket Connection States](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/readyState)

---

**Summary:**
- Enhanced proxy configuration with better error handling
- Updated all docker-compose → docker compose
- Added debugging tools and logs
- Provided temporary workarounds if needed
- Created testing checklist

**If issue persists, the backend WebSocket endpoint needs verification/fixing.**
