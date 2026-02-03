#!/usr/bin/env python3
"""Process all DDA files with the Advanced Knowledge Representation pipeline."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def enrich_all_domains():
    from src.composition_root import (
        bootstrap_graphiti, 
        bootstrap_knowledge_management,
        create_generate_metadata_command_handler
    )
    from src.application.commands.metadata_command import GenerateMetadataCommand
    from src.application.commands.base import CommandBus
    
    print("🚀 Starting Batch Enrichment of All Domains...")
    print("=" * 70)
    
    # Initialize shared components
    print("\n🔧 Initializing Knowledge Graph Backend...")
    kg_backend, event_bus = await bootstrap_knowledge_management()
    
    print("🔧 Initializing Graphiti (LLM)...")
    graph = await bootstrap_graphiti("batch-enrichment")
    
    # Create command bus and register handler
    command_bus = CommandBus()
    metadata_handler = create_generate_metadata_command_handler(graph, kg_backend)
    command_bus.register(GenerateMetadataCommand, metadata_handler)
    
    # Find all DDA files
    examples_dir = Path("examples")
    dda_files = sorted(examples_dir.glob("*_dda.md"))
    
    print(f"\n📚 Found {len(dda_files)} DDA files to process")
    print("=" * 70)
    
    results = []
    successful = 0
    failed = 0
    
    for i, dda_file in enumerate(dda_files, 1):
        # Extract domain name from filename
        domain_name = dda_file.stem.replace('_dda', '').replace('_', ' ').title()
        
        print(f"\n[{i}/{len(dda_files)}] Processing: {dda_file.name}")
        print(f"    Domain: {domain_name}")
        
        try:
            # Create command
            command = GenerateMetadataCommand(
                dda_path=str(dda_file),
                domain=domain_name
            )
            
            # Execute
            result = await command_bus.dispatch(command)
            
            if result["success"]:
                successful += 1
                print(f"    ✅ Success!")
                results.append({
                    "file": dda_file.name,
                    "domain": domain_name,
                    "status": "success"
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
    print("📊 ENRICHMENT SUMMARY")
    print("=" * 70)
    print(f"Total files: {len(dda_files)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    # Show failed files if any
    if failed > 0:
        print(f"\n⚠️  Failed files:")
        for r in results:
            if r['status'] != 'success':
                print(f"   - {r['file']}: {r.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)
    print("✅ Batch enrichment complete!")
    print("=" * 70)
    print("\n💡 View results:")
    print("   - Neo4j Browser: http://localhost:7474")
    print("   - Query: MATCH (n) RETURN n LIMIT 100")
    
    return results

if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set in environment")
        print("   LLM enrichment will use heuristic fallbacks")
    
    results = asyncio.run(enrich_all_domains())
