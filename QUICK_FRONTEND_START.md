# Quick Frontend Start

**One-command startup with automatic prerequisite checks.**

---

## 🚀 Start Frontend (Recommended)

```bash
./start_frontend.sh
```

This script automatically:
- ✅ Checks if backend is running
- ✅ Checks if databases are running
- ✅ Shows you what to start if something is missing
- ✅ Clears Vite cache
- ✅ Only starts when everything is ready

---

## 🔧 What If Services Are Missing?

The script will tell you exactly what to do:

### If Backend Is Missing

```bash
uv run uvicorn src.application.api.main:app --reload --port 8000
```

### If Databases Are Missing

```bash
docker-compose -f docker-compose.memory.yml up -d
```

Then run `./start_frontend.sh` again.

---

## 📊 Check All Services

```bash
./check_services.sh
```

Shows status of all 7 services:
- Neo4j, Redis, Qdrant, FalkorDB (databases)
- Backend API (FastAPI)
- Frontend (Astro)

---

## 🌐 Access Points

Once everything is running:

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:4321 |
| Backend API | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |
| Qdrant Dashboard | http://localhost:6333/dashboard |

---

## 🛑 Stop Services

**Stop Frontend:** Press `Ctrl+C` in terminal

**Stop All Services:**
```bash
./manage_services.sh stop-all
```

---

## 💡 Tips

1. **Always use `./start_frontend.sh`** - It prevents proxy errors
2. **Backend must be running first** - Frontend proxies API/WebSocket requests to it
3. **Connection errors?** - Check the yellow banner in chat, it tells you what's wrong
4. **Clear cache if needed** - Script does this automatically

---

## 🐛 Troubleshooting

### "Vite proxy error" in console

**Cause:** Backend not running
**Fix:** Start backend first, then frontend

### Chat shows "Disconnected"

**Cause:** WebSocket can't reach backend
**Fix:** Verify backend is running on port 8000

### Build errors

**Cause:** Stale Vite cache
**Fix:** Run `./start_frontend.sh` (clears cache automatically)

---

## 📚 More Documentation

- [FIXES_APPLIED.md](FIXES_APPLIED.md) - All fixes implemented
- [START_FRONTEND.md](START_FRONTEND.md) - Detailed startup guide
- [SERVICES_GUIDE.md](SERVICES_GUIDE.md) - Complete service reference
- [QUICK_START.md](QUICK_START.md) - Full system startup

---

**That's it! Use `./start_frontend.sh` and you're good to go! 🎉**
