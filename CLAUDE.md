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
docker-compose -f docker-compose.services.yml up -d   # Neo4j, RabbitMQ, FalkorDB
docker-compose -f docker-compose.memory.yml up -d     # Redis, Qdrant (for patient memory)
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
```

## DDA (Domain Data Architecture) Files
DDAs are Markdown files in `examples/` that define business domains. Key sections:
- `## Data Entities` with `### EntityName`, `- **Key Attributes**:`, `- **Business Rules**:`
- `## Relationships` defining entity connections

Upload via API: `POST /api/dda/upload` with file form data.

## Frontend (Astro + React)
- Located in `frontend/`
- Astro for static pages, React for interactive components
- Zustand for state management
- D3 for knowledge graph visualization
- Tests: Playwright (`npm run test`)

## Testing Notes
- Use `@pytest.mark.asyncio` for async tests
- `asyncio_mode = "auto"` is configured in pyproject.toml
- Integration tests may require running Neo4j/Redis containers
