"""Text Chunker Service.

Splits Markdown/text into semantic chunks for embedding and processing.
"""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    id: str
    text: str
    sequence: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]


class TextChunker:
    """Splits text into overlapping chunks for RAG processing."""
    
    def __init__(
        self, 
        chunk_size: int = 1000, 
        chunk_overlap: int = 200,
        separators: List[str] = None
    ):
        """Initialize the text chunker.
        
        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of overlapping characters between chunks
            separators: List of separators to split on (in order of preference)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]
    
    def chunk_text(
        self, 
        text: str, 
        doc_id: str = "doc",
        metadata: Dict[str, Any] = None
    ) -> List[TextChunk]:
        """Split text into chunks.
        
        Args:
            text: The text to split
            doc_id: Document ID for generating chunk IDs
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of TextChunk objects
        """
        if not text:
            return []
        
        metadata = metadata or {}
        chunks = []
        
        # Use recursive splitting with separators
        raw_chunks = self._recursive_split(text, self.separators)
        
        # Merge small chunks and split large ones
        merged_chunks = self._merge_and_split_chunks(raw_chunks)
        
        # Create TextChunk objects with proper IDs and positions
        current_pos = 0
        for i, chunk_text in enumerate(merged_chunks):
            # Find the actual position in original text
            start_pos = text.find(chunk_text[:50], current_pos)  # Use first 50 chars to find
            if start_pos == -1:
                start_pos = current_pos
            
            chunk = TextChunk(
                id=f"{doc_id}_chunk_{i}",
                text=chunk_text.strip(),
                sequence=i,
                start_char=start_pos,
                end_char=start_pos + len(chunk_text),
                metadata={**metadata, "chunk_index": i, "total_chunks": len(merged_chunks)}
            )
            chunks.append(chunk)
            current_pos = start_pos + len(chunk_text) - self.chunk_overlap
        
        return chunks
    
    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text using separators in order of preference."""
        if not separators:
            return [text]
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        if separator == "":
            # Character-level split
            return [text[i:i+self.chunk_size] for i in range(0, len(text), self.chunk_size)]
        
        splits = text.split(separator)
        
        result = []
        for split in splits:
            if len(split) > self.chunk_size and remaining_separators:
                # Recursively split with next separator
                result.extend(self._recursive_split(split, remaining_separators))
            else:
                if split.strip():
                    result.append(split + (separator if separator != "\n\n" else "\n"))
        
        return result
    
    def _merge_and_split_chunks(self, chunks: List[str]) -> List[str]:
        """Merge small chunks and split large ones to target size."""
        result = []
        current_chunk = ""
        
        for chunk in chunks:
            # If adding this chunk exceeds target, save current and start new
            if len(current_chunk) + len(chunk) > self.chunk_size:
                if current_chunk:
                    result.append(current_chunk.strip())
                
                # If single chunk is too large, split it
                if len(chunk) > self.chunk_size:
                    # Split into smaller pieces
                    for i in range(0, len(chunk), self.chunk_size - self.chunk_overlap):
                        piece = chunk[i:i + self.chunk_size]
                        if piece.strip():
                            result.append(piece.strip())
                    current_chunk = ""
                else:
                    current_chunk = chunk
            else:
                current_chunk += chunk
        
        # Don't forget the last chunk
        if current_chunk.strip():
            result.append(current_chunk.strip())
        
        return result
    
    def get_stats(self, chunks: List[TextChunk]) -> Dict[str, Any]:
        """Get statistics about the chunks."""
        if not chunks:
            return {"total_chunks": 0}
        
        lengths = [len(c.text) for c in chunks]
        return {
            "total_chunks": len(chunks),
            "total_chars": sum(lengths),
            "avg_chunk_size": sum(lengths) / len(chunks),
            "min_chunk_size": min(lengths),
            "max_chunk_size": max(lengths),
        }
