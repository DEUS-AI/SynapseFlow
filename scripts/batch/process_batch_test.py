#!/usr/bin/env python3
"""Process a small batch of DDA files with verbose logging."""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Override Neo4j settings to use local instance
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"

async def process_batch():
    from src.composition_root import bootstrap_graphiti, create_modeling_command_handler
    from src.application.commands.modeling_command import ModelingCommand
    
    # Create Graphiti instance
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔧 Initializing Graphiti...")
    sys.stdout.flush()
    
    graph = await bootstrap_graphiti("batch-modeling")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Graphiti initialized")
    sys.stdout.flush()
    
    # Create modeling handler
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔧 Creating modeling handler...")
    sys.stdout.flush()
    
    handler = create_modeling_command_handler(graph)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Handler created\n")
    sys.stdout.flush()
    
    # Process all DDA files
    examples_dir = Path("examples")
    dda_files = sorted(examples_dir.glob("*_dda.md"))
    
    print(f"📚 Processing {len(dda_files)} DDA files\n")
    print("=" * 70)
    sys.stdout.flush()
    
    results = []
    
    for i, dda_file in enumerate(dda_files, 1):
        domain_name = dda_file.stem.replace('_dda', '').replace('_', ' ').title()
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [{i}/{len(dda_files)}] Processing: {dda_file.name}")
        print(f"    Domain: {domain_name}")
        sys.stdout.flush()
        
        command = ModelingCommand(
            dda_path=str(dda_file),
            domain=domain_name,
            update_existing=False,
            validate_only=False
        )
        
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]     Calling handler...")
            sys.stdout.flush()
            
            result = await handler.handle(command)
            
            if result["success"]:
                graph_doc = result['graph_document']
                print(f"[{datetime.now().strftime('%H:%M:%S')}]     ✅ Success!")
                print(f"       Entities: {graph_doc.get('entities_count', 0)}")
                print(f"       Nodes: {graph_doc.get('nodes_created', 0)}")
                print(f"       Edges: {graph_doc.get('edges_created', 0)}")
                sys.stdout.flush()
                
                results.append({
                    "file": dda_file.name,
                    "domain": domain_name,
                    "status": "success",
                    "entities": graph_doc.get('entities_count', 0),
                    "nodes": graph_doc.get('nodes_created', 0),
                    "edges": graph_doc.get('edges_created', 0)
                })
            else:
                errors = result.get('errors', ['Unknown error'])
                print(f"[{datetime.now().strftime('%H:%M:%S')}]     ❌ Failed: {errors[0]}")
                sys.stdout.flush()
                
                results.append({
                    "file": dda_file.name,
                    "domain": domain_name,
                    "status": "failed",
                    "error": errors[0]
                })
        
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]     ❌ Exception: {str(e)}")
            sys.stdout.flush()
            results.append({
                "file": dda_file.name,
                "domain": domain_name,
                "status": "error",
                "error": str(e)
            })
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 BATCH SUMMARY")
    print("=" * 70)
    successful = sum(1 for r in results if r['status'] == 'success')
    print(f"✅ Successful: {successful}/{len(dda_files)}")
    
    total_nodes = sum(r.get('nodes', 0) for r in results if r['status'] == 'success')
    total_edges = sum(r.get('edges', 0) for r in results if r['status'] == 'success')
    print(f"📈 Total: {total_nodes} nodes, {total_edges} edges created")
    print("=" * 70)
    
    return results

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set")
        exit(1)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting batch processing...")
    sys.stdout.flush()
    
    results = asyncio.run(process_batch())
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✅ Complete!")
