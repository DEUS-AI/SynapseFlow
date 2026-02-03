#!/usr/bin/env python3
"""Direct FalkorDB inspection without the backend wrapper."""

from falkordb import FalkorDB

client = FalkorDB(host="localhost", port=6379)
graph = client.select_graph("knowledge_graph")

# Count all nodes
result = graph.query("MATCH (n) RETURN count(n) as total")
print(f"Total nodes in knowledge_graph: {result.result_set}")

# Show labels
result = graph.query("MATCH (n) RETURN labels(n)[0] as label, count(n) as cnt")
print(f"\nNode labels:")
for row in result.result_set:
    print(f"  {row[0]}: {row[1]}")

# Inspect layer distribution
print("\nLayer distribution:")
res = graph.query("MATCH (n) RETURN n.layer, count(n)")
for row in res.result_set:
    print(f"  {row[0]}: {row[1]}")

# Inspect some nodes with their layers
print("\nSample nodes with layers:")
res = graph.query("MATCH (n) RETURN labels(n), n.name, n.layer LIMIT 5")
for row in res.result_set:
    print(f"  {row[0]}: {row[1]} ({row[2]})")

