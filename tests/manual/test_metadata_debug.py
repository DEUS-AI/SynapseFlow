#!/usr/bin/env python3
"""Debug metadata workflow to find the empty query issue."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
os.environ["FALKORDB_HOST"] = "localhost"
os.environ["FALKORDB_PORT"] = "6379"

async def test_metadata_workflow():
    from src.application.agents.data_architect.dda_parser import DDAParserFactory
    from src.infrastructure.parsers.markdown_parser import MarkdownDDAParser
    from src.application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
    from src.application.agents.data_engineer.type_inference import TypeInferenceService
    from src.infrastructure.falkor_backend import FalkorBackend
    from src.composition_root import bootstrap_graphiti
    
    print("🔧 Setting up metadata workflow...")
    
    # Parse DDA
    parser_factory = DDAParserFactory()
    markdown_parser = MarkdownDDAParser()
    parser_factory.register_parser(markdown_parser)
    
    dda_path = "examples/sample_dda.md"
    parser = parser_factory.get_parser(dda_path)
    dda_document = await parser.parse(dda_path)
    
    print(f"✅ Parsed DDA: {dda_document.domain}")
    print(f"   Entities: {len(dda_document.entities)}")
    
    # Initialize Graphiti for type inference
    print("\n🔧 Initializing Graphiti...")
    graph = await bootstrap_graphiti("metadata-test")
    
    # Initialize FalkorDB backend
    print("🔧 Initializing FalkorDB...")
    backend = FalkorBackend(host="localhost", port=6379, graph_name="metadata_test")
    
    # Clear graph
    try:
        backend.graph.delete()
        print("✅ Cleared test graph")
    except:
        pass
    
    # Initialize type inference
    print("🔧 Initializing type inference...")
    type_inference = TypeInferenceService(graph)
    
    # Create metadata builder
    print("🔧 Creating metadata builder...")
    builder = MetadataGraphBuilder(backend, type_inference)
    
    # Build metadata graph
    print("\n📊 Building metadata graph...")
    try:
        result = await builder.build_metadata_graph(dda_document)
        
        print("\n✅ Metadata graph created!")
        print(f"   Catalog: {result.get('catalog_name')}")
        print(f"   Schema: {result.get('schema_name')}")
        print(f"   Tables: {result.get('tables_count')}")
        print(f"   Columns: {result.get('columns_count')}")
        print(f"   Constraints: {result.get('constraints_count')}")
        
        # Query the graph
        print("\n🔍 Querying FalkorDB...")
        query_result = await backend.query("MATCH (n) RETURN labels(n)[0] as label, count(n) as count")
        if query_result:
            print("   Nodes by type:")
            for row in query_result:
                print(f"      {row[0]}: {row[1]}")
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_metadata_workflow())
