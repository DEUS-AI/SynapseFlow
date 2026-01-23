#!/usr/bin/env python3
"""Clear Neo4j database for fresh testing."""

from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password")
)

with driver.session() as session:
    # Delete all nodes and relationships
    result = session.run("MATCH (n) DETACH DELETE n")
    print("✅ Cleared all nodes and relationships from Neo4j")
    
    # Verify
    result = session.run("MATCH (n) RETURN count(n) as count")
    count = result.single()["count"]
    print(f"📊 Remaining nodes: {count}")

driver.close()
print("\n🔄 Ready for fresh modeling run!")
