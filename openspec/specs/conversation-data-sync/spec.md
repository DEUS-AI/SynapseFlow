## ADDED Requirements

### Requirement: Neo4j to PostgreSQL conversation sync script
A sync script SHALL exist at `scripts/sync_sessions_to_postgres.py` that migrates all conversation sessions and messages from Neo4j to PostgreSQL. The script SHALL be idempotent (safe to re-run without creating duplicates). The script SHALL report counts of synced sessions, synced messages, skipped duplicates, and errors.

#### Scenario: First-time sync with existing data
- **WHEN** the sync script runs against a Neo4j database with 50 sessions and 500 messages, and PostgreSQL has no session data
- **THEN** 50 session rows are inserted into the `sessions` table
- **THEN** 500 message rows are inserted into the `messages` table
- **THEN** the script outputs "Synced: 50 sessions, 500 messages. Skipped: 0. Errors: 0"

#### Scenario: Re-run after partial sync
- **WHEN** the sync script runs again after 30 of 50 sessions were already synced
- **THEN** 20 new sessions are inserted, 30 are skipped (ON CONFLICT DO NOTHING)
- **THEN** all messages for the 20 new sessions are inserted
- **THEN** the script outputs counts reflecting the delta

#### Scenario: Session ID format mapping
- **WHEN** a Neo4j session has `id: "session:abc123-def456"`
- **THEN** the PostgreSQL row uses UUID `abc123-def456` as the primary key
- **THEN** the `extra_data` JSONB column contains `{"neo4j_id": "session:abc123-def456"}`

#### Scenario: Message timestamp preservation
- **WHEN** a Neo4j message has `timestamp: "2026-02-15T10:30:00"`
- **THEN** the PostgreSQL message row has `created_at: "2026-02-15T10:30:00"` (preserving original time, not insert time)

### Requirement: Dual-write health includes session counts
The `/api/admin/dual-write-health` endpoint SHALL include session and message counts from both Neo4j and PostgreSQL when `dual_write_sessions` is enabled. The sync status SHALL be computed by comparing the counts: "synced" if counts match within 5%, "minor_drift" if within 20%, "out_of_sync" otherwise.

#### Scenario: Counts match
- **WHEN** Neo4j has 100 sessions and PostgreSQL has 100 sessions
- **THEN** the session data type reports `sync_status: "synced"`, `neo4j_count: 100`, `postgres_count: 100`

#### Scenario: Minor drift detected
- **WHEN** Neo4j has 100 sessions and PostgreSQL has 88 sessions
- **THEN** the session data type reports `sync_status: "minor_drift"`

#### Scenario: Dual-write disabled
- **WHEN** `dual_write_sessions` is false
- **THEN** the sessions data type reports `dual_write_enabled: false` and `sync_status: "disabled"`
