"""
Memory configuration for Mem0 framework.

Configures the three-layer memory system:
1. Neo4j: Graph store for relationships
2. Qdrant: Vector store for semantic search
3. OpenAI: Embeddings and LLM for fact extraction
"""

from mem0 import Memory
from typing import Optional
import os


def create_memory_instance(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    qdrant_url: str = "http://localhost:6333",
    openai_api_key: Optional[str] = None
) -> Memory:
    """
    Initialize Mem0 with Neo4j graph + Qdrant vector store.

    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        qdrant_url: Qdrant service URL (default: http://localhost:6333)
        openai_api_key: OpenAI API key for embeddings (optional, uses env var if None)

    Returns:
        Memory: Configured Mem0 Memory instance
    """
    # Use provided API key or fall back to environment variable
    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

    config = {
        "version": "v1.1",

        # Graph store for relationships
        "graph_store": {
            "provider": "neo4j",
            "config": {
                "url": neo4j_uri,
                "username": neo4j_user,
                "password": neo4j_password
            }
        },

        # Vector store for semantic search
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "url": qdrant_url,
                "collection_name": "patient_memories",
                "embedding_model_dims": 1536  # OpenAI text-embedding-3-small
            }
        },

        # Embedding model
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "api_key": api_key
            }
        },

        # LLM for fact extraction
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "temperature": 0.1,  # More deterministic for fact extraction
                "api_key": api_key
            }
        }
    }

    return Memory.from_config(config)
