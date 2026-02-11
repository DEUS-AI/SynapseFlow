# 🔍 Neo4j Cypher Queries for SynapseFlow Demo

## 📋 **Overview**

This document contains a comprehensive set of Cypher queries to explore and verify the data created by the SynapseFlow Multi-Agent DDA Demo in Neo4j.

## 🚀 **Quick Start**

### **Access Neo4j Browser**
1. Open your browser and go to: `http://localhost:7474`
2. Login with credentials: `neo4j` / `password`
3. Copy and paste these queries to explore your data

### **Query Categories**
- **Basic Data Verification** - Check if data exists
- **Entity Exploration** - Explore entities and properties
- **Relationship Analysis** - Analyze connections
- **Demo Validation** - Verify demo results
- **Advanced Analytics** - Complex queries and insights

---

## 🔍 **Basic Data Verification**

### **1. Check if Demo Data Exists**
```cypher
// Check total count of entities
MATCH (n:Entity)
RETURN count(n) as total_entities;
```

### **2. Verify Entity Types**
```cypher
// Check what types of entities we have
MATCH (n:Entity)
RETURN DISTINCT n.entity_type as entity_type, count(n) as count
ORDER BY count DESC;
```

### **3. Check Relationship Types**
```cypher
// Check what types of relationships exist
MATCH ()-[r]->()
RETURN DISTINCT type(r) as relationship_type, count(r) as count
ORDER BY count DESC;
```

---

## 📊 **Entity Exploration**

### **4. List All Entities with Properties**
```cypher
// Get all entities with their properties
MATCH (n:Entity)
RETURN n.id as entity_id, 
       n.name as entity_name, 
       n.source as source,
       n.domain as domain,
       n.entity_type as entity_type
ORDER BY n.name;
```

### **5. Find Entities by Domain**
```cypher
// Find entities from specific domain (e.g., Crohn's Disease)
MATCH (n:Entity)
WHERE n.domain CONTAINS "Crohn"
RETURN n.id as entity_id, 
       n.name as entity_name,
       n.source as source
ORDER BY n.name;
```

### **6. Search Entities by Name Pattern**
```cypher
// Find entities with names containing specific text
MATCH (n:Entity)
WHERE n.name CONTAINS "Patient" OR n.name CONTAINS "Assessment"
RETURN n.id as entity_id, 
       n.name as entity_name,
       n.domain as domain
ORDER BY n.name;
```

---

## 🔗 **Relationship Analysis**

### **7. View All Relationships**
```cypher
// Show all relationships with source and target
MATCH (source:Entity)-[r]->(target:Entity)
RETURN source.name as source_entity,
       type(r) as relationship_type,
       target.name as target_entity,
       r.source as relationship_source
ORDER BY source.name, target.name;
```

### **8. Relationship Path Analysis**
```cypher
// Find paths between entities (useful for understanding flow)
MATCH path = (start:Entity)-[:RELATES_TO*1..3]->(end:Entity)
WHERE start.name = "Patient" AND end.name = "Compliance"
RETURN path;
```

### **9. Count Relationships per Entity**
```cypher
// Count incoming and outgoing relationships per entity
MATCH (n:Entity)
OPTIONAL MATCH (n)-[r_out]->()
OPTIONAL MATCH ()-[r_in]->(n)
RETURN n.name as entity_name,
       count(r_out) as outgoing_relationships,
       count(r_in) as incoming_relationships,
       count(r_out) + count(r_in) as total_relationships
ORDER BY total_relationships DESC;
```

---

## ✅ **Demo Validation Queries**

### **10. Verify Demo 3 Results (Entity Creation)**
```cypher
// Check if we have the expected 18 entities from Crohn's DDA
MATCH (n:Entity)
WHERE n.source = "dda"
RETURN count(n) as entities_created,
       "Expected: 18" as expected_count,
       CASE 
         WHEN count(n) = 18 THEN "✅ PASS" 
         ELSE "❌ FAIL" 
       END as status;
```

### **11. Verify Demo 3 Results (Relationship Creation)**
```cypher
// Check if we have the expected 17 relationships
MATCH ()-[r:RELATES_TO]->()
WHERE r.source = "dda_processing"
RETURN count(r) as relationships_created,
       "Expected: 17" as expected_count,
       CASE 
         WHEN count(r) = 17 THEN "✅ PASS" 
         ELSE "❌ FAIL" 
       END as status;
```

