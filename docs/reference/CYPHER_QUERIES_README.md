# 🔍 Cypher Queries for SynapseFlow Demo

## 📋 **Overview**

This document explains how to use the Cypher queries to verify and explore the data created by the SynapseFlow Multi-Agent DDA Demo in Neo4j.

## 🚀 **Two Ways to Run Queries**

### **Option 1: Automated Python Script (Recommended)**
```bash
# Run all queries automatically
python run_neo4j_queries.py
```

### **Option 2: Manual Execution in Neo4j Browser**
1. Open Neo4j Browser: `http://localhost:7474`
2. Login: `neo4j` / `password`
3. Copy queries from `neo4j_cypher_queries.md`

## 📚 **Available Query Files**

| File | Purpose | Use Case |
|------|---------|----------|
| **`neo4j_cypher_queries.md`** | Complete query collection | Manual execution, reference |
| **`run_neo4j_queries.py`** | Automated query runner | Batch verification, testing |
| **`CYPHER_QUERIES_README.md`** | This file | Usage instructions |

## 🎯 **Query Categories**

### **1. Basic Data Verification**
- **Total entity count** - Verify 18 entities created
- **Entity types** - Check entity classifications
- **Relationship types** - Verify relationship structure

### **2. Entity Exploration**
- **Entity properties** - View all entity details
- **Domain filtering** - Find Crohn's Disease entities
- **Pattern search** - Search by entity name patterns

### **3. Relationship Analysis**
- **All relationships** - View connection structure
- **Path analysis** - Find paths between entities
- **Relationship counts** - Analyze connectivity

### **4. Demo Validation**
- **Entity creation** - Verify 18 entities created
- **Relationship creation** - Verify 17 relationships
- **Property validation** - Check data completeness

### **5. Advanced Analytics**
- **Entity clustering** - Group by domain
- **Density analysis** - Calculate graph density
- **Isolated entities** - Find disconnected nodes

### **6. Data Quality Checks**
- **Duplicate detection** - Find duplicate entities
- **Missing properties** - Check data completeness
- **Relationship validation** - Verify relationship data

### **7. Demo-Specific Analysis**
- **Crohn's Disease analysis** - Domain-specific insights
- **DDA processing validation** - Verify workflow completion
- **Agent collaboration data** - Check inter-agent communication

## 🔧 **Using the Automated Script**

### **Prerequisites**
```bash
# Ensure Neo4j is running
docker ps | grep neo4j

# Check environment variables
echo $NEO4J_URI
echo $NEO4J_USERNAME
echo $NEO4J_PASSWORD
```

### **Running the Script**
```bash
# Basic execution
python run_neo4j_queries.py

# With verbose output
python -u run_neo4j_queries.py
```

### **Expected Output**
```
🚀 Starting Neo4j Query Verification for SynapseFlow Demo
This will run a comprehensive set of queries to verify your data.

🔌 Connecting to Neo4j...
✅ Connected to Neo4j successfully!

============================================================
🎯 Basic Data Verification
============================================================
🔍 Running: Total Entities Count
   ✅ Total Entities Count: 18 entities
🔍 Running: Entity Types
   ✅ Entity Types: 1 entity types found
      - business_entity
🔍 Running: Relationship Types
   ✅ Relationship Types: 1 relationships found
      - RELATES_TO: 17

============================================================
🎯 Entity Exploration
============================================================
🔍 Running: Entities with Properties
   ✅ Entities with Properties: 10 entities found
      - Patient
      - Disease Activity Assessment
      - Endoscopy Report
      - Medication Therapy
      - Nutritional Assessment
      ... and 5 more

============================================================
🎯 Demo Validation
============================================================
🔍 Running: Entity Creation Verification
   ✅ Entity Creation Verification: 18 entities
🔍 Running: Relationship Creation Verification
   ✅ Relationship Creation Verification: 17 relationships
🔍 Running: Entity Properties Check
   ✅ Entity Properties Check: 10 entities found
      - Patient
      - Disease Activity Assessment
      - Endoscopy Report
      - Medication Therapy
      - Nutritional Assessment
      ... and 5 more

============================================================
🎯 Query Execution Summary
============================================================
📊 Total Queries: 21
✅ Successful: 21
❌ Failed: 0
📈 Success Rate: 100.0%

🎯 Next Steps:
1. Review the results above
2. Check Neo4j Browser at http://localhost:7474 for visual exploration
3. Run specific queries from neo4j_cypher_queries.md
4. Fix any data quality issues identified
```

## 🎭 **Using Neo4j Browser**

### **Access Neo4j Browser**
1. **Open browser**: Go to `http://localhost:7474`
2. **Login**: Username `neo4j`, Password `password`
3. **First time**: Change password if prompted

