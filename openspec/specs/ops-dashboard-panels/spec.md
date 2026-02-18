## ADDED Requirements

### Requirement: Operations dashboard page layout
The `/admin` page SHALL render a single `OperationsDashboard` React component containing a health bar, 7 data panels, and navigation links to sub-pages. The page SHALL use the existing dark theme (slate-900 background). Each panel SHALL load its data independently so that a failure in one panel does not affect others.

#### Scenario: Page renders all sections
- **WHEN** a user navigates to `/admin`
- **THEN** the page displays a health bar at the top, followed by panels arranged in a 2-column grid (Knowledge Graph, Agents, Crystallization Pipeline, Promotion Gate, Ontology Quality, Feedback, Data Sync), followed by navigation links to `/admin/patients`, `/admin/documents`, `/admin/feedback`, and `/admin/quality`

#### Scenario: Partial backend failure
- **WHEN** one API endpoint fails (e.g., crystallization stats returns 500)
- **THEN** that panel displays an error state with the message "Failed to load"
- **THEN** all other panels continue to load and display data normally

### Requirement: Health bar shows subsystem status
The dashboard SHALL display a horizontal health bar showing the status of 5 core subsystems: Neo4j, Crystallization Pipeline, Agents, Promotion Gate, and Entity Resolver. Each subsystem SHALL be displayed as a status indicator with a color (green for healthy, yellow for degraded, red for down) and a label.

#### Scenario: All subsystems healthy
- **WHEN** `/api/crystallization/health` returns `healthy: true` and `/api/admin/agents` returns at least one active agent and `/api/admin/metrics` succeeds
- **THEN** the health bar shows all 5 indicators in green

#### Scenario: Crystallization service down
- **WHEN** `/api/crystallization/health` returns `crystallization_service: false`
- **THEN** the Crystallization Pipeline indicator shows red
- **THEN** other indicators reflect their own status independently

#### Scenario: No agents registered
- **WHEN** `/api/admin/agents` returns an empty list
- **THEN** the Agents indicator shows yellow with label text indicating no agents are registered

#### Scenario: Neo4j unreachable
- **WHEN** `/api/admin/metrics` returns a 500 error
- **THEN** the Neo4j indicator shows red

### Requirement: Knowledge Graph panel displays real metrics
The dashboard SHALL display a Knowledge Graph panel showing node count, relationship count, patient count (from `/api/admin/metrics`), and DIKW layer distribution (from `/api/admin/layer-stats`). The panel SHALL NOT display `total_queries`, `avg_response_time`, or `redis_memory_usage` fields. The panel SHALL NOT use a WebSocket connection.

#### Scenario: Metrics and layer stats load successfully
- **WHEN** both `/api/admin/metrics` and `/api/admin/layer-stats` return data
- **THEN** the panel shows node count, relationship count, and patient count as numeric values
- **THEN** the panel shows DIKW layer distribution as horizontal bars with layer name, count, and percentage

#### Scenario: Layer stats show distribution
- **WHEN** `/api/admin/layer-stats` returns `{ layers: { PERCEPTION: 100, SEMANTIC: 300, REASONING: 150, APPLICATION: 50 } }`
- **THEN** the PERCEPTION bar fills ~17%, SEMANTIC ~50%, REASONING ~25%, APPLICATION ~8% of the available width
- **THEN** each bar displays the layer name and absolute count

### Requirement: Agents panel displays real agent data
The dashboard SHALL display an Agents panel showing agents from `/api/admin/agents` with their name, status (active/inactive/degraded/starting), capabilities list, and time since last heartbeat. The panel SHALL poll every 5 seconds.

#### Scenario: Agents with mixed status
- **WHEN** `/api/admin/agents` returns agents with different statuses
- **THEN** each agent displays a color-coded status indicator (green=active, yellow=degraded, red=inactive, blue=starting)
- **THEN** each agent displays its name, capabilities, and heartbeat recency

#### Scenario: Agent heartbeat stale
- **WHEN** an agent's last heartbeat was more than 5 minutes ago
- **THEN** the agent row displays the heartbeat time in a warning color

#### Scenario: No agents registered
- **WHEN** `/api/admin/agents` returns an empty list
- **THEN** the panel displays "No agents registered" with a hint about the agent registration endpoint

### Requirement: Crystallization Pipeline panel displays pipeline status
The dashboard SHALL display a Crystallization Pipeline panel showing data from `/api/crystallization/stats`: running status, pending entity count, total crystallized, total merged, total promotions, and error count. The panel SHALL poll every 10 seconds.

#### Scenario: Pipeline running with data
- **WHEN** `/api/crystallization/stats` returns `{ running: true, pending_entities: 14, total_crystallized: 1203, total_merged: 87, total_promotions: 342, errors: 3 }`
- **THEN** the panel shows a green "Running" status indicator
- **THEN** the panel displays each metric as a labeled value

