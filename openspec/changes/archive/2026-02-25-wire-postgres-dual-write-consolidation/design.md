## Context

The Neo4j-to-PostgreSQL migration uses a dual-write strategy controlled by feature flags. Three data types are migrating: sessions, feedback, and documents. Each evolved independently, resulting in inconsistent patterns:

| Data type | Write encapsulation | Factory injection | Duplication |
|-----------|-------------------|-------------------|-------------|
| Sessions | Inside ChatHistoryService | Yes (`db_session_factory`) | ConversationNodes duplicates write logic |
| Feedback | Explicit in main.py endpoints | Yes (`db_session_factory`) | None |
| Documents | Inside DocumentService | No (hardcoded `db_session()`) | None |

The health check endpoint (~180 lines in main.py) uses hardcoded `db_session()` calls and repeated boilerplate for each data type.

## Goals / Non-Goals

**Goals:**
- Encapsulate all dual-write logic inside service methods so API endpoints never call dual-write directly
- Standardize on injected `db_session_factory` for all services (no hardcoded `db_session()`)
- Remove duplicated session dual-write from ConversationNodes
- Extract health check into a dedicated service with injected dependencies

**Non-Goals:**
- Creating a shared base class or mixin — the boilerplate (`_has_postgres`, `_db_session`) is 4 lines per service and doesn't justify an inheritance hierarchy
- Changing read-path routing (already consolidated in previous changes)
- Modifying feature flag definitions or API response shapes
- Migrating write operations off Neo4j (that's the next phase)

## Decisions

### D1: No shared mixin — keep per-service pattern

**Decision:** Keep `_has_postgres` and `_db_session` as per-service fields rather than extracting a mixin.

**Rationale:** The duplication is minimal (4 lines per service). A mixin adds indirection and a new import chain for marginal DRY benefit. Each service has different constructor signatures and domain concerns. The three services are likely to diverge further as Neo4j is deprecated for different data types on different timelines.

**Alternative considered:** `DualWriteMixin` base class. Rejected because it couples unrelated services and the effort exceeds the benefit for 3 consumers.

### D2: Feedback dual-write moves into submit_feedback()

**Decision:** Move the `dual_write_to_postgres()` call inside `FeedbackTracerService.submit_feedback()` so the service owns the complete write path, matching ChatHistoryService.

**Rationale:** Currently main.py calls `submit_feedback()` then separately calls `dual_write_to_postgres()`. This means the service doesn't know if dual-write was attempted. Encapsulating it makes the write atomic from the caller's perspective and reduces main.py responsibilities.

The existing `dual_write_to_postgres()` public method stays as-is (it's already there). We just add a call to it at the end of `submit_feedback()`.

### D3: ConversationNodes delegates to ChatHistoryService

**Decision:** Replace the ~35 lines of inline dual-write in `memory_persist_node()` with a call to `ChatHistoryService._store_message_postgres()`.

**Rationale:** ConversationNodes already has access to a chat_history_service (or can receive one). The inline code duplicates session/message creation logic, uses its own UUID extraction, and calls `increment_message_count` twice instead of once. Delegating eliminates this duplication and ensures message creation goes through one code path.

**Approach:** ConversationNodes will call a new public method `chat_history_service.dual_write_messages(session_id, patient_id, user_msg, assistant_msg)` that encapsulates the PostgreSQL write. This avoids exposing private `_store_message_postgres`.

### D4: DocumentService uses injected db_session_factory

**Decision:** Replace hardcoded `from infrastructure.database.session import db_session` inside `DocumentService._dual_write_to_postgres()` with a `db_session_factory` parameter on the constructor, following the ChatHistoryService pattern.

**Rationale:** Hardcoded imports make DocumentService untestable without a running PostgreSQL instance. Injecting the factory allows mocking and is consistent with other services.

### D5: Health check extracted to DualWriteHealthService

**Decision:** Extract the ~180-line health check from main.py into `src/application/services/dual_write_health_service.py`. The service accepts `kg_backend` and `db_session_factory` via constructor. Main.py calls `service.get_health()`.

**Rationale:** The inline health check mixes infrastructure imports, Neo4j Cypher queries, repository calls, and business logic. Extracting it into a service makes it testable and reduces main.py complexity.

## Risks / Trade-offs

**[Feedback submit_feedback encapsulation]** → Adding dual-write inside `submit_feedback()` changes behavior: previously if the endpoint forgot to call dual-write, no PG write happened; now it always happens. This is the desired behavior but needs care to ensure the dual-write failure is still non-blocking (fire-and-forget with logging).

**[ConversationNodes delegation]** → ConversationNodes must now have a reference to ChatHistoryService. If this creates a circular dependency, we can use a thin callback function instead of a direct service reference. Risk is low since ConversationNodes is already initialized after ChatHistoryService.

**[DocumentService factory injection]** → Existing code that creates DocumentService without passing `db_session_factory` will still work (parameter is optional, defaults to None). No breaking change.
