"""Test script for LLM-based reasoning in Knowledge Manager."""

import asyncio
from composition_root import bootstrap_graphiti, bootstrap_knowledge_management
from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
from domain.event import KnowledgeEvent
from domain.roles import Role

async def test_llm_reasoning():
    """Test LLM reasoning capabilities."""
    
    # Set up environment for local Neo4j
    import os
    os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    os.environ["NEO4J_USERNAME"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "password"
    
    # Bootstrap components
    print("🔧 Initializing components...")
    graphiti = await bootstrap_graphiti()
    kg_backend, event_bus = bootstrap_knowledge_management()
    
    # Create Reasoning Engine with LLM
    print("🔧 Creating Reasoning Engine with LLM...")
    reasoning_engine = ReasoningEngine(kg_backend, llm=graphiti)
    
    # Test entity creation with LLM reasoning
    print("\n📊 Testing LLM reasoning on entity creation...")
    
    test_event = KnowledgeEvent(
        action="create_entity",
        data={
            "id": "customer:john_doe",
            "properties": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "customer_since": "2020-01-15",
                "total_orders": 42,
                "layer": "PERCEPTION"
            }
        },
        role=Role.DATA_ENGINEER
    )
    
    # Apply reasoning
    reasoning_result = await reasoning_engine.apply_reasoning(test_event)
    
    print("\n✅ Reasoning Results:")
    print(f"   Applied Rules: {reasoning_result['applied_rules']}")
    print(f"   Reasoning Time: {reasoning_result['reasoning_time']}")
    
    if reasoning_result.get('inferences'):
        print(f"\n🔍 Inferences ({len(reasoning_result['inferences'])}):")
        for inf in reasoning_result['inferences']:
            print(f"   - {inf}")
    
    if reasoning_result.get('suggestions'):
        print(f"\n💡 Suggestions ({len(reasoning_result['suggestions'])}):")
        for sug in reasoning_result['suggestions']:
            print(f"   - {sug}")
    
    if reasoning_result.get('warnings'):
        print(f"\n⚠️  Warnings ({len(reasoning_result['warnings'])}):")
        for warn in reasoning_result['warnings']:
            print(f"   - {warn}")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_llm_reasoning())

