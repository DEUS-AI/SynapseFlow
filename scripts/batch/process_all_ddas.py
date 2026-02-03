#!/usr/bin/env python3
"""Process all DDA files in the examples folder."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Override Neo4j settings to use local instance
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"

async def process_all_ddas():
    from src.composition_root import bootstrap_graphiti, create_modeling_command_handler
    from src.application.commands.modeling_command import ModelingCommand
    print("🔧 Initializing Graphiti...")
    graph = await bootstrap_graphiti("batch-modeling")
    
    # Create modeling handler with Neo4j credentials (architecture graph writer)
    print("🔧 Creating modeling handler with Neo4j credentials...\n")
    handler = create_modeling_command_handler(
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_user=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD")
    )
    
    # Find all DDA files
    examples_dir = Path("examples")
    dda_files = sorted(examples_dir.glob("*_dda.md"))
    
    print(f"📚 Found {len(dda_files)} DDA files to process\n")
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
        command = ModelingCommand(
            dda_path=str(dda_file),
            domain=domain_name,
            update_existing=False,
            validate_only=False
        )
        
        try:
            # Execute
            result = await handler.handle(command)
            
            if result["success"]:
                successful += 1
                graph_doc = result['graph_document']
                print(f"    ✅ Success!")
                print(f"       Entities: {graph_doc.get('entities_count', 0)}")
                print(f"       Nodes: {graph_doc.get('nodes_created', 0)}")
                print(f"       Edges: {graph_doc.get('edges_created', 0)}")
                
                results.append({
                    "file": dda_file.name,
                    "domain": domain_name,
                    "status": "success",
                    "entities": graph_doc.get('entities_count', 0),
                    "nodes": graph_doc.get('nodes_created', 0),
                    "edges": graph_doc.get('edges_created', 0),
                    "episode_uuid": graph_doc.get('episode_uuid', 'N/A')
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
    total_entities = sum(r.get('entities', 0) for r in results if r['status'] == 'success')
    total_nodes = sum(r.get('nodes', 0) for r in results if r['status'] == 'success')
    total_edges = sum(r.get('edges', 0) for r in results if r['status'] == 'success')
    
    print(f"\n📈 Total Graph Statistics:")
    print(f"   Entities defined: {total_entities}")
    print(f"   Nodes created: {total_nodes}")
    print(f"   Edges created: {total_edges}")
    
    # Show failed files if any
    if failed > 0:
        print(f"\n⚠️  Failed files:")
        for r in results:
            if r['status'] != 'success':
                print(f"   - {r['file']}: {r.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)
    print("✅ Batch processing complete!")
    print("=" * 70)
    print("\n💡 View results:")
    print("   - Neo4j Browser: http://localhost:7474")
    print("   - Run: uv run python check_graphs.py")
    
    return results

if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set in environment")
        print("   Please set it in your .env file or export it")
        exit(1)
    
    results = asyncio.run(process_all_ddas())
