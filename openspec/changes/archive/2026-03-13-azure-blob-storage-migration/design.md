## Context

Documents are stored on the backend pod's ephemeral filesystem (`PDFs/`, `markdown_output/`, `data/document_tracking.json`). Every redeployment or pod restart destroys all uploaded documents. The Knowledge Graph in Neo4j retains ingested entities, but the admin UI shows no documents and re-upload is required.

The project already has Terraform modules for all Azure services (AKS, PostgreSQL, Redis, Key Vault, ACR). The pattern is: Terraform module creates the resource and stores its connection string in Key Vault, AKS mounts the secret via CSI driver.

The existing `documents` table in Postgres already tracks document metadata (filename, status, entity_count, etc.) but the `DocumentTracker` class uses a separate JSON file. There's duplicated tracking.

## Goals / Non-Goals

**Goals:**
- Documents survive pod restarts and redeployments
- Single source of truth for document tracking (Postgres `documents` table)
- Clean abstraction that works locally (filesystem) and in Azure (blob)
- Follow existing Terraform module patterns
- Minimal disruption to existing upload/ingest/preview API contracts

**Non-Goals:**
- CDN or public access to documents (all access through backend API)
- Document versioning or soft-delete (simple overwrite semantics)
- Migrating existing local documents to blob (fresh start on Azure is acceptable)
- Changing the frontend document management UI

## Decisions

### 1. Azure Blob Storage with connection string auth

**Decision**: Use `azure-storage-blob` Python SDK with connection string from Key Vault.

**Alternatives considered**:
- Managed Identity / Workload Identity: More secure but requires OIDC federation setup on AKS, adds complexity. Connection string is simpler and follows the existing pattern (Postgres and Redis use passwords from Key Vault).
- AzureDisk PVC: Quick fix but tied to a single AZ, doesn't scale, and the PVC lifecycle is tied to the cluster.

**Rationale**: Connection string matches the existing secret management pattern. Can upgrade to workload identity later.

### 2. Two blob containers: `documents` and `markdown`

**Decision**: Use two containers in one storage account.
- `documents`: Raw uploaded PDFs, keyed by `{category}/{doc_id}/{filename}`
- `markdown`: Processed markdown output, keyed by `{doc_id}/{filename}.md`

**Rationale**: Separates raw uploads from processed output. Simple key scheme allows listing by category or document.

### 3. Storage abstraction with Protocol class

**Decision**: Define a `DocumentStorage` Protocol with methods: `upload`, `download`, `exists`, `delete`, `list_documents`. Two implementations: `LocalDocumentStorage` (filesystem, for dev) and `BlobDocumentStorage` (Azure, for prod). Selected at startup via env var `DOCUMENT_STORAGE_BACKEND=local|blob`.

**Rationale**: Keeps local development simple (no Azure SDK needed). Protocol over ABC is lighter and more Pythonic.

### 4. Replace DocumentTracker JSON with Postgres DocumentRepository

**Decision**: Remove `DocumentTracker` class and `document_tracking.json`. Use the existing `DocumentRepository` (which wraps the `documents` Postgres table) as the single source of truth. Add missing methods (`register_document`, `update_status`, `list_by_status`) to `DocumentRepository`.

**Alternatives considered**:
- Keep both: More work, data consistency risk.
- Keep JSON, add blob: Still ephemeral, doesn't solve the problem.

**Rationale**: The `documents` table already exists and has all needed columns. Eliminating the JSON tracker removes the duplicated state.

### 5. Terraform module follows existing patterns

**Decision**: New `infra/terraform/modules/storage/` module. Creates storage account, containers, stores connection string in Key Vault. Uses private endpoint on the existing PE subnet. Naming: `st{project}{env}{region}` (storage accounts don't allow hyphens).

## Risks / Trade-offs

- **[Cold start latency]** → Blob reads add ~50-100ms vs local filesystem. Acceptable for document operations (not real-time chat). Markdown preview can be cached in-memory if needed.
- **[Storage costs]** → Minimal: Hot tier blob storage for PDFs is ~$0.02/GB/month. Well within budget.
- **[Migration gap]** → Existing documents on Azure won't auto-migrate. Users need to re-upload. → Acceptable since documents were already lost on last restart.
- **[Connection string rotation]** → If Key Vault rotates the key, pod needs restart. → Standard pattern, same as Postgres/Redis.
