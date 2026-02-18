## Context

Conversations are stored exclusively in Neo4j. A half-built PostgreSQL dual-write system exists but is completely disconnected: `bootstrap_postgres_repositories()` is never called, `ChatHistoryService` is created without PG repos, and the WebSocket chat handler bypasses `ChatHistoryService` entirely (writing directly via `PatientMemoryService`).

The existing Postgres infrastructure includes: SQLAlchemy models (`Session`, `Message`), repositories (`SessionRepository`, `MessageRepository`), async engine setup (`asyncpg`), and feature flags (`dual_write_sessions`, `use_postgres_sessions`). All of this code works in isolation but has never been integrated into the runtime.

Key constraint: the `IntelligentChatService.query()` method stores messages internally (lines 407-446 of `intelligent_chat_service.py`), calling `PatientMemoryService.store_message()` directly. This is the primary chat path and it completely bypasses `ChatHistoryService`.

## Goals / Non-Goals

**Goals:**
- PostgreSQL becomes the primary persistence layer for sessions and messages
- All conversation write paths (WebSocket, REST, LangGraph) route through a single service that writes to Postgres
- Existing Neo4j graph links (Patient → Session) are maintained for KG traversal
- Feature flags control the rollout (dual-write phase → Postgres-primary phase)
- Existing conversations are migrated from Neo4j to Postgres

**Non-Goals:**
- Removing Neo4j conversation writes entirely (keep as secondary for now)
- Changing the frontend session/message API contracts
- Adding new session features (search improvements, full-text search in Postgres)
- Modifying the Mem0 integration (user message fact extraction stays as-is)
- Adding Alembic migrations (continue using `create_all` + init SQL)

## Decisions

### D1: Fix repository session lifecycle (per-request sessions)

**Problem:** `bootstrap_postgres_repositories()` creates repos inside a `db_session()` context manager. When the context exits, the session commits and closes. Any subsequent repo call would fail with a closed session.

**Decision:** Replace the single-session repo pattern with a session-factory pattern. `ChatHistoryService` receives the `async_sessionmaker` (or a lightweight factory) and creates fresh `SessionRepository`/`MessageRepository` instances per operation using `db_session()`.

**Alternative considered:** Long-lived session - rejected because async SQLAlchemy sessions are not thread-safe and shouldn't span multiple requests.

**Implementation:**
- Modify `ChatHistoryService.__init__` to accept `db_session_factory` (the `async_sessionmaker` or `db_session` context manager) instead of repo instances
- Each ChatHistoryService method creates repos within a `db_session()` block
- Remove `bootstrap_postgres_repositories()` repo-in-context pattern
- Init just calls `init_database(create_tables=True)` at startup

### D2: Consolidate writes through ChatHistoryService (post-query hook)

**Problem:** `IntelligentChatService.query()` stores both user and assistant messages by calling `PatientMemoryService.store_message()` directly (lines 413-443). Changing this to call `ChatHistoryService` instead would create a circular dependency and tightly couple the chat engine to the history service.

**Decision:** Keep `IntelligentChatService` storing to Neo4j as it does today. Add a **post-query hook in the WebSocket handler** that also writes to Postgres via `ChatHistoryService.store_message()`. The WebSocket handler already has access to both services and to the message content + response.

**Alternative considered:** Refactoring IntelligentChatService to accept a storage callback - rejected as too invasive and risky for the core chat path.

**Implementation:**
- After `chat_service.query()` returns in the WebSocket handler, call `history_service.store_message()` for both the user message and assistant response
- `ChatHistoryService.store_message()` skips the Neo4j write (already done by IntelligentChatService) and only writes to Postgres
- Add a `postgres_only=True` parameter to `ChatHistoryService.store_message()` for this case
- For the REST `POST /sessions/start` path, the existing dual-write code in `ChatHistoryService.create_session()` handles both stores

### D3: Session creation dual-write from WebSocket handler

**Problem:** The WebSocket handler calls `patient_memory.create_session()` directly (line 179 of main.py), bypassing ChatHistoryService.

