## ADDED Requirements

### Requirement: use_postgres_documents feature flag helper
A `use_postgres_documents()` helper function SHALL exist in `feature_flag_service.py` that returns `True` when the `use_postgres_documents` feature flag is enabled. This follows the same pattern as `use_postgres_sessions()` and `use_postgres_feedback()`.

#### Scenario: Helper returns flag state
- **WHEN** `FEATURE_FLAG_USE_POSTGRES_DOCUMENTS=true` is set in the environment
- **THEN** `use_postgres_documents()` returns `True`

#### Scenario: Helper returns default when not set
- **WHEN** no environment override or database flag exists for `use_postgres_documents`
- **THEN** `use_postgres_documents()` returns `False` (the configured default)

### Requirement: DocumentRepository supports filtered listing
`DocumentRepository` SHALL provide a `list_filtered(status, category, search, limit)` method that returns documents matching optional filters. The `search` parameter SHALL match against `filename` using case-insensitive `ILIKE`. Results SHALL be ordered by `created_at` descending.

#### Scenario: Filter by status
- **WHEN** `list_filtered(status="completed")` is called
- **THEN** only documents with `status = "completed"` are returned
- **THEN** results are ordered by `created_at` descending

#### Scenario: Filter by category and search
- **WHEN** `list_filtered(category="medical", search="kidney")` is called
- **THEN** only documents with `category = "medical"` and `filename ILIKE '%kidney%'` are returned

#### Scenario: No filters
- **WHEN** `list_filtered()` is called with no filters
- **THEN** all documents are returned up to the limit, ordered by `created_at` descending

### Requirement: DocumentRepository supports category listing
`DocumentRepository` SHALL provide a `get_categories()` method that returns a sorted list of distinct non-null category values from the documents table.

#### Scenario: Multiple categories exist
- **WHEN** documents exist with categories "medical", "legal", "general"
- **THEN** `get_categories()` returns `["general", "legal", "medical"]`

#### Scenario: No documents
- **WHEN** no documents exist in the table
- **THEN** `get_categories()` returns an empty list

### Requirement: DocumentRepository supports full statistics
`DocumentRepository` SHALL provide a `get_full_statistics()` method that returns a dictionary with: `total` count, counts per status (`not_started`, `processing`, `completed`, `failed`), `total_entities` (sum of entity_count), `total_relationships` (sum of relationship_count), and `with_markdown` (count where markdown_path is not null).

#### Scenario: Mixed document statuses
- **WHEN** 3 completed, 2 processing, 1 failed documents exist with total 50 entities and 30 relationships
- **THEN** `get_full_statistics()` returns `{"total": 6, "completed": 3, "processing": 2, "failed": 1, "not_started": 0, "total_entities": 50, "total_relationships": 30, "with_markdown": ...}`

### Requirement: Document list endpoint reads from PostgreSQL when flag enabled
When `use_postgres_documents` is enabled and PostgreSQL is available, `GET /api/admin/documents` SHALL read document metadata from PostgreSQL via `DocumentRepository.list_filtered()` instead of `DocumentTracker.list_documents()`. The response shape SHALL be identical.

#### Scenario: List from PostgreSQL
- **WHEN** `use_postgres_documents` is `True` and PostgreSQL is initialized
- **WHEN** `GET /api/admin/documents?status=completed` is called
- **THEN** the endpoint queries PostgreSQL for documents with status "completed"
- **THEN** the response contains the same fields as the DocumentTracker-based response

#### Scenario: Fallback to DocumentTracker
- **WHEN** `use_postgres_documents` is `False`
- **WHEN** `GET /api/admin/documents` is called
- **THEN** the endpoint uses `DocumentTracker.list_documents()` (existing behavior unchanged)

### Requirement: Document categories endpoint reads from PostgreSQL when flag enabled
When `use_postgres_documents` is enabled, `GET /api/admin/documents/categories` SHALL read from PostgreSQL via `DocumentRepository.get_categories()`.

#### Scenario: Categories from PostgreSQL
- **WHEN** `use_postgres_documents` is `True`
- **THEN** categories are loaded from PostgreSQL
- **THEN** the response is a sorted list of distinct category strings

### Requirement: Document statistics endpoint reads from PostgreSQL when flag enabled
When `use_postgres_documents` is enabled, `GET /api/admin/documents/statistics` SHALL read from PostgreSQL via `DocumentRepository.get_full_statistics()`.

#### Scenario: Statistics from PostgreSQL
- **WHEN** `use_postgres_documents` is `True`
- **THEN** statistics are computed from PostgreSQL aggregations
- **THEN** the response contains `total`, `not_started`, `processing`, `completed`, `failed`, `total_entities`, `total_relationships`, `with_markdown`

### Requirement: Document detail endpoint reads metadata from PostgreSQL when flag enabled
When `use_postgres_documents` is enabled, `GET /api/admin/documents/{doc_id}` SHALL read document metadata from PostgreSQL via `DocumentRepository.get_by_external_id()`. The markdown preview SHALL still be read from the filesystem using the `markdown_path` stored in the PostgreSQL record.

#### Scenario: Detail from PostgreSQL with markdown preview
- **WHEN** `use_postgres_documents` is `True`
- **WHEN** `GET /api/admin/documents/{doc_id}` is called for a completed document
- **THEN** metadata (filename, status, category, counts) comes from PostgreSQL
- **THEN** markdown preview (first 2000 chars) comes from the filesystem path stored in the PG record

#### Scenario: Document not found in PostgreSQL
- **WHEN** `use_postgres_documents` is `True`
- **WHEN** the document ID does not exist in PostgreSQL
- **THEN** the endpoint returns 404

### Requirement: Document router receives db_session_factory
The document router SHALL accept a `db_session_factory` parameter during initialization so that endpoints can create PostgreSQL sessions for reads. This follows the same pattern as `ChatHistoryService`.

#### Scenario: Router initialized with PostgreSQL
- **WHEN** PostgreSQL is initialized at startup
- **THEN** the document router receives a valid `db_session_factory`
- **THEN** endpoints can use it for PostgreSQL reads when the flag is enabled

#### Scenario: Router initialized without PostgreSQL
- **WHEN** PostgreSQL is not available
- **THEN** the document router receives `None` as `db_session_factory`
- **THEN** all endpoints use `DocumentTracker` regardless of flag state