### **12. Check Entity Properties**
```cypher
// Verify that entities have the expected properties
MATCH (n:Entity)
WHERE n.source = "dda"
RETURN n.name as entity_name,
       n.id as entity_id,
       CASE 
         WHEN n.name IS NOT NULL THEN "✅" 
         ELSE "❌" 
       END as has_name,
       CASE 
         WHEN n.domain IS NOT NULL THEN "✅" 
         ELSE "❌" 
       END as has_domain,
       CASE 
         WHEN n.entity_type IS NOT NULL THEN "✅" 
         ELSE "❌" 
       END as has_type
ORDER BY n.name;
```

---

## 🧠 **Advanced Analytics**

### **13. Entity Clustering by Domain**
```cypher
// Group entities by domain and show counts
MATCH (n:Entity)
WHERE n.domain IS NOT NULL
RETURN n.domain as domain,
       count(n) as entity_count,
       collect(n.name) as entity_names
ORDER BY entity_count DESC;
```

### **14. Relationship Density Analysis**
```cypher
// Calculate relationship density (relationships per entity)
MATCH (n:Entity)
WITH count(n) as total_entities
MATCH ()-[r:RELATES_TO]->()
WITH total_entities, count(r) as total_relationships
RETURN total_entities,
       total_relationships,
       round(100.0 * total_relationships / total_entities, 2) as density_percentage;
```

### **15. Find Isolated Entities**
```cypher
// Find entities with no relationships (isolated nodes)
MATCH (n:Entity)
WHERE NOT (n)-[]-() AND NOT ()-[]->(n)
RETURN n.name as isolated_entity,
       n.domain as domain,
       n.source as source;
```

### **16. Circular Relationship Detection**
```cypher
// Find potential circular relationships (A->B->C->A)
MATCH path = (start:Entity)-[:RELATES_TO*2..]->(start)
RETURN start.name as start_entity,
       [node in nodes(path) | node.name] as path_nodes,
       length(path) as path_length;
```

---

## 🔧 **Data Quality Checks**

### **17. Duplicate Entity Detection**
```cypher
// Find entities with duplicate IDs or names
MATCH (n:Entity)
WITH n.id as entity_id, collect(n) as nodes
WHERE size(nodes) > 1
RETURN entity_id, 
       size(nodes) as duplicate_count,
       [node in nodes | node.name] as duplicate_names;
```

### **18. Missing Required Properties**
```cypher
// Check for entities missing required properties
MATCH (n:Entity)
WHERE n.name IS NULL OR n.source IS NULL OR n.domain IS NULL
RETURN n.id as entity_id,
       CASE WHEN n.name IS NULL THEN "❌" ELSE "✅" END as has_name,
       CASE WHEN n.source IS NULL THEN "❌" ELSE "✅" END as has_source,
       CASE WHEN n.domain IS NULL THEN "❌" ELSE "✅" END as has_domain;
```

### **19. Relationship Property Validation**
```cypher
// Check relationship properties
MATCH ()-[r:RELATES_TO]->()
RETURN type(r) as relationship_type,
       count(r) as total_count,
       count(CASE WHEN r.source IS NOT NULL THEN 1 END) as with_source,
       count(CASE WHEN r.source IS NULL THEN 1 END) as without_source;
```

---

## 📈 **Performance and Statistics**

### **20. Database Statistics**
```cypher
// Get overall database statistics
MATCH (n:Entity)
WITH count(n) as total_entities
MATCH ()-[r]->()
WITH total_entities, count(r) as total_relationships
MATCH (n:Entity)
WITH total_entities, total_relationships, 
     collect(DISTINCT n.domain) as domains,
     collect(DISTINCT n.source) as sources
RETURN total_entities,
       total_relationships,
       size(domains) as unique_domains,
       size(sources) as unique_sources,
       domains,
       sources;
```

### **21. Memory Usage Estimation**
```cypher
// Estimate memory usage of entities
MATCH (n:Entity)
WITH n, size(keys(n)) as property_count
RETURN sum(property_count) as total_properties,
       avg(property_count) as avg_properties_per_entity,
       max(property_count) as max_properties,
       min(property_count) as min_properties;
```

---

## 🎯 **Demo-Specific Queries**

