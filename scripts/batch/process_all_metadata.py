#!/usr/bin/env python3
"""Process all DDA files to generate Metadata Graphs in FalkorDB."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Override settings
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"
os.environ["FALKORDB_HOST"] = "localhost"
os.environ["FALKORDB_PORT"] = "6379"

async def process_all_metadata():
    from src.composition_root import (
        create_generate_metadata_command_handler,
        bootstrap_graphiti,
        bootstrap_knowledge_management
    )
    from src.application.commands.metadata_command import GenerateMetadataCommand
    
    print("=" * 70)
    print("BATCH PROCESSING: METADATA GRAPH GENERATION (FALKORDB)")
    print("=" * 70)
    
    # Initialize Graphiti for type inference
    print("🔧 Initializing Graphiti...")
    graph = await bootstrap_graphiti("batch-metadata")
    
    # Initialize knowledge management (FalkorDB backend)
    print("🔧 Initializing FalkorDB backend...")
    kg_backend, event_bus = bootstrap_knowledge_management()
    
    # Create metadata handler
    handler = create_generate_metadata_command_handler(graph, kg_backend)
    
    # Find all DDA files
    examples_dir = Path("examples")
    dda_files = sorted(examples_dir.glob("*_dda.md"))
    
    print(f"\n📚 Found {len(dda_files)} DDA files to process\n")
    print("=" * 70)
    
    results = []
    successful = 0
    failed = 0
    
    for i, dda_file in enumerate(dda_files, 1):
        # Extract domain name from filename
        domain_name = dda_file.stem.replace('_dda', '').replace('_', ' ').title()
        
        print(f"\n[{i}/{len(dda_files)}] Processing: {dda_file.name}")
        print(f"    Domain: {domain_name}")
        
        # Create command
        # We don't pass architecture_graph_ref here as we are relying on the DDA content mostly
        # In a stricter flow, we would look up the architecture graph ID first.
        command = GenerateMetadataCommand(
            dda_path=str(dda_file),
            domain=domain_name,
            architecture_graph_ref=None 
        )
        
        try:
            # Execute
            result = await handler.handle(command)
            
            if result["success"]:
                successful += 1
                metadata_summary = result['metadata_graph']
                print(f"    ✅ Success!")
                print(f"       Tables: {metadata_summary.get('tables_created', 0)}")
                print(f"       Columns: {metadata_summary.get('columns_created', 0)}")
                
                results.append({
                    "file": dda_file.name,
                    "domain": domain_name,
                    "status": "success",
                    "tables": metadata_summary.get('tables_created', 0),
                    "columns": metadata_summary.get('columns_created', 0)
                })
            else:
                failed += 1
                errors = result.get('errors', ['Unknown error'])
                print(f"    ❌ Failed: {errors[0]}")
                
                results.append({
                    "file": dda_file.name,
                    "domain": domain_name,
                    "status": "failed",
                    "error": errors[0]
                })
        
        except Exception as e:
            failed += 1
            print(f"    ❌ Exception: {str(e)}")
            results.append({
                "file": dda_file.name,
                "domain": domain_name,
                "status": "error",
                "error": str(e)
            })
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 PROCESSING SUMMARY")
    print("=" * 70)
    print(f"Total files: {len(dda_files)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    # Calculate totals
    total_tables = sum(r.get('tables', 0) for r in results if r['status'] == 'success')
    total_columns = sum(r.get('columns', 0) for r in results if r['status'] == 'success')
    
    print(f"\n📈 Total Metadata Statistics:")
    print(f"   Tables created: {total_tables}")
    print(f"   Columns created: {total_columns}")
    
    # Show failed files if any
    if failed > 0:
        print(f"\n⚠️  Failed files:")
        for r in results:
            if r['status'] != 'success':
                print(f"   - {r['file']}: {r.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)
    print("✅ Batch processing complete!")
    print("=" * 70)

if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set")
        print("   Type inference will use default types")
    
    asyncio.run(process_all_metadata())
