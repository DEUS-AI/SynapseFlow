## Why

Feedback reads currently operate from an in-memory list in `FeedbackTracerService`, with a fallback to Neo4j. This means feedback data is process-local (lost on restart, invisible across instances) and doesn't use the PostgreSQL infrastructure that's already in place from the dual-write work. The `FeedbackRepository` has read methods (`get_statistics`, `get_preference_pairs`, `get_for_training`) that were built during dual-write but are never called. Wiring up the read path completes the feedback migration and brings it to parity with the sessions data type.

## What Changes

- `FeedbackTracerService` gains a `db_session_factory` parameter and PostgreSQL read methods, following the same pattern as `ChatHistoryService`
- Three public read methods (`get_feedback_statistics`, `get_preference_pairs`, `get_correction_examples`) gain flag-based routing to PostgreSQL when `use_postgres_feedback` is enabled
- `get_feedback_service()` in `main.py` passes the `db_session_factory` to the service
- The feedback dual-write function (`_dual_write_feedback_to_postgres`) is moved from `main.py` into `FeedbackTracerService` for consistency with how sessions handle dual-writes

## Capabilities

### New Capabilities
- `postgres-feedback-reads`: PostgreSQL read path for feedback data, controlled by the existing `use_postgres_feedback` feature flag

### Modified Capabilities
- `postgres-session-storage`: No requirement changes — this change follows the same pattern established there

## Impact

- **Code**: `feedback_tracer.py` (~100-150 lines added), `main.py` (service init update, dual-write function relocated)
- **APIs**: No endpoint signature changes — same endpoints, same response shapes, different data source when flag is on
- **Dependencies**: No new dependencies — uses existing `FeedbackRepository`, `db_session`, and feature flag infrastructure
- **Risk**: Low — behind feature flag, existing read behavior unchanged when flag is off
