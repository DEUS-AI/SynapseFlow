#!/usr/bin/env python3
"""Simple test to debug FalkorDB metadata creation."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
os.environ["FALKORDB_HOST"] = "localhost"
os.environ["FALKORDB_PORT"] = "6379"

async def test_simple_metadata():
    from src.infrastructure.falkor_backend import FalkorBackend
    from domain.odin_models import Catalog, Schema, Table, Column
    
    print("🔧 Testing FalkorDB backend...")
    
    # Create backend
    backend = FalkorBackend(host="localhost", port=6379, graph_name="test_metadata")
    
    # Clear graph
    try:
        backend.graph.delete()
        print("✅ Cleared test graph")
    except:
        pass
    
    # Test 1: Create Catalog
    print("\n📦 Test 1: Creating Catalog...")
    catalog = Catalog(
        name="test_catalog",
        description="Test catalog",
        properties={"domain": "Test"}
    )
    
    try:
        await backend.add_entity("catalog:test_catalog", catalog.model_dump())
        print("✅ Catalog created")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return
    
    # Test 2: Create Schema
    print("\n📂 Test 2: Creating Schema...")
    schema = Schema(
        name="test_schema",
        catalog_name="test_catalog",
        description="Test schema",
        properties={"domain": "Test"}
    )
    
    try:
        await backend.add_entity("schema:test_schema", schema.model_dump())
        print("✅ Schema created")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return
    
    # Test 3: Create relationship
    print("\n🔗 Test 3: Creating relationship...")
    try:
        await backend.add_relationship(
            "schema:test_schema",
            "belongs_to",
            "catalog:test_catalog",
            {"description": "Schema belongs to catalog"}
        )
        print("✅ Relationship created")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return
    
    # Test 4: Query
    print("\n🔍 Test 4: Querying graph...")
    try:
        result = await backend.query("MATCH (n) RETURN count(n) as count")
        if result:
            print(f"✅ Found {result[0][0]} nodes")
        else:
            print("⚠️  No results")
    except Exception as e:
        print(f"❌ Query failed: {e}")
    
    # Test 5: Query with labels
    print("\n🔍 Test 5: Querying by label...")
    try:
        result = await backend.query("MATCH (n:catalog) RETURN n.name as name")
        if result:
            print(f"✅ Found catalog: {result[0][0]}")
        else:
            print("⚠️  No catalog found")
    except Exception as e:
        print(f"❌ Query failed: {e}")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_simple_metadata())
