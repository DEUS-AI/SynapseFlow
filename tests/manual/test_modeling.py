#!/usr/bin/env python3
"""Test the modeling workflow with proper environment setup."""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Override Neo4j settings to use local instance
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"

async def test_modeling():
    from src.composition_root import create_modeling_command_handler
    from src.application.commands.modeling_command import ModelingCommand
    
    # Create modeling handler with Neo4j credentials
    print("🔧 Creating modeling handler...")
    handler = create_modeling_command_handler(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    # Create command
    command = ModelingCommand(
        dda_path="examples/sample_dda.md",
        domain="Customer Analytics",
        update_existing=False,
        validate_only=False
    )
    
    # Execute
    print(f"\n🚀 Processing DDA: {command.dda_path}")
    print(f"   Domain: {command.domain}\n")
    
    result = await handler.handle(command)
    
    # Display results
    if result["success"]:
        print("✅ Modeling completed successfully!")
        print(f"   Domain: {result['graph_document'].get('domain', 'Unknown')}")
        print(f"   Entities: {result['graph_document'].get('entities_count', 0)}")
        print(f"   Relationships: {result['graph_document'].get('relationships_count', 0)}")
        print(f"   Nodes Created: {result['graph_document'].get('nodes_created', 0)}")
        print(f"   Edges Created: {result['graph_document'].get('edges_created', 0)}")
        print(f"   Episode UUID: {result['graph_document'].get('episode_uuid', 'N/A')}")
        print(f"   Group ID: {result['graph_document'].get('group_id', 'N/A')}")
    else:
        print("❌ Modeling failed:")
        for error in result.get('errors', []):
            print(f"   - {error}")
    
    return result

if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set in environment")
        print("   Please set it in your .env file or export it")
        exit(1)
    
    result = asyncio.run(test_modeling())
