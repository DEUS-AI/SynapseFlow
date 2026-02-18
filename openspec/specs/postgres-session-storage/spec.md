## ADDED Requirements

### Requirement: PostgreSQL database initialization at startup
The application SHALL initialize the PostgreSQL database connection and create tables (if they do not exist) during server startup, before any request is served. The initialization SHALL use `init_database(create_tables=True)` from `infrastructure.database.session`. If PostgreSQL is unavailable, the application SHALL log a warning and continue operating with Neo4j-only mode.

#### Scenario: Successful startup with Postgres
- **WHEN** the server starts and PostgreSQL is reachable at the configured host/port
- **THEN** the database engine is initialized with `asyncpg` driver
- **THEN** the `sessions` and `messages` tables exist in PostgreSQL
- **THEN** the startup log contains "PostgreSQL connection initialized"

#### Scenario: Postgres unavailable at startup
- **WHEN** the server starts and PostgreSQL is unreachable
- **THEN** the startup log contains a warning about PostgreSQL initialization failure
- **THEN** the server continues to operate using Neo4j for all session operations
- **THEN** no requests fail due to missing PostgreSQL connection

### Requirement: ChatHistoryService uses per-request database sessions
`ChatHistoryService` SHALL accept a `db_session_factory` (the `db_session` async context manager) instead of pre-created repository instances. Each database operation SHALL create fresh `SessionRepository` and `MessageRepository` instances within a `db_session()` block that commits on success and rolls back on failure.

#### Scenario: Multiple concurrent requests
- **WHEN** two WebSocket connections simultaneously store messages
- **THEN** each message is written within its own database session
- **THEN** a failure in one write does not roll back the other

#### Scenario: Database session lifecycle
- **WHEN** `ChatHistoryService.store_message()` is called with `db_session_factory` configured
- **THEN** a new `AsyncSession` is created for the operation
- **THEN** the session is committed after a successful write
- **THEN** the session is rolled back if the write fails

### Requirement: WebSocket handler writes messages to PostgreSQL
After `IntelligentChatService.query()` completes and stores messages in Neo4j, the WebSocket handler SHALL also write the user message and assistant response to PostgreSQL via `ChatHistoryService.store_message()` with `postgres_only=True`. The Postgres write SHALL NOT block the WebSocket response to the client. A failure in the Postgres write SHALL be logged but SHALL NOT cause an error response to the client.

#### Scenario: Message stored in both Neo4j and Postgres
- **WHEN** a user sends a message via WebSocket and gets a response
- **THEN** the user message exists in both Neo4j (via IntelligentChatService) and PostgreSQL (via ChatHistoryService)
- **THEN** the assistant response exists in both Neo4j and PostgreSQL
- **THEN** the WebSocket response is sent to the client before the Postgres write completes

#### Scenario: Postgres write fails during chat
- **WHEN** a user sends a message and PostgreSQL is temporarily unavailable
- **THEN** the user receives the assistant response normally
- **THEN** the message exists in Neo4j but not in PostgreSQL
- **THEN** the error is logged with the session_id and message content summary

### Requirement: WebSocket handler writes session creation to PostgreSQL
When the WebSocket handler creates a session via `patient_memory.create_session()`, it SHALL also create the corresponding session record in PostgreSQL via `ChatHistoryService`. The Postgres session creation SHALL use the same `session_id`, `patient_id`, and `title` values. A failure in the Postgres write SHALL be logged but SHALL NOT prevent the WebSocket connection from proceeding.

#### Scenario: Session created in both stores
- **WHEN** a WebSocket connection is established for a new session
- **THEN** a `ConversationSession` node exists in Neo4j
- **THEN** a `Session` row exists in PostgreSQL with matching id, patient_id, and title
- **THEN** the PostgreSQL `Session.extra_data` contains `{"neo4j_id": "session:uuid"}`

#### Scenario: Idempotent session creation
- **WHEN** a WebSocket reconnects with an existing session_id
- **THEN** Neo4j uses MERGE (no duplicate)
- **THEN** PostgreSQL uses INSERT with conflict handling (no duplicate, no error)

