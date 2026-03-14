## ADDED Requirements

### Requirement: DocumentRepository replaces JSON tracker
The system SHALL use `DocumentRepository` (backed by the Postgres `documents` table) as the single source of truth for document tracking. The `DocumentTracker` class and `document_tracking.json` file SHALL be removed.

#### Scenario: Document registration in Postgres
- **WHEN** a new document is uploaded
- **THEN** a record is created in the `documents` table with filename, category, size, status, and storage key

#### Scenario: No JSON tracking file used
- **WHEN** the backend starts
- **THEN** it SHALL NOT read from or write to `data/document_tracking.json`

### Requirement: DocumentRepository has tracking methods
The `DocumentRepository` SHALL provide the following methods (in addition to existing CRUD):
- `register_document(filename, category, size_bytes, storage_key) -> Document`
- `update_status(doc_id, status, error_message=None) -> Document`
- `list_by_status(status) -> List[Document]`
- `get_by_external_id(external_id) -> Optional[Document]`
- `update_ingestion_results(doc_id, entity_count, relationship_count, markdown_key) -> Document`

#### Scenario: Register new document
- **WHEN** `register_document("paper.pdf", "research", 1024000, "research/abc123/paper.pdf")` is called
- **THEN** a new row is created in the `documents` table with `status="pending"` and the given storage key stored in `source_path`

#### Scenario: Update document status
- **WHEN** `update_status(doc_id, "completed")` is called
- **THEN** the document's status is updated and `updated_at` is refreshed

#### Scenario: List pending documents
- **WHEN** `list_by_status("pending")` is called
- **THEN** all documents with `status="pending"` are returned

### Requirement: Document model stores storage keys
The `Document` model's `source_path` column SHALL store the blob storage key (e.g., `general/abc123/file.pdf`) instead of a local filesystem path. The `markdown_path` column SHALL store the markdown blob key.

#### Scenario: Source path is storage key
- **WHEN** a document is registered after upload
- **THEN** `source_path` contains the storage key, not a local path like `/app/PDFs/file.pdf`

### Requirement: document_router uses Postgres tracking
All document management endpoints in `document_router.py` SHALL use `DocumentRepository` instead of `DocumentTracker` for document listing, status queries, and updates.

#### Scenario: List documents from Postgres
- **WHEN** `GET /api/documents` is called
- **THEN** documents are queried from Postgres via `DocumentRepository`, not from JSON file

#### Scenario: Document status updates go to Postgres
- **WHEN** ingestion completes or fails
- **THEN** the document status is updated via `DocumentRepository.update_status()`
