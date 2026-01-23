#!/usr/bin/env python3
"""
Neo4j Query Runner for SynapseFlow Demo

This script automatically runs a set of Cypher queries to verify
and explore the data created by the SynapseFlow demo in Neo4j.
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.infrastructure.neo4j_backend import create_neo4j_backend


class Neo4jQueryRunner:
    """Runner for Neo4j Cypher queries to verify demo data."""
    
    def __init__(self):
        """Initialize the query runner."""
        self.backend = None
        self.results = {}
        
    async def connect(self):
        """Connect to Neo4j."""
        try:
            print("🔌 Connecting to Neo4j...")
            self.backend = await create_neo4j_backend()
            print("✅ Connected to Neo4j successfully!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            return False
    
    async def close(self):
        """Close Neo4j connection."""
        if self.backend:
            await self.backend.close()
    
    async def run_query(self, query_name: str, query: str) -> Dict[str, Any]:
        """Run a single Cypher query."""
        try:
            print(f"🔍 Running: {query_name}")
            result = await self.backend.query(query)
            
            # Store result
            self.results[query_name] = {
                "success": True,
                "data": result,
                "error": None
            }
            
            return result
            
        except Exception as e:
            error_msg = f"Query failed: {e}"
            print(f"❌ {error_msg}")
            
            self.results[query_name] = {
                "success": False,
                "data": None,
                "error": str(e)
            }
            
            return None
    
    def print_header(self, title: str):
        """Print a formatted header."""
        print(f"\n{'='*60}")
        print(f"🎯 {title}")
        print(f"{'='*60}")
    
    def print_result(self, query_name: str, result: Dict[str, Any]):
        """Print query results in a formatted way."""
        if not result or "success" not in result:
            print(f"   ❌ {query_name}: No result")
            return
        
        if not result["success"]:
            print(f"   ❌ {query_name}: {result['error']}")
            return
        
        data = result["data"]
        if not data:
            print(f"   ℹ️  {query_name}: No data returned")
            return
        
        # Print based on query type
        if "total_entities" in str(data):
            self._print_count_result(query_name, data)
        elif "entity_name" in str(data):
            self._print_entity_result(query_name, data)
        elif "relationship_type" in str(data):
            self._print_relationship_result(query_name, data)
        else:
            self._print_generic_result(query_name, data)
    
    def _print_count_result(self, query_name: str, data: Dict[str, Any]):
        """Print count-based results."""
        if "nodes" in data and data["nodes"]:
            for node_id, node_data in data["nodes"].items():
                if "total_entities" in str(node_data):
                    count = node_data.get("total_entities", "Unknown")
                    print(f"   ✅ {query_name}: {count} entities")
                    break
        else:
            print(f"   ℹ️  {query_name}: No count data")
    
    def _print_entity_result(self, query_name: str, data: Dict[str, Any]):
        """Print entity-based results."""
        if "nodes" in data and data["nodes"]:
            entities = []
            for node_id, node_data in data["nodes"].items():
                name = node_data.get("properties", {}).get("name", "Unknown")
                entities.append(name)
            
            if entities:
                print(f"   ✅ {query_name}: {len(entities)} entities found")
                for entity in entities[:5]:  # Show first 5
                    print(f"      - {entity}")
                if len(entities) > 5:
                    print(f"      ... and {len(entities) - 5} more")
        else:
            print(f"   ℹ️  {query_name}: No entities found")
    
    def _print_relationship_result(self, query_name: str, data: Dict[str, Any]):
        """Print relationship-based results."""
        if "edges" in data and data["edges"]:
            relationships = []
            for edge_id, edge_data in data["edges"].items():
                rel_type = edge_data.get("type", "Unknown")
                relationships.append(rel_type)
            
            if relationships:
                print(f"   ✅ {query_name}: {len(relationships)} relationships found")
                # Count by type
                from collections import Counter
                rel_counts = Counter(relationships)
                for rel_type, count in rel_counts.items():
                    print(f"      - {rel_type}: {count}")
        else:
            print(f"   ℹ️  {query_name}: No relationships found")
    
    def _print_generic_result(self, query_name: str, data: Dict[str, Any]):
        """Print generic results."""
        if "nodes" in data and data["nodes"]:
            print(f"   ✅ {query_name}: {len(data['nodes'])} nodes returned")
        elif "edges" in data and data["edges"]:
            print(f"   ✅ {query_name}: {len(data['edges'])} edges returned")
        else:
            print(f"   ℹ️  {query_name}: Generic data returned")
    
    async def run_basic_verification(self):
        """Run basic data verification queries."""
        self.print_header("Basic Data Verification")
        
        # Query 1: Check total entities
        await self.run_query(
            "Total Entities Count",
            "MATCH (n:Entity) RETURN count(n) as total_entities"
        )
        
        # Query 2: Check entity types
        await self.run_query(
            "Entity Types",
            "MATCH (n:Entity) RETURN DISTINCT n.entity_type as entity_type, count(n) as count ORDER BY count DESC"
        )
        
        # Query 3: Check relationship types
        await self.run_query(
            "Relationship Types",
            "MATCH ()-[r]->() RETURN DISTINCT type(r) as relationship_type, count(r) as count ORDER BY count DESC"
        )
    
    async def run_entity_exploration(self):
        """Run entity exploration queries."""
        self.print_header("Entity Exploration")
        
        # Query 4: List entities with properties
        await self.run_query(
            "Entities with Properties",
            "MATCH (n:Entity) RETURN n.id as entity_id, n.name as entity_name, n.source as source, n.domain as domain, n.entity_type as entity_type ORDER BY n.name LIMIT 10"
        )
        
        # Query 5: Find entities by domain
        await self.run_query(
            "Crohn's Disease Entities",
            "MATCH (n:Entity) WHERE n.domain CONTAINS 'Crohn' RETURN n.id as entity_id, n.name as entity_name, n.source as source ORDER BY n.name"
        )
    
    async def run_relationship_analysis(self):
        """Run relationship analysis queries."""
        self.print_header("Relationship Analysis")
        
        # Query 7: View all relationships
        await self.run_query(
            "All Relationships",
            "MATCH (source:Entity)-[r]->(target:Entity) RETURN source.name as source_entity, type(r) as relationship_type, target.name as target_entity, r.source as relationship_source ORDER BY source.name, target.name LIMIT 10"
        )
        
        # Query 9: Count relationships per entity
        await self.run_query(
            "Relationships per Entity",
            "MATCH (n:Entity) OPTIONAL MATCH (n)-[r_out]->() OPTIONAL MATCH ()-[r_in]->(n) RETURN n.name as entity_name, count(r_out) as outgoing_relationships, count(r_in) as incoming_relationships, count(r_out) + count(r_in) as total_relationships ORDER BY total_relationships DESC LIMIT 10"
        )
    
    async def run_demo_validation(self):
        """Run demo validation queries."""
        self.print_header("Demo Validation")
        
        # Query 10: Verify entity creation
        await self.run_query(
            "Entity Creation Verification",
            "MATCH (n:Entity) WHERE n.source = 'dda' RETURN count(n) as entities_created, 'Expected: 18' as expected_count, CASE WHEN count(n) = 18 THEN '✅ PASS' ELSE '❌ FAIL' END as status"
        )
        
        # Query 11: Verify relationship creation
        await self.run_query(
            "Relationship Creation Verification",
            "MATCH ()-[r:RELATES_TO]->() WHERE r.source = 'dda_processing' RETURN count(r) as relationships_created, 'Expected: 17' as expected_count, CASE WHEN count(r) = 17 THEN '✅ PASS' ELSE '❌ FAIL' END as status"
        )
        
        # Query 12: Check entity properties
        await self.run_query(
            "Entity Properties Check",
            "MATCH (n:Entity) WHERE n.source = 'dda' RETURN n.name as entity_name, n.id as entity_id, CASE WHEN n.name IS NOT NULL THEN '✅' ELSE '❌' END as has_name, CASE WHEN n.domain IS NOT NULL THEN '✅' ELSE '❌' END as has_domain, CASE WHEN n.entity_type IS NOT NULL THEN '✅' ELSE '❌' END as has_type ORDER BY n.name LIMIT 10"
        )
    
    async def run_advanced_analytics(self):
        """Run advanced analytics queries."""
        self.print_header("Advanced Analytics")
        
        # Query 13: Entity clustering by domain
        await self.run_query(
            "Entity Clustering by Domain",
            "MATCH (n:Entity) WHERE n.domain IS NOT NULL RETURN n.domain as domain, count(n) as entity_count, collect(n.name) as entity_names ORDER BY entity_count DESC"
        )
        
        # Query 14: Relationship density analysis
        await self.run_query(
            "Relationship Density Analysis",
            "MATCH (n:Entity) WITH count(n) as total_entities MATCH ()-[r:RELATES_TO]->() WITH total_entities, count(r) as total_relationships RETURN total_entities, total_relationships, round(100.0 * total_relationships / total_entities, 2) as density_percentage"
        )
        
        # Query 15: Find isolated entities
        await self.run_query(
            "Isolated Entities",
            "MATCH (n:Entity) WHERE NOT (n)-[]-() AND NOT ()-[]->(n) RETURN n.name as isolated_entity, n.domain as domain, n.source as source"
        )
    
    async def run_data_quality_checks(self):
        """Run data quality check queries."""
        self.print_header("Data Quality Checks")
        
        # Query 17: Duplicate entity detection
        await self.run_query(
            "Duplicate Entity Detection",
            "MATCH (n:Entity) WITH n.id as entity_id, collect(n) as nodes WHERE size(nodes) > 1 RETURN entity_id, size(nodes) as duplicate_count, [node in nodes | node.name] as duplicate_names"
        )
        
        # Query 18: Missing required properties
        await self.run_query(
            "Missing Required Properties",
            "MATCH (n:Entity) WHERE n.name IS NULL OR n.source IS NULL OR n.domain IS NULL RETURN n.id as entity_id, CASE WHEN n.name IS NULL THEN '❌' ELSE '✅' END as has_name, CASE WHEN n.source IS NULL THEN '❌' ELSE '✅' END as has_source, CASE WHEN n.domain IS NULL THEN '❌' ELSE '✅' END as has_domain"
        )
    
    async def run_demo_specific_queries(self):
        """Run demo-specific queries."""
        self.print_header("Demo-Specific Analysis")
        
        # Query 22: Crohn's Disease domain analysis
        await self.run_query(
            "Crohn's Disease Domain Analysis",
            "MATCH (n:Entity) WHERE n.domain CONTAINS 'Crohn' OPTIONAL MATCH (n)-[r_out]->(target) OPTIONAL MATCH (source)-[r_in]->(n) RETURN n.name as entity_name, n.id as entity_id, count(r_out) as outgoing, count(r_in) as incoming ORDER BY n.name"
        )
        
        # Query 23: DDA processing validation
        await self.run_query(
            "DDA Processing Validation",
            "MATCH (n:Entity) WHERE n.source = 'dda' WITH n.domain as domain, count(n) as entity_count MATCH ()-[r:RELATES_TO]->() WHERE r.source = 'dda_processing' WITH domain, entity_count, count(r) as relationship_count RETURN domain, entity_count, relationship_count, CASE WHEN entity_count > 0 AND relationship_count > 0 THEN '✅ Complete' WHEN entity_count > 0 THEN '⚠️  Entities only' ELSE '❌ No data' END as processing_status"
        )
    
    async def run_all_queries(self):
        """Run all query categories."""
        print("🚀 Starting Neo4j Query Verification for SynapseFlow Demo")
        print("This will run a comprehensive set of queries to verify your data.\n")
        
        # Run all query categories
        await self.run_basic_verification()
        await self.run_entity_exploration()
        await self.run_relationship_analysis()
        await self.run_demo_validation()
        await self.run_advanced_analytics()
        await self.run_data_quality_checks()
        await self.run_demo_specific_queries()
        
        # Print summary
        self.print_header("Query Execution Summary")
        total_queries = len(self.results)
        successful_queries = sum(1 for r in self.results.values() if r["success"])
        failed_queries = total_queries - successful_queries
        
        print(f"📊 Total Queries: {total_queries}")
        print(f"✅ Successful: {successful_queries}")
        print(f"❌ Failed: {failed_queries}")
        print(f"📈 Success Rate: {(successful_queries/total_queries)*100:.1f}%")
        
        if failed_queries > 0:
            print("\n❌ Failed Queries:")
            for query_name, result in self.results.items():
                if not result["success"]:
                    print(f"   - {query_name}: {result['error']}")
        
        print("\n🎯 Next Steps:")
        print("1. Review the results above")
        print("2. Check Neo4j Browser at http://localhost:7474 for visual exploration")
        print("3. Run specific queries from neo4j_cypher_queries.md")
        print("4. Fix any data quality issues identified")


async def main():
    """Main function to run all queries."""
    runner = Neo4jQueryRunner()
    
    try:
        # Connect to Neo4j
        if not await runner.connect():
            print("❌ Cannot proceed without Neo4j connection")
            return
        
        # Run all queries
        await runner.run_all_queries()
        
    except KeyboardInterrupt:
        print("\n\n👋 Query execution interrupted")
    except Exception as e:
        print(f"❌ Query execution failed: {e}")
    finally:
        # Clean up
        await runner.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Script execution failed: {e}")
        print("💡 Make sure Neo4j is running and properly configured")
