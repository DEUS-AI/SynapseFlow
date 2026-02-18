## Why

Conversations (sessions, messages, titles) are stored exclusively in Neo4j, which is architecturally wrong for tabular data and operationally fragile. Users lose messages and titles after page refreshes. The dual-write path to PostgreSQL exists in code but is completely disconnected: repos are never instantiated at startup, the WebSocket chat handler bypasses `ChatHistoryService` entirely, and title updates never reach Postgres. Neo4j is a graph database optimized for relationship traversal, not a reliable document store for ordered message sequences.

## What Changes

- **Wire up PostgreSQL repositories at startup** - Call `bootstrap_postgres_repositories()` and pass repos to `ChatHistoryService`
- **Route all conversation writes through ChatHistoryService** - The WebSocket handler and `IntelligentChatService` currently write directly to `PatientMemoryService` (Neo4j only), bypassing the dual-write logic. All message and session writes must go through `ChatHistoryService`
- **Complete missing Postgres write paths** - `auto_generate_title()`, manual title updates, `get_session_metadata()`, and `search_sessions()` have no Postgres path
- **Make PostgreSQL the primary read source** - Flip `use_postgres_sessions` to read from Postgres, keeping Neo4j as secondary for graph traversal links
- **Add LangGraph persistence hook** - If `enable_langgraph_chat` is on, the `memory_persist_node` writes to Neo4j only. Add a Postgres write path
- **Sync existing Neo4j conversations to Postgres** - One-time migration of historical data

## Capabilities

### New Capabilities
- `postgres-session-storage`: PostgreSQL as the primary persistence layer for conversation sessions and messages, including startup wiring, write-path consolidation, and read-path switching
- `conversation-data-sync`: One-time and ongoing synchronization of conversation data between Neo4j and PostgreSQL, including migration tooling and dual-write health monitoring

### Modified Capabilities
- `ops-dashboard-panels`: Add a conversation persistence health indicator to the dashboard (Postgres vs Neo4j record counts, sync status)

## Impact

- **Backend services**: `main.py` (startup wiring, WebSocket handler), `ChatHistoryService`, `IntelligentChatService`, `conversation_nodes.py` (LangGraph persist node), `composition_root.py`
- **Infrastructure**: `docker-compose.services.yml` (Postgres container must be running), database init scripts
- **APIs**: No endpoint signature changes. Behavior change: reads shift from Neo4j to Postgres. Write path adds Postgres as target.
- **Feature flags**: `dual_write_sessions` and `use_postgres_sessions` become meaningful (currently dead code)
- **Dependencies**: `asyncpg`, `sqlalchemy` (already installed)
- **Risk**: Existing conversations in Neo4j need migration before flipping the read source. Dual-write adds latency to each message store (~5-10ms per Postgres write).
