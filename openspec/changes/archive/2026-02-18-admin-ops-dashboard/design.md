## Context

The admin landing page at `/admin` currently renders two components: `SystemStats` (partially real Neo4j data, 3 hardcoded fields, WebSocket that only pings) and `AgentMonitor` (fully mocked endpoint returning static JSON). The backend has 15+ real stats APIs that are only consumed by their dedicated sub-pages (`/admin/quality`, `/admin/documents`, etc.) but never aggregated on the landing page.

Existing frontend patterns: Astro 4 + React 18 hydrated via `client:load`, TanStack React Query 5 for server state, Zustand for client state, Tailwind/slate-900 dark theme, `lucide-react` icons, `Recharts` for charts. Polling via `setInterval` in `useEffect` is the current pattern, but React Query's `refetchInterval` is available and preferred.

## Goals / Non-Goals

**Goals:**
- Surface real operational data from all major subsystems on a single landing page
- Replace the mock `/api/admin/agents` endpoint with a call to the real agent discovery service
- Provide at-a-glance system health via a status bar
- Maintain the existing dark theme, component patterns, and navigation to sub-pages
- Each panel loads independently so partial backend failures don't break the whole page
- Remove hardcoded/TODO metrics that mislead operators

**Non-Goals:**
- Implementing the 3 TODO metrics (query counter, response time tracking, Redis stats) — these need middleware/instrumentation work outside this change
- Real-time push via WebSocket — the existing `/ws/admin/monitor` only does ping/pong; full event streaming is future scope
- Time-series trend charts on the landing page — trends already live on `/admin/quality`
- Adding new backend API endpoints — we consume only what already exists
- Mobile-optimized layout — admin dashboard is a desktop tool

## Decisions

### D1: Panel-per-subsystem layout in a responsive CSS grid

Replace the current 2-component layout with 7-8 panel cards in a responsive grid (3 columns on xl, 2 on lg, 1 on md). Each panel is a self-contained React component that fetches its own data.

**Why over alternative** (single monolith fetch): Each panel maps to one backend API domain, making them independently loadable and testable. One failed API doesn't block the others. Progressive loading makes the page feel responsive even if one endpoint is slow.

### D2: React Query with per-panel polling intervals

Each panel uses `useQuery` with `refetchInterval`. No shared data layer needed — React Query handles caching, deduplication, and stale-while-revalidate. Intervals vary per panel: agents every 10s, KG stats every 30s, ontology quality every 60s.

**Why over alternative** (manual `useEffect` + `setInterval`): React Query is already in the project (TanStack React Query 5). It handles loading/error states, deduplication, background refetching, and caching automatically. The existing `useEffect` pattern works but requires more boilerplate.

**Why not WebSocket?** The existing `/ws/admin/monitor` only pushes connection count. Building full event streaming for all panels is scope creep at this scale (~14 requests/minute with 7 panels at 30s).

### D3: Fix `/api/admin/agents` by calling agent registry

Replace the hardcoded mock response in `get_agent_status()` with a call to `agent_registry` (already populated during startup via `register_agent_capabilities()`). Keep the `/api/admin/agents` URL.

**Why over alternative** (having frontend call `/api/agents` directly): Keeps a consistent `/api/admin/*` namespace. The `/api/agents/*` endpoints are for agent-to-agent interactions. A thin adapter in the admin endpoint lets us shape the response for dashboard needs (e.g., computed "time since heartbeat").

**Fallback:** If no agents are registered (standalone mode), return an empty list rather than fake data.

### D4: Health bar derives status from existing endpoints

A horizontal bar at the top showing 5 subsystem indicators (Neo4j, Agents, Crystallization, Promotion Gate, Entity Resolver). Status colors derived from existing APIs:
- **Neo4j**: green if `/api/admin/metrics` returns node count > 0
- **Agents**: green if any agent has recent heartbeat, yellow if stale, red if none
- **Crystallization**: from `/api/crystallization/health` (already checks pipeline + resolver)
- **Promotion Gate**: green if `/api/crystallization/promotion/stats` returns without error
- **Entity Resolver**: green if `/api/crystallization/resolution/stats` returns without error

**Why no new `/api/admin/health`?** Zero backend work. Existing endpoints already return what we need.

### D5: Single OperationsDashboard parent component

One parent component imported in `admin/index.astro` via `client:load`, with sub-components for each panel.

**Why over alternative** (multiple Astro islands): Allows shared types, potential shared refresh trigger, and simpler Astro page (one `client:load` instead of 8). Panels can share a "last refreshed" indicator.

### D6: Drop WebSocket, remove TODO metrics

Remove the `useWebSocket` connection from SystemStats (does nothing useful). Drop the 3 hardcoded metrics (total_queries, avg_response_time, redis_memory_usage). Replace with panels showing data we actually have.

**Why:** Showing "N/A" or "TODO" erodes trust. Better to show fewer metrics that are real.

## Risks / Trade-offs

**[8 parallel API calls on page load]** → Each is a fast query (simple counts/stats). React Query deduplicates and caches. If this becomes a concern, a backend aggregation endpoint can be added later without changing component structure.

**[Agent discovery returns empty if no agents registered]** → Agents must self-register via `/api/agents/register`. If none have, the panel shows "No agents registered" with a hint. This is correct behavior — the mock was hiding the truth.

**[Ontology quality endpoint is expensive]** → Use the quick endpoint (`GET /api/ontology/quality`) for the panel, not the full assessment (`POST /api/ontology/quality/assess`). Poll at 60s. The quality sub-page already handles on-demand re-assessment.

**[Dual-write health only relevant during migration]** → The Data Sync panel may show "all disabled" if PostgreSQL migration hasn't started. Panel handles this gracefully.
