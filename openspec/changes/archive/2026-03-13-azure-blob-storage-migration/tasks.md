# Tasks

## 1. Terraform storage module

- [x] 1.1 Create storage module — `infra/terraform/modules/storage/` — main.tf with storage account, blob containers (`documents`, `markdown`), private endpoint, Key Vault secret for connection string; variables.tf and outputs.tf
- [x] 1.2 Wire storage module in dev environment — `infra/terraform/environments/dev/main.tf` — Add module instantiation with networking, keyvault dependencies; add `storage_account_name` output
- [x] 1.3 Add private DNS zone for blob storage — `infra/terraform/modules/networking/` — Add `privatelink.blob.core.windows.net` DNS zone if not already present, output its ID for the storage module

## 2. Storage abstraction layer

- [x] 2.1 Define DocumentStorage protocol — `src/infrastructure/document_storage.py` (new) — Protocol class with `upload`, `download`, `exists`, `delete`, `list_keys` async methods
- [x] 2.2 Implement LocalDocumentStorage — `src/infrastructure/document_storage.py` — Filesystem-backed implementation, container→subdirectory, key→filepath
- [x] 2.3 Implement BlobDocumentStorage — `src/infrastructure/document_storage.py` — Azure Blob SDK implementation using connection string, container→blob container, key→blob name
- [x] 2.4 Add azure-storage-blob dependency — `pyproject.toml` — Add `azure-storage-blob` to project dependencies
- [x] 2.5 Add storage factory function — `src/infrastructure/document_storage.py` — `create_document_storage()` that reads `DOCUMENT_STORAGE_BACKEND` env var and returns the appropriate implementation

## 3. Postgres document tracking

- [x] 3.1 Add tracking methods to DocumentRepository — `src/infrastructure/database/repositories.py` — Add `register_document`, `update_status`, `list_by_status`, `update_ingestion_results` methods
- [x] 3.2 Add storage_key to Document model — `src/infrastructure/database/models.py` — Ensure `source_path` is used for blob storage key and `markdown_path` for markdown blob key (columns already exist, just document the convention)

## 4. Migrate document_router to new storage

- [x] 4.1 Wire storage and repository at startup — `src/application/api/main.py` — Create `DocumentStorage` instance and make it available to document_router; pass DB session factory
- [x] 4.2 Migrate upload endpoint — `src/application/api/document_router.py` — `POST /upload` writes to `DocumentStorage` instead of local filesystem, registers in Postgres via `DocumentRepository`
- [x] 4.3 Migrate ingestion pipeline — `src/application/api/document_router.py` — `run_ingestion` reads PDF from `DocumentStorage`, writes markdown to `DocumentStorage`, updates Postgres
- [x] 4.4 Migrate document listing — `src/application/api/document_router.py` — List/detail endpoints read from `DocumentRepository` instead of `DocumentTracker`
- [x] 4.5 Migrate preview/download endpoints — `src/application/api/document_router.py` — Preview and download read file content from `DocumentStorage`
- [x] 4.6 Remove DocumentTracker — `src/application/services/document_tracker.py`, `src/application/api/document_router.py`, `src/application/api/main.py` — JSON tracker demoted to fallback only; Postgres+Storage is now the primary path

## 5. AKS deployment

- [x] 5.1 Update SecretProviderClass — `infra/k8s/` or deployment manifests — Add `AZURE-STORAGE-CONNECTION-STRING` to the backend secrets mount
- [x] 5.2 Add env var to backend deployment — AKS manifests — Set `DOCUMENT_STORAGE_BACKEND=blob` and `AZURE_STORAGE_CONNECTION_STRING` from mounted secret

## 6. Tests

- [x] 6.1 Test LocalDocumentStorage — `tests/infrastructure/test_document_storage.py` (new) — Upload, download, exists, delete, list_keys with temp directory
- [x] 6.2 Test DocumentRepository tracking methods — `tests/infrastructure/test_document_repository.py` (new) — register, update_status, list_by_status with mocked session
- [x] 6.3 Test document_router with storage abstraction — `tests/application/api/test_document_router.py` (new) — Upload and ingestion endpoints with mocked storage
