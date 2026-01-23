"""Verification script for Neo4j Backend Consolidation."""

import asyncio
import os
from src.composition_root import bootstrap_knowledge_management
from infrastructure.neo4j_backend import Neo4jBackend

# Set up environment for local Neo4j
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"

async def verify_neo4j_consolidation():
    print("🚀 Starting Neo4j Backend Verification...")
    
    # 1. Bootstrap Components
    print("\n1️⃣  Bootstrapping Knowledge Management...")
    kg_backend, event_bus = await bootstrap_knowledge_management()
    
    # 2. Verify Backend Type
    print(f"   Backend Type: {type(kg_backend).__name__}")
    if isinstance(kg_backend, Neo4jBackend):
        print("   ✅ Correctly using Neo4jBackend")
    else:
        print(f"   ❌ Error: Expected Neo4jBackend, got {type(kg_backend).__name__}")
        return

    # 3. Verify Connection & CRUD
    print("\n2️⃣  Verifying CRUD Operations...")
    test_id = "test_entity_consolidation"
    try:
        # Create
        await kg_backend.add_entity(test_id, {"name": "Test Entity", "layer": "VERIFICATION"})
        print("   ✅ Entity Created")
        
        # Read
        entity = await kg_backend.get_entity(test_id)
        if entity and entity["properties"]["name"] == "Test Entity":
            print("   ✅ Entity Read Verified")
        else:
            print(f"   ❌ Entity Read Failed: {entity}")
            
        # Cleanup
        await kg_backend.delete_entity(test_id)
        print("   ✅ Entity Deleted")
        
    except Exception as e:
        print(f"   ❌ CRUD Failed: {e}")
    finally:
        await kg_backend.close()

if __name__ == "__main__":
    asyncio.run(verify_neo4j_consolidation())
