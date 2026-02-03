"""Verification script for Relationship Densification."""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List

from infrastructure.in_memory_backend import InMemoryGraphBackend
from application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
from domain.dda_models import DDADocument, DataEntity
from domain.event import KnowledgeEvent
from src.domain.knowledge_layers import KnowledgeLayer
from domain.roles import Role

# Mock Graphiti/LLM
class MockGraphiti:
    async def add_episode(self, **kwargs):
        # Mock response for semantic linking
        if "concept_linking" in kwargs.get("name", ""):
            class MockEdge:
                def __init__(self, target, name):
                    self.target_node_uuid = target
                    self.name = name
            
            class MockEpisode:
                edges = [MockEdge("Customer Concept", "represents")]
            
            return MockEpisode()
        return None

# Mock DDA with raw and dim tables
mock_dda = DDADocument(
    domain="Sales",
    business_context="Sales data",
    data_owner="jane.doe",
    stakeholders=["finance"],
    effective_date=datetime.now(),
    entities=[
        DataEntity(
            name="raw_orders",
            description="Raw orders data",
            attributes=["order_id", "amount"],
            origin="ERP"
        ),
        DataEntity(
            name="dim_orders",
            description="Cleaned orders dimension",
            attributes=["order_id", "total_amount"],
            origin="Warehouse"
        )
    ],
    relationships=[]
)

async def verify_densification():
    print("🚀 Starting Relationship Densification Verification...")
    
    # Setup
    kg_backend = InMemoryGraphBackend()
    
    # Mock Type Inference
    class MockTypeInference:
        async def infer_data_type(self, *args):
            from domain.odin_models import DataTypeEntity
            return DataTypeEntity(name="VARCHAR", base_type="STRING")
        async def infer_precision(self, *args): return 50
        async def infer_scale(self, *args): return None
        
    builder = MetadataGraphBuilder(kg_backend, MockTypeInference())
    
    # 1. Verify Lineage Inference (MetadataGraphBuilder)
    print("\n1️⃣  Verifying Lineage Inference...")
    await builder.build_metadata_graph(mock_dda)
    
    # Check for relationship between raw_orders and dim_orders
    # Note: InMemoryBackend stores edges as list of tuples in a dict keyed by source_id
    # We need to find the ID for raw_orders
    raw_id = "table:sales_schema.raw_orders"
    dim_id = "table:sales_schema.dim_orders"
    
    edges = kg_backend.edges.get(raw_id, [])
    lineage_found = False
    for rel_type, target, props in edges:
        if target == dim_id and rel_type == "transforms_into":
            lineage_found = True
            print(f"   ✅ Found inferred lineage: {raw_id} -> {dim_id}")
            break
            
    if not lineage_found:
        print(f"   ❌ Lineage inference failed. Edges for {raw_id}: {edges}")

    # 2. Verify Semantic Linking (ReasoningEngine)
    print("\n2️⃣  Verifying Semantic Linking...")
    reasoner = ReasoningEngine(kg_backend, MockGraphiti())
    
    # Create event for a table
    event = KnowledgeEvent(
        action="create_entity",
        data={
            "id": "table:sales_schema.dim_orders",
            "properties": {"name": "dim_orders", "layer": "PERCEPTION"},
            "labels": ["Table"]
        },
        role=Role.DATA_ENGINEER
    )
    
    result = await reasoner.apply_reasoning(event)
    
    # Check for semantic linking suggestion
    linking_found = False
    for suggestion in result.get("suggestions", []):
        if suggestion.get("type") == "semantic_linking" and suggestion.get("target_concept") == "Customer Concept":
            linking_found = True
            print(f"   ✅ Found semantic link suggestion: {suggestion}")
            break
            
    if not linking_found:
        print(f"   ❌ Semantic linking failed. Result: {result}")

    # 3. Verify Transitive Closure (ReasoningEngine)
    print("\n3️⃣  Verifying Transitive Closure...")
    # Setup: A -> B (is_a) and B -> C (is_a)
    await kg_backend.add_entity("A", {"name": "A"})
    await kg_backend.add_entity("B", {"name": "B"})
    await kg_backend.add_entity("C", {"name": "C"})
    await kg_backend.add_relationship("A", "is_a", "B", {})
    await kg_backend.add_relationship("B", "is_a", "C", {})
    
    # Trigger event for B -> C creation (to check backward transitivity logic)
    event_transitive = KnowledgeEvent(
        action="create_relationship",
        data={
            "source": "B",
            "target": "C",
            "type": "is_a"
        },
        role=Role.DATA_ENGINEER
    )
    
    result_transitive = await reasoner.apply_reasoning(event_transitive)
    
    closure_found = False
    for suggestion in result_transitive.get("suggestions", []):
        if suggestion.get("relationship_type") == "is_a" and suggestion.get("source") == "A" and suggestion.get("target") == "C":
            closure_found = True
            print(f"   ✅ Found transitive closure suggestion: A -> C")
            break
            
    if not closure_found:
        print(f"   ❌ Transitive closure failed. Result: {result_transitive}")

if __name__ == "__main__":
    asyncio.run(verify_densification())
