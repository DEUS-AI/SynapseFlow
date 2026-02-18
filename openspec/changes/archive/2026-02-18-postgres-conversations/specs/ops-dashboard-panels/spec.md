## MODIFIED Requirements

### Requirement: Data Sync panel displays dual-write health
The dashboard SHALL display a Data Sync panel showing data from `/api/admin/dual-write-health`: sync status for sessions, feedback, and documents between Neo4j and PostgreSQL. Each data type SHALL display its sync status, Neo4j count, and PostgreSQL count. The panel SHALL poll every 30 seconds. When `dual_write_sessions` is enabled, the sessions row SHALL show live counts from both stores and highlight any drift with a warning color.

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

#### Scenario: Session dual-write enabled with drift
- **WHEN** `dual_write_sessions` is enabled and session counts differ between Neo4j and PostgreSQL
- **THEN** the sessions row shows both counts and a warning indicator
- **THEN** the sync status reflects the drift level (minor_drift or out_of_sync)