### **Basic Query Examples**
```cypher
// Check total entities
MATCH (n:Entity) RETURN count(n) as total_entities;

// View all entities
MATCH (n:Entity) RETURN n LIMIT 10;

// Check relationships
MATCH ()-[r]->() RETURN count(r) as total_relationships;
```

### **Visual Graph Exploration**
```cypher
// Visualize the graph structure
MATCH (n:Entity)-[r:RELATES_TO]->(m:Entity)
RETURN n, r, m
LIMIT 20;
```

## 📊 **Expected Results**

### **After Running the Demo**
- **Total Entities**: 18
- **Total Relationships**: 17
- **Entity Source**: All from "dda"
- **Relationship Source**: All from "dda_processing"
- **Domain**: "Crohn's Disease Management"

### **Data Quality Indicators**
- ✅ **No duplicate entities**
- ✅ **All entities have names**
- ✅ **All entities have domains**
- ✅ **All entities have source information**
- ✅ **No isolated entities**
- ✅ **Connected graph structure**

## 🚨 **Troubleshooting**

### **Common Issues**

#### **No Data Found**
```cypher
// Check if any data exists
MATCH (n) RETURN count(n) as total_nodes;
MATCH ()-[r]->() RETURN count(r) as total_relationships;
```

#### **Wrong Entity Count**
```cypher
// Check what entities exist
MATCH (n:Entity) RETURN n.name, n.source, n.domain;
```

#### **Missing Relationships**
```cypher
// Check relationship creation
MATCH ()-[r:RELATES_TO]->() RETURN count(r), r.source;
```

### **Debug Queries**
```cypher
// Check entity labels
MATCH (n) RETURN DISTINCT labels(n);

// Check relationship types
MATCH ()-[r]->() RETURN DISTINCT type(r);

// Check node properties
MATCH (n:Entity) RETURN n LIMIT 1;
```

## 🔍 **Customizing Queries**

### **Modifying Query Parameters**
```cypher
// Change limit for more results
MATCH (n:Entity) RETURN n LIMIT 50;

// Filter by different domain
MATCH (n:Entity) WHERE n.domain CONTAINS "Diabetes" RETURN n;

// Check different source
MATCH (n:Entity) WHERE n.source = "agent_collaboration" RETURN n;
```

### **Adding New Queries**
```cypher
// Example: Find entities by creation date
MATCH (n:Entity)
WHERE n.created_at IS NOT NULL
RETURN n.name, n.created_at
ORDER BY n.created_at DESC;

// Example: Find entities with specific properties
MATCH (n:Entity)
WHERE n.properties CONTAINS "medical"
RETURN n.name, n.properties;
```

## 📈 **Performance Tips**

### **Query Optimization**
```cypher
// Use LIMIT for large datasets
MATCH (n:Entity) RETURN n LIMIT 100;

// Filter early in the query
MATCH (n:Entity) WHERE n.domain = "Crohn's Disease Management" RETURN n;

// Use specific labels
MATCH (n:Entity) RETURN n;  // Instead of MATCH (n)
```

### **Indexing (for Production)**
```cypher
// Create indexes for better performance
CREATE INDEX entity_id_index FOR (n:Entity) ON (n.id);
CREATE INDEX entity_name_index FOR (n:Entity) ON (n.name);
CREATE INDEX entity_domain_index FOR (n:Entity) ON (n.domain);
```

## 🎯 **Use Cases**

### **For Development**
- **Verify data creation** after code changes
- **Debug data issues** in the demo
- **Test new features** with real data

### **For Testing**
- **Validate demo results** automatically
- **Check data quality** before presentations
- **Verify integration** with Neo4j

### **For Presentations**
- **Show real data** in Neo4j Browser
- **Demonstrate persistence** between runs
- **Explore data relationships** visually

### **For Production**
- **Monitor data quality** in real systems
- **Debug production issues** with queries
- **Analyze system performance** and usage

## 🚀 **Next Steps**

1. **Run the automated script**: `python run_neo4j_queries.py`
2. **Explore manually** in Neo4j Browser
3. **Customize queries** for your specific needs
4. **Add new queries** to the collection
5. **Integrate queries** into your testing workflow

---

## 🎉 **Success Criteria**

Your Cypher queries are working correctly when:

✅ **Automated script runs** without errors  
✅ **All queries execute** successfully  
✅ **Expected results** are returned (18 entities, 17 relationships)  
✅ **Data quality checks** pass  
✅ **Neo4j Browser** shows visual graph  
✅ **Queries are fast** and responsive  

**Happy querying! 🎯✨**
