#!/usr/bin/env python
"""Clear all memories for a patient (Mem0, Neo4j, Redis).

Usage: uv run python scripts/clear_patient_memories.py [patient_id]
Default patient_id: patient:demo
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path)
except ImportError:
    pass


async def clear_all_memories(patient_id: str = "patient:demo"):
    print(f"Clearing all memories for '{patient_id}'...")
    print("-" * 40)

    # 1. Clear Mem0
    print("\n[1/3] Clearing Mem0 memories...")
    try:
        from mem0 import Memory

        mem0_config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "model": "gpt-4o-mini"
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": os.getenv("QDRANT_HOST", "localhost"),
                    "port": int(os.getenv("QDRANT_PORT", "6333")),
                }
            }
        }
        mem0 = Memory.from_config(mem0_config)

        # Get count before deletion
        memories = mem0.get_all(user_id=patient_id, limit=100)
        count = len(memories.get("results", [])) if memories else 0

        mem0.delete_all(user_id=patient_id)
        print(f"  ✓ Deleted {count} Mem0 memories")
    except Exception as e:
        print(f"  ✗ Failed to clear Mem0: {e}")

    # 2. Clear Neo4j patient data
    print("\n[2/3] Clearing Neo4j patient data...")
    try:
        from infrastructure.neo4j_backend import Neo4jBackend

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        backend = Neo4jBackend(uri=neo4j_uri, username=neo4j_user, password=neo4j_password)

        # Count before deletion
        count_query = """
        MATCH (p:Patient {id: $patient_id})
        OPTIONAL MATCH (p)-[r]->(related)
        RETURN count(DISTINCT related) as count
        """
        count_result = await backend.query_raw(count_query, {"patient_id": patient_id})
        count = count_result[0]["count"] if count_result else 0

        # Delete patient and all related nodes
        query = """
        MATCH (p:Patient {id: $patient_id})
        OPTIONAL MATCH (p)-[r]->(related)
        DETACH DELETE p, related
        """
        await backend.query_raw(query, {"patient_id": patient_id})
        print(f"  ✓ Deleted patient and {count} related nodes")
    except Exception as e:
        print(f"  ✗ Failed to clear Neo4j: {e}")

    # 3. Clear Redis sessions
    print("\n[3/3] Clearing Redis sessions...")
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
