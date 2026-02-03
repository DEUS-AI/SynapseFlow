
import pytest
import sys
import os
from unittest.mock import MagicMock, AsyncMock

sys.path.append(os.getcwd())

from src.application.services.knowledge_enricher import KnowledgeEnricher
from domain.ontologies.odin import ODIN

@pytest.mark.asyncio
async def test_enrich_entity():
    # Mock Graphiti
    mock_graph = MagicMock()
    
    # Mock LLM response (since we haven't implemented the actual call yet, we need to mock _call_llm)
    enricher = KnowledgeEnricher(mock_graph)
    
    # Mock the _call_llm method
    enricher._call_llm = AsyncMock(return_value={
        "concept": "Customer",
        "relationship": "represents",
        "confidence": 0.9,
        "reason": "Entity has customer attributes"
    })
    
    entity_data = {
        "id": "table:sales.customers",
        "name": "customers",
        "type": "Table",
        "attributes": ["id", "name", "email"]
    }
    
    inferences = await enricher.enrich_entity(entity_data)
    
    assert len(inferences) == 2
    
    # Check Node
    node = next(i for i in inferences if i["type"] == "node")
    assert ODIN.BUSINESS_CONCEPT in node["labels"]
    assert node["properties"]["name"] == "Customer"
    assert node["properties"][ODIN.STATUS] == "hypothetical"
    
    # Check Relationship
    rel = next(i for i in inferences if i["type"] == "relationship")
    assert rel["source_id"] == "table:sales.customers"
    assert rel["target_id"] == "concept:Customer"
    assert rel["rel_type"] == ODIN.REPRESENTS

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_enrich_entity())
        print("✅ test_enrich_entity passed")
    except Exception as e:
        print(f"❌ Tests failed: {e}")
