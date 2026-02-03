"""Document Service.

Orchestrates document ingestion: conversion, chunking, entity extraction,
embedding generation, and storage.
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


class DocumentService:
    """Orchestrates document ingestion and retrieval."""
    
    def __init__(
        self,
        kg_backend=None,
        chunk_size: int = 1500,  # Larger for technical docs
        chunk_overlap: int = 300,
        faiss_index_path: str = "data/faiss_index"
    ):
        """Initialize the document service.
        
        Args:
            kg_backend: Knowledge graph backend for storing document metadata
            chunk_size: Target chunk size (larger for technical/medical docs)
            chunk_overlap: Overlap between chunks
            faiss_index_path: Path to store FAISS index
        """
        self.kg_backend = kg_backend
        self.converter = MarkItDownWrapper()
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.extractor = EntityExtractor()
        self.faiss_index_path = faiss_index_path
        
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
        
        document = Document(
            id=doc_id,
            name=source_name,
            source_path=file_path,
            ingested_at=datetime.now(),
            content_hash=content_hash,
            chunk_count=len(chunks),
            metadata=metadata
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
