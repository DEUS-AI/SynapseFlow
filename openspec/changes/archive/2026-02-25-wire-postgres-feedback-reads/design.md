## Context

Feedback data follows a three-phase migration path (dual-write → read switch → Neo4j deprecation), matching the pattern established for sessions. Sessions completed all three phases. Feedback is stuck at phase 1: dual-write works, but reads still come from an in-memory list in `FeedbackTracerService` with a Neo4j fallback.

The PostgreSQL `FeedbackRepository` already has read methods (`get_statistics`, `get_preference_pairs`, `get_for_training`) that were built during dual-write but are never called from any endpoint.

The `ChatHistoryService` provides a proven pattern: constructor accepts `db_session_factory`, each read method checks `use_postgres_*()` flag and routes to a `_method_postgres()` private method.

## Goals / Non-Goals

**Goals:**
- Wire up PostgreSQL read path for all feedback read operations
- Follow the established ChatHistoryService pattern for consistency
- Move the dual-write feedback function from `main.py` into `FeedbackTracerService`
- Enable the existing `use_postgres_feedback` feature flag to control read routing

**Non-Goals:**
- Adding new feedback query capabilities (filter by patient, date range, etc.)
- Changing the feedback write path or Neo4j storage
- Migrating feedback Neo4j data to PostgreSQL (that's the sync script's job)
- Modifying the `FeedbackRepository` read methods (they already work)

## Decisions

### Decision 1: Follow ChatHistoryService pattern exactly

Add `db_session_factory` to `FeedbackTracerService.__init__()` and route reads via `_has_postgres` property + `use_postgres_feedback()` flag check.

**Alternative considered:** Create a new `FeedbackReadService` that wraps the repository. Rejected because it adds a new class for no reason — the existing service already owns these methods.

### Decision 2: Move `_dual_write_feedback_to_postgres()` into the service

Currently this is a free function at `main.py:1835`. Moving it into `FeedbackTracerService` as a private method makes it consistent with how `ChatHistoryService._store_message_postgres()` works and keeps all feedback persistence logic in one place.

The two call sites in `main.py` (lines ~1953 and ~2040) change from calling the free function to calling `feedback_service._dual_write_to_postgres(...)` or a public method on the service.

**Alternative considered:** Leave it in `main.py`. Rejected because it creates an inconsistent pattern — sessions dual-write lives in the service, feedback dual-write lives in the API layer.

### Decision 3: Map repository return types to existing domain types

`FeedbackRepository.get_statistics()` returns a dict. The public method `get_feedback_statistics()` returns `FeedbackStatistics`. The PostgreSQL read method needs to map between these. This mapping lives in the private `_get_statistics_postgres()` method, not in the repository.

### Decision 4: Keep in-memory fallback as third tier

When `use_postgres_feedback` is off, behavior is unchanged (in-memory + Neo4j fallback). When it's on, PostgreSQL is the source. The in-memory list continues to be populated by writes regardless of the read flag — this means switching the flag back to off still works.

## Risks / Trade-offs

- **[Risk] Repository methods may not return all fields needed by domain types** → Mitigation: Verify `FeedbackRepository.get_statistics()` output matches `FeedbackStatistics` fields during implementation. Add missing fields to the SQL query if needed.

- **[Risk] Moving dual-write function changes call sites in main.py** → Mitigation: Two call sites, both straightforward. The service instance is already available at both locations via `get_feedback_service()`.

- **[Trade-off] In-memory list becomes redundant when PG reads are on** → Acceptable. It still serves as write-through cache and the fallback path. Can be removed in a future cleanup.
