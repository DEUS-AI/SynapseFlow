# Quick Start: Testing the Frontend

This guide will get you up and running with the new frontend in under 5 minutes.

## Prerequisites

✅ Backend services running (Neo4j, Redis, Qdrant)
✅ FastAPI application ready
✅ Node.js 20+ installed

## Step 1: Start Backend Services

```bash
# Start memory services
docker-compose -f docker-compose.memory.yml up -d

# Verify services are running
docker ps
# Should see: neo4j, redis, qdrant containers
```

## Step 2: Start FastAPI Backend

```bash
# From project root
uv run uvicorn src.application.api.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

## Step 3: Create Test Patient (Optional)

If `patient:demo` doesn't exist yet:

```bash
# In a new terminal
uv run python demo_patient_memory.py
```

This creates a test patient with:
- Diagnosis: Crohn's Disease
- Medication: Humira
- Allergy: Ibuprofen (severe)

## Step 4: Start Frontend Dev Server

```bash
cd frontend
npm run dev
```

Expected output:
```
  🚀  astro  v4.15.11 started in 50ms

  ┃ Local    http://localhost:3000/
  ┃ Network  use --host to expose
```

## Step 5: Open Browser

Navigate to: **http://localhost:3000**

You should see the home page with 4 feature cards.

## Step 6: Test Patient Chat

Click on "Patient Chat" card, or navigate to:

**http://localhost:3000/chat/patient:demo**

### What You Should See

1. **Header**
   - "Medical Assistant" title
   - Green dot + "Connected" status

2. **Left Side (Chat Area)**
   - Empty message list
   - Input box at bottom with "Ask a medical question..." placeholder
   - Send button (arrow icon)

3. **Right Side (Patient Context Sidebar)**
   - "Patient Context" header
   - **Allergies** section (red) - "Ibuprofen"
   - **Diagnoses** section - "Crohn's Disease (K50.0)"
   - **Current Medications** - "Humira 40mg every 2 weeks"

## Step 7: Send a Test Message

Type in the input box:
```
What medications am I taking?
```

Press Enter or click Send button.

### Expected Behavior

1. Message appears on right side (blue bubble)
2. "Thinking..." indicator appears on left side
3. After 2-3 seconds, assistant response appears (white bubble)
4. Response includes:
   - Text answer mentioning "Humira"
   - Confidence bar (e.g., 85%)
   - Sources list
   - Related concepts (blue tags)

## Step 8: Test Safety Warning

Type this message:
```
Can I take ibuprofen for my headache?
```

### Expected Behavior

1. Red alert banner appears at top of chat
2. Banner says "Safety Warning"
3. Lists contraindication detected: "Patient has allergy to Ibuprofen"
4. Assistant response warns against taking ibuprofen
5. Click X to dismiss the banner

## Step 9: Check Browser Console

Open Developer Tools (F12) → Console tab

You should see:
```
WebSocket connected
```

No errors should be present.

## Troubleshooting

### Issue: "Disconnected" (Red Dot)

**Cause**: Backend not running or WebSocket endpoint unavailable

**Fix**:
```bash
# Check FastAPI is running on port 8000
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

### Issue: Patient Context Not Loading

**Cause**: Patient doesn't exist in database

**Fix**:
```bash
# Create test patient
uv run python demo_patient_memory.py
```

### Issue: "Failed to load patient context"

**Cause**: Patient Memory Service not initialized

**Fix**: Check FastAPI logs for errors during startup. Ensure:
- Neo4j is running
- Redis is running
- Environment variables are set (.env file)

### Issue: WebSocket Connection Failed

**Cause**: Port 8000 not accessible or CORS issue

**Fix**:
```bash
# Verify FastAPI is listening
lsof -i :8000

# Check CORS settings in src/application/api/main.py
# Should allow all origins in dev mode
```

### Issue: Frontend Won't Start

**Cause**: Dependencies not installed

**Fix**:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

## Testing Checklist

- [ ] Home page loads at http://localhost:3000
- [ ] Four feature cards display
- [ ] Clicking "Patient Chat" navigates to chat page
- [ ] Chat page shows "Connected" status
- [ ] Patient context sidebar loads with data
- [ ] Can send a message
- [ ] "Thinking..." indicator appears
- [ ] Assistant response appears
- [ ] Confidence score displays
- [ ] Safety warning appears for contraindicated medication
- [ ] Can dismiss safety warning
- [ ] Messages auto-scroll to bottom
- [ ] Input disabled when disconnected

## Success! 🎉

If all checks pass, your frontend is working perfectly!

## Next Steps

1. **Explore the Code**
   - [frontend/src/components/chat/ChatInterface.tsx](frontend/src/components/chat/ChatInterface.tsx) - Main chat component
   - [src/application/api/main.py](src/application/api/main.py) - WebSocket endpoint

2. **Customize**
   - Change colors in [frontend/tailwind.config.mjs](frontend/tailwind.config.mjs)
   - Add more UI components to [frontend/src/components/ui/](frontend/src/components/ui/)

3. **Build More Features**
   - Knowledge Graph Visualization
   - Admin Dashboard
   - DDA Management

## Getting Help

- Check [PHASE_3_STATUS.md](PHASE_3_STATUS.md) for detailed status
- Review [frontend/README.md](frontend/README.md) for frontend docs
- Check [CURRENT_STATUS.md](CURRENT_STATUS.md) for overall system status

**Happy Testing!** 🚀
