#!/usr/bin/env python3
"""
Interactive CLI Chat - Query Medical Knowledge Graph

This demo allows you to query the medical knowledge graph with natural language
using simple keyword matching.

Usage:
    python demos/interactive_chat.py
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import re

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from falkordb import FalkorDB
from dotenv import load_dotenv


class InteractiveChatCLI:
    """Interactive CLI for querying medical knowledge graph."""

    def __init__(self, graph_name: str = "medical_knowledge"):
        """Initialize the chat CLI."""
        load_dotenv()

        # Connect to FalkorDB
        self.db = FalkorDB(host='localhost', port=6379)
        self.graph = self.db.select_graph(graph_name)
        self.graph_name = graph_name

        print(f"\n{'='*70}")
        print(f"  Medical Knowledge Graph - Interactive Chat")
        print(f"{'='*70}\n")
        print(f"Connected to graph: {graph_name}")

        # Get graph statistics
        self._print_statistics()

    def _print_statistics(self):
        """Print graph statistics."""
        try:
            node_count = self.graph.query('MATCH (n) RETURN count(n)').result_set[0][0]
            edge_count = self.graph.query('MATCH ()-[r]->() RETURN count(r)').result_set[0][0]

            # Get entity types
            type_result = self.graph.query(
                'MATCH (n) RETURN DISTINCT n.type as type, count(*) as count ORDER BY count DESC LIMIT 5'
            )

            print(f"\nGraph Statistics:")
            print(f"  Total Entities: {node_count:,}")
            print(f"  Total Relationships: {edge_count:,}")

            if type_result.result_set:
                print(f"\n  Top Entity Types:")
                for row in type_result.result_set[:5]:
                    entity_type = row[0] if row[0] else "Unknown"
                    count = row[1]
                    print(f"    - {entity_type}: {count}")

        except Exception as e:
            print(f"  Warning: Could not retrieve statistics: {e}")

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from user query."""
        # Remove common stop words
        stop_words = {
            'what', 'is', 'are', 'the', 'a', 'an', 'about', 'for', 'with',
            'how', 'does', 'do', 'can', 'tell', 'me', 'show', 'find', 'information'
        }

        # Tokenize and filter
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    def search_entities(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Search for entities matching keywords."""
        if not keywords:
            return []

        # Build WHERE clause with CONTAINS for each keyword (case-insensitive via toLower)
        conditions = []
        for kw in keywords:
            kw_lower = kw.lower()
            conditions.append(f"toLower(n.name) CONTAINS '{kw_lower}'")

        where_clause = " OR ".join(conditions)

        # Search query
        query = f"""
        MATCH (n)
        WHERE {where_clause}
        RETURN n.name as name, n.type as type, n.description as description,
               n.confidence as confidence, n.source_document as source
        ORDER BY n.confidence DESC
        LIMIT 10
        """

        try:
            result = self.graph.query(query)

            entities = []
            for row in result.result_set:
                entities.append({
                    'name': row[0],
                    'type': row[1],
                    'description': row[2],
                    'confidence': row[3] if row[3] else 0.5,
                    'source': row[4]
                })

            return entities

        except Exception as e:
            print(f"  Error searching entities: {e}")
            return []

    def get_relationships(self, entity_name: str) -> List[Dict[str, Any]]:
        """Get relationships for an entity."""
        # Escape single quotes in entity name for Cypher query
        escaped_name = entity_name.replace("'", "\\'")

        query = f"""
        MATCH (a {{name: '{escaped_name}'}})-[r]->(b)
        RETURN a.name as source, type(r) as relationship, b.name as target,
               b.type as target_type, r.description as description
        LIMIT 20
        """

        try:
            result = self.graph.query(query)

            relationships = []
            for row in result.result_set:
                relationships.append({
                    'source': row[0],
                    'relationship': row[1],
                    'target': row[2],
                    'target_type': row[3],
                    'description': row[4]
                })

            return relationships

        except Exception as e:
            print(f"  Error getting relationships: {e}")
            return []

    def display_results(self, entities: List[Dict[str, Any]]):
        """Display search results."""
        if not entities:
            print("\n  No entities found matching your query.\n")
            return

        print(f"\n  Found {len(entities)} entit{'y' if len(entities) == 1 else 'ies'}:\n")

        for i, entity in enumerate(entities, 1):
            print(f"  [{i}] {entity['name']} ({entity['type']})")
            if entity.get('description'):
                desc = entity['description'][:100]
                if len(entity['description']) > 100:
                    desc += "..."
                print(f"      {desc}")
            print(f"      Confidence: {entity.get('confidence', 0.5):.2f} | Source: {entity.get('source', 'N/A')}")

        print()

    def display_relationships(self, entity_name: str, relationships: List[Dict[str, Any]]):
        """Display relationships for an entity."""
        if not relationships:
            print(f"\n  No relationships found for '{entity_name}'.\n")
            return

        print(f"\n  Relationships for '{entity_name}':\n")

        for i, rel in enumerate(relationships, 1):
            print(f"  [{i}] {rel['source']} --[{rel['relationship']}]--> {rel['target']} ({rel['target_type']})")
            if rel.get('description'):
                print(f"      {rel['description']}")

        print()

    def handle_query(self, query: str):
        """Handle a user query."""
        if not query.strip():
            return

        # Extract keywords
        keywords = self._extract_keywords(query)

        if not keywords:
            print("\n  Could not extract meaningful keywords from your query.")
            print("  Try asking about specific medical terms (e.g., 'lupus', 'autoimmune').\n")
            return

        print(f"\n  Searching for: {', '.join(keywords)}...\n")

        # Search entities
        entities = self.search_entities(keywords)

        # Display results
        self.display_results(entities)

        # If we found entities, ask if user wants to see relationships
        if entities:
            try:
                response = input("  View relationships for an entity? (enter number or 'n' to skip): ").strip()

                if response.lower() not in ['n', 'no', '']:
                    try:
                        idx = int(response) - 1
                        if 0 <= idx < len(entities):
                            entity = entities[idx]
                            relationships = self.get_relationships(entity['name'])
                            self.display_relationships(entity['name'], relationships)
                    except ValueError:
                        print("\n  Invalid input. Skipping relationships.\n")
            except (EOFError, KeyboardInterrupt):
                print("\n")

    def run(self):
        """Run the interactive chat loop."""
        print("\nCommands:")
        print("  - Type a query to search (e.g., 'What is lupus?', 'Show me treatments for IBD')")
        print("  - Type 'stats' to show graph statistics")
        print("  - Type 'help' for help")
        print("  - Type 'quit' or 'exit' to quit\n")

        while True:
            try:
                query = input("You: ").strip()

                if not query:
                    continue

                # Handle commands
                if query.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye!\n")
                    break

                elif query.lower() == 'stats':
                    self._print_statistics()
                    print()

                elif query.lower() == 'help':
                    print("\n  Available commands:")
                    print("    - Search by keywords: 'lupus treatment', 'autoimmune diseases'")
                    print("    - Ask questions: 'What causes rheumatoid arthritis?'")
                    print("    - View statistics: 'stats'")
                    print("    - Quit: 'quit' or 'exit'\n")

                else:
                    self.handle_query(query)

            except (EOFError, KeyboardInterrupt):
                print("\n\nGoodbye!\n")
                break
            except Exception as e:
                print(f"\n  Error: {e}\n")


def main():
    """Main entry point."""
    try:
        chat = InteractiveChatCLI()
        chat.run()
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
