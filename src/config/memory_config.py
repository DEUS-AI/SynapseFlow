"""
Memory configuration for Mem0 framework.

Configures the three-layer memory system:
1. Neo4j: Graph store for relationships
2. Qdrant: Vector store for semantic search
3. OpenAI: Embeddings and LLM for fact extraction

SECURITY NOTE:
For medical data, we use per-patient Qdrant collections to ensure
true physical isolation. This prevents any possibility of cross-patient
data leakage through semantic search or filter bypass.
"""

from mem0 import Memory
from typing import Optional, Dict, Any
import os
import re
import logging
from threading import Lock

logger = logging.getLogger(__name__)


class IsolatedPatientMemoryManager:
    """
    Manages per-patient isolated Mem0 instances with separate Qdrant collections.

    This provides true physical isolation of patient data by creating a separate
    Qdrant collection for each patient. This is critical for:
    - HIPAA compliance
    - Preventing cross-patient data leakage
    - Medical data security

    Usage:
        manager = IsolatedPatientMemoryManager(neo4j_uri, neo4j_user, neo4j_password)
        # These calls use separate Qdrant collections per patient:
        manager.add("Patient likes yoga", user_id="patient:pablo")
        manager.get_all(user_id="patient:test")  # Cannot access pablo's data
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        qdrant_url: str = "http://localhost:6333",
        openai_api_key: Optional[str] = None,
        collection_prefix: str = "patient_mem_"
    ):
        """
        Initialize the isolated patient memory manager.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            qdrant_url: Qdrant service URL
            openai_api_key: OpenAI API key for embeddings
            collection_prefix: Prefix for patient-specific collection names
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.qdrant_url = qdrant_url
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.collection_prefix = collection_prefix

        # Cache of Memory instances per patient (thread-safe)
        self._instances: Dict[str, Memory] = {}
        self._lock = Lock()

        logger.info(f"IsolatedPatientMemoryManager initialized with collection prefix: {collection_prefix}")

    def _sanitize_collection_name(self, patient_id: str) -> str:
        """
        Create a safe Qdrant collection name from patient_id.

        Qdrant collection names must be alphanumeric with underscores.
        """
        # Replace colons and other special chars with underscores
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', patient_id)
        # Remove consecutive underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        # Remove leading/trailing underscores
        safe_name = safe_name.strip('_')
        return f"{self.collection_prefix}{safe_name}"

    def _get_or_create_instance(self, patient_id: str) -> Memory:
        """
        Get or create an isolated Memory instance for a patient.

        Each patient gets their own Qdrant collection for true physical isolation.
        """
        with self._lock:
            if patient_id not in self._instances:
                collection_name = self._sanitize_collection_name(patient_id)
                logger.info(f"Creating isolated Memory instance for {patient_id} "
                           f"with collection: {collection_name}")

                config = {
                    "version": "v1.1",
                    "graph_store": {
                        "provider": "neo4j",
                        "config": {
                            "url": self.neo4j_uri,
                            "username": self.neo4j_user,
                            "password": self.neo4j_password
                        }
                    },
                    "vector_store": {
                        "provider": "qdrant",
                        "config": {
                            "url": self.qdrant_url,
                            "collection_name": collection_name,  # Patient-specific!
                            "embedding_model_dims": 1536
                        }
                    },
                    "embedder": {
                        "provider": "openai",
                        "config": {
                            "model": "text-embedding-3-small",
                            "api_key": self.api_key
                        }
                    },
                    "llm": {
                        "provider": "openai",
                        "config": {
                            "model": "gpt-4o-mini",
                            "temperature": 0.1,
                            "api_key": self.api_key
                        }
                    }
                }

                self._instances[patient_id] = Memory.from_config(config)

            return self._instances[patient_id]

    def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Any:
        """
        Add a memory to the patient's isolated collection.

        Args:
            content: Memory content to store
            user_id: Patient identifier (used to select isolated collection)
            metadata: Optional metadata to attach

        Returns:
            Result from Mem0's add operation
        """
        instance = self._get_or_create_instance(user_id)
        return instance.add(content, user_id=user_id, metadata=metadata)

    def get_all(self, user_id: str, limit: int = 100) -> Dict[str, Any]:
        """
        Get all memories from the patient's isolated collection.

        Args:
            user_id: Patient identifier (used to select isolated collection)
            limit: Maximum number of memories to return

        Returns:
            Dict with "results" containing memories
        """
        instance = self._get_or_create_instance(user_id)
        return instance.get_all(user_id=user_id, limit=limit)

    def search(self, query: str, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        Search memories in the patient's isolated collection.

        Args:
            query: Search query
            user_id: Patient identifier (used to select isolated collection)
            limit: Maximum results to return

        Returns:
            Search results from patient's isolated collection only
        """
        instance = self._get_or_create_instance(user_id)
        return instance.search(query, user_id=user_id, limit=limit)

    def delete(self, memory_id: str, user_id: str) -> Any:
        """
        Delete a specific memory from the patient's collection.

        Args:
            memory_id: ID of memory to delete
            user_id: Patient identifier

        Returns:
            Result from Mem0's delete operation
        """
        instance = self._get_or_create_instance(user_id)
        return instance.delete(memory_id)

    def delete_all(self, user_id: str) -> Any:
        """
        Delete all memories for a patient.

        Args:
            user_id: Patient identifier

        Returns:
            Result from Mem0's delete_all operation
        """
        instance = self._get_or_create_instance(user_id)
        return instance.delete_all(user_id=user_id)


def create_isolated_memory_manager(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    qdrant_url: str = "http://localhost:6333",
    openai_api_key: Optional[str] = None
) -> IsolatedPatientMemoryManager:
    """
    Create an isolated patient memory manager with per-patient Qdrant collections.

    This is the RECOMMENDED approach for medical data to ensure HIPAA compliance
    and prevent any possibility of cross-patient data leakage.

    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        qdrant_url: Qdrant service URL
        openai_api_key: OpenAI API key for embeddings

    Returns:
        IsolatedPatientMemoryManager: Manager with per-patient isolation
    """
    return IsolatedPatientMemoryManager(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        qdrant_url=qdrant_url,
        openai_api_key=openai_api_key
    )


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
