## Why

Dual-write logic for the Neo4j-to-PostgreSQL migration is scattered across 4 files with 3 different patterns. Sessions encapsulate dual-write inside ChatHistoryService, feedback calls dual-write explicitly from API endpoints, documents use a hardcoded `db_session()` instead of an injected factory, and ConversationNodes duplicates session dual-write logic entirely. This inconsistency increases the risk of data drift and makes the eventual Neo4j deprecation harder.

## What Changes

- Extract a `DualWriteMixin` that provides `_has_postgres`, `_db_session`, and a guarded `_with_pg_session()` context manager — eliminating per-service boilerplate
- Move feedback dual-write call from main.py endpoints into `FeedbackTracerService.submit_feedback()` so the service owns the full write path (matching ChatHistoryService)
- Refactor `DocumentService._dual_write_to_postgres()` to use an injected `db_session_factory` instead of hardcoded `db_session()`, and wire it from main.py startup
- Replace the inline dual-write in `ConversationNodes.memory_persist_node()` with a call to ChatHistoryService, removing ~35 lines of duplicated session/message write logic
- Move the dual-write health check from an inline function in main.py into a dedicated `DualWriteHealthService` with proper repository access

## Capabilities

### New Capabilities
- `dual-write-consolidation`: Standardized dual-write mixin, encapsulated write paths, and health service

### Modified Capabilities

## Impact

- `src/application/services/chat_history_service.py` — adopt mixin, no behavior change
- `src/application/services/feedback_tracer.py` — adopt mixin, encapsulate dual-write inside `submit_feedback()`
- `src/application/services/document_service.py` — adopt mixin, switch from hardcoded `db_session()` to injected factory
- `src/application/services/conversation_nodes.py` — remove inline dual-write, delegate to ChatHistoryService
- `src/application/api/main.py` — remove explicit dual-write calls from feedback endpoints, extract health check, wire document service factory
- No API contract changes; all endpoints return the same responses
