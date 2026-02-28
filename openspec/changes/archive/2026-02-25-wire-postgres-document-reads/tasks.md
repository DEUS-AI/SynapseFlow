## 1. Feature Flag & Plumbing

- [x] 1.1 Add `use_postgres_documents()` helper function to `feature_flag_service.py`
- [x] 1.2 Pass `db_session_factory` to the document router during app startup in `main.py`

## 2. Repository Methods

- [x] 2.1 Add `list_filtered(status, category, search, limit)` to `DocumentRepository`
- [x] 2.2 Add `get_categories()` to `DocumentRepository`
- [x] 2.3 Add `get_full_statistics()` to `DocumentRepository` (total, per-status counts, entity/relationship sums, markdown count)

## 3. Router Read Path Routing

- [x] 3.1 Add PostgreSQL routing to `GET /api/admin/documents` (list endpoint)
- [x] 3.2 Add PostgreSQL routing to `GET /api/admin/documents/categories`
- [x] 3.3 Add PostgreSQL routing to `GET /api/admin/documents/statistics`
- [x] 3.4 Add PostgreSQL routing to `GET /api/admin/documents/{doc_id}` (detail endpoint, with filesystem markdown preview)

## 4. Verify

- [x] 4.1 Verify existing tests still pass with flag off
- [x] 4.2 Verify DocumentRepository methods return fields matching DocumentTracker response shape