#### Scenario: Pipeline stopped
- **WHEN** `/api/crystallization/stats` returns `{ running: false, ... }`
- **THEN** the panel shows a gray "Stopped" status indicator

#### Scenario: Pipeline has errors
- **WHEN** the error count is greater than 0
- **THEN** the error count displays in a red/warning color

### Requirement: Promotion Gate panel displays evaluation statistics
The dashboard SHALL display a Promotion Gate panel showing data from `/api/crystallization/promotion/stats`: total evaluated, approved, pending review, rejected counts, and a breakdown by risk level. The panel SHALL poll every 10 seconds.

#### Scenario: Promotion stats with risk breakdown
- **WHEN** `/api/crystallization/promotion/stats` returns data with `by_risk_level` containing LOW, MEDIUM, and HIGH counts
- **THEN** the panel displays the 4 top-line counts (evaluated, approved, pending, rejected)
- **THEN** the panel displays risk level distribution as labeled horizontal bars

#### Scenario: Pending reviews exist
- **WHEN** `total_pending_review` is greater than 0
- **THEN** the pending review count displays in an attention-drawing color (amber/yellow)

### Requirement: Ontology Quality panel displays quality dimensions
The dashboard SHALL display an Ontology Quality panel showing data from `/api/ontology/quality`: overall score, quality level, and the 4 dimension scores (coverage, compliance, coherence, consistency). The panel SHALL poll every 60 seconds and display a "last assessed" timestamp. Critical issues count SHALL be shown if greater than 0.

#### Scenario: Quality data available
- **WHEN** `/api/ontology/quality` returns `{ has_assessment: true, latest: { overall_score: 0.82, quality_level: "good", coverage_ratio: 0.91, compliance_ratio: 0.85, coherence_ratio: 0.78, consistency_ratio: 0.74, critical_issues: ["..."], assessed_at: "..." } }`
- **THEN** the panel displays the overall score prominently with a color-coded quality level badge
- **THEN** the panel displays each dimension as a labeled value
- **THEN** the panel shows "assessed at" timestamp

#### Scenario: No assessment exists
- **WHEN** `/api/ontology/quality` returns `{ has_assessment: false }`
- **THEN** the panel displays "No assessment available" with a suggestion to run one from `/admin/quality`

### Requirement: Feedback panel displays feedback statistics
The dashboard SHALL display a Feedback panel showing data from `/api/feedback/stats`: total feedbacks, average rating, and distribution by feedback type. The panel SHALL also show quality scanner status from `/api/quality/scanner/status`: enabled/running state and last scan timestamps. The panel SHALL poll every 15 seconds.

#### Scenario: Feedback stats with scanner running
- **WHEN** `/api/feedback/stats` returns feedback totals and `/api/quality/scanner/status` returns `{ enabled: true, running: true }`
- **THEN** the panel displays total feedback count and average rating
- **THEN** the panel shows feedback type distribution (positive, negative, corrections) with percentages
- **THEN** the panel shows scanner status as "Running" in green

#### Scenario: Scanner disabled
- **WHEN** `/api/quality/scanner/status` returns `{ enabled: false }`
- **THEN** the scanner status displays as "Disabled" in gray

### Requirement: Data Sync panel displays dual-write health
The dashboard SHALL display a Data Sync panel showing data from `/api/admin/dual-write-health`: sync status for sessions, feedback, and documents between Neo4j and PostgreSQL. Each data type SHALL display its sync status, Neo4j count, and PostgreSQL count. The panel SHALL poll every 30 seconds.

#### Scenario: All synced
- **WHEN** all three data types have `sync_status: "synced"`
- **THEN** each data type shows a green indicator with matching counts

#### Scenario: Drift detected
- **WHEN** a data type has `sync_status: "minor_drift"` or `"out_of_sync"`
- **THEN** that data type shows a yellow or red indicator respectively
- **THEN** the differing counts are visible (e.g., "Neo4j: 89 / PG: 87")

#### Scenario: Dual-write not enabled
- **WHEN** all data types have `dual_write_enabled: false`
- **THEN** the panel displays "Dual-write not enabled" in a muted state

### Requirement: Panels display last-updated indicator
Each dashboard panel SHALL display a "last updated" indicator showing how many seconds ago the data was last successfully fetched. The indicator SHALL update every second independently of the data polling interval.

#### Scenario: Fresh data
- **WHEN** data was fetched less than 5 seconds ago
- **THEN** the indicator shows "just now" or "Xs ago"

#### Scenario: Stale data
- **WHEN** the panel has not successfully fetched data for more than twice its polling interval
- **THEN** the indicator text changes to a warning color

### Requirement: Navigation links preserved
The dashboard SHALL include navigation links to `/admin/patients`, `/admin/documents`, `/admin/feedback`, and `/admin/quality` below the panels, matching the current link style and layout.

#### Scenario: Navigation links render
- **WHEN** the dashboard loads
- **THEN** all 4 navigation links are visible with their existing icons and colors
- **THEN** clicking each link navigates to the correct sub-page
