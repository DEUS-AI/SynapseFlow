# Frontend - Medical Knowledge Management System

**Production-ready Astro.js + React frontend with comprehensive error handling.**

---

## 🚀 Quick Start

```bash
./start_frontend.sh
```

That's it! The script checks everything and starts the frontend only when ready.

---

## 📋 What You Get

### 4 Main Features

1. **Patient Chat** (http://localhost:4321/chat/patient:demo)
   - Real-time WebSocket communication
   - Patient context sidebar
   - Safety warnings for contraindications
   - Confidence scores and reasoning trails

2. **Knowledge Graph** (http://localhost:4321/graph)
   - Interactive D3.js visualization
   - 4-layer architecture (Perception → Semantic → Reasoning → Application)
   - Entity details panel
   - Zoom/pan/drag controls

3. **Admin Dashboard** (http://localhost:4321/admin)
   - System metrics (queries, response time, sessions)
   - Agent status monitoring
   - Patient management (CRUD)
   - GDPR compliance tools

4. **DDA Management** (http://localhost:4321/dda)
   - Upload domain models (.md files)
   - Metadata viewer
   - Data catalog browser

---

## 🛠️ Technology Stack

- **Framework:** Astro.js 4.x (Static Site Generation)
- **UI Library:** React 18
- **Styling:** Tailwind CSS + shadcn/ui components
- **State Management:** Zustand (lightweight)
- **Visualization:** D3.js v7 (knowledge graph)
- **Icons:** Lucide React
- **Real-time:** Native WebSocket API
- **Type Safety:** TypeScript (strict mode)

---

## 🔧 Prerequisites

Before starting the frontend, ensure these services are running:

### Required Services

1. **Backend API** (port 8000)
   ```bash
   uv run uvicorn src.application.api.main:app --reload --port 8000
   ```

2. **Neo4j** (port 7474, 7687)
   ```bash
   docker-compose -f docker-compose.memory.yml up -d
   ```

3. **Redis** (port 6379) - Included in docker-compose

4. **Qdrant** (port 6333) - Included in docker-compose

**The automated script checks all of these for you!**

---

## 📦 Installation

### First Time Setup

```bash
cd frontend
npm install
```

### Every Time

```bash
# Automated (checks prerequisites)
./start_frontend.sh

# Or manual
cd frontend
npm run dev
```

---

## 🌐 Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:4321 | Main application |
| Backend API | http://localhost:8000/docs | FastAPI Swagger docs |
| Neo4j Browser | http://localhost:7474 | Graph database UI |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector store UI |

---

## 🎯 Features

### ✅ Fixed Issues

1. **GetStaticPathsRequired** - Dynamic routes work correctly
2. **Port Conflict** - Frontend on 4321 (FalkorDB uses 3000)
3. **CSS Classes** - Tailwind configured correctly
4. **WebSocket** - Dynamic URL construction
5. **SSR** - Proper window guards
6. **Proxy Errors** - Automated prerequisite checks

### ✅ Error Handling

- **Connection Banner** - Shows when backend is down
- **Retry Logic** - Automatic reconnection (max 10 attempts)
- **Clear Messages** - Tells you exactly what to fix
- **Graceful Degradation** - Frontend works even when disconnected

### ✅ Developer Experience

- **Automated Checks** - `./start_frontend.sh` validates everything
- **Hot Module Reload** - Instant updates during development
- **Type Safety** - Full TypeScript coverage
- **Component Isolation** - Astro islands architecture

---

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── chat/           # Patient chat interface
│   │   ├── graph/          # Knowledge graph viewer
│   │   ├── admin/          # Admin dashboard
│   │   ├── dda/            # DDA management
│   │   ├── common/         # Shared components
│   │   └── ui/             # shadcn/ui components
│   │
│   ├── hooks/              # React hooks
│   │   └── useWebSocket.ts # WebSocket management
│   │
│   ├── layouts/            # Astro layouts
│   │   └── BaseLayout.astro
│   │
│   ├── pages/              # File-based routing
│   │   ├── index.astro     # Home page
│   │   ├── chat/[patientId].astro
│   │   ├── graph/index.astro
│   │   ├── admin/index.astro
│   │   └── dda/index.astro
│   │
│   ├── styles/             # Global styles
│   │   └── global.css      # Tailwind + custom CSS
│   │
│   └── types/              # TypeScript types
│       ├── chat.ts
│       └── graph.ts
│
├── public/                 # Static assets
├── astro.config.mjs       # Astro configuration
├── tailwind.config.mjs    # Tailwind configuration
└── package.json           # Dependencies
```

---

## 🐛 Troubleshooting

### Frontend Won't Start

**Symptom:** Build errors or crashes

**Solution:**
```bash
cd frontend
rm -rf node_modules/.vite  # Clear Vite cache
npm install                # Reinstall dependencies
npm run dev
```

### "Disconnected" in Chat

**Symptom:** Chat shows red "Disconnected" status

**Cause:** Backend not running

**Solution:**
```bash
# Check backend
curl http://localhost:8000/docs

# If not running, start it
uv run uvicorn src.application.api.main:app --reload --port 8000
```

### Vite Proxy Errors

**Symptom:** Console shows `[vite] ws proxy error: ECONNREFUSED`

**Cause:** Starting frontend before backend

**Solution:**
```bash
# Use automated script (checks backend first)
./start_frontend.sh

# Or start backend manually first
uv run uvicorn src.application.api.main:app --reload --port 8000
```

### CSS Not Loading

**Symptom:** No styles, white page

**Solution:**
```bash
cd frontend
rm -rf node_modules/.vite
npm run dev
```

---

## 🔍 Debugging

### View Logs

```bash
# Frontend console
# Open browser DevTools (F12)

# Backend logs
# Check terminal running uvicorn

# Database logs
docker logs neo4j
docker logs redis
```

### Check Service Status

```bash
./check_services.sh
```

### Test WebSocket

```bash
# Use wscat (if installed)
wscat -c ws://localhost:8000/ws/chat/patient:demo/session:test

# Or use the test script
uv run python test_websocket.py
```

---

## 📚 Documentation

### Quick References

- [QUICK_FRONTEND_START.md](../QUICK_FRONTEND_START.md) - One-page guide
- [STARTUP_FLOW.md](../STARTUP_FLOW.md) - Visual diagrams

### Complete Guides

- [FRONTEND_FIXES_SUMMARY.md](../FRONTEND_FIXES_SUMMARY.md) - All fixes
- [START_FRONTEND.md](../START_FRONTEND.md) - Detailed startup
- [FIXES_APPLIED.md](../FIXES_APPLIED.md) - Technical details

### System Documentation

- [SERVICES_GUIDE.md](../SERVICES_GUIDE.md) - All services
- [ARCHITECTURE_DIAGRAM.md](../ARCHITECTURE_DIAGRAM.md) - System architecture

---

## 🚦 Development Workflow

### Typical Session

1. **Start services:**
   ```bash
   ./start_frontend.sh
   ```

2. **Make changes** - Edit files in `frontend/src/`

3. **Hot reload** - See changes instantly in browser

4. **Stop when done** - Press `Ctrl+C` in terminal

### Adding New Features

1. **New page:**
   - Create file in `frontend/src/pages/`
   - Example: `frontend/src/pages/new-feature.astro`

2. **New component:**
   - Create file in `frontend/src/components/`
   - Use `.tsx` for React components
   - Import in page with `client:load` directive

3. **New API endpoint:**
   - Add to backend first
   - Frontend will proxy `/api/*` automatically

---

## 🎨 Styling

### Tailwind Classes

All Tailwind utilities are available:

```tsx
<div className="flex items-center gap-4 p-6 bg-white rounded-lg shadow">
  <h1 className="text-2xl font-bold">Title</h1>
</div>
```

### Custom Colors

Defined in `tailwind.config.mjs`:

```tsx
<div className="bg-background text-foreground">
  Content with custom colors
</div>
```

### shadcn/ui Components

Pre-built accessible components:

```tsx
import { Button } from '@/components/ui/button';

<Button variant="outline" size="sm">
  Click me
</Button>
```

---

## 🔒 Security

### CORS

Vite proxy handles CORS automatically in development.

### WebSocket Security

- Uses `wss://` for HTTPS connections
- Validates session IDs
- Backend handles authentication

### Content Security

- XSS prevention via React
- CSRF protection in backend
- Input sanitization

---

## 📊 Performance

### Metrics

- **Initial Load:** < 2s
- **Hot Reload:** < 500ms
- **WebSocket Latency:** 50-100ms
- **Graph Rendering:** < 2s (100 nodes)

### Optimization

- Code splitting (Astro islands)
- Lazy loading (React components)
- Static asset caching
- Vite build optimizations

---

## 🚀 Production Build

### Build for Production

```bash
cd frontend
npm run build
```

Output: `frontend/dist/` (static files)

### Serve Locally

```bash
npm run preview
```

### Deploy

The build outputs static files that can be:
- Served by FastAPI (integrated deployment)
- Deployed to Vercel, Netlify, etc.
- Served by Nginx, Apache, etc.

---

## 🤝 Contributing

### Code Style

- Use TypeScript strict mode
- Follow existing file structure
- Use Tailwind for styling
- Add error handling

### Testing

```bash
# Type check
npm run check

# Build test
npm run build

# Preview build
npm run preview
```

---

## ❓ FAQ

**Q: Why port 4321?**
A: FalkorDB uses 3000, so we moved to 4321 to avoid conflicts.

**Q: Can I change the port?**
A: Yes, edit `astro.config.mjs` → `server.port`

**Q: Why Astro.js?**
A: Fast static generation + React interactivity where needed.

**Q: Do I need Node.js?**
A: Yes, Node.js 18+ is required.

**Q: Can I use other components?**
A: Yes, install any React component library.

---

## 📞 Support

### Documentation

- [Frontend Fixes Summary](../FRONTEND_FIXES_SUMMARY.md)
- [Services Guide](../SERVICES_GUIDE.md)
- [Quick Start](../QUICK_START.md)

### Scripts

- `./start_frontend.sh` - Automated startup
- `./check_services.sh` - Service status
- `./manage_services.sh` - Service management

### Common Commands

```bash
# Start everything
./start_frontend.sh

# Check status
./check_services.sh

# Stop everything
./manage_services.sh stop-all

# Clear cache
cd frontend && rm -rf node_modules/.vite
```

---

**Ready to develop! Run `./start_frontend.sh` and start coding! 🎉**
