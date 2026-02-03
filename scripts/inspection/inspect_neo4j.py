#!/usr/bin/env python3
"""Detailed inspection of Neo4j graph structure."""

from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password")
)

with driver.session() as session:
    print("=" * 70)
    print("RELATIONSHIP TYPES IN GRAPH")
    print("=" * 70)
    
    # Get all relationship types
    result = session.run("""
        MATCH ()-[r]->()
        RETURN DISTINCT type(r) as rel_type, count(*) as count
        ORDER BY count DESC
    """)
    
    print("\nRelationship Types:")
    for record in result:
        print(f"  - {record['rel_type']}: {record['count']}")
    
    print("\n" + "=" * 70)
    print("SAMPLE ENTITIES")
    print("=" * 70)
    
    # Get sample entities with their properties
    result = session.run("""
        MATCH (n:Entity)
        RETURN n.name as name, n.summary as summary, labels(n) as labels
        LIMIT 10
    """)
    
    print("\nSample Entities:")
    for record in result:
        print(f"\n  Name: {record['name']}")
        print(f"  Summary: {record['summary'][:100] if record['summary'] else 'N/A'}...")
        print(f"  Labels: {record['labels']}")
    
    print("\n" + "=" * 70)
    print("SAMPLE RELATIONSHIPS")
    print("=" * 70)
    
    # Get sample relationships with context
    result = session.run("""
        MATCH (a:Entity)-[r]->(b:Entity)
        RETURN a.name as source, type(r) as rel_type, b.name as target, r.fact as fact
        LIMIT 15
    """)
    
    print("\nSample Relationships:")
    for record in result:
        print(f"\n  {record['source']} --[{record['rel_type']}]--> {record['target']}")
        if record['fact']:
            print(f"  Fact: {record['fact'][:150]}...")
    
    print("\n" + "=" * 70)
    print("ENTITY TYPES DISTRIBUTION")
    print("=" * 70)
    
    # Check if entities have type information
    result = session.run("""
        MATCH (n:Entity)
        WHERE n.name IS NOT NULL
        RETURN n.name as name
        ORDER BY n.name
        LIMIT 30
    """)
    
    print("\nEntity Names (first 30):")
    for i, record in enumerate(result, 1):
        print(f"  {i}. {record['name']}")

driver.close()
