
import asyncio
import os
from graphiti_core import Graphiti

async def explore_graphiti():
    print("Exploring Graphiti Core...")
    # We might not have a real Neo4j connection for Graphiti in this environment if it requires one.
    # But we can inspect the class.
    
    print("\nGraphiti methods:")
    for method in dir(Graphiti):
        if not method.startswith("_"):
            print(f" - {method}")
            
    # Check if we can instantiate it without a real connection just to check methods
    try:
        g = Graphiti("bolt://localhost:7687", "neo4j", "password")
        print("\nDriver methods:")
        for method in dir(g.driver):
            if not method.startswith("_"):
                print(f" - {method}")
    except Exception as e:
        print(f"\nCould not instantiate Graphiti: {e}")

if __name__ == "__main__":
    asyncio.run(explore_graphiti())
