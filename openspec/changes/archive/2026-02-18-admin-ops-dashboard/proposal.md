## Why

The admin landing page (`/admin`) displays mostly fake data. The agent status panel returns hardcoded mock data (4 agents, always "running", fixed task counts), system metrics have 3 of 7 fields hardcoded as TODOs, and the WebSocket monitor only does ping/pong. Meanwhile, the backend already has 10+ real stats APIs (agent discovery, DIKW layer stats, crystallization pipeline, promotion gate, ontology quality, feedback, dual-write health) that go completely unused on the landing page. The dashboard should be a real operations view, not a placeholder.

## What Changes

- **Replace the admin landing page** with an operations dashboard that aggregates real data from existing backend APIs
- **Fix `/api/admin/agents`** to call the real agent discovery service instead of returning hardcoded mock data
- **Add a health bar** that shows at-a-glance status of core subsystems (Neo4j, crystallization pipeline, agents, promotion gate, entity resolver)
- **Add Knowledge Graph panel** showing node/relationship counts and DIKW pyramid layer distribution
- **Add Agents panel** showing real agent status, capabilities, heartbeat recency, and stale detection
- **Add Crystallization Pipeline panel** showing running status, pending entities, crystallized/merged/promotion counts, errors
- **Add Promotion Gate panel** showing evaluation stats broken down by risk level and entity type
- **Add Ontology Quality panel** showing overall score and the 4 quality dimensions (coverage, compliance, coherence, consistency)
- **Add Feedback/RLHF panel** showing feedback totals, rating distribution, and quality scanner status
- **Add Data Sync panel** showing Neo4j vs PostgreSQL dual-write health for sessions, feedback, and documents
- **Remove hardcoded/TODO metrics** (total_queries, avg_response_time, redis_memory_usage) from display until they have real implementations

## Capabilities

### New Capabilities
- `ops-dashboard-panels`: The set of dashboard panel components that fetch and display real-time operational data from existing backend APIs (health bar, KG stats, agents, crystallization, promotions, ontology quality, feedback, data sync)
- `real-agent-monitoring`: Wiring the admin agent endpoint to the real agent discovery service, replacing mock data with live registration status, heartbeats, capabilities, and stale detection

### Modified Capabilities
_(none - all backend APIs already exist, we're only consuming them from the frontend and fixing one mock endpoint)_

## Impact

- **Frontend**: `frontend/src/pages/admin/index.astro` (page layout), `frontend/src/components/admin/SystemStats.tsx` and `AgentMonitor.tsx` (replaced/rewritten), ~7 new panel components
- **Backend**: `src/application/api/main.py` - `/api/admin/agents` endpoint (replace mock with real agent discovery call)
- **APIs consumed** (all already exist, no new endpoints):
  - `/api/agents` (or fixed `/api/admin/agents`)
  - `/api/admin/metrics`, `/api/admin/layer-stats`
  - `/api/crystallization/stats`, `/api/crystallization/health`
  - `/api/crystallization/promotion/stats`
  - `/api/ontology/quality`
  - `/api/feedback/stats`, `/api/quality/scanner/status`
  - `/api/admin/dual-write-health`
- **No breaking changes** - existing sub-pages (`/admin/patients`, `/admin/documents`, `/admin/feedback`, `/admin/quality`) are unaffected
