## Context

Document tracking currently uses a JSON file (`data/document_tracking.json`) read/written by `DocumentTracker`. The PostgreSQL `documents` table already receives dual-writes during ingestion, but no read path exists. The `DocumentRepository` has basic read methods (`get_by_external_id`, `get_by_status`, `get_statistics`) but is missing filtered list, category listing, and full statistics matching the tracker's output.

Document endpoints live in `document_router.py` (a FastAPI `APIRouter`), not in `main.py`. The router currently receives a `DocumentTracker` instance and uses it directly.

Key constraint: documents have three data sources:
1. **Metadata** (JSON tracker → PostgreSQL): filename, status, category, counts, quality scores
2. **Content** (filesystem): PDF files, markdown output — stays on disk
3. **Graph** (Neo4j): entities, relationships, subgraph — stays in Neo4j

Only source #1 migrates.

## Goals / Non-Goals

**Goals:**
- Route document metadata reads to PostgreSQL when `use_postgres_documents` flag is enabled
- Add missing `DocumentRepository` query methods to match `DocumentTracker` capabilities
- Follow the same pattern established by `ChatHistoryService` and `FeedbackTracerService`
- Keep `DocumentTracker` as fallback (no removal)

**Non-Goals:**
- Migrating content reads (markdown files) — stays on filesystem
- Migrating entity/graph queries — stays on Neo4j
- Migrating job tracking — stays in-memory
- Replacing `DocumentTracker` entirely — it stays as fallback and for filesystem sync
- Adding the `use_postgres_documents()` helper to the feature flag service is technically needed but trivial

## Decisions

### Decision 1: Route at the router level, not a service level

Unlike sessions (which have `ChatHistoryService` as a service layer) and feedback (which has `FeedbackTracerService`), documents don't have a read service — the router calls `DocumentTracker` directly. Rather than introducing a new `DocumentReadService`, add routing logic directly in the router endpoints. This keeps changes minimal.

**Alternative considered:** Create a `DocumentReadService` wrapping both tracker and repository. Rejected because it adds indirection for 4-5 endpoints that are straightforward.

### Decision 2: Map DocumentTracker IDs to DocumentRepository external_id

`DocumentTracker` generates IDs via `_generate_id(pdf_path)` (SHA256 hash). The PostgreSQL `Document` model has an `external_id` field that stores this same ID during dual-write. The read path uses `DocumentRepository.get_by_external_id()` for single-document lookups.

### Decision 3: Extend DocumentRepository with missing methods

The repository needs:
- `list_filtered(status, category, search, limit)` — combines filtering that tracker does in-memory
- `get_categories()` — distinct category values
- `get_full_statistics()` — status counts + entity/relationship totals + markdown count

These are SQL queries, not application logic.

### Decision 4: Keep filesystem reads for markdown preview in document detail

The `GET /api/admin/documents/{id}` endpoint returns a `markdown_preview` (first 2000 chars of the markdown file). Even when reading metadata from PostgreSQL, the preview still comes from the filesystem via `markdown_path`. PostgreSQL stores the path, filesystem provides the content.

## Risks / Trade-offs

- **[Risk] DocumentTracker.scan_pdf_directory() syncs filesystem state into JSON** — When reading from PG, this sync doesn't happen. If a PDF is added to the filesystem without being uploaded via API, PG won't know about it. → Mitigation: The upload endpoint writes to PG. Manual filesystem additions are an edge case; `scan_pdf_directory` can be run separately for reconciliation.

- **[Risk] DocumentTracker ID format may not match external_id in PG** — The dual-write in `document_service.py` sets `external_id` from the doc_id parameter. Need to verify the ID format matches. → Mitigation: Check during implementation.

- **[Trade-off] Statistics query hits PG instead of scanning filesystem** — Faster but may not reflect un-uploaded PDFs. Acceptable since the API upload path is the primary ingestion method.
