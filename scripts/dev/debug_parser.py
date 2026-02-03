import asyncio
from src.infrastructure.parsers.markdown_parser import MarkdownDDAParser

async def debug_parser():
    parser = MarkdownDDAParser()
    file_path = "examples/vasculitis_management_dda.md"
    print(f"Parsing {file_path}...")
    
    try:
        doc = await parser.parse(file_path)
        print(f"Domain: {doc.domain}")
        print(f"Entities found: {len(doc.entities)}")
        for e in doc.entities:
            print(f" - {e.name} ({len(e.attributes)} attributes)")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_parser())
