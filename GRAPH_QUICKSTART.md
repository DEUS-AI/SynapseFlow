# Knowledge Graph - Quick Start Guide

## 🚀 Get Started in 30 Seconds

### 1. Start Services

```bash
# Backend
uv run uvicorn src.application.api.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend && npm run dev
```

### 2. Open Graph

Browser: **http://localhost:3000/graph**

---

## 🎨 What You'll See

### Main View

```
┌─────────────────────────────────────────────────────────────┐
│  [Controls]                                                  │
│   Nodes: 50                                                  │
│   Edges: 120                                                 │
│   [Reset View]                                              │
│   ● Perception                                               │
│   ● Semantic                                                 │
│   ● Reasoning                                                │
│   ● Application                                              │
│                                                              │
│                    ●───────●                                 │
│                   ╱         ╲                                │
│                  ●           ●                               │
│                   ╲         ╱                                │
│                    ●───────●                                 │
│                                                              │
│     Interactive Graph                                        │
│     (Zoom, Pan, Drag)                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### With Node Selected

```
┌────────────────────────────────┬──────────────────────────┐
│                                 │  Crohn's Disease         │
│         ●───────●              │  [Diagnosis][Perception] │
│        ╱         ╲             │                          │
│       ●     🔵    ●            │  Properties:             │
│        ╲         ╱             │  • icd10: K50.0         │
│         ●───────●              │  • status: active        │
│      Selected Node             │                          │
│                                 │  Incoming:               │
│                                 │  → Patient (HAS)         │
│                                 │                          │
│                                 │  Outgoing:               │
│                                 │  → Treatment (REQUIRES)  │
└────────────────────────────────┴──────────────────────────┘
```

---

## 🖱️ How to Interact

### Click Node
- **Action**: Click any node
- **Result**: Details panel slides in from right
- **Shows**: Properties, relationships

### Drag Node
- **Action**: Click + hold + move
- **Result**: Node repositions
- **Note**: Other nodes adjust via physics

### Zoom
- **Action**: Scroll wheel up/down
- **Result**: Graph zooms in/out
- **Range**: 0.1x to 4x

### Pan
- **Action**: Click background + drag
- **Result**: View moves
- **Note**: Like Google Maps

### Reset View
- **Action**: Click "Reset View" button
- **Result**: Returns to default position/zoom

### Close Details
- **Action**: Click X or click background
- **Result**: Details panel closes

---

## 🎨 Color Legend

| Color | Layer | Meaning |
|-------|-------|---------|
| 🔵 Blue | Perception | Raw data entities |
| 🟢 Green | Semantic | Concepts and meanings |
| 🟠 Orange | Reasoning | Inferred knowledge |
| 🟣 Purple | Application | Business logic |

---

## 📊 Example Use Cases

### 1. Explore Medical Entities

**Goal**: See all diagnoses and their relationships

**Steps**:
1. Open graph
2. Look for blue nodes (Perception layer)
3. Click a Diagnosis node
4. View relationships in panel

### 2. Trace Data Lineage

**Goal**: Find where data came from

**Steps**:
1. Find a Table or Column node
2. Click it
3. Check "Incoming" relationships
4. Follow the chain back to source

### 3. Understand Domain Model

**Goal**: See how business concepts connect

**Steps**:
1. Look for green nodes (Semantic layer)
2. Click a Concept node
3. View related entities
4. Explore connections

---

## 🔧 Troubleshooting

### Empty Graph

**Symptom**: "No graph data available" message

**Causes**:
- No data in Neo4j
- Backend not connected

**Fix**:
```bash
# Load sample data
uv run multi_agent_system model --dda-path specs/example.md
```

### Graph Won't Load

**Symptom**: Infinite loading spinner

**Causes**:
- Backend not running
- API endpoint error

**Fix**:
```bash
# Check backend is running
curl http://localhost:8000/health

# Check API endpoint
curl http://localhost:8000/api/graph/data?limit=10
```

### Nodes Overlapping

**Symptom**: Nodes on top of each other

**Cause**: Physics simulation needs time

**Fix**: Wait 2-3 seconds for simulation to settle

### Can't See Node Labels

**Symptom**: Labels cut off or missing

**Cause**: Zoom level too low

**Fix**: Zoom in using scroll wheel

---

## 🎯 Pro Tips

### Tip 1: Start Small
- Use `?limit=20` in URL for faster loading
- Explore a subset first
- Then increase limit

### Tip 2: Follow the Colors
- Blue → Raw data
- Green → Concepts
- Orange → Rules
- Purple → Actions

### Tip 3: Use Details Panel
- Don't just look at the graph
- Click nodes to see full context
- Properties reveal important info

### Tip 4: Drag to Organize
- Create your own layout
- Group related nodes
- Pin important nodes

### Tip 5: Reset Often
- Lost? Click "Reset View"
- Returns to centered view
- Fresh perspective

---

## 🚀 Advanced Features (Coming Soon)

- [ ] Search nodes by name
- [ ] Filter by layer or type
- [ ] Export graph as image
- [ ] Hierarchical layout
- [ ] Mini-map for navigation
- [ ] Time-based playback

---

## 📚 Learn More

- **Phase 3C Docs**: [PHASE_3C_COMPLETE.md](PHASE_3C_COMPLETE.md)
- **API Reference**: http://localhost:8000/docs
- **D3.js Docs**: https://d3js.org

---

**Happy Exploring!** 🎉

The knowledge graph brings your data to life. See connections, discover patterns, and understand your domain like never before.
