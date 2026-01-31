"""Document Service.

Orchestrates document ingestion: conversion, chunking, entity extraction,
embedding generation, storage, and quality assessment.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import os
import hashlib
import pickle

from application.services.markitdown_wrapper import MarkItDownWrapper
from application.services.text_chunker import TextChunker, TextChunk
from application.services.entity_extractor import EntityExtractor, ExtractedEntity
from application.services.document_quality_service import DocumentQualityService
from domain.quality_models import DocumentQualityReport, QualityLevel


@dataclass
class Document:
    """Represents an ingested document."""
    id: str
    name: str
    source_path: str
    ingested_at: datetime
    content_hash: str
    chunk_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_report: Optional[DocumentQualityReport] = None


class DocumentService:
    """Orchestrates document ingestion and retrieval.

    Supports dual-write to PostgreSQL via feature flags:
    - dual_write_documents: Write document metadata to both Neo4j and PostgreSQL
    - use_postgres_documents: Read from PostgreSQL (migration complete)
    """

    def __init__(
        self,
        kg_backend=None,
        chunk_size: int = 1500,  # Larger for technical docs
        chunk_overlap: int = 300,
        faiss_index_path: str = "data/faiss_index",
        enable_quality_assessment: bool = True,
        pg_document_repo=None,
    ):
        """Initialize the document service.

        Args:
            kg_backend: Knowledge graph backend for storing document metadata
            chunk_size: Target chunk size (larger for technical/medical docs)
            chunk_overlap: Overlap between chunks
            faiss_index_path: Path to store FAISS index
            enable_quality_assessment: Whether to run quality assessment during ingestion
            pg_document_repo: Optional PostgreSQL document repository for dual-write
        """
        self.kg_backend = kg_backend
        self.converter = MarkItDownWrapper()
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.extractor = EntityExtractor()
        self.faiss_index_path = faiss_index_path
        self.enable_quality_assessment = enable_quality_assessment
        self.pg_document_repo = pg_document_repo

        # Initialize quality service
        self.quality_service = DocumentQualityService()

        # Initialize FAISS and embedding model
        self._embedding_model = None
        self._faiss_index = None
        self._chunk_store = {}  # Map chunk_id -> chunk text

        # Ensure data directory exists
        os.makedirs(os.path.dirname(faiss_index_path) or "data", exist_ok=True)

        # Load existing index if available
        self._load_faiss_index()
    
    async def ingest_document(
        self,
        file_path: str,
        source_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Ingest a document into the knowledge graph.
        
        Args:
            file_path: Path to the document (PDF, DOCX, etc.)
            source_name: Human-readable name for the document
            metadata: Additional metadata to attach
            
        Returns:
            Document object with ingestion details
        """
        metadata = metadata or {}
        source_name = source_name or os.path.basename(file_path)
        
        print(f"📄 Ingesting document: {source_name}")
        
        # 1. Convert to Markdown
        print("  → Converting to Markdown...")
        markdown_text = self.converter.convert_to_markdown(file_path)
        if not markdown_text:
            raise ValueError(f"Failed to convert document: {file_path}")
        
        # 2. Generate document ID from content hash
        content_hash = hashlib.sha256(markdown_text.encode()).hexdigest()[:16]
        doc_id = f"doc:{content_hash}"
        
        # 3. Chunk the text
        print("  → Chunking text...")
        chunks = self.chunker.chunk_text(
            markdown_text, 
            doc_id=doc_id,
            metadata={"source": source_name, **metadata}
        )
        print(f"    Created {len(chunks)} chunks")
        
        # 4. Generate embeddings and store in FAISS
        print("  → Generating embeddings...")
        await self._embed_and_store_chunks(chunks)
        
        # 5. Extract entities from chunks
        print("  → Extracting entities...")
        all_entities = []
        for chunk in chunks[:5]:  # Limit entity extraction to first 5 chunks for speed
            entities = await self.extractor.extract_entities(chunk.text, chunk.id)
            all_entities.extend(entities)
        print(f"    Extracted {len(all_entities)} entities")
        
        # 6. Link entities to existing graph nodes
        if self.kg_backend:
            print("  → Linking to knowledge graph...")
            for entity in all_entities:
                linked_id = await self.extractor.link_to_graph(entity, self.kg_backend)
                entity.linked_node_id = linked_id
        
        # 7. Store document and entities in Neo4j
        if self.kg_backend:
            await self._store_in_graph(doc_id, source_name, file_path, chunks, all_entities, metadata)

        # 8. Save FAISS index
        self._save_faiss_index()

        # 9. Run quality assessment
        quality_report = None
        if self.enable_quality_assessment:
            print("  → Assessing document quality...")
            try:
                # Convert entities to dict format for quality service
                entity_dicts = [
                    {
                        "name": e.name,
                        "type": e.entity_type,
                        "confidence": e.confidence,
                        "chunk_id": e.source_chunk_id
                    }
                    for e in all_entities
                ]

                quality_report = await self.quality_service.assess_document(
                    document_id=doc_id,
                    document_name=source_name,
                    markdown_text=markdown_text,
                    chunks=chunks,
                    entities=entity_dicts,
                )

                print(f"    Quality: {quality_report.quality_level.value} "
                      f"(score: {quality_report.overall_score:.2f})")

                if quality_report.improvement_priority:
                    print(f"    Top recommendation: {quality_report.improvement_priority[0]}")

                # Store quality metrics in Neo4j
                if self.kg_backend:
                    await self._store_quality_metrics(doc_id, quality_report)

            except Exception as e:
                print(f"    Warning: Quality assessment failed: {e}")

        document = Document(
            id=doc_id,
            name=source_name,
            source_path=file_path,
            ingested_at=datetime.now(),
            content_hash=content_hash,
            chunk_count=len(chunks),
            metadata=metadata,
            quality_report=quality_report,
        )

        # 10. Dual-write to PostgreSQL if enabled
        await self._dual_write_to_postgres(
            doc_id=doc_id,
            name=source_name,
            source_path=file_path,
            chunk_count=len(chunks),
            entity_count=len(all_entities),
            metadata=metadata,
            quality_report=quality_report,
        )

        print(f"✅ Document ingested: {doc_id}")
        return document
    
    async def search_similar(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for chunks similar to the query.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of matching chunks with scores
        """
        if self._faiss_index is None:
            return []
        
        # Embed the query
        query_embedding = await self._get_embedding(query)
        if query_embedding is None:
            return []
        
        import numpy as np
        query_vector = np.array([query_embedding]).astype('float32')
        
        # Search FAISS
        distances, indices = self._faiss_index.search(query_vector, top_k)
        
        results = []
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx >= 0 and idx < len(self._chunk_ids):
                chunk_id = self._chunk_ids[idx]
                results.append({
                    "chunk_id": chunk_id,
                    "text": self._chunk_store.get(chunk_id, ""),
                    "score": float(1 / (1 + distance)),  # Convert distance to similarity
                    "rank": i + 1
                })
        
        return results
    
    async def _embed_and_store_chunks(self, chunks: List[TextChunk]) -> None:
        """Generate embeddings for chunks and store in FAISS."""
        import numpy as np
        
        embeddings = []
        chunk_ids = []
        
        for chunk in chunks:
            embedding = await self._get_embedding(chunk.text)
            if embedding:
                embeddings.append(embedding)
                chunk_ids.append(chunk.id)
                self._chunk_store[chunk.id] = chunk.text
        
        if not embeddings:
            return
        
        # Initialize FAISS index if needed
        if self._faiss_index is None:
            import faiss
            dimension = len(embeddings[0])
            self._faiss_index = faiss.IndexFlatL2(dimension)
            self._chunk_ids = []
        
        # Add to FAISS
        vectors = np.array(embeddings).astype('float32')
        self._faiss_index.add(vectors)
        self._chunk_ids.extend(chunk_ids)
    
    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using OpenAI."""
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            # Fallback: use simple hash-based pseudo-embedding
            return self._simple_embedding(text)
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000]  # Truncate to avoid token limits
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            print(f"Warning: Embedding failed: {e}")
            return self._simple_embedding(text)
    
    def _simple_embedding(self, text: str, dim: int = 256) -> List[float]:
        """Simple fallback embedding using hashing."""
        import hashlib
        import struct
        
        # Create a deterministic pseudo-embedding
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Extend hash to desired dimension
        result = []
        for i in range(dim):
            idx = i % len(hash_bytes)
            result.append((hash_bytes[idx] - 128) / 128.0)
        return result
    
    async def _store_in_graph(
        self,
        doc_id: str,
        name: str,
        source_path: str,
        chunks: List[TextChunk],
        entities: List[ExtractedEntity],
        metadata: Dict[str, Any]
    ) -> None:
        """Store document structure in Neo4j."""
        # Store Document node
        await self.kg_backend.add_entity(
            doc_id,
            {
                "name": name,
                "source_path": source_path,
                "ingested_at": datetime.now().isoformat(),
                "chunk_count": len(chunks),
                **metadata
            },
            labels=["Document"]
        )
        
        # Store Chunk nodes and relationships
        for chunk in chunks:
            await self.kg_backend.add_entity(
                chunk.id,
                {
                    "text": chunk.text[:500],  # Truncate for storage
                    "sequence": chunk.sequence,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char
                },
                labels=["Chunk"]
            )
            
            await self.kg_backend.add_relationship(
                doc_id,
                "HAS_CHUNK",
                chunk.id,
                {"sequence": chunk.sequence}
            )
        
        # Store ExtractedEntity nodes
        for entity in entities:
            entity_id = f"extracted:{entity.name.lower().replace(' ', '_')}"
            
            # Sanitize entity type for Neo4j label (remove spaces, special chars)
            safe_type = entity.entity_type.replace(" ", "").replace("-", "_")
            safe_type = ''.join(c for c in safe_type if c.isalnum() or c == '_')
            
            await self.kg_backend.add_entity(
                entity_id,
                {
                    "name": entity.name,
                    "type": entity.entity_type,
                    "confidence": entity.confidence,
                    "context": entity.context
                },
                labels=["ExtractedEntity", safe_type] if safe_type else ["ExtractedEntity"]
            )
            
            # Link chunk -> entity (MENTIONS)
            await self.kg_backend.add_relationship(
                entity.source_chunk_id,
                "MENTIONS",
                entity_id,
                {"confidence": entity.confidence}
            )
            
            # Link to existing graph node if found
            if entity.linked_node_id:
                await self.kg_backend.add_relationship(
                    entity_id,
                    "LINKS_TO",
                    entity.linked_node_id,
                    {"confidence": entity.confidence}
                )

    async def _store_quality_metrics(
        self,
        doc_id: str,
        report: DocumentQualityReport
    ) -> None:
        """Store document quality metrics in Neo4j."""
        quality_id = f"{doc_id}:quality"

        await self.kg_backend.add_entity(
            quality_id,
            {
                "overall_score": report.overall_score,
                "quality_level": report.quality_level.value,
                "assessed_at": report.assessed_at.isoformat(),
                # Contextual relevancy
                "context_precision": report.contextual_relevancy.context_precision,
                "context_recall": report.contextual_relevancy.context_recall,
                "context_f1": report.contextual_relevancy.f1_score,
                # Sufficiency
                "topic_coverage": report.context_sufficiency.topic_coverage,
                "completeness": report.context_sufficiency.completeness,
                # Density
                "facts_per_chunk": report.information_density.unique_facts_per_chunk,
                "redundancy_ratio": report.information_density.redundancy_ratio,
                "signal_to_noise": report.information_density.signal_to_noise,
                # Structure
                "heading_hierarchy_score": report.structural_clarity.heading_hierarchy_score,
                "section_coherence": report.structural_clarity.section_coherence,
                # Entity
                "entity_extraction_rate": report.entity_density.entity_extraction_rate,
                "entity_consistency": report.entity_density.entity_consistency,
                # Chunking
                "boundary_coherence": report.chunking_quality.boundary_coherence,
                "retrieval_quality": report.chunking_quality.retrieval_quality,
                # Recommendations
                "recommendations": report.recommendations[:5],
            },
            labels=["DocumentQuality"]
        )

        # Link quality report to document
        await self.kg_backend.add_relationship(
            doc_id,
            "HAS_QUALITY_REPORT",
            quality_id,
            {"assessed_at": report.assessed_at.isoformat()}
        )

    async def _dual_write_to_postgres(
        self,
        doc_id: str,
        name: str,
        source_path: str,
        chunk_count: int,
        entity_count: int,
        metadata: Dict[str, Any],
        quality_report: Optional[DocumentQualityReport] = None,
    ) -> bool:
        """Dual-write document metadata to PostgreSQL.

        Args:
            doc_id: Document ID (e.g., "doc:abc123")
            name: Document filename
            source_path: Path to source file
            chunk_count: Number of chunks created
            entity_count: Number of entities extracted
            metadata: Additional metadata
            quality_report: Optional quality assessment report

        Returns:
            True if successful, False otherwise
        """
        from application.services.feature_flag_service import dual_write_enabled

        if not dual_write_enabled("documents"):
            return False

        try:
            from infrastructure.database.session import db_session
            from infrastructure.database.repositories import DocumentRepository
            from infrastructure.database.models import (
                Document as PgDocument,
                DocumentQuality as PgDocumentQuality,
            )
            from uuid import uuid4

            async with db_session() as session:
                repo = DocumentRepository(session)

                # Check if document already exists
                existing = await repo.get_by_external_id(doc_id)
                if existing:
                    # Update existing document
                    existing.filename = name
                    existing.source_path = source_path
                    existing.chunk_count = chunk_count
                    existing.entity_count = entity_count
                    existing.extra_data = metadata
                    existing.status = "ingested"
                    existing.ingested_at = datetime.now()
                    await repo.update(existing)
                    pg_doc = existing
                    print(f"    📝 Updated PostgreSQL document: {doc_id}")
                else:
                    # Create new document
                    pg_doc = PgDocument(
                        id=uuid4(),
                        external_id=doc_id,
                        filename=name,
                        source_path=source_path,
                        category=metadata.get("category"),
                        status="ingested",
                        chunk_count=chunk_count,
                        entity_count=entity_count,
                        ingested_at=datetime.now(),
                        extra_data=metadata,
                    )
                    pg_doc = await repo.create(pg_doc)
                    print(f"    📝 Created PostgreSQL document: {doc_id}")

                # Store quality report if available
                if quality_report:
                    quality_entry = PgDocumentQuality(
                        id=uuid4(),
                        document_id=pg_doc.id,
                        overall_score=quality_report.overall_score,
                        quality_level=quality_report.quality_level.value,
                        context_precision=quality_report.contextual_relevancy.context_precision,
                        context_recall=quality_report.contextual_relevancy.context_recall,
                        context_f1=quality_report.contextual_relevancy.f1_score,
                        topic_coverage=quality_report.context_sufficiency.topic_coverage,
                        completeness=quality_report.context_sufficiency.completeness,
                        facts_per_chunk=quality_report.information_density.unique_facts_per_chunk,
                        redundancy_ratio=quality_report.information_density.redundancy_ratio,
                        signal_to_noise=quality_report.information_density.signal_to_noise,
                        heading_hierarchy_score=quality_report.structural_clarity.heading_hierarchy_score,
                        section_coherence=quality_report.structural_clarity.section_coherence,
                        entity_extraction_rate=quality_report.entity_density.entity_extraction_rate,
                        entity_consistency=quality_report.entity_density.entity_consistency,
                        boundary_coherence=quality_report.chunking_quality.boundary_coherence,
                        retrieval_quality=quality_report.chunking_quality.retrieval_quality,
                        recommendations=quality_report.recommendations[:5],
                        assessed_at=quality_report.assessed_at,
                    )
                    session.add(quality_entry)
                    print(f"    📊 Stored quality metrics in PostgreSQL")

                await session.commit()
                return True

        except Exception as e:
            print(f"    ⚠️ PostgreSQL dual-write failed: {e}")
            return False

    async def get_document_quality(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve quality metrics for a document.

        Args:
            doc_id: Document ID

        Returns:
            Quality metrics dictionary or None if not found
        """
        if not self.kg_backend:
            return None

        try:
            query = """
            MATCH (d:Document {id: $doc_id})-[:HAS_QUALITY_REPORT]->(q:DocumentQuality)
            RETURN q
            """
            result = await self.kg_backend.query_raw(query, {"doc_id": doc_id})
            if result and len(result) > 0:
                return dict(result[0].get("q", {}))
        except Exception:
            pass

        return None

    async def reassess_document_quality(
        self,
        doc_id: str,
        expected_topics: Optional[List[str]] = None
    ) -> Optional[DocumentQualityReport]:
        """Re-run quality assessment on an existing document.

        Args:
            doc_id: Document ID to reassess
            expected_topics: Optional list of topics to verify coverage

        Returns:
            New quality report or None if document not found
        """
        if not self.kg_backend:
            return None

        try:
            # Get document chunks
            query = """
            MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
            RETURN d.name as name, c.id as chunk_id, c.text as text, c.sequence as seq
            ORDER BY c.sequence
            """
            result = await self.kg_backend.query_raw(query, {"doc_id": doc_id})

            if not result:
                return None

            doc_name = result[0].get("name", "Unknown")

            # Reconstruct chunks
            chunks = [
                TextChunk(
                    id=r["chunk_id"],
                    text=r["text"],
                    sequence=r["seq"],
                    start_char=0,
                    end_char=len(r["text"]),
                    metadata={}
                )
                for r in result
            ]

            # Get full text from chunks
            full_text = "\n\n".join(c.text for c in chunks)

            # Run quality assessment
            report = await self.quality_service.assess_document(
                document_id=doc_id,
                document_name=doc_name,
                markdown_text=full_text,
                chunks=chunks,
                expected_topics=expected_topics,
            )

            # Update quality metrics in Neo4j
            await self._store_quality_metrics(doc_id, report)

            return report

        except Exception as e:
            print(f"Error reassessing document quality: {e}")
            return None

    def _load_faiss_index(self) -> None:
        """Load FAISS index from disk."""
        index_file = f"{self.faiss_index_path}.index"
        meta_file = f"{self.faiss_index_path}.meta"
        
        if os.path.exists(index_file) and os.path.exists(meta_file):
            try:
                import faiss
                self._faiss_index = faiss.read_index(index_file)
                with open(meta_file, 'rb') as f:
                    data = pickle.load(f)
                    self._chunk_ids = data.get('chunk_ids', [])
                    self._chunk_store = data.get('chunk_store', {})
                print(f"📂 Loaded FAISS index with {len(self._chunk_ids)} chunks")
            except Exception as e:
                print(f"Warning: Could not load FAISS index: {e}")
    
    def _save_faiss_index(self) -> None:
        """Save FAISS index to disk."""
        if self._faiss_index is None:
            return
        
        try:
            import faiss
            index_file = f"{self.faiss_index_path}.index"
            meta_file = f"{self.faiss_index_path}.meta"
            
            faiss.write_index(self._faiss_index, index_file)
            with open(meta_file, 'wb') as f:
                pickle.dump({
                    'chunk_ids': self._chunk_ids,
                    'chunk_store': self._chunk_store
                }, f)
            print(f"💾 Saved FAISS index with {len(self._chunk_ids)} chunks")
        except Exception as e:
            print(f"Warning: Could not save FAISS index: {e}")