**Decision:** After the existing `patient_memory.create_session()` call, add a Postgres write via ChatHistoryService. Keep the Neo4j call first (it's idempotent via MERGE) and add Postgres as secondary.

**Alternative considered:** Replace the `patient_memory.create_session()` call with `history_service.create_session()` - viable but riskier since the existing Neo4j session creation has been working reliably.

### D4: Title updates go through ChatHistoryService

**Problem:** `auto_generate_title()` updates Neo4j via `self.memory.update_session_title()` but has no Postgres path. The manual `PUT /sessions/{id}/title` endpoint calls `patient_memory.update_session_title()` directly.

**Decision:** Add a `update_title_postgres()` method to `ChatHistoryService` that updates the Postgres `Session.title` column. Call it from both `auto_generate_title()` and the manual title endpoint.

### D5: Postgres as primary read source (feature-flag gated)

**Decision:** When `use_postgres_sessions` is enabled:
- `list_sessions()` reads from Postgres (already implemented in `_list_sessions_postgres`)
- `get_session_messages()` reads from Postgres (already implemented in `_get_session_messages_postgres`)
- `get_session_metadata()` reads from Postgres (NEW - currently Neo4j only)
- `search_sessions()` reads from Postgres (NEW - use `ILIKE` on content/title)

The feature flag stays OFF during dual-write stabilization. Once record counts match between stores (verified via `/api/admin/dual-write-health`), flip to Postgres reads.

### D6: LangGraph persistence hook

**Problem:** `memory_persist_node` in `conversation_nodes.py` writes to Neo4j only via `PatientMemoryService`.

**Decision:** Same pattern as D2 - add a Postgres write after the Neo4j write. Since the LangGraph path is behind a feature flag (`enable_langgraph_chat`) and rarely used, keep the fix minimal: have the `memory_persist_node` also call a Postgres store function when `dual_write_sessions` is enabled.

### D7: One-time migration (Neo4j → Postgres sync script)

**Decision:** Extend the existing `scripts/sync_data_to_postgres.py` script to handle sessions and messages. The script:
1. Queries all `ConversationSession` nodes and `Message` nodes from Neo4j
2. Inserts them into Postgres with proper UUID mapping (`session:uuid` → `uuid`)
3. Uses `ON CONFLICT DO NOTHING` to be idempotent (safe to re-run)
4. Reports record counts for verification

Run this before flipping `use_postgres_sessions` to true.

## Risks / Trade-offs

**[Dual-write latency]** → Each message write adds ~5-10ms for the Postgres INSERT. Acceptable for a chat application where the bottleneck is LLM inference (seconds, not milliseconds). Postgres write is fire-and-forget with error logging (same pattern as existing dual-write code).

**[Data divergence during dual-write]** → If Postgres writes fail silently, the stores drift apart. Mitigation: the dual-write health endpoint (`/api/admin/dual-write-health`) already compares record counts. The ops dashboard shows sync status. Add an alert threshold.

**[Session ID format mismatch]** → Neo4j uses `session:uuid` format, Postgres stores raw UUIDs. `_extract_uuid_from_session_id()` already handles this conversion. Ensure all new Postgres paths use this consistently.

**[Message ordering]** → Neo4j messages are ordered by `m.timestamp`. Postgres messages are ordered by `created_at`. If timestamps differ slightly between the two writes, ordering could diverge. Mitigation: pass the same timestamp to both writes.

**[Rollback path]** → If Postgres proves unreliable, flip `use_postgres_sessions` back to false. Neo4j remains the source of truth during dual-write. No data loss scenario.

## Migration Plan

**Phase 1: Wire up Postgres (dual-write OFF, reads from Neo4j)**
- Initialize Postgres at startup (`init_database`)
- Pass session factory to ChatHistoryService
- Add post-query Postgres writes in WebSocket handler
- Add title update Postgres writes
- All reads still from Neo4j - zero user-facing change

**Phase 2: Enable dual-write**
- Set `FEATURE_FLAG_DUAL_WRITE_SESSIONS=true`
- Monitor dual-write health on dashboard
- Run sync script for historical data
- Verify record count parity

**Phase 3: Flip reads to Postgres**
- Set `FEATURE_FLAG_USE_POSTGRES_SESSIONS=true`
- Monitor for any issues
- Rollback: set flag back to false

## Open Questions

- Should we add a Postgres search path for `search_sessions()` using `ILIKE`, or defer full-text search to a future change?
- Should the sync script run as a one-time migration or as a periodic reconciliation job?
