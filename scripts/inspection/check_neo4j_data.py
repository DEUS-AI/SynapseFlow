#!/usr/bin/env python3
"""
Script to check what data is actually stored in Neo4j after running modeling commands.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

async def check_neo4j_data():
    """Check what data is in Neo4j."""
    
    print("🔍 Checking Neo4j data directly...")
    
    # Load environment variables
    load_dotenv()
    
    uri = os.environ.get("NEO4J_URI")
    username = os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER", "neo4j"))
    password = os.environ.get("NEO4J_PASSWORD")
    
    print(f"Connecting to: {uri}")
    print(f"Username: {username}")
    
    try:
        # Connect directly to Neo4j
        driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        
        async with driver.session() as session:
            # Test connection
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            print("✅ Connected to Neo4j successfully!")
            
            # Get all nodes
            print("\n📊 NODE STATISTICS:")
            print("=" * 50)
            
            result = await session.run("MATCH (n) RETURN count(n) as count")
            record = await result.single()
            total_nodes = record["count"]
            print(f"Total nodes: {total_nodes}")
            
            # Count nodes by label
            result = await session.run("""
                MATCH (n)
                RETURN labels(n) as labels, count(n) as count
                ORDER BY count DESC
            """)
            
            print("\nNodes by label:")
            async for record in result:
                labels = record["labels"]
                count = record["count"]
                print(f"  {labels}: {count}")
            
            # Get all relationships
            print("\n🔗 RELATIONSHIP STATISTICS:")
            print("=" * 50)
            
            result = await session.run("MATCH ()-[r]->() RETURN count(r) as count")
            record = await result.single()
            total_rels = record["count"]
            print(f"Total relationships: {total_rels}")
            
            # Count relationships by type
            result = await session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            """)
            
            print("\nRelationships by type:")
            async for record in result:
                rel_type = record["type"]
                count = record["count"]
                print(f"  {rel_type}: {count}")
            
            # Check for episodes
            print("\n📄 EPISODE DATA:")
            print("=" * 50)
            
            result = await session.run("""
                MATCH (e:Episode)
                RETURN e.name as name, e.uuid as uuid, e.group_id as group_id
                ORDER BY e.name
            """)
            
            episodes = []
            async for record in result:
                episodes.append(record)
            
            print(f"Found {len(episodes)} episodes:")
            for record in episodes:
                name = record["name"]
                uuid = record["uuid"]
                group_id = record["group_id"]
                print(f"  📄 {name}")
                print(f"     UUID: {uuid}")
                print(f"     Group ID: {group_id}")
            
            # Check for DDA-specific data
            print("\n🏥 DDA-SPECIFIC DATA:")
            print("=" * 50)
            
            # Look for nodes with DDA-related properties
            result = await session.run("""
                MATCH (n)
                WHERE n.name CONTAINS 'DDA' OR n.name CONTAINS 'Crohn' OR n.name CONTAINS 'Patient'
                RETURN labels(n) as labels, n.name as name, n.description as description
                ORDER BY labels(n), n.name
                LIMIT 20
            """)
            
            print("\nDDA-related nodes:")
            async for record in result:
                labels = record["labels"]
                name = record["name"]
                description = record["description"]
                if description and len(description) > 50:
                    description = description[:50] + "..."
                print(f"  {labels}: {name} - {description}")
            
            # Check for relationships between entities
            print("\n🔗 ENTITY RELATIONSHIPS:")
            print("=" * 50)
            
            result = await session.run("""
                MATCH (e1:DataEntity)-[r]->(e2:DataEntity)
                RETURN e1.name as source, type(r) as relationship, e2.name as target
                ORDER BY e1.name, e2.name
                LIMIT 20
            """)
            
            print("\nEntity relationships:")
            async for record in result:
                source = record["source"]
                rel_type = record["relationship"]
                target = record["target"]
                print(f"  {source} --[{rel_type}]--> {target}")
            
            # Check for any relationships in DDA episodes
            print("\n🔗 DDA EPISODE RELATIONSHIPS:")
            print("=" * 50)
            
            result = await session.run("""
                MATCH (e:Episode)-[:HAS_NODE]->(n)-[r]->(m)
                WHERE e.name CONTAINS 'DDA'
                RETURN e.name as episode, n.name as source, type(r) as relationship, m.name as target
                ORDER BY e.name, n.name
                LIMIT 20
            """)
            
            print("\nDDA episode relationships:")
            async for record in result:
                episode = record["episode"]
                source = record["source"]
                rel_type = record["relationship"]
                target = record["target"]
                print(f"  [{episode}] {source} --[{rel_type}]--> {target}")
        
        await driver.close()
        print("\n✅ Neo4j data check completed!")
        
    except Exception as e:
        print(f"❌ Error checking Neo4j data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_neo4j_data()) 