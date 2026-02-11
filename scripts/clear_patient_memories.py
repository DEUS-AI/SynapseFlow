#!/usr/bin/env python
"""Clear all memories for a patient (Mem0, Neo4j, Redis, Qdrant).

Usage: uv run python scripts/clear_patient_memories.py [patient_id]
Default patient_id: patient:demo

This script clears:
1. Mem0 memories via IsolatedPatientMemoryManager (per-patient Qdrant collections)
2. Qdrant collection directly (ensures complete cleanup)
3. Neo4j patient data + Mem0 graph nodes (Patient entities + memory relationships)
4. Redis sessions (conversation cache)
"""

import asyncio
import sys
import os
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path)
except ImportError:
    pass


def sanitize_collection_name(patient_id: str, prefix: str = "patient_mem_") -> str:
    """
    Create a safe Qdrant collection name from patient_id.
    Must match IsolatedPatientMemoryManager._sanitize_collection_name()
    """
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', patient_id)
    safe_name = re.sub(r'_+', '_', safe_name)
    safe_name = safe_name.strip('_')
    return f"{prefix}{safe_name}"


async def clear_all_memories(patient_id: str = "patient:demo"):
    print(f"Clearing all memories for '{patient_id}'...")
    print("-" * 50)

    # 1. Clear Mem0 via IsolatedPatientMemoryManager (same config as app uses)
    print("\n[1/4] Clearing Mem0 memories (IsolatedPatientMemoryManager)...")
    collection_name = sanitize_collection_name(patient_id)
    print(f"  → Target collection: {collection_name}")

    try:
        from config.memory_config import IsolatedPatientMemoryManager

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

        manager = IsolatedPatientMemoryManager(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            qdrant_url=qdrant_url,
        )

        # Get count before deletion
        memories = manager.get_all(user_id=patient_id, limit=100)
        count = len(memories.get("results", [])) if memories else 0

        # Delete via Mem0
        manager.delete_all(user_id=patient_id)
        print(f"  ✓ Deleted {count} Mem0 memories via IsolatedPatientMemoryManager")

    except Exception as e:
        print(f"  ✗ Failed to clear via IsolatedPatientMemoryManager: {e}")
        print("  → Trying direct Qdrant collection deletion...")

    # 2. Also delete Qdrant collection directly (in case Mem0 delete_all doesn't fully clear)
    print("\n[2/4] Clearing Qdrant collection directly...")
    try:
        from qdrant_client import QdrantClient

        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

        client = QdrantClient(host=qdrant_host, port=qdrant_port)

        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if collection_name in collection_names:
            client.delete_collection(collection_name)
            print(f"  ✓ Deleted Qdrant collection: {collection_name}")
        else:
            print(f"  ○ Collection '{collection_name}' not found (already clean)")

        # List remaining patient collections for reference (refresh after deletion)
        collections_after = client.get_collections().collections
        remaining = [c.name for c in collections_after if c.name.startswith("patient_mem_")]
        if remaining:
            print(f"  ℹ Remaining patient collections: {remaining}")

    except Exception as e:
        print(f"  ✗ Failed to clear Qdrant: {e}")

    # 3. Clear Neo4j patient data + Mem0 graph data
    print("\n[3/4] Clearing Neo4j patient data + Mem0 graph...")
    try:
        from infrastructure.neo4j_backend import Neo4jBackend

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        backend = Neo4jBackend(uri=neo4j_uri, username=neo4j_user, password=neo4j_password)

        # Count before deletion (Patient nodes)
        count_query = """
        MATCH (p:Patient {id: $patient_id})
        OPTIONAL MATCH (p)-[r]->(related)
        RETURN count(DISTINCT related) as count
        """
        count_result = await backend.query_raw(count_query, {"patient_id": patient_id})
        patient_count = count_result[0]["count"] if count_result else 0

        # Delete patient and all related nodes
        query = """
        MATCH (p:Patient {id: $patient_id})
        OPTIONAL MATCH (p)-[r]->(related)
        DETACH DELETE p, related
        """
        await backend.query_raw(query, {"patient_id": patient_id})
        print(f"  ✓ Deleted patient and {patient_count} related entities")

        # Also clear Mem0's Neo4j graph data (stored with user_id property)
        # Mem0 uses nodes with user_id to track memory relationships
        mem0_count_query = """
        MATCH (n)
        WHERE n.user_id = $patient_id
        RETURN count(n) as count
        """
        mem0_count_result = await backend.query_raw(mem0_count_query, {"patient_id": patient_id})
        mem0_count = mem0_count_result[0]["count"] if mem0_count_result else 0

        if mem0_count > 0:
            mem0_delete_query = """
            MATCH (n)
            WHERE n.user_id = $patient_id
            DETACH DELETE n
            """
            await backend.query_raw(mem0_delete_query, {"patient_id": patient_id})
            print(f"  ✓ Deleted {mem0_count} Mem0 graph nodes")
        else:
            print(f"  ○ No Mem0 graph nodes found for {patient_id}")

    except Exception as e:
        print(f"  ✗ Failed to clear Neo4j: {e}")

    # 4. Clear Redis sessions
    print("\n[4/4] Clearing Redis sessions...")
    try:
        from infrastructure.redis_session_cache import RedisSessionCache

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6380"))

        redis_cache = RedisSessionCache(host=redis_host, port=redis_port)
        sessions = await redis_cache.list_patient_sessions(patient_id)
        for session_id in sessions:
            await redis_cache.delete_session(session_id)
        print(f"  ✓ Deleted {len(sessions)} Redis sessions")
    except Exception as e:
        print(f"  ✗ Failed to clear Redis: {e}")

    print("\n" + "=" * 40)
    print("✅ Done! You can now test with a fresh patient.")


if __name__ == "__main__":
    patient_id = sys.argv[1] if len(sys.argv) > 1 else "patient:demo"
    asyncio.run(clear_all_memories(patient_id))
