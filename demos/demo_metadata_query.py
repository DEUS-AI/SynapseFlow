#!/usr/bin/env python3
"""Run a sample Cypher query to show the catalog/schema/table/column hierarchy."""

from falkordb import FalkorDB

client = FalkorDB(host="localhost", port=6379)
graph = client.select_graph("knowledge_graph")

# Query 1: Count summary
print("=" * 70)
print("METADATA SUMMARY")
print("=" * 70)
result = graph.query("""
MATCH (cat:catalog)
WITH count(cat) as catalogs
MATCH (sch:schema)
WITH catalogs, count(sch) as schemas
MATCH (tbl:table)
WITH catalogs, schemas, count(tbl) as tables
MATCH (col:column)
RETURN catalogs, schemas, tables, count(col) as columns
""")
for row in result.result_set:
    print(f"Catalogs: {row[0]}")
    print(f"Schemas:  {row[1]}")
    print(f"Tables:   {row[2]}")
    print(f"Columns:  {row[3]}")

# Query 2: Sample hierarchy for first catalog
print("\n" + "=" * 70)
print("SAMPLE HIERARCHY (Vasculitis Management)")
print("=" * 70)
result = graph.query("""
MATCH (cat:catalog)<-[:belongs_to]-(sch:schema)<-[:belongs_to]-(tbl:table)<-[:belongs_to]-(col:column)
WHERE cat.id = 'vasculitis_management_catalog'
RETURN cat.name AS catalog, 
       sch.name AS schema, 
       tbl.name AS table, 
       col.name AS column
LIMIT 15
""")
print(f"{'Catalog':<30} {'Schema':<35} {'Table':<25} {'Column':<30}")
print("-" * 120)
for row in result.result_set:
    print(f"{row[0]:<30} {row[1]:<35} {row[2]:<25} {row[3]:<30}")

print("\n" + "=" * 70)
print("✅ Metadata successfully populated in FalkorDB!")
print("=" * 70)
