
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

sys.path.append(os.getcwd())

# Mock dependencies that might require external services
sys.modules["graphiti_core"] = MagicMock()
sys.modules["neo4j"] = MagicMock()
# We need pyshacl for validation, but if it's not installed, the engine skips it.
# We'll assume it's installed or handled gracefully.

from src.application.agents.data_engineer.metadata_workflow import MetadataGenerationWorkflow
from src.application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
from src.application.agents.data_architect.dda_parser import DDAParserFactory
from src.application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
from src.application.agents.knowledge_manager.validation_engine import ValidationEngine
from src.application.services.knowledge_enricher import KnowledgeEnricher
from src.infrastructure.in_memory_backend import InMemoryGraphBackend
from domain.dda_models import DDADocument, DataEntity
from domain.ontologies.odin import ODIN
from domain.ontologies.schema_org import SCHEMA
from domain.event import KnowledgeEvent
from domain.roles import Role

async def verify_hybrid_ontology():
    print("🚀 Verifying Advanced Knowledge Representation...")
    
    # 1. Setup Components
    print("\n1️⃣  Initializing Components...")
    backend = InMemoryGraphBackend()
    graph_mock = MagicMock()
    
    # Reasoning Engine with Ontology Mapper
    reasoner = ReasoningEngine(backend, graph_mock)
    
    # Validation Engine with SHACL
    validator = ValidationEngine(backend)
    
    # Knowledge Enricher (Mocked LLM)
    enricher = KnowledgeEnricher(graph_mock)
    enricher._call_llm = AsyncMock(return_value={
        "concept": "Customer",
        "relationship": "represents",
        "confidence": 0.95,
        "reason": "Table name is 'customers'"
    })
    
    # Metadata Builder (uses Reasoner and Validator)
    # We need to mock the builder to use our reasoner/validator or instantiate it properly
    # For this verification, we'll manually simulate the workflow steps to check the integration
    
    # 2. Verify Ontology Mapping (Reasoning Engine)
    print("\n2️⃣  Verifying Ontology Mapping...")
    event = KnowledgeEvent(
        action="create_entity",
        data={
            "id": "table:sales.customers",
            "labels": ["Table"],
            "properties": {"name": "customers"}
        },
        role=Role.DATA_ENGINEER
    )
    
    # Apply Reasoning (should trigger ontology_mapping)
    result = await reasoner.apply_reasoning(event)
    
    mapping_applied = False
    for inference in result.get("inferences", []):
        if inference.get("type") == "ontology_enrichment":
            labels = inference["labels"]
            if ODIN.DATA_ENTITY in labels and SCHEMA.DATASET in labels:
                mapping_applied = True
                print(f"   ✅ Applied labels: {labels}")
                break
    
    if not mapping_applied:
        print(f"   ❌ Ontology mapping failed. Result: {result}")

    # 3. Verify Knowledge Enrichment
    print("\n3️⃣  Verifying Knowledge Enrichment...")
    entity_data = {
        "id": "table:sales.customers",
        "name": "customers",
        "type": "Table",
        "attributes": ["id", "name", "email"]
    }
    
    inferences = await enricher.enrich_entity(entity_data)
    
    if len(inferences) == 2:
        concept_node = next(i for i in inferences if i["type"] == "node")
        rel = next(i for i in inferences if i["type"] == "relationship")
        
        print(f"   ✅ Enriched with Concept: {concept_node['properties']['name']}")
        print(f"   ✅ Created Relationship: {rel['rel_type']} -> {rel['target_id']}")
    else:
        print(f"   ❌ Enrichment failed. Inferences: {inferences}")

    # 4. Verify SHACL Validation
    print("\n4️⃣  Verifying SHACL Validation...")
    # Valid Event
    valid_event = KnowledgeEvent(
        action="create_entity",
        data={
            "id": "table:valid",
            "labels": ["Table"], # Will be mapped to DataEntity in RDF conversion
            "properties": {"name": "ValidTable", "origin": "ERP"}
        },
        role=Role.DATA_ENGINEER
    )
    
    # We need to ensure _event_to_rdf uses the labels. 
    # In ValidationEngine._event_to_rdf, we map "Table" to ODIN.DataEntity.
    
    res_valid = await validator.validate_event(valid_event)
    if res_valid["is_valid"]:
        print("   ✅ Valid entity passed SHACL check")
    else:
        print(f"   ❌ Valid entity failed SHACL check: {res_valid.get('errors')}")
        
    # Invalid Event (Missing 'origin' for DataEntity)
    invalid_event = KnowledgeEvent(
        action="create_entity",
        data={
            "id": "table:invalid",
            "labels": ["Table"],
            "properties": {"name": "InvalidTable"} # Missing origin
        },
        role=Role.DATA_ENGINEER
    )
    
    res_invalid = await validator.validate_event(invalid_event)
    
    # Note: If pyshacl is not installed, this will pass with warning.
    # We check for that.
    if res_invalid["is_valid"]:
        if "pyshacl not installed" in str(res_invalid.get("warnings")):
            print("   ⚠️  SHACL validation skipped (pyshacl not installed)")
        else:
            print("   ❌ Invalid entity PASSED SHACL check (Expected Failure)")
    else:
        print("   ✅ Invalid entity caught by SHACL check")
        print(f"      Error: {res_invalid['errors'][0]}")

if __name__ == "__main__":
    asyncio.run(verify_hybrid_ontology())
