# Project Directory Structure

Updated: January 20, 2026

## Overview

```
Notebooks/
├── demos/                          # Demonstration scripts
├── scripts/                        # Utility scripts
│   ├── inspection/                # Graph inspection tools
│   ├── maintenance/               # Cleanup & setup utilities
│   ├── batch/                     # Batch processing
│   └── dev/                       # Development tools
├── tests/                          # Test suite
│   ├── application/               # Application layer tests
│   ├── domain/                    # Domain model tests
│   ├── infrastructure/            # Infrastructure tests
│   ├── integration/               # Integration tests
│   └── manual/                    # Manual/exploratory tests
├── src/                            # Source code
│   ├── application/               # Application layer
│   ├── domain/                    # Domain models
│   ├── infrastructure/            # Infrastructure adapters
│   └── interfaces/                # User interfaces
├── docs/                           # Documentation
├── examples/                       # Example DDA files
└── [config files]                 # Project configuration
```

## Directory Descriptions

### `demos/` - Demonstration Scripts
Showcases system capabilities through interactive demonstrations.
- End-to-end neurosymbolic workflows
- Multi-agent collaboration
- API demonstrations
- See [demos/README.md](../demos/README.md)

### `scripts/` - Utility Scripts

**`inspection/`** - Graph inspection and verification tools
- Health checks
- Backend verification
- Ontology validation
- Relationship analysis

**`maintenance/`** - System maintenance utilities
- Database cleanup
- Backend setup
- Configuration management

**`batch/`** - Batch processing operations
- DDA processing
- Metadata generation
- Domain enrichment
- Query execution

**`dev/`** - Development and debugging tools
- Graph exploration
- Parser debugging
- Feature testing

See [scripts/README.md](../scripts/README.md)

### `tests/` - Test Suite

**`application/`** - Application layer unit tests
- Services (entity resolution, normalization, etc.)
- Commands and workflows
- Agent behavior

**`domain/`** - Domain model unit tests
- Canonical concepts
- Confidence models
- Knowledge layers

**`infrastructure/`** - Infrastructure tests
- Backend implementations
- Parsers
- External integrations

**`integration/`** - Integration tests
- End-to-end workflows
- Multi-component interactions
- Phase integration tests

**`manual/`** - Manual/exploratory tests
- Ad-hoc testing scripts
- Debugging utilities
- Not part of automated suite

See [tests/manual/README.md](../tests/manual/README.md)

### `src/` - Source Code

**`application/`** - Application layer (use cases, services)
- Agents (data_architect, data_engineer, knowledge_manager)
- Services (entity resolution, semantic grounding, etc.)
- Commands and workflows

**`domain/`** - Domain models (business logic)
- Core models (canonical concepts, confidence, layers)
- Ontologies (ODIN, Schema.org)
- SHACL shapes for validation

**`infrastructure/`** - Infrastructure adapters
- Backends (Graphiti, Neo4j, FalkorDB, In-Memory)
- Parsers (Markdown, DDA)
- External service integrations

**`interfaces/`** - User interfaces
- CLI
- REST API
- Knowledge graph operations API

### `docs/` - Documentation
- Architecture diagrams
- Implementation progress
- API reference
- User guides

### `examples/` - Example Files
- Sample DDAs (Healthcare, Finance, etc.)
- Template documents
- Test data

## File Naming Conventions

### Python Files
- **Services**: `{name}_service.py` (e.g., `entity_resolver.py`)
- **Agents**: `agent.py` in agent subdirectory
- **Tests**: `test_{name}.py` (e.g., `test_entity_resolver.py`)
- **Demos**: `{purpose}_demo.py` (e.g., `multi_agent_dda_demo.py`)
- **Scripts**: `{action}_{target}.py` (e.g., `clear_neo4j.py`)

### Documentation
- **README files**: `README.md` in each directory
- **Guides**: `{TOPIC}_GUIDE.md` (e.g., `DEMO_GUIDE.md`)
- **Specs**: `{COMPONENT}.md` (e.g., `ARCHITECTURE.md`)

## Import Paths

When importing from project code:

```python
# From src/ modules
from application.services.entity_resolver import EntityResolver
from domain.canonical_concepts import CanonicalConcept
from infrastructure.graphiti_backend import GraphitiBackend

# Running scripts from project root
python demos/run_full_demo.py
python scripts/inspection/check_graphs.py
python -m pytest tests/
```

## Best Practices

1. **Keep root clean** - Only essential config files in root
2. **Use appropriate directory** - Demos go in demos/, scripts in scripts/, etc.
3. **Update READMEs** - When adding files, update relevant README
4. **Follow naming conventions** - Consistent naming helps navigation
5. **Write documentation** - Explain purpose and usage

## Related Documentation

- [Main README](../README.md) - Project overview
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute
- [Cleanup Summary](../CLEANUP_SUMMARY.md) - Recent reorganization
- [Demo Organization Proposal](../DEMO_ORGANIZATION_PROPOSAL.md) - Future plans

---

For questions or suggestions about project structure, please open an issue.
