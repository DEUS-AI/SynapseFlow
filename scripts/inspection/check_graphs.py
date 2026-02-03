#!/usr/bin/env python3
"""Quick script to check what's in Neo4j and FalkorDB."""

import asyncio
from neo4j import GraphDatabase
from falkordb import FalkorDB

async def check_neo4j():
    """Check Neo4j for Graphiti data."""
    print("=" * 60)
    print("NEO4J (Architecture Graph - Graphiti)")
    print("=" * 60)
    
    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )
    
    with driver.session() as session:
        # Count entities
        result = session.run("MATCH (n:Entity) RETURN count(n) as count")
        entity_count = result.single()["count"]
        print(f"📊 Entities: {entity_count}")
        
        # Count relationships
        result = session.run("MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count")
        rel_count = result.single()["count"]
        print(f"🔗 Relationships: {rel_count}")
        
        # Get sample entities
        result = session.run("MATCH (n:Entity) RETURN n.name as name LIMIT 5")
        print(f"\n📝 Sample Entities:")
        for record in result:
            print(f"   - {record['name']}")
    
    driver.close()

def check_falkordb():
    """Check FalkorDB for ODIN metadata."""
    print("\n" + "=" * 60)
    print("FALKORDB (Metadata Graph - ODIN)")
    print("=" * 60)
    
    client = FalkorDB(host="localhost", port=6379)
    graph = client.select_graph("knowledge_graph")
    
    # Count all nodes
    result = graph.query("MATCH (n) RETURN count(n) as count")
    node_count = result.result_set[0][0] if result.result_set else 0
    print(f"📊 Total Nodes: {node_count}")
    
    # Count by label
    result = graph.query("MATCH (n) RETURN labels(n)[0] as label, count(n) as count")
    if result.result_set:
        print(f"\n📝 Nodes by Label:")
        for row in result.result_set:
            print(f"   - {row[0]}: {row[1]}")
    
    # Sample nodes
    result = graph.query("MATCH (n) RETURN n LIMIT 5")
    if result.result_set:
        print(f"\n🔍 Sample Nodes:")
        for row in result.result_set:
            node = row[0]
            print(f"   - {node}")

if __name__ == "__main__":
    asyncio.run(check_neo4j())
    check_falkordb()
    
    print("\n" + "=" * 60)
    print("✅ Check complete!")
    print("=" * 60)
    print("\n💡 To view graphs:")
    print("   - Neo4j Browser: http://localhost:7474")
    print("   - FalkorDB Browser: http://localhost:3000")
