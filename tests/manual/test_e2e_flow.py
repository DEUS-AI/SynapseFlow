#!/usr/bin/env python3
"""End-to-end test: DDA → Architecture Graph (Neo4j) → Metadata Graph (FalkorDB)"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Override settings
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"
os.environ["FALKORDB_HOST"] = "localhost"
os.environ["FALKORDB_PORT"] = "6379"

async def test_end_to_end():
    from src.composition_root import (
        create_modeling_command_handler,
        create_generate_metadata_command_handler,
        bootstrap_graphiti,
        bootstrap_knowledge_management
    )
    from src.application.commands.modeling_command import ModelingCommand
    from src.application.commands.metadata_command import GenerateMetadataCommand
    
    print("=" * 70)
    print("END-TO-END TEST: DDA → ARCHITECTURE → METADATA")
    print("=" * 70)
    
    # =========================================================================
    # STEP 1: Data Architect creates Architecture Graph
    # =========================================================================
    print("\n📐 STEP 1: DATA ARCHITECT - Creating Architecture Graph")
    print("-" * 70)
    
    # Create modeling handler
    modeling_handler = create_modeling_command_handler(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    # Execute modeling command
    modeling_command = ModelingCommand(
        dda_path="examples/sample_dda.md",
        domain="Customer Analytics",
        update_existing=False,
        validate_only=False
    )
    
    print(f"   Processing: {modeling_command.dda_path}")
    modeling_result = await modeling_handler.handle(modeling_command)
    
    if modeling_result["success"]:
        print(f"   ✅ Architecture graph created!")
        print(f"      Domain: {modeling_result['graph_document']['domain']}")
        print(f"      Entities: {modeling_result['graph_document']['entities_count']}")
        print(f"      Nodes: {modeling_result['graph_document']['nodes_created']}")
        print(f"      Edges: {modeling_result['graph_document']['edges_created']}")
        domain_id = modeling_result['graph_document']['domain_id']
    else:
        print(f"   ❌ Failed: {modeling_result.get('errors')}")
        return
    
    # =========================================================================
    # STEP 2: Data Engineer creates ODIN Metadata Graph
    # =========================================================================
    print("\n🔧 STEP 2: DATA ENGINEER - Creating ODIN Metadata Graph")
    print("-" * 70)
    
    # Initialize Graphiti for type inference
    print("   Initializing Graphiti for type inference...")
    graph = await bootstrap_graphiti("data-engineer-test")
    
    # Initialize knowledge management (FalkorDB backend)
    print("   Initializing FalkorDB backend...")
    kg_backend, event_bus = bootstrap_knowledge_management()
    
    # Create metadata handler
    metadata_handler = create_generate_metadata_command_handler(graph, kg_backend)
    
    # Execute metadata generation command
    metadata_command = GenerateMetadataCommand(
        dda_path="examples/sample_dda.md",
        domain="Customer Analytics",
        architecture_graph_ref=domain_id
    )
    
    print(f"   Processing: {metadata_command.dda_path}")
    metadata_result = await metadata_handler.handle(metadata_command)
    
    if metadata_result["success"]:
        print(f"   ✅ Metadata graph created!")
        metadata_summary = metadata_result['metadata_graph']
        print(f"      Catalog: {metadata_summary.get('catalog_name')}")
        print(f"      Schema: {metadata_summary.get('schema_name')}")
        print(f"      Tables: {metadata_summary.get('tables_count', 0)}")
        print(f"      Columns: {metadata_summary.get('columns_count', 0)}")
        print(f"      Constraints: {metadata_summary.get('constraints_count', 0)}")
    else:
        print(f"   ❌ Failed: {metadata_result.get('errors')}")
        return
    
    # =========================================================================
    # STEP 3: Verify both graphs
    # =========================================================================
    print("\n🔍 STEP 3: VERIFICATION")
    print("-" * 70)
    
    # Check Neo4j (Architecture Graph)
    from neo4j import GraphDatabase
    neo4j_driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )
    
    with neo4j_driver.session() as session:
        result = session.run("MATCH (n:DataEntity) RETURN count(n) as count")
        entity_count = result.single()["count"]
        print(f"   Neo4j (Architecture):")
        print(f"      DataEntities: {entity_count}")
    
    neo4j_driver.close()
    
    # Check FalkorDB (Metadata Graph)
    from falkordb import FalkorDB
    falkor_client = FalkorDB(host="localhost", port=6379)
    falkor_graph = falkor_client.select_graph("knowledge_graph")
    
    result = falkor_graph.query("MATCH (n) RETURN labels(n)[0] as label, count(n) as count")
    print(f"\n   FalkorDB (Metadata):")
    if result.result_set:
        for row in result.result_set:
            print(f"      {row[0]}: {row[1]}")
    else:
        print(f"      No nodes found")
    
    print("\n" + "=" * 70)
    print("✅ END-TO-END TEST COMPLETE")
    print("=" * 70)
    print("\n💡 View results:")
    print("   - Architecture Graph: http://localhost:7474")
    print("     Query: MATCH (n:DataEntity)-[r]->(m) RETURN n, r, m")
    print("   - Metadata Graph: http://localhost:3000")
    print("     Query: MATCH (n) RETURN n LIMIT 25")
    print("=" * 70)

if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set")
        print("   Type inference will use default types")
    
    asyncio.run(test_end_to_end())
