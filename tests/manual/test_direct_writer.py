#!/usr/bin/env python3
"""Test the new direct architecture graph writer."""

import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Override Neo4j settings
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"

async def test_direct_writer():
    from src.infrastructure.architecture_graph_writer import ArchitectureGraphWriter
    from src.application.agents.data_architect.dda_parser import DDAParserFactory
    from src.infrastructure.parsers.markdown_parser import MarkdownDDAParser
    
    # Setup parser
    parser_factory = DDAParserFactory()
    markdown_parser = MarkdownDDAParser()
    parser_factory.register_parser(markdown_parser)
    
    # Parse DDA
    dda_path = "examples/sample_dda.md"
    print(f"📄 Parsing: {dda_path}")
    
    parser = parser_factory.get_parser(dda_path)
    dda_document = await parser.parse(dda_path)
    
    print(f"✅ Parsed DDA:")
    print(f"   Domain: {dda_document.domain}")
    print(f"   Entities: {len(dda_document.entities)}")
    print(f"   Relationships: {len(dda_document.relationships)}")
    
    # Create architecture graph directly
    print(f"\n🔧 Creating architecture graph (direct write)...")
    
    writer = ArchitectureGraphWriter(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password"
    )
    
    try:
        result = writer.create_architecture_graph(dda_document)
        
        print(f"\n✅ Architecture graph created!")
        print(f"   Domain: {result['domain']}")
        print(f"   Entities: {result['entities_count']}")
        print(f"   Relationships: {result['relationships_count']}")
        print(f"   Nodes created: {result['nodes_created']}")
        print(f"   Edges created: {result['edges_created']}")
        
        # Show entity details
        print(f"\n📊 Entity Details:")
        for entity in dda_document.entities:
            print(f"\n   {entity.name}:")
            print(f"      Description: {entity.description[:80]}...")
            print(f"      Attributes: {len(entity.attributes)}")
            print(f"      Primary Key: {entity.primary_key}")
            if entity.foreign_keys:
                print(f"      Foreign Keys: {', '.join(entity.foreign_keys)}")
        
        # Show relationships
        print(f"\n🔗 Relationships:")
        for rel in dda_document.relationships:
            print(f"   {rel.source_entity} --[{rel.relationship_type}]--> {rel.target_entity}")
            print(f"      {rel.description[:80]}...")
        
    finally:
        writer.close()
    
    return result

if __name__ == "__main__":
    print("=" * 70)
    print("DIRECT ARCHITECTURE GRAPH WRITER TEST")
    print("=" * 70)
    print()
    
    result = asyncio.run(test_direct_writer())
    
    print("\n" + "=" * 70)
    print("💡 Next: Check Neo4j Browser at http://localhost:7474")
    print("   Query: MATCH (n:DataEntity)-[r]->(m) RETURN n, r, m")
    print("=" * 70)
