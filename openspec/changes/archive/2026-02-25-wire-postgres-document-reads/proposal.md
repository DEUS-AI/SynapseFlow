## Why

Document metadata reads currently come from a JSON file (`data/document_tracking.json`) via `DocumentTracker`. This works for a single instance but doesn't scale: the JSON file is process-local, has no concurrent access safety, and re-scans the filesystem on every list/stats call. PostgreSQL dual-write for documents already exists (`DocumentService.dual_write_document_to_postgres`), and `DocumentRepository` has read methods that are never called. Wiring up the read path completes the document migration to parity with sessions and feedback.

Not all document endpoints can move — content reads (markdown files), graph queries (Neo4j entities/relationships), and job tracking (in-memory) stay as-is. This change only migrates the **metadata tracking layer**: listing, filtering, statistics, and detail lookups.

## What Changes

- Document router endpoints (`/api/admin/documents`, `/categories`, `/statistics`, `/{id}`) gain flag-based routing to PostgreSQL when `use_postgres_documents` is enabled
- `DocumentRepository` gains missing read methods: `list_filtered()` (status/category/search), `get_categories()`, `get_full_statistics()`
- A `use_postgres_documents()` helper is added to `feature_flag_service.py`
- The document router receives a `db_session_factory` for PostgreSQL access
- The `DocumentTracker` remains as the fallback when the flag is off (no removal)

## Capabilities

### New Capabilities
- `postgres-document-reads`: PostgreSQL read path for document metadata, controlled by the `use_postgres_documents` feature flag

### Modified Capabilities

## Impact

- **Code**: `document_router.py` (routing logic in ~4-5 endpoints), `repositories.py` (2-3 new query methods), `feature_flag_service.py` (1 helper function)
- **APIs**: No endpoint signature changes — same endpoints, same response shapes
- **Dependencies**: No new dependencies
- **Boundaries**: Content reads (filesystem), entity/graph queries (Neo4j), job tracking (in-memory) are explicitly out of scope
- **Risk**: Low — behind feature flag, JSON tracker remains as fallback
