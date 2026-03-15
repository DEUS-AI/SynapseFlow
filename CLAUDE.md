# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SynapseFlow** is a neurosymbolic multi-agent system for intelligent knowledge management. It combines symbolic AI (rule-based reasoning, ontology mapping) with neural AI (LLM inference, embeddings) using a multi-agent architecture with domain-driven design.

## Commands

### Development Setup
```bash
uv sync                      # Install dependencies
uv run pip install -e .      # Install package in dev mode
```

### Running the Backend API
```bash
uv run uvicorn application.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running the Frontend
```bash
cd frontend && npm run dev   # Astro dev server on localhost:4321
```

### Starting Required Services (Docker)
```bash
docker-compose -f docker-compose.services.yml up -d   # Postgres, Neo4j, RabbitMQ, FalkorDB
docker-compose -f docker-compose.memory.yml up -d     # Redis, Qdrant (for patient memory)
make services                                          # Shortcut: starts both
make services-stop                                     # Stop all services
```

### Testing
```bash
uv run pytest tests/ -v                              # All tests
uv run pytest tests/application/ -v                  # Specific layer
uv run pytest tests/test_file.py -v                  # Single file
uv run pytest tests/test_file.py::test_function -v  # Single test
uv run pytest tests/ --cov=src --cov-report=html    # With coverage
```

### Linting and Formatting
```bash
make lint        # ruff check
make format      # black + ruff --fix
make precommit   # pre-commit hooks
```

### Maintenance
```bash
make reset-dry-run                                    # Preview what full reset would clear
make reset-all                                        # Clear ALL derived data (Neo4j, Postgres, Redis, Qdrant, FalkorDB, storage, local files)
make clear-memory PATIENT=patient:demo                # Clear memories for a specific patient
uv run python scripts/maintenance/full_reset.py --env-file .env.azure --confirm  # Reset Azure environment
uv run python scripts/maintenance/full_reset.py --confirm --only neo4j,postgres  # Reset specific stores
```

### CLI Commands
```bash
uv run python -m multi_agent_system model examples/sample_dda.md --domain "Customer Analytics"
uv run python -m multi_agent_system model examples/sample_dda.md --validate-only
```

## Architecture

### Clean Architecture Layers (src/)
```
src/
├── domain/           # Core business logic, models (NO external dependencies)
├── application/      # Orchestration, services, agents, commands
├── infrastructure/   # External integrations (Neo4j, Redis, parsers)
├── interfaces/       # CLI, REST API
└── composition_root.py  # Dependency injection
```

**Dependency Rule**: Dependencies point inward only. Domain layer has zero external dependencies.

### 4-Layer Knowledge Graph (DIKW Pyramid)
All entities have a `layer` property:
- **PERCEPTION**: Raw extracted data (PDFs, DDAs) - confidence ~0.7
- **SEMANTIC**: Validated concepts with ontology mappings - confidence ≥0.85
- **REASONING**: Inferred knowledge, business rules - confidence ≥0.90
- **APPLICATION**: Query patterns, cached results, user feedback

Entities are automatically promoted between layers based on confidence thresholds, validation counts, and ontology matches.

### Multi-Agent System
- **DataArchitectAgent**: Domain modeling, DDA processing, simple KG updates
- **DataEngineerAgent**: Implementation, full KG operations, metadata generation
- **KnowledgeManagerAgent**: Complex operations, validation, reasoning, conflict resolution
- **MedicalAssistantAgent**: Patient interactions, medical reasoning, memory management

Agents communicate via message passing and escalation. Complex operations are escalated from DataArchitect → KnowledgeManager.

### Key Services
- **PatientMemoryService**: 3-layer memory (Redis short-term → Mem0 mid-term → Neo4j long-term)
- **AutomaticLayerTransitionService**: Manages entity promotions between layers
- **PromotionScannerJob**: Background job scanning for promotion candidates
- **EntityResolver**: Prevents duplicates using exact/fuzzy/embedding strategies
- **ReasoningEngine**: Neurosymbolic reasoning with confidence tracking

### Backend Implementations
All backends implement `KnowledgeGraphBackend` abstract class:
- **Neo4jBackend**: Primary production backend (async driver)
- **GraphitiBackend**: Episodic memory with Graphiti framework
- **FalkorBackend**: Redis-based graph (sync-to-async wrapper)

## Key Patterns

- **CQRS**: Commands via `CommandBus`, queries via services
- **Event-Driven**: `EventBus` pub/sub between agents
- **Repository Pattern**: `KnowledgeGraphBackend` abstraction
- **Strategy Pattern**: Resolution strategies, reasoning modes
- **Factory Pattern**: Agent registry in composition_root.py

## Document Storage

Documents use a storage abstraction (`DocumentStorage` protocol in `src/infrastructure/document_storage.py`) with two backends:
- **LocalDocumentStorage**: Filesystem-backed (`storage/` dir) — default for local dev
- **BlobDocumentStorage**: Azure Blob Storage — used in production

Controlled by `DOCUMENT_STORAGE_BACKEND` env var (`local` or `blob`). Blob backend reads connection string from `AZURE_STORAGE_CONNECTION_STRING` env var or mounted secret at `/mnt/secrets/storage-connection-string`.

Storage key format: `{category}/{doc_id}/{filename}` (includes doc_id to prevent overwrites).

Containers: `documents` (PDFs), `markdown` (converted markdown).

## Environment Variables (.env)
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
OPENAI_API_KEY=sk-...
QDRANT_URL=http://localhost:6333
REDIS_HOST=localhost
REDIS_PORT=6380
ENABLE_AUTO_PROMOTION=true
ENABLE_PROMOTION_SCANNER=true
DOCUMENT_STORAGE_BACKEND=local               # "local" or "blob"

# Evaluation Framework (for agent testing)
SYNAPSEFLOW_EVAL_MODE=true                    # Enable /api/eval/* endpoints
SYNAPSEFLOW_EVAL_API_KEY=your-eval-key        # API key for eval endpoints
```

