## 1. Service Constructor & Plumbing

- [x] 1.1 Add `db_session_factory` parameter to `FeedbackTracerService.__init__()` and `_has_postgres` property
- [x] 1.2 Update `get_feedback_service()` in `main.py` to pass `db_session_factory` when PostgreSQL is initialized

## 2. PostgreSQL Read Methods

- [x] 2.1 Add `_get_statistics_postgres()` that calls `FeedbackRepository.get_statistics()` and maps result to `FeedbackStatistics`
- [x] 2.2 Add `_get_preference_pairs_postgres()` that calls `FeedbackRepository.get_preference_pairs()`
- [x] 2.3 Add `_get_correction_examples_postgres()` that queries feedback with non-null `correction_text`

## 3. Read Path Routing

- [x] 3.1 Add `use_postgres_feedback` flag check in `get_feedback_statistics()` to route to PostgreSQL read method
- [x] 3.2 Add `use_postgres_feedback` flag check in `get_preference_pairs()` to route to PostgreSQL read method
- [x] 3.3 Add `use_postgres_feedback` flag check in `get_correction_examples()` to route to PostgreSQL read method

## 4. Consolidate Dual-Write

- [x] 4.1 Move `_dual_write_feedback_to_postgres()` from `main.py` into `FeedbackTracerService` as a method
- [x] 4.2 Update call sites in `main.py` (`submit_feedback` and `submit_simple_feedback`) to use the service method

## 5. Verify

- [x] 5.1 Verify existing tests still pass with flag off (no behavior change)
- [x] 5.2 Verify `FeedbackRepository` read methods return all fields needed by domain types
