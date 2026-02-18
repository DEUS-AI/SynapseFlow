## 1. Database Initialization & Session Factory (D1)

- [x] 1.1 Add `init_database(create_tables=True)` call to the `startup` event in `main.py`, wrapped in try/except that logs a warning and continues if Postgres is unavailable
- [x] 1.2 Refactor `ChatHistoryService.__init__` to accept `db_session_factory` (the `db_session` context manager from `infrastructure.database.session`) instead of `pg_session_repo` and `pg_message_repo` parameters
- [x] 1.3 Refactor all Postgres write methods in `ChatHistoryService` (`create_session`, `store_message`, `end_session`, `delete_session`) to create `SessionRepository`/`MessageRepository` inside a `db_session()` block per operation
- [x] 1.4 Update `get_chat_history_service()` in `main.py` to pass `db_session_factory=db_session` to `ChatHistoryService` after successful Postgres initialization

## 2. postgres_only Write Mode (D2)

- [x] 2.1 Add `postgres_only: bool = False` parameter to `ChatHistoryService.store_message()`
- [x] 2.2 When `postgres_only=True`, skip the `PatientMemoryService.store_message()` call and write directly to Postgres
- [x] 2.3 When `postgres_only=False`, keep existing behavior (Neo4j primary + Postgres dual-write if flag enabled)

## 3. WebSocket Handler - Message Dual-Write (D2)

- [x] 3.1 In the WebSocket handler (after `chat_service.query()` returns and before title generation), add calls to `history_service.store_message(postgres_only=True)` for the user message (using `message_text`, `patient_id`, `session_id`, role="user")
- [x] 3.2 Add call to `history_service.store_message(postgres_only=True)` for the assistant response (using `response.answer`, `patient_id`, `session_id`, role="assistant", `response_id`)
- [x] 3.3 Wrap both Postgres writes in try/except that logs errors but does not affect the WebSocket response

## 4. WebSocket Handler - Session Creation Dual-Write (D3)

- [x] 4.1 After the existing `patient_memory.create_session()` call in the WebSocket handler, add a Postgres session creation via `history_service.create_session_postgres()` (or reuse `create_session` with a flag to skip Neo4j)
- [x] 4.2 Add `create_session_postgres()` method to `ChatHistoryService` that only writes to Postgres with `ON CONFLICT DO NOTHING` for idempotency
- [x] 4.3 Wrap the Postgres session creation in try/except that logs errors but does not block the WebSocket connection

## 5. Title Update Dual-Write (D4)

- [x] 5.1 Add `update_title_postgres(session_id, title)` method to `ChatHistoryService` that updates `Session.title` in Postgres using a `db_session()` block
- [x] 5.2 Call `update_title_postgres()` from `auto_generate_title()` after the Neo4j title update succeeds
- [x] 5.3 Update the `PUT /api/chat/sessions/{session_id}/title` endpoint in `main.py` to also call `history_service.update_title_postgres()` after the Neo4j update

## 6. Postgres Read Paths (D5)

- [x] 6.1 Add `_get_session_metadata_postgres(session_id)` method to `ChatHistoryService` that reads from the Postgres `sessions` table and returns `SessionMetadata`
- [x] 6.2 Update `get_session_metadata()` to check `use_postgres_sessions()` flag and delegate to the Postgres method when enabled
- [x] 6.3 Add `_search_sessions_postgres(patient_id, query, limit)` method that uses `ILIKE` on `Session.title` and `Message.content`
- [x] 6.4 Update `search_sessions()` to check `use_postgres_sessions()` flag and delegate to the Postgres method when enabled
- [x] 6.5 Update existing `_list_sessions_postgres` and `_get_session_messages_postgres` to use the new `db_session_factory` pattern (they currently reference `self.pg_session_repo` / `self.pg_message_repo`)

## 7. LangGraph Persistence Hook (D6)

- [x] 7.1 In `conversation_nodes.py` `memory_persist_node`, after the `PatientMemoryService.store_message()` call, add a Postgres write when `dual_write_sessions` flag is enabled
- [x] 7.2 Use `db_session()` and `MessageRepository` directly (same per-request pattern) since this node doesn't have access to `ChatHistoryService`

## 8. Sync Script (D7)

- [x] 8.1 Create `scripts/sync_sessions_to_postgres.py` that connects to both Neo4j and Postgres (existing `scripts/sync_data_to_postgres.py`)
- [x] 8.2 Query all `ConversationSession` nodes from Neo4j with their properties
- [x] 8.3 Insert sessions into Postgres with UUID mapping (`session:uuid` → `uuid`), using `ON CONFLICT DO NOTHING`
- [x] 8.4 Query all `Message` nodes linked to sessions, preserving original timestamps
- [x] 8.5 Insert messages into Postgres with proper `session_id` foreign key, using `ON CONFLICT DO NOTHING`
- [x] 8.6 Print summary: synced sessions, synced messages, skipped duplicates, errors

## 9. Dual-Write Health Endpoint Update

- [x] 9.1 Update `/api/admin/dual-write-health` in `main.py` to include session and message counts from both Neo4j and Postgres when `dual_write_sessions` is enabled
- [x] 9.2 Compute sync status: "synced" if counts within 5%, "minor_drift" if within 20%, "out_of_sync" otherwise
- [x] 9.3 Return `dual_write_enabled: false` and `sync_status: "disabled"` for sessions when the flag is off

## 10. Cleanup & Feature Flags

- [x] 10.1 Remove the old `bootstrap_postgres_repositories()` function from `composition_root.py` (replaced by direct `init_database` call)
- [x] 10.2 Remove the unused `get_postgres_repository_factory()` function from `composition_root.py`
- [x] 10.3 Remove `pg_session_repo` and `pg_message_repo` parameters from `ChatHistoryService.__init__` (replaced by `db_session_factory`)
- [x] 10.4 Verify `FEATURE_FLAG_DUAL_WRITE_SESSIONS` and `FEATURE_FLAG_USE_POSTGRES_SESSIONS` env vars are documented in `.env.example`
