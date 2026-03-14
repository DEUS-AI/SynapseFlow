## Why

Documents (PDFs, markdown output, tracking metadata) are stored on the container's ephemeral filesystem. Every pod restart or redeployment wipes all uploaded documents and processed markdown. The Knowledge Graph retains ingested entities in Neo4j, but the source files and document management UI break completely. This has caused data loss on every deployment.

## What Changes

- Add Azure Blob Storage account via Terraform module for durable document storage
- Create a storage abstraction layer (`DocumentStorage` interface) with local and blob implementations
- Migrate document upload to write PDFs to blob storage instead of local `PDFs/` directory
- Migrate markdown output to write to blob storage instead of local `markdown_output/`
- Move document tracking from `data/document_tracking.json` to Postgres (already has `documents` table)
- Update document retrieval (preview, download, quality assessment) to read from blob storage
- Add blob storage connection string to Key Vault and AKS secrets
- Update ingestion pipeline to read source PDFs from blob storage

## Capabilities

### New Capabilities
- `blob-storage-infra`: Terraform module for Azure Storage Account with blob containers, private endpoint, Key Vault secret, and AKS pod identity access
- `document-storage-abstraction`: Storage interface with local filesystem and Azure Blob implementations, used by upload, ingestion, and retrieval flows
- `postgres-document-tracking`: Replace JSON file-based document tracking with Postgres-backed tracking using the existing `documents` table

### Modified Capabilities
- `postgres-document-reads`: Document reads now source file content from blob storage instead of local filesystem

## Impact

- **Infrastructure**: New Terraform module (`infra/terraform/modules/storage`), updates to dev environment main.tf
- **Backend code**: `src/application/api/document_router.py` (upload, ingest, preview endpoints), `src/application/services/document_tracker.py`, ingestion service
- **Configuration**: New env vars (`AZURE_STORAGE_CONNECTION_STRING` or managed identity), Key Vault secret
- **Dependencies**: `azure-storage-blob` Python package
- **Deployment**: AKS backend deployment needs storage secret mount or workload identity
- **No breaking API changes**: Upload/download endpoints keep the same interface, storage is transparent to frontend