### **22. Crohn's Disease Domain Analysis**
```cypher
// Comprehensive analysis of Crohn's Disease domain
MATCH (n:Entity)
WHERE n.domain CONTAINS "Crohn"
OPTIONAL MATCH (n)-[r_out]->(target)
OPTIONAL MATCH (source)-[r_in]->(n)
RETURN n.name as entity_name,
       n.id as entity_id,
       count(r_out) as outgoing,
       count(r_in) as incoming,
       collect(DISTINCT target.name) as connected_to,
       collect(DISTINCT source.name) as connected_from
ORDER BY n.name;
```

### **23. DDA Processing Validation**
```cypher
// Validate that DDA processing worked correctly
MATCH (n:Entity)
WHERE n.source = "dda"
WITH n.domain as domain, count(n) as entity_count
MATCH ()-[r:RELATES_TO]->()
WHERE r.source = "dda_processing"
WITH domain, entity_count, count(r) as relationship_count
RETURN domain,
       entity_count,
       relationship_count,
       CASE 
         WHEN entity_count > 0 AND relationship_count > 0 THEN "✅ Complete"
         WHEN entity_count > 0 THEN "⚠️  Entities only"
         ELSE "❌ No data"
       END as processing_status;
```

### **24. Agent Collaboration Data**
```cypher
// Check if agent collaboration data exists
MATCH (n:Entity)
WHERE n.source = "dda"
WITH collect(n) as dda_entities
MATCH (n:Entity)
WHERE n.source = "agent_collaboration"
WITH dda_entities, collect(n) as collaboration_entities
RETURN size(dda_entities) as dda_entities_count,
       size(collaboration_entities) as collaboration_entities_count,
       CASE 
         WHEN size(collaboration_entities) > 0 THEN "✅ Collaboration data exists"
         ELSE "ℹ️  No collaboration data yet"
       END as status;
```

---

## 🧹 **Cleanup Queries**

### **25. Remove Demo Data**
```cypher
// WARNING: This will delete all demo data!
// Only run if you want to start fresh
MATCH (n:Entity)
WHERE n.source = "dda" OR n.source = "dda_processing"
DETACH DELETE n;
```

### **26. Remove Specific Domain**
```cypher
// Remove data for a specific domain
MATCH (n:Entity)
WHERE n.domain CONTAINS "Crohn"
DETACH DELETE n;
```

### **27. Remove Test Relationships**
```cypher
// Remove test relationships only
MATCH ()-[r:RELATES_TO]->()
WHERE r.source = "dda_processing"
DELETE r;
```

---

## 📊 **Query Results Interpretation**

### **Expected Results After Demo**

#### **Entity Count**
- **Total Entities**: Should be 18 (from Crohn's DDA)
- **Entity Types**: All should have `entity_type: "business_entity"`
- **Sources**: All should have `source: "dda"`

#### **Relationship Count**
- **Total Relationships**: Should be 17
- **Relationship Type**: All should be `[:RELATES_TO]`
- **Relationship Source**: All should have `source: "dda_processing"`

#### **Data Quality**
- **No Duplicates**: Each entity should have unique ID
- **Complete Properties**: All entities should have name, domain, source
- **Connected Graph**: No isolated entities

### **Troubleshooting Common Issues**

#### **No Data Found**
```cypher
// Check if Neo4j is connected and has data
MATCH (n) RETURN count(n) as total_nodes;
MATCH ()-[r]->() RETURN count(r) as total_relationships;
```

#### **Wrong Entity Count**
```cypher
// Check what entities actually exist
MATCH (n:Entity) RETURN n.name, n.source, n.domain;
```

#### **Missing Relationships**
```cypher
// Check relationship creation
MATCH ()-[r:RELATES_TO]->() RETURN count(r), r.source;
```

---

## 🎉 **Success Criteria**

Your Neo4j integration is working correctly when you see:

✅ **18 entities** created from the DDA  
✅ **17 relationships** connecting entities  
✅ **All entities** have proper properties  
✅ **No isolated nodes** in the graph  
✅ **Data persists** between demo runs  
✅ **Queries execute** without errors  

---

## 🚀 **Next Steps**

1. **Run the demo**: `python multi_agent_dda_demo.py`
2. **Execute these queries** in Neo4j Browser
3. **Verify the results** match expectations
4. **Explore the data** using the advanced queries
5. **Customize queries** for your specific needs

**Happy querying! 🎯✨**
