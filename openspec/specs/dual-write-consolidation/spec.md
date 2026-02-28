## ADDED Requirements

### Requirement: FeedbackTracerService encapsulates dual-write in submit_feedback
`FeedbackTracerService.submit_feedback()` SHALL call `self.dual_write_to_postgres()` internally after recording feedback in-memory and publishing events. The dual-write SHALL be non-blocking: failures SHALL be logged at warning level but SHALL NOT raise exceptions or prevent the primary feedback submission from succeeding.

#### Scenario: Dual-write happens automatically on feedback submission
- **WHEN** `dual_write_enabled("feedback")` is `True` and `_has_postgres` is `True`
- **WHEN** `submit_feedback()` is called with valid feedback data
- **THEN** the feedback is stored in-memory (existing behavior)
- **THEN** `dual_write_to_postgres()` is called with the feedback data
- **THEN** the method returns successfully regardless of PostgreSQL write outcome

#### Scenario: Dual-write skipped when flag is off
- **WHEN** `dual_write_enabled("feedback")` is `False`
- **WHEN** `submit_feedback()` is called
- **THEN** the feedback is stored in-memory only (existing behavior)
- **THEN** no PostgreSQL write is attempted

#### Scenario: Dual-write failure does not block submission
- **WHEN** `dual_write_to_postgres()` raises an exception
- **THEN** `submit_feedback()` still returns the feedback result successfully
- **THEN** the error is logged at warning level

### Requirement: Main.py feedback endpoints do not call dual-write directly
The `submit_feedback` and `submit_thumbs_feedback` endpoints in main.py SHALL NOT call `feedback_service.dual_write_to_postgres()` directly. The service encapsulates the dual-write internally.

#### Scenario: Endpoint only calls submit_feedback
- **WHEN** `POST /api/feedback` is called
- **THEN** the endpoint calls `feedback_service.submit_feedback()` only
- **THEN** no explicit `dual_write_to_postgres()` call exists in the endpoint code

#### Scenario: Thumbs endpoint only calls submit_feedback
- **WHEN** `POST /api/feedback/thumbs` is called
- **THEN** the endpoint calls `feedback_service.submit_feedback()` only
- **THEN** no explicit `dual_write_to_postgres()` call exists in the endpoint code

### Requirement: ChatHistoryService exposes dual_write_messages for external callers
`ChatHistoryService` SHALL provide a `dual_write_messages(session_id, patient_id, user_msg, assistant_msg)` public method that writes a user and assistant message pair to PostgreSQL when dual-write is enabled. This method SHALL handle session ID extraction, message creation, and message count increments. The method SHALL be non-blocking: failures SHALL be logged but SHALL NOT raise exceptions.

#### Scenario: Messages written to PostgreSQL
- **WHEN** `dual_write_enabled("sessions")` is `True` and `_has_postgres` is `True`
- **WHEN** `dual_write_messages("session:uuid", "patient1", "hello", "hi there")` is called
- **THEN** a user message with content "hello" is created in PostgreSQL
- **THEN** an assistant message with content "hi there" is created in PostgreSQL
- **THEN** the session message count is incremented by 2

#### Scenario: Dual-write disabled
- **WHEN** `dual_write_enabled("sessions")` is `False`
- **WHEN** `dual_write_messages()` is called
- **THEN** no PostgreSQL writes occur
- **THEN** the method returns without error

#### Scenario: Invalid session ID format
- **WHEN** `dual_write_messages("invalid-id", ...)` is called
- **THEN** the method logs a warning and returns without error
- **THEN** no PostgreSQL writes occur

### Requirement: ConversationNodes delegates dual-write to ChatHistoryService
`ConversationNodes.memory_persist_node()` SHALL NOT contain inline PostgreSQL dual-write logic. Instead, it SHALL call `chat_history_service.dual_write_messages()` to persist messages to PostgreSQL when dual-write is enabled.

#### Scenario: LangGraph message persistence uses ChatHistoryService
- **WHEN** `memory_persist_node()` persists a conversation turn
- **WHEN** dual-write is enabled for sessions
- **THEN** the method calls `chat_history_service.dual_write_messages()` with the session ID, patient ID, user message, and assistant message
- **THEN** no inline imports of `MessageRepository`, `SessionRepository`, or `db_session` exist in the method

#### Scenario: No ChatHistoryService available
- **WHEN** `memory_persist_node()` runs without a chat_history_service reference
- **THEN** PostgreSQL dual-write is skipped silently
- **THEN** Neo4j memory persistence still completes normally

### Requirement: DocumentService uses injected db_session_factory
`DocumentService.__init__()` SHALL accept an optional `db_session_factory` parameter (an async context manager that yields `AsyncSession`). The `_dual_write_to_postgres()` method SHALL use this factory instead of importing `db_session` directly from `infrastructure.database.session`.

#### Scenario: DocumentService with injected factory
- **WHEN** `DocumentService` is created with a `db_session_factory`
- **WHEN** `_dual_write_to_postgres()` is called
- **THEN** the method uses the injected factory to create a database session
- **THEN** no direct import of `infrastructure.database.session.db_session` occurs

#### Scenario: DocumentService without factory
- **WHEN** `DocumentService` is created without `db_session_factory`
- **WHEN** `_dual_write_to_postgres()` is called
- **THEN** the method returns `False` without attempting a write
- **THEN** no import of `infrastructure.database.session` occurs

### Requirement: DualWriteHealthService encapsulates health check logic
A `DualWriteHealthService` class SHALL exist in `src/application/services/dual_write_health_service.py`. It SHALL accept `kg_backend` and `db_session_factory` via constructor. It SHALL provide a `get_health()` method that returns the same response shape as the current inline health check endpoint.

#### Scenario: Health check returns data type breakdown
- **WHEN** `get_health()` is called with a valid kg_backend and db_session_factory
- **THEN** the response includes `status`, `data_types`, `sync_issues`, and `recommendations`
- **THEN** `data_types` contains entries for "sessions", "feedback", and "documents"
- **THEN** each entry includes `dual_write_enabled`, `use_postgres`, `neo4j_count`, `postgres_count`, and `sync_status`

#### Scenario: Health check without PostgreSQL
- **WHEN** `get_health()` is called with `db_session_factory=None`
- **THEN** PostgreSQL counts are reported as 0
- **THEN** sync status reflects available data only

#### Scenario: Main.py endpoint delegates to service
- **WHEN** `GET /api/admin/dual-write-health` is called
- **THEN** the endpoint creates/uses a `DualWriteHealthService` instance and calls `get_health()`
- **THEN** no inline health check logic remains in main.py
