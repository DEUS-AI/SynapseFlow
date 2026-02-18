## 1. Backend: Fix agent endpoint

- [x] 1.1 Replace mock data in `GET /api/admin/agents` (`src/application/api/main.py`) with a call to the agent discovery service, returning `agent_id`, `name`, `status`, `capabilities`, `last_heartbeat`, `heartbeat_seconds_ago`, `tier`, `description`, `version` per agent
- [x] 1.2 Add optional `status` query parameter for filtering agents by status
- [x] 1.3 Return empty array when no agents are registered, HTTP 500 on discovery service failure

## 2. Frontend: Dashboard shell and page layout

- [x] 2.1 Create `OperationsDashboard` parent component in `frontend/src/components/admin/OperationsDashboard.tsx` with 2-column responsive grid layout and navigation links section
- [x] 2.2 Update `frontend/src/pages/admin/index.astro` to replace `SystemStats` and `AgentMonitor` with single `OperationsDashboard` component via `client:load`
- [x] 2.3 Define shared TypeScript interfaces for all API response types used by panels

## 3. Frontend: Health bar

- [x] 3.1 Create `HealthBar` component that fetches `/api/crystallization/health` and derives status for Crystallization Pipeline, Promotion Gate, and Entity Resolver indicators
- [x] 3.2 Derive Neo4j status from `/api/admin/metrics` success/failure, Agents status from `/api/admin/agents` response (active count vs empty)
- [x] 3.3 Display 5 subsystem indicators with green/yellow/red color coding and labels

## 4. Frontend: Knowledge Graph panel

- [x] 4.1 Create `KnowledgeGraphPanel` component that fetches `/api/admin/metrics` and `/api/admin/layer-stats`
- [x] 4.2 Display node count, relationship count, and patient count (exclude total_queries, avg_response_time, redis_memory_usage)
- [x] 4.3 Render DIKW layer distribution as horizontal bars with layer name, count, and percentage fill

## 5. Frontend: Agents panel

- [x] 5.1 Create `AgentsPanel` component that fetches `/api/admin/agents` with 5s polling interval
- [x] 5.2 Display each agent with color-coded status indicator, name, capabilities, and heartbeat recency
- [x] 5.3 Show warning color for heartbeats older than 5 minutes
- [x] 5.4 Handle empty state with "No agents registered" message and registration hint

## 6. Frontend: Crystallization Pipeline panel

- [x] 6.1 Create `CrystallizationPanel` component that fetches `/api/crystallization/stats` with 10s polling interval
- [x] 6.2 Display running/stopped status indicator and metrics: pending entities, total crystallized, merged, promotions, errors
- [x] 6.3 Show error count in red/warning color when greater than 0

## 7. Frontend: Promotion Gate panel

- [x] 7.1 Create `PromotionGatePanel` component that fetches `/api/crystallization/promotion/stats` with 10s polling interval
- [x] 7.2 Display top-line counts (evaluated, approved, pending review, rejected) with amber highlight on pending reviews
- [x] 7.3 Render risk level breakdown (LOW, MEDIUM, HIGH) as horizontal bars

## 8. Frontend: Ontology Quality panel

- [x] 8.1 Create `OntologyQualityPanel` component that fetches `/api/ontology/quality` with 60s polling interval
- [x] 8.2 Display overall score with color-coded quality level badge, and 4 dimension scores (coverage, compliance, coherence, consistency)
- [x] 8.3 Show critical issues count when > 0 and "assessed at" timestamp
- [x] 8.4 Handle `has_assessment: false` with "No assessment available" message linking to `/admin/quality`

## 9. Frontend: Feedback panel

- [x] 9.1 Create `FeedbackPanel` component that fetches `/api/feedback/stats` and `/api/quality/scanner/status` with 15s polling interval
- [x] 9.2 Display total feedbacks, average rating, and feedback type distribution with percentages
- [x] 9.3 Show quality scanner status (Running/Disabled) with appropriate color

## 10. Frontend: Data Sync panel

- [x] 10.1 Create `DataSyncPanel` component that fetches `/api/admin/dual-write-health` with 30s polling interval
- [x] 10.2 Display sync status per data type (sessions, feedback, documents) with green/yellow/red indicators and Neo4j vs PG counts
- [x] 10.3 Handle "dual-write not enabled" state with muted display

## 11. Frontend: Shared panel behavior

- [x] 11.1 Add "last updated X ago" indicator to each panel, updating every second, with warning color when data is stale (>2x polling interval)
- [x] 11.2 Add per-panel error state displaying "Failed to load" with the panel still rendering its frame
- [x] 11.3 Add loading skeleton/spinner state for initial panel load
