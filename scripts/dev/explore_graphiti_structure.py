#!/usr/bin/env python3
"""
Script to explore the actual Graphiti structure in Neo4j.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

async def explore_graphiti_structure():
    """Explore the actual Graphiti structure in Neo4j."""
    
    print("🔍 Exploring Graphiti structure in Neo4j...")
    
    # Load environment variables
    load_dotenv()
    
    uri = os.environ.get("NEO4J_URI")
    username = os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER", "neo4j"))
    password = os.environ.get("NEO4J_PASSWORD")
    
    try:
        # Connect directly to Neo4j
        driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        
        async with driver.session() as session:
            print("✅ Connected to Neo4j successfully!")
            
            # Get all labels
            print("\n📊 ALL LABELS:")
            print("=" * 50)
            
            result = await session.run("CALL db.labels() YIELD label RETURN label ORDER BY label")
            labels = []
            async for record in result:
                labels.append(record["label"])
                print(f"  - {record['label']}")
            
            # Get all relationship types
            print("\n🔗 ALL RELATIONSHIP TYPES:")
            print("=" * 50)
            
            result = await session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType")
            rel_types = []
            async for record in result:
                rel_types.append(record["relationshipType"])
                print(f"  - {record['relationshipType']}")
            
            # Get all property keys
            print("\n🔑 ALL PROPERTY KEYS:")
            print("=" * 50)
            
            result = await session.run("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey")
            properties = []
            async for record in result:
                properties.append(record["propertyKey"])
                print(f"  - {record['propertyKey']}")
            
            # Explore Entity nodes (these seem to be the main nodes)
            print("\n🏗️ ENTITY NODES:")
            print("=" * 50)
            
            result = await session.run("""
                MATCH (e:Entity)
                RETURN e.name as name, e.text as text, e.embedding as has_embedding
                ORDER BY e.name
                LIMIT 10
            """)
            
            print("Sample Entity nodes:")
            async for record in result:
                name = record["name"]
                text = record["text"]
                has_embedding = "Yes" if record["has_embedding"] else "No"
                if text and len(text) > 100:
                    text = text[:100] + "..."
                print(f"  📄 {name}")
                print(f"     Text: {text}")
                print(f"     Has embedding: {has_embedding}")
                print()
            
            # Explore Episodic nodes (these seem to be episodes)
            print("\n📚 EPISODIC NODES:")
            print("=" * 50)
            
            result = await session.run("""
                MATCH (e:Episodic)
                RETURN e.name as name, e.text as text, e.uuid as uuid, e.group_id as group_id
                ORDER BY e.name
                LIMIT 10
            """)
            
            print("Sample Episodic nodes:")
            async for record in result:
                name = record["name"]
                text = record["text"]
                uuid = record["uuid"]
                group_id = record["group_id"]
                if text and len(text) > 100:
                    text = text[:100] + "..."
                print(f"  📚 {name}")
                print(f"     UUID: {uuid}")
                print(f"     Group ID: {group_id}")
                print(f"     Text: {text}")
                print()
            
            # Explore relationships
            print("\n🔗 RELATIONSHIPS:")
            print("=" * 50)
            
            # MENTIONS relationships
            print("MENTIONS relationships (sample):")
            result = await session.run("""
                MATCH (a)-[r:MENTIONS]->(b)
                RETURN a.name as source, b.name as target, r.weight as weight
                ORDER BY r.weight DESC
                LIMIT 10
            """)
            
            async for record in result:
                source = record["source"]
                target = record["target"]
                weight = record["weight"]
                print(f"  {source} --[MENTIONS weight:{weight}]--> {target}")
            
            # RELATES_TO relationships
            print("\nRELATES_TO relationships (sample):")
            result = await session.run("""
                MATCH (a)-[r:RELATES_TO]->(b)
                RETURN a.name as source, b.name as target, r.weight as weight
                ORDER BY r.weight DESC
                LIMIT 10
            """)
            
            async for record in result:
                source = record["source"]
                target = record["target"]
                weight = record["weight"]
                print(f"  {source} --[RELATES_TO weight:{weight}]--> {target}")
            
            # Look for DDA-specific episodes
            print("\n🏥 DDA EPISODES:")
            print("=" * 50)
            
            result = await session.run("""
                MATCH (e:Episodic)
                WHERE e.name CONTAINS 'DDA'
                RETURN e.name as name, e.uuid as uuid, e.group_id as group_id
                ORDER BY e.name
            """)
            
            dda_episodes = []
            async for record in result:
                dda_episodes.append(record)
            
            print(f"Found {len(dda_episodes)} DDA episodes:")
            for record in dda_episodes:
                name = record["name"]
                uuid = record["uuid"]
                group_id = record["group_id"]
                print(f"  📚 {name}")
                print(f"     UUID: {uuid}")
                print(f"     Group ID: {group_id}")
            
            # Check what entities are connected to DDA episodes
            if dda_episodes:
                print("\n🔗 DDA EPISODE ENTITIES:")
                print("=" * 50)
                
                # Get entities that mention DDA episodes
                result = await session.run("""
                    MATCH (e:Entity)-[r:MENTIONS]->(ep:Episodic)
                    WHERE ep.name CONTAINS 'DDA'
                    RETURN e.name as entity, ep.name as episode, r.weight as weight
                    ORDER BY r.weight DESC
                    LIMIT 20
                """)
                
                print("Entities that mention DDA episodes:")
                async for record in result:
                    entity = record["entity"]
                    episode = record["episode"]
                    weight = record["weight"]
                    print(f"  {entity} --[MENTIONS weight:{weight}]--> {episode}")
                
                # Get entities that are related to DDA episodes
                result = await session.run("""
                    MATCH (e:Entity)-[r:RELATES_TO]->(ep:Episodic)
                    WHERE ep.name CONTAINS 'DDA'
                    RETURN e.name as entity, ep.name as episode, r.weight as weight
                    ORDER BY r.weight DESC
                    LIMIT 20
                """)
                
                print("\nEntities that relate to DDA episodes:")
                async for record in result:
                    entity = record["entity"]
                    episode = record["episode"]
                    weight = record["weight"]
                    print(f"  {entity} --[RELATES_TO weight:{weight}]--> {episode}")
        
        await driver.close()
        print("\n✅ Graphiti structure exploration completed!")
        
    except Exception as e:
        print(f"❌ Error exploring Graphiti structure: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(explore_graphiti_structure()) 