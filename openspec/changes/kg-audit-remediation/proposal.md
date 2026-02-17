## Why

The knowledge graph audit (2026-02-17) identified 85+ issues across 7 dimensions. Five findings are P0-critical — a Cypher injection vulnerability, exposed API keys, 74% orphan nodes, 0% ontology mapping, and 131 duplicate entities. These block production readiness. This change addresses the P0 items and supporting P1 items (Sprint 1: Security & Data Quality Foundation) as the first remediation pass.

## What Changes

- **Fix Cypher injection** in `neo4j_backend.py:443` — relationship type interpolated via `%` operator, replace with parameterized query
- **Secure secrets management** — remove exposed API keys from `.env` defaults, add startup validation for required env vars, remove hardcoded Neo4j password in `composition_root.py`
- **Expand remediation queries** — add missing queries for Cytokine (9 entities), Pathway (52), Study (46), and aliases for Chemical, Compound, Bacteria, Species/Cell types currently unmapped
- **Execute ontology remediation** — run dry-run validation, then full batch remediation against live graph to bring ontology mapping from 0% to target >80%
- **Deduplicate entities** — merge 131 case-insensitive duplicate pairs detected by audit, preserving the entity with more relationships/higher confidence

## Capabilities

### New Capabilities
- `cypher-injection-fix`: Parameterize all raw Cypher string interpolation in Neo4j backend to prevent injection attacks
- `secrets-management`: Remove hardcoded secrets, enforce env var validation at startup, fail-fast on missing required config
- `entity-deduplication`: Implement entity deduplication pipeline — detect, merge, and clean up duplicate entity pairs in the knowledge graph

### Modified Capabilities
- `kg-remediation-api`: Expand REMEDIATION_QUERIES with mappings for Cytokine, Pathway, Study, Chemical, Compound, Bacteria, Species/Cell; implement no-op query detection in dry-run
- `ontology-type-completeness`: Add missing MEDICAL_TYPE_ALIASES for graph types not yet covered (cytokine, chemical, compound, bacteria, species, cell, pathway, study)

## Impact

- **Security**: `src/infrastructure/backends/neo4j_backend.py` — Cypher query parameterization
- **Configuration**: `.env`, `src/composition_root.py`, new startup validation module
- **Ontology**: `src/domain/ontology/medical_ontology.py` — new aliases and registry entries
- **Remediation**: `src/application/services/remediation_service.py` — new queries, no-op detection
- **New service**: Entity deduplication service in `src/application/services/`
- **API**: Possible new endpoint for deduplication dry-run/execute
- **Graph data**: Batch remediation will modify entity properties on ~5,900 nodes; deduplication will merge ~131 node pairs
