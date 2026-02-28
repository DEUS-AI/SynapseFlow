## 1. Feedback Write Encapsulation

- [x] 1.1 Add `dual_write_to_postgres()` call inside `FeedbackTracerService.submit_feedback()` (non-blocking, try/except with warning log)
- [x] 1.2 Remove explicit `dual_write_to_postgres()` calls from `submit_feedback` endpoint in main.py
- [x] 1.3 Remove explicit `dual_write_to_postgres()` call from `submit_thumbs_feedback` endpoint in main.py

## 2. ConversationNodes Delegation

- [x] 2.1 Add `dual_write_messages(session_id, patient_id, user_msg, assistant_msg)` public method to ChatHistoryService
- [x] 2.2 Wire ChatHistoryService reference into ConversationNodes (constructor or setter)
- [x] 2.3 Replace inline dual-write block in `memory_persist_node()` with call to `chat_history_service.dual_write_messages()`

## 3. DocumentService Factory Injection

- [x] 3.1 Add `db_session_factory` parameter to `DocumentService.__init__()` and store as `self._db_session`
- [x] 3.2 Refactor `_dual_write_to_postgres()` to use `self._db_session` instead of hardcoded `db_session()` import
- [x] 3.3 Wire `db_session_factory` into DocumentService during startup in main.py (or wherever it's constructed)

## 4. Health Check Extraction

- [x] 4.1 Create `src/application/services/dual_write_health_service.py` with `DualWriteHealthService` class (accepts `kg_backend` and `db_session_factory`)
- [x] 4.2 Move `_compute_sync_status()` and all per-data-type health logic into `DualWriteHealthService.get_health()`
- [x] 4.3 Replace inline health check in main.py with a call to `DualWriteHealthService.get_health()`

## 5. Verify

- [x] 5.1 Run existing tests to confirm no regressions with flags off
- [x] 5.2 Verify feedback tests still pass (dual-write encapsulated inside submit_feedback)
- [x] 5.3 Verify ConversationNodes no longer imports MessageRepository, SessionRepository, or db_session directly