### Requirement: Title updates persist to PostgreSQL
When a session title is generated (via `auto_generate_title()`) or manually updated (via `PUT /api/chat/sessions/{id}/title`), the title SHALL be written to both Neo4j and PostgreSQL. The Postgres update SHALL use `ChatHistoryService.update_title_postgres()` which updates the `Session.title` column.

#### Scenario: Auto-generated title persisted to both stores
- **WHEN** a session has 3+ messages and `auto_generate_title()` generates "Knee Pain Discussion"
- **THEN** the Neo4j `ConversationSession` node has `title: "Knee Pain Discussion"`
- **THEN** the PostgreSQL `sessions` row has `title: "Knee Pain Discussion"`

#### Scenario: Manual title update persisted to both stores
- **WHEN** a user calls `PUT /api/chat/sessions/{id}/title` with `{"title": "My Custom Title"}`
- **THEN** both Neo4j and PostgreSQL reflect the new title
- **THEN** the response confirms the update

### Requirement: ChatHistoryService postgres_only write mode
`ChatHistoryService.store_message()` SHALL accept a `postgres_only` boolean parameter (default `False`). When `postgres_only=True`, the method SHALL skip the Neo4j write via `PatientMemoryService` and only write to PostgreSQL. This mode is used by the WebSocket handler where Neo4j writes are already performed by `IntelligentChatService`.

#### Scenario: postgres_only skips Neo4j
- **WHEN** `store_message(postgres_only=True)` is called
- **THEN** `PatientMemoryService.store_message()` is NOT called
- **THEN** the message is written to PostgreSQL only

#### Scenario: Default mode writes to both
- **WHEN** `store_message()` is called without `postgres_only` (or `postgres_only=False`)
- **THEN** the message is written to Neo4j via `PatientMemoryService`
- **THEN** the message is written to PostgreSQL if `dual_write_sessions` flag is enabled

### Requirement: PostgreSQL read paths for session metadata and search
When `use_postgres_sessions` feature flag is enabled, `get_session_metadata()` SHALL read from PostgreSQL instead of Neo4j. `search_sessions()` SHALL query PostgreSQL using `ILIKE` on `Session.title` and `Message.content` columns.

#### Scenario: Session metadata from Postgres
- **WHEN** `use_postgres_sessions` is true and `get_session_metadata(session_id)` is called
- **THEN** the session is loaded from the PostgreSQL `sessions` table
- **THEN** the returned `SessionMetadata` has correct `title`, `status`, `message_count`, and timestamps

#### Scenario: Session search from Postgres
- **WHEN** `use_postgres_sessions` is true and `search_sessions(patient_id, "knee pain")` is called
- **THEN** PostgreSQL is queried for sessions where the title or message content contains "knee pain" (case-insensitive)
- **THEN** results are returned as `SessionMetadata` objects ordered by last activity

#### Scenario: Feature flag off reads from Neo4j
- **WHEN** `use_postgres_sessions` is false
- **THEN** `get_session_metadata()` and `search_sessions()` read from Neo4j (existing behavior unchanged)

### Requirement: LangGraph persistence writes to PostgreSQL
When the `enable_langgraph_chat` and `dual_write_sessions` feature flags are both enabled, the `memory_persist_node` in `conversation_nodes.py` SHALL write messages to PostgreSQL in addition to Neo4j. The Postgres write SHALL use the same session_id and message content.

#### Scenario: LangGraph message stored in both stores
- **WHEN** both `enable_langgraph_chat` and `dual_write_sessions` are true
- **WHEN** a user sends a message through the LangGraph chat path
- **THEN** the message exists in Neo4j (via PatientMemoryService)
- **THEN** the message exists in PostgreSQL

#### Scenario: LangGraph without dual-write
- **WHEN** `enable_langgraph_chat` is true but `dual_write_sessions` is false
- **THEN** messages are stored only in Neo4j (existing behavior)
