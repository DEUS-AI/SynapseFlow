## ADDED Requirements

### Requirement: FeedbackTracerService accepts PostgreSQL session factory
`FeedbackTracerService.__init__()` SHALL accept an optional `db_session_factory` parameter (an async context manager that yields `AsyncSession`). When provided, the service SHALL expose a `_has_postgres` property that returns `True`. When not provided, all read behavior SHALL remain unchanged (in-memory + Neo4j fallback).

#### Scenario: Service initialized with PostgreSQL support
- **WHEN** `FeedbackTracerService` is created with a valid `db_session_factory`
- **THEN** `service._has_postgres` returns `True`
- **THEN** the service logs that PostgreSQL support is available

#### Scenario: Service initialized without PostgreSQL
- **WHEN** `FeedbackTracerService` is created without `db_session_factory`
- **THEN** `service._has_postgres` returns `False`
- **THEN** all read methods use in-memory + Neo4j fallback (existing behavior)

### Requirement: Feedback statistics read from PostgreSQL when flag enabled
When `use_postgres_feedback` feature flag is enabled and PostgreSQL is available, `get_feedback_statistics()` SHALL read from PostgreSQL via `FeedbackRepository.get_statistics()` instead of the in-memory list. The returned `FeedbackStatistics` object SHALL contain the same fields as the existing in-memory implementation.

#### Scenario: Statistics from PostgreSQL
- **WHEN** `use_postgres_feedback` is `True` and `_has_postgres` is `True`
- **WHEN** `get_feedback_statistics()` is called
- **THEN** the method queries PostgreSQL via `FeedbackRepository.get_statistics()`
- **THEN** the returned `FeedbackStatistics` includes `total_count`, `average_rating`, `rating_distribution`, and `feedback_type_distribution`

#### Scenario: Statistics fallback to in-memory when flag off
- **WHEN** `use_postgres_feedback` is `False`
- **WHEN** `get_feedback_statistics()` is called
- **THEN** the method uses the existing in-memory calculation (no change)

### Requirement: Preference pairs read from PostgreSQL when flag enabled
When `use_postgres_feedback` feature flag is enabled and PostgreSQL is available, `get_preference_pairs()` SHALL read from PostgreSQL via `FeedbackRepository.get_preference_pairs()`. The returned list SHALL contain the same dict structure as the existing in-memory implementation.

#### Scenario: Preference pairs from PostgreSQL
- **WHEN** `use_postgres_feedback` is `True` and `_has_postgres` is `True`
- **WHEN** `get_preference_pairs(min_rating_gap=2, limit=100)` is called
- **THEN** the method queries PostgreSQL for feedback pairs where rating difference >= `min_rating_gap`
- **THEN** results are returned as a list of dicts with `chosen`, `rejected`, `query`, and `rating_gap` keys

#### Scenario: Preference pairs fallback when flag off
- **WHEN** `use_postgres_feedback` is `False`
- **WHEN** `get_preference_pairs()` is called
- **THEN** the method uses the existing in-memory preference pairs (no change)

### Requirement: Correction examples read from PostgreSQL when flag enabled
When `use_postgres_feedback` feature flag is enabled and PostgreSQL is available, `get_correction_examples()` SHALL read from PostgreSQL, filtering feedback records that have non-null `correction_text`. The returned list SHALL contain the same dict structure as the existing in-memory implementation.

#### Scenario: Corrections from PostgreSQL
- **WHEN** `use_postgres_feedback` is `True` and `_has_postgres` is `True`
- **WHEN** `get_correction_examples(feedback_type=None, limit=50)` is called
- **THEN** the method queries PostgreSQL for feedback with non-null `correction_text`
- **THEN** results are filtered by `feedback_type` if provided
- **THEN** results are returned as a list of dicts with `query`, `original_response`, `correction`, and `feedback_type` keys

#### Scenario: Corrections fallback when flag off
- **WHEN** `use_postgres_feedback` is `False`
- **WHEN** `get_correction_examples()` is called
- **THEN** the method uses the existing in-memory filtering (no change)

### Requirement: Feedback service initialization passes db_session_factory
The `get_feedback_service()` factory function in `main.py` SHALL pass `db_session_factory` to `FeedbackTracerService` when PostgreSQL is initialized, following the same pattern as `ChatHistoryService` initialization. The factory SHALL check `is_initialized()` from `infrastructure.database.session` and pass `db_session` if available.

#### Scenario: Feedback service gets PostgreSQL access
- **WHEN** PostgreSQL is initialized at application startup
- **WHEN** `get_feedback_service()` is called for the first time
- **THEN** the `FeedbackTracerService` instance has `_has_postgres == True`

#### Scenario: Feedback service without PostgreSQL
- **WHEN** PostgreSQL is not available at startup
- **WHEN** `get_feedback_service()` is called
- **THEN** the `FeedbackTracerService` instance has `_has_postgres == False`
- **THEN** all feedback operations work using existing Neo4j/in-memory paths

### Requirement: Dual-write feedback function moves into FeedbackTracerService
The `_dual_write_feedback_to_postgres()` function in `main.py` SHALL be moved into `FeedbackTracerService` as a method. Call sites in `main.py` (submit_feedback and submit_simple_feedback endpoints) SHALL call the service method instead of the free function. The method SHALL check `dual_write_enabled("feedback")` and `_has_postgres` before writing.

#### Scenario: Dual-write via service method
- **WHEN** `dual_write_feedback` flag is enabled and `_has_postgres` is `True`
- **WHEN** feedback is submitted via `POST /api/feedback`
- **THEN** the feedback is written to PostgreSQL via the service method
- **THEN** the behavior is identical to the previous free function

#### Scenario: Dual-write disabled
- **WHEN** `dual_write_feedback` flag is disabled
- **WHEN** feedback is submitted
- **THEN** no PostgreSQL write occurs (same as before)
