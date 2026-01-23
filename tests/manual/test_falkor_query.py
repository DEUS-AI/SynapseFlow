import asyncio
import os
from src.infrastructure.falkor_backend import FalkorBackend

async def test_query():
    backend = FalkorBackend(host="localhost", port=6379)
    
    # Test query
    query = "MATCH (n:Table) RETURN n LIMIT 3"
    print(f"Executing: {query}")
    result = await backend.query(query)
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
    
if __name__ == "__main__":
    asyncio.run(test_query())
