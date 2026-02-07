# Document Ingestion Pipeline

## Overview

```mermaid
flowchart TB
    subgraph Input["Input Layer"]
        PDF[("PDF Files<br/>PDFs/")]
    end

    subgraph Conversion["Conversion Layer"]
        MD["Markdown Conversion<br/>(markitdown)"]
        STORE_MD[("Markdown Files<br/>markdown_output/")]
    end

    subgraph Chunking["Chunking Layer"]
        CHUNK["Text Chunking<br/>(1500 chars, 200 overlap)"]
    end

    subgraph RAG["RAG Pipeline<br/>(ingest_pdfs_for_rag.py)"]
        EMBED["Generate Embeddings<br/>(OpenAI text-embedding-ada-002)"]
        FAISS[("FAISS Index<br/>data/faiss_index")]
        RAG_ENTITY["Entity Extraction<br/>(First 5 chunks only)"]
    end

    subgraph EntityPipeline["Entity Pipeline<br/>(reprocess_all_pdfs.py)"]
        EXTRACT["Entity Extraction<br/>(First N chunks, default 20)"]
        NORMALIZE["Semantic Normalization<br/>(Medical domain)"]
    end

    subgraph Storage["Storage Layer"]
        NEO4J[("Neo4j Graph<br/>Document → Chunk → Entity")]
        TRACKER[("Document Tracker<br/>data/document_tracking.json")]
    end

    subgraph Chat["Chat/Query Layer"]
        SEARCH["Semantic Search"]
        GRAPH["Graph Queries"]
    end

    PDF --> MD
    MD --> STORE_MD
    STORE_MD --> CHUNK

    CHUNK --> EMBED
    EMBED --> FAISS
    CHUNK --> RAG_ENTITY
    RAG_ENTITY --> NEO4J

    STORE_MD --> EXTRACT
    EXTRACT --> NORMALIZE
    NORMALIZE --> NEO4J

    MD --> TRACKER
    EXTRACT --> TRACKER

    FAISS --> SEARCH
    NEO4J --> GRAPH

    style RAG fill:#e1f5fe
    style EntityPipeline fill:#fff3e0
    style NEO4J fill:#c8e6c9
    style FAISS fill:#c8e6c9
```

## Detailed Flow

### 1. RAG Ingestion (`ingest_pdfs_for_rag.py`)

```mermaid
sequenceDiagram
    participant PDF as PDF File
    participant DS as DocumentService
    participant MD as MarkItDown
    participant CH as Chunker
    participant OAI as OpenAI API
    participant FAISS as FAISS Index
    participant EX as EntityExtractor
    participant NEO as Neo4j

    PDF->>DS: ingest_document()
    DS->>MD: convert_to_markdown()
    MD-->>DS: markdown_text

    DS->>CH: chunk_text()
    CH-->>DS: chunks[]

    loop For each chunk
        DS->>OAI: get_embedding()
        OAI-->>DS: embedding vector
    end

    DS->>FAISS: add_vectors()
    FAISS-->>DS: indexed

    loop First 5 chunks only
        DS->>EX: extract_entities()
        EX->>OAI: LLM extraction
        OAI-->>EX: entities JSON
        EX-->>DS: entities[]
    end

    DS->>NEO: store_in_graph()
    Note over NEO: Creates Document, Chunk,<br/>ExtractedEntity nodes
```

### 2. Entity Reprocessing (`reprocess_all_pdfs.py`)

```mermaid
sequenceDiagram
    participant MD as Markdown File
    participant RP as PDFReprocessor
    participant CH as Chunker
    participant EX as EntityExtractor
    participant OAI as OpenAI API
    participant NORM as SemanticNormalizer
    participant NEO as Neo4j
    participant TR as DocumentTracker

    MD->>RP: process_pdf()
    RP->>RP: Check existing entities

    alt Has entities & not force
        RP-->>RP: Skip (already processed)
    else No entities or force
        RP->>CH: chunk_text()
        CH-->>RP: chunks[]

        loop First N chunks (default 20)
            RP->>EX: extract_entities()
            EX->>OAI: LLM extraction (gpt-4o-mini)

            alt JSON parse success
                OAI-->>EX: entities JSON
            else JSON parse failure
                EX->>EX: Fallback to heuristic extraction
            end

            EX->>NORM: normalize(entity_name)
            NORM-->>EX: normalized_name
            EX-->>RP: entities[]
        end

        RP->>NEO: store_in_neo4j()
        Note over NEO: MERGE Document node<br/>CREATE Chunk nodes<br/>CREATE ExtractedEntity nodes<br/>CREATE relationships

        RP->>TR: Update entity_count
    end
```

## Neo4j Graph Schema

```mermaid
erDiagram
    Document ||--o{ Chunk : HAS_CHUNK
    Chunk ||--o{ ExtractedEntity : MENTIONS
    ExtractedEntity ||--o{ ExtractedEntity : LINKS_TO

    Document {
        string name PK
        string path
        datetime ingested_at
        int chunk_count
    }

    Chunk {
        string id PK
        string text
        int chunk_num
    }

    ExtractedEntity {
        string id PK
        string name
        string type
        string layer
        float confidence
        string source_document
    }
```

## Data Flow Summary

| Stage | RAG Pipeline | Entity Pipeline |
|-------|--------------|-----------------|
| **Input** | PDF files | Existing markdown files |
| **Conversion** | PDF → Markdown | (uses existing) |
| **Chunking** | All chunks | All chunks |
| **Embeddings** | ALL chunks → FAISS | None |
| **Entity Extraction** | First 5 chunks | First N chunks (configurable) |
| **Storage** | FAISS + Neo4j | Neo4j only |
| **Use Case** | Semantic search in chat | Document detail view, graph visualization |

## Current State

```
FAISS Index:     18 vectors (limited RAG coverage)
Neo4j Entities:  Varies per document (20 chunks processed)
Documents:       42 PDFs tracked
```

## Commands

```bash
# Full RAG ingestion (embeddings + entities)
uv run python ingest_pdfs_for_rag.py

# Entity-only reprocessing (no embeddings)
uv run python scripts/reprocess_all_pdfs.py

# Reprocess with more chunks
uv run python scripts/reprocess_all_pdfs.py --max-chunks 50

# Skip already processed documents
uv run python scripts/reprocess_all_pdfs.py --skip-existing
```
