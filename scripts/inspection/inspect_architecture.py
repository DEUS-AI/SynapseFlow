#!/usr/bin/env python3
"""Inspect the new architecture graph structure."""

from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password")
)

with driver.session() as session:
    print("=" * 70)
    print("ARCHITECTURE GRAPH STRUCTURE")
    print("=" * 70)
    
    # Get all node labels
    result = session.run("""
        MATCH (n)
        RETURN DISTINCT labels(n) as labels, count(*) as count
        ORDER BY count DESC
    """)
    
    print("\nNode Types:")
    for record in result:
        print(f"  - {record['labels']}: {record['count']}")
    
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
    print("DOMAIN")
    print("=" * 70)
    
    # Get domain
    result = session.run("""
        MATCH (d:Domain)
        RETURN d.name as name, d.description as description
    """)
    
    for record in result:
        print(f"\nDomain: {record['name']}")
        print(f"Description: {record['description'][:100]}...")
    
    print("\n" + "=" * 70)
    print("DATA ENTITIES")
    print("=" * 70)
    
    # Get entities
    result = session.run("""
        MATCH (e:DataEntity)
        RETURN e.name as name, e.description as description, 
               e.primary_key as pk, e.foreign_keys as fks
        ORDER BY e.name
    """)
    
    print("\nEntities:")
    for record in result:
        print(f"\n  {record['name']}:")
        print(f"    Description: {record['description'][:80]}...")
        print(f"    Primary Key: {record['pk']}")
        if record['fks']:
            print(f"    Foreign Keys: {', '.join(record['fks'])}")
    
    print("\n" + "=" * 70)
    print("ENTITY RELATIONSHIPS")
    print("=" * 70)
    
    # Get entity relationships
    result = session.run("""
        MATCH (source:DataEntity)-[r]->(target:DataEntity)
        RETURN source.name as source, type(r) as rel_type, 
               target.name as target, r.cardinality as cardinality,
               r.description as description
    """)
    
    print("\nRelationships:")
    for record in result:
        print(f"\n  {record['source']} --[{record['rel_type']}]--> {record['target']}")
        print(f"    Cardinality: {record['cardinality']}")
        print(f"    Description: {record['description'][:80]}...")
    
    print("\n" + "=" * 70)
    print("ATTRIBUTES")
    print("=" * 70)
    
    # Get sample attributes
    result = session.run("""
        MATCH (e:DataEntity)-[:HAS_ATTRIBUTE]->(a:Attribute)
        RETURN e.name as entity, collect(a.name) as attributes
        ORDER BY e.name
    """)
    
    print("\nEntity Attributes:")
    for record in result:
        print(f"\n  {record['entity']}:")
        for attr in record['attributes']:
            print(f"    - {attr}")

driver.close()
