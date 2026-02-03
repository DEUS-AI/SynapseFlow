import asyncio
from src.infrastructure.falkor_backend import FalkorBackend

async def test_labels():
    backend = FalkorBackend(host="localhost", port=6379)
    
    # Check all node labels
    query = "MATCH (n) RETURN labels(n)[0] as label, count(n) as count"
    print(f"Executing: {query}")
    result = await backend.query(query)
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
    
if __name__ == "__main__":
    asyncio.run(test_labels())
