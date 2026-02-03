"""Test script for Knowledge Graph API."""

import os
from fastapi.testclient import TestClient
from src.application.api.main import app

# Set up environment for local Neo4j
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"

client = TestClient(app)

def test_api():
    print("🚀 Starting API Tests...")
    
    # 1. Health Check
    print("\n1️⃣  Testing Health Check...")
    response = client.get("/health")
    assert response.status_code == 200
    print(f"✅ Health Check Passed: {response.json()}")
    
    # 2. Raw Query (Admin)
    print("\n2️⃣  Testing Raw Cypher Query...")
    # Simple query to count nodes
    query = {"query": "MATCH (n) RETURN count(n) as count LIMIT 1"}
    response = client.post("/graph/query", json=query)
    
    if response.status_code == 200:
        print(f"✅ Raw Query Passed: {response.json()}")
    else:
        print(f"❌ Raw Query Failed: {response.text}")
        
    # 3. Pre-defined View
    print("\n3️⃣  Testing Pre-defined View (domain_summary)...")
    response = client.get("/graph/view/domain_summary")
    
    if response.status_code == 200:
        print(f"✅ View Query Passed: {response.json()}")
    else:
        print(f"❌ View Query Failed: {response.text}")

    # 4. Text-to-Cypher (Mock)
    print("\n4️⃣  Testing Text-to-Cypher (Mock)...")
    ask = {"question": "How many tables are there?"}
    response = client.post("/graph/ask", json=ask)
    
    if response.status_code == 200:
        print(f"✅ Text-to-Cypher Passed: {response.json()}")
    else:
        print(f"❌ Text-to-Cypher Failed: {response.text}")

if __name__ == "__main__":
    test_api()
