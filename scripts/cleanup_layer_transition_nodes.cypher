// Cleanup LayerTransition nodes - remove incorrectly assigned layer property
//
// LayerTransition nodes are audit records, not knowledge entities.
// They should NOT have a layer property as this pollutes the KG visualization.
//
// Run this query in Neo4j Browser or via cypher-shell:
// cypher-shell -u neo4j -p password < scripts/cleanup_layer_transition_nodes.cypher

// Remove layer property from LayerTransition nodes
MATCH (t:LayerTransition)
WHERE t.layer IS NOT NULL
REMOVE t.layer
RETURN count(t) as nodes_cleaned;

// Also remove layer from __User__ nodes (Graphiti internal tracking)
MATCH (u:__User__)
WHERE u.layer IS NOT NULL
REMOVE u.layer
RETURN count(u) as user_nodes_cleaned;

// Verify cleanup
MATCH (n)
WHERE n.layer = 'APPLICATION'
RETURN labels(n) as node_type, count(*) as count
ORDER BY count DESC;
