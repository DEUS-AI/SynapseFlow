# Scripts Directory

Utility scripts for development, maintenance, and batch operations.

## Directory Structure

```
scripts/
├── inspection/     # Graph inspection and verification
├── maintenance/    # Cleanup and setup utilities
├── batch/          # Batch processing operations
└── dev/            # Development and debugging tools
```

## Inspection Scripts (`inspection/`)

Scripts for inspecting and verifying the knowledge graph:

- **`check_graphs.py`** - General graph health check
- **`check_neo4j_data.py`** - Neo4j data verification
- **`inspect_neo4j.py`** - Detailed Neo4j inspection
- **`inspect_falkordb.py`** - FalkorDB inspection
- **`inspect_architecture.py`** - Architecture graph inspection
- **`verify_hybrid_ontology.py`** - Ontology mapping verification
- **`verify_metadata_enhancement.py`** - Metadata enrichment verification
- **`verify_neo4j_backend.py`** - Neo4j backend verification
- **`verify_relationship_densification.py`** - Relationship density checks

### Usage Example
```bash
python scripts/inspection/check_graphs.py
python scripts/inspection/inspect_neo4j.py --verbose
```

## Maintenance Scripts (`maintenance/`)

Scripts for database cleanup and setup:

- **`clear_neo4j.py`** - Clear all Neo4j data
- **`clear_falkordb.py`** - Clear all FalkorDB data

### Usage Example
```bash
# ⚠️  WARNING: These scripts delete all data!
python scripts/maintenance/clear_neo4j.py --confirm
python scripts/maintenance/clear_falkordb.py --confirm
```

## Batch Processing Scripts (`batch/`)

Scripts for processing multiple DDAs and metadata:

- **`process_all_ddas.py`** - Batch process all DDA documents
- **`process_all_metadata.py`** - Batch process metadata
- **`process_batch_test.py`** - Test batch processing
- **`enrich_all_domains.py`** - Enrich all domain entities
- **`generate_dda_documents.py`** - Generate DDA documentation
- **`run_all_queries.py`** - Run all predefined queries
- **`run_neo4j_queries.py`** - Run Neo4j-specific queries

### Usage Example
```bash
python scripts/batch/process_all_ddas.py --input examples/ --output results/
python scripts/batch/enrich_all_domains.py --domains healthcare,finance
```

## Development Scripts (`dev/`)

Scripts for development and debugging:

- **`explore_graphiti.py`** - Explore Graphiti backend features
- **`explore_graphiti_structure.py`** - Analyze Graphiti graph structure
- **`debug_parser.py`** - Debug DDA parsing

### Usage Example
```bash
python scripts/dev/explore_graphiti.py
python scripts/dev/debug_parser.py --file examples/sample_dda.md
```

## Best Practices

1. **Always backup before running maintenance scripts**
2. **Test batch scripts on small datasets first**
3. **Use `--dry-run` flags when available**
4. **Check script output and logs**
5. **Run inspection scripts regularly**

## Adding New Scripts

When adding new utility scripts:

1. Place in appropriate subdirectory
2. Add shebang and docstring
3. Include usage instructions
4. Update this README
5. Add to `.gitignore` if generating temp files

## Troubleshooting

- **Connection errors**: Check backend services are running
- **Permission errors**: Ensure write permissions for output directories
- **Import errors**: Run scripts from project root

For more information, see the main [README.md](../README.md)
