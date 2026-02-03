"""Verification script for Metadata Model Enhancements."""

import asyncio
import os
from datetime import datetime

from infrastructure.in_memory_backend import InMemoryGraphBackend
from application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
from application.agents.data_engineer.type_inference import TypeInferenceService
from infrastructure.graphiti import get_graphiti
from domain.dda_models import DDADocument, DataEntity

# Mock DDA Document
mock_dda = DDADocument(
    domain="Customer Domain",
    business_context="Customer management",
    data_owner="john.doe",
    stakeholders=["marketing", "sales"],
    effective_date=datetime.now(),
    entities=[
        DataEntity(
            name="Customer",
            description="Customer master data",
            attributes=["Customer ID (Primary Key)", "Name", "Email"],
            business_rules=["Email must be unique", "Name cannot be null"],
            origin="CRM System"
        )
    ],
    relationships=[]
)

async def verify_enhancements():
    print("🚀 Starting Metadata Enhancement Verification...")
    
    # Setup
    kg_backend = InMemoryGraphBackend()
    
    # Mock Graphiti for Type Inference (using a simple stub if possible, or real if env set)
    # For verification, we just need it to not crash.
    # We'll mock the type inference service to avoid needing real LLM/Graphiti here
    class MockTypeInference:
        async def infer_data_type(self, *args):
            from domain.odin_models import DataTypeEntity, DataType
            return DataTypeEntity(name="VARCHAR", base_type="STRING")
        async def infer_precision(self, *args): return 50
        async def infer_scale(self, *args): return None
        
    builder = MetadataGraphBuilder(kg_backend, MockTypeInference())
    
    # Run Builder
    print("\n1️⃣  Building Metadata Graph...")
    results = await builder.build_metadata_graph(mock_dda)
    print(f"✅ Build Complete: {results}")
    
    # Verify Nodes
    print("\n2️⃣  Verifying New Nodes...")
    
    # Check Lineage
    lineage_nodes = [v for k, v in kg_backend.nodes.items() if "file:" in k or v.get("type") == "FILE"]
    print(f"   Lineage Nodes Found: {len(lineage_nodes)}")
    if len(lineage_nodes) > 0:
        print(f"   ✅ Lineage Node: {lineage_nodes[0]}")
        
    # Check Data Quality
    dq_rules = [v for k, v in kg_backend.nodes.items() if "dq_rule" in k]
    dq_scores = [v for k, v in kg_backend.nodes.items() if "dq_score" in k]
    print(f"   DQ Rules Found: {len(dq_rules)}")
    print(f"   DQ Scores Found: {len(dq_scores)}")
    if len(dq_rules) > 0:
        print(f"   ✅ DQ Rule: {dq_rules[0]}")
        
    # Check Usage
    usage_stats = [v for k, v in kg_backend.nodes.items() if "usage" in k]
    print(f"   Usage Stats Found: {len(usage_stats)}")
    if len(usage_stats) > 0:
        print(f"   ✅ Usage Stat: {usage_stats[0]}")

if __name__ == "__main__":
    asyncio.run(verify_enhancements())
