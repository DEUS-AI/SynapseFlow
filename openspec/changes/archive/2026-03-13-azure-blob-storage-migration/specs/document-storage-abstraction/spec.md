## ADDED Requirements

### Requirement: DocumentStorage protocol
The system SHALL define a `DocumentStorage` Protocol at `src/infrastructure/document_storage.py` with the following methods:
- `async upload(container: str, key: str, data: bytes, content_type: str) -> str` — returns the storage key
- `async download(container: str, key: str) -> bytes` — returns file content
- `async exists(container: str, key: str) -> bool`
- `async delete(container: str, key: str) -> None`
- `async list_keys(container: str, prefix: str) -> List[str]`

#### Scenario: Protocol defines storage contract
- **WHEN** a new storage backend is implemented
- **THEN** it SHALL implement all methods of the `DocumentStorage` protocol

### Requirement: Local filesystem implementation
The system SHALL provide `LocalDocumentStorage` that implements `DocumentStorage` using the local filesystem. Container maps to a subdirectory, key maps to a file path within it.

#### Scenario: Upload file locally
- **WHEN** `upload("documents", "general/doc1/file.pdf", data, "application/pdf")` is called
- **THEN** the file is written to `{base_dir}/documents/general/doc1/file.pdf`

#### Scenario: Download file locally
- **WHEN** `download("documents", "general/doc1/file.pdf")` is called
- **THEN** the file bytes are returned from `{base_dir}/documents/general/doc1/file.pdf`

#### Scenario: File not found locally
- **WHEN** `download("documents", "nonexistent.pdf")` is called
- **THEN** a `FileNotFoundError` is raised

### Requirement: Azure Blob Storage implementation
The system SHALL provide `BlobDocumentStorage` that implements `DocumentStorage` using `azure-storage-blob` SDK. Container maps to a blob container, key maps to the blob name.

#### Scenario: Upload file to blob
- **WHEN** `upload("documents", "general/doc1/file.pdf", data, "application/pdf")` is called
- **THEN** a blob is created in the `documents` container with name `general/doc1/file.pdf`

#### Scenario: Download file from blob
- **WHEN** `download("documents", "general/doc1/file.pdf")` is called
- **THEN** the blob content is returned

#### Scenario: Blob not found
- **WHEN** `download("documents", "nonexistent.pdf")` is called
- **THEN** a `FileNotFoundError` is raised

### Requirement: Storage backend selection
The system SHALL select the storage backend based on the `DOCUMENT_STORAGE_BACKEND` environment variable:
- `local` (default): Use `LocalDocumentStorage`
- `blob`: Use `BlobDocumentStorage` with connection string from `AZURE_STORAGE_CONNECTION_STRING`

#### Scenario: Local backend selected
- **WHEN** `DOCUMENT_STORAGE_BACKEND` is unset or set to `local`
- **THEN** `LocalDocumentStorage` is used

#### Scenario: Blob backend selected
- **WHEN** `DOCUMENT_STORAGE_BACKEND` is set to `blob`
- **THEN** `BlobDocumentStorage` is initialized with the connection string

### Requirement: Document upload uses storage abstraction
The `POST /api/documents/upload` endpoint SHALL write uploaded PDF files to the `documents` container via `DocumentStorage` instead of writing directly to the local filesystem.

The storage key SHALL be `{category}/{doc_id}/{filename}`.

#### Scenario: Upload stores file in storage backend
- **WHEN** a PDF is uploaded via the API
- **THEN** the file is stored via `DocumentStorage.upload()` with the correct container and key

### Requirement: Ingestion reads from storage abstraction
The ingestion pipeline SHALL read PDF source files from `DocumentStorage` instead of the local filesystem.

#### Scenario: Ingestion reads PDF from storage
- **WHEN** a document ingestion is triggered
- **THEN** the PDF is read from `DocumentStorage.download("documents", key)` rather than from a local file path

### Requirement: Markdown output uses storage abstraction
The ingestion pipeline SHALL write processed markdown to the `markdown` container via `DocumentStorage`.

#### Scenario: Markdown saved to storage
- **WHEN** document ingestion completes and `save_markdown=True`
- **THEN** the markdown output is stored via `DocumentStorage.upload("markdown", key, data, "text/markdown")`

### Requirement: Document preview reads from storage
The document preview/download endpoints SHALL read from `DocumentStorage` instead of the local filesystem.

#### Scenario: Preview reads from storage
- **WHEN** a user requests document preview or download
- **THEN** the content is fetched via `DocumentStorage.download()` from the appropriate container