Use `.env.azure` for Azure-specific overrides (gitignored). Create it from Key Vault + AKS secrets.

## DDA (Domain Data Architecture) Files
DDAs are Markdown files in `examples/` that define business domains. Key sections:
- `## Data Entities` with `### EntityName`, `- **Key Attributes**:`, `- **Business Rules**:`
- `## Relationships` defining entity connections

Upload via API: `POST /api/dda/upload` with file form data.

## Frontend (Astro + React)
- Located in `frontend/`
- Astro hybrid mode (`output: 'hybrid'`) with Node adapter for SSR pages
- React for interactive components, Zustand for state management
- D3 for knowledge graph visualization
- Tests: Playwright (`npm run test`)
- **Deployment**: Azure Static Web Apps (`proud-mushroom-0def81803.6.azurestaticapps.net`). Dynamic pages read params client-side from `window.location`.
- **Auth**: Invite-based access control. Create invites via `POST /api/admin/invites`, users redeem via `/invite/{token}` which sets `session_token` in localStorage.
- **API URL**: Backend at `https://20-50-212-98.nip.io` (nip.io auto-resolves to AKS ingress IP). Set via `PUBLIC_API_URL` env var at build time.

### Frontend Deployment
```bash
make deploy-frontend-swa                      # Build + deploy to Azure Static Web App
```

## Azure Infrastructure

Terraform modules in `infra/terraform/modules/` manage: ACR, AKS, Key Vault, Networking, Postgres, Redis, Storage (Blob), Static Web App, FinOps, Monitoring.

```bash
cd infra/terraform/environments/dev
terraform init
terraform plan                                # Review changes
terraform apply                               # Apply all modules
terraform apply -target=module.storage        # Apply specific module
```

K8s manifests in `infra/k8s/base/` (backend deployment, secret-provider, ingress with TLS via cert-manager + Let's Encrypt).

Backend image: `az acr build --registry acrodindev --image synapseflow/backend:latest --file Dockerfile.agent --platform linux/amd64 .`

**Key Vault secrets** (lowercase-with-hyphens convention): `pg-connection-string`, `redis-connection-string`, `neo4j-password`, `openai-api-key`, `storage-connection-string`.

**Backend deployment uses `strategy: Recreate`** (not RollingUpdate) due to resource quota constraints — only one backend pod can run at a time.

**Backend TLS**: cert-manager with Let's Encrypt issues TLS certs for `20-50-212-98.nip.io`. AKS subnet NSG blocks direct internet access to ports 80/443, allowing only Azure-originated traffic (SWA outbound, AzureCloud service tag).

## Testing Notes
- Use `@pytest.mark.asyncio` for async tests
- `asyncio_mode = "auto"` is configured in pyproject.toml
- Integration tests may require running Neo4j/Redis containers
