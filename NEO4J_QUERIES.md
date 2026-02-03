# Neo4j Browser Queries - Medical Knowledge + DDA Metadata

Use these queries in the Neo4j Browser to visualize the unified knowledge graph.

---

## View Medical Entities

### All Medical Entities (sample)
```cypher
MATCH (m:MedicalEntity)
RETURN m
LIMIT 50
```

### Medical Entities by Type
```cypher
MATCH (m:MedicalEntity)
WHERE m.type = 'Disease'
RETURN m.name as disease, m.source_document as source
LIMIT 20
```

### Medical Entity Types Distribution
```cypher
MATCH (m:MedicalEntity)
RETURN m.type as entity_type, count(*) as count
ORDER BY count DESC
```

---

## View Cross-Graph Relationships

### All Cross-Graph Links (Medical ↔ Data)
```cypher
MATCH (m:MedicalEntity)-[r]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN m, r, d
LIMIT 25
```

### Cross-Graph Links with Details
```cypher
MATCH (m:MedicalEntity)-[r]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN
    m.name as medical_entity,
    m.type as medical_type,
    type(r) as relationship,
    d.name as data_entity,
    labels(d) as data_labels,
    r.confidence as confidence,
    r.linking_strategy as strategy
ORDER BY r.confidence DESC
```

### Specific Medical Entity and Its Data Links
```cypher
MATCH (m:MedicalEntity {name: "Crohn's Disease"})-[r]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN m, r, d
```

---

## View DDA Metadata

### All Tables
```cypher
MATCH (t:Table)
RETURN t.name as table_name, t.domain as domain
LIMIT 20
```

### All Columns
```cypher
MATCH (c:Column)
RETURN c.name as column_name, c.data_type as type
LIMIT 50
```

### Tables with Columns
```cypher
MATCH (t:Table)-[r:HAS_COLUMN]->(c:Column)
RETURN t, r, c
LIMIT 100
```

### Business Concepts
```cypher
MATCH (bc:BusinessConcept)
RETURN bc.name as concept, bc.domain as domain
LIMIT 20
```

---

## Combined Medical + Data Views

### Disease to Data Table Paths
```cypher
MATCH (disease:MedicalEntity {type: 'Disease'})-[r:APPLICABLE_TO]->(data)
WHERE data:Table OR data:DataEntity
RETURN disease.name as disease, data.name as table, r.confidence as confidence
ORDER BY disease.name
```

### Treatment to Data Column Paths
```cypher
MATCH (treatment:MedicalEntity {type: 'Treatment'})-[r:RELATES_TO]->(data)
WHERE data:Column OR data:Entity
RETURN treatment.name as treatment, data.name as column, r.linking_strategy as how
```

### Full Context for a Disease
```cypher
MATCH path = (disease:MedicalEntity {name: "Crohn's Disease"})-[*1..2]-(related)
RETURN path
LIMIT 50
```

---

## Statistics

### Count All Entity Types
```cypher
CALL db.labels() YIELD label
CALL {
    WITH label
    MATCH (n)
    WHERE label IN labels(n)
    RETURN count(n) as count
}
RETURN label, count
ORDER BY count DESC
```

### Count All Relationship Types
```cypher
CALL db.relationshipTypes() YIELD relationshipType
CALL {
    WITH relationshipType
    MATCH ()-[r]->()
    WHERE type(r) = relationshipType
    RETURN count(r) as count
}
RETURN relationshipType, count
ORDER BY count DESC
```

### Knowledge Graph Summary
```cypher
// Medical entities
MATCH (m:MedicalEntity)
WITH count(m) as medical_count

// Data entities (Tables + Columns)
MATCH (d)
WHERE d:Table OR d:Column
WITH medical_count, count(d) as data_count

// Cross-graph relationships
MATCH ()-[r]-()
WHERE r.layer = 'SEMANTIC'
WITH medical_count, data_count, count(r) as cross_links

RETURN
    medical_count as medical_entities,
    data_count as data_entities,
    cross_links as cross_graph_links,
    medical_count + data_count as total_entities
```

---

## Visualization Tips

### Best Visualization Query (Start Here!)
```cypher
// Show medical entities connected to data entities
MATCH (m:MedicalEntity)-[r]->(d)
WHERE r.layer = 'SEMANTIC'
WITH m, r, d
MATCH (d)-[r2]-(related)
RETURN m, r, d, r2, related
LIMIT 100
```

### Focused View: Autoimmune Diseases
```cypher
MATCH (m:MedicalEntity)
WHERE toLower(m.name) CONTAINS 'autoimmune'
   OR toLower(m.name) CONTAINS 'crohn'
   OR toLower(m.name) CONTAINS 'lupus'
OPTIONAL MATCH (m)-[r]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN m, r, d
```

### Show Medical Entity Types as Separate Colors
```cypher
MATCH (m:MedicalEntity)
WHERE m.type IN ['Disease', 'Treatment', 'Drug', 'Test']
OPTIONAL MATCH (m)-[r]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN m, r, d
LIMIT 200
```

---

## Troubleshooting

### Check if Medical Entities Exist
```cypher
MATCH (m:MedicalEntity)
RETURN count(m) as medical_entity_count
// Should return 201
```

### Check if Cross-Graph Links Exist
```cypher
MATCH ()-[r]-()
WHERE r.layer = 'SEMANTIC'
RETURN count(r) as semantic_links
// Should return 10
```

### Find Orphaned Medical Entities
```cypher
MATCH (m:MedicalEntity)
WHERE NOT (m)-[]-()
RETURN m.name as orphan, m.type as type
LIMIT 20
```

### Find Medical Entities WITH Data Connections
```cypher
MATCH (m:MedicalEntity)-[r]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN DISTINCT m.name as medical_entity, m.type as type
```

---

## Example Queries from the Demo

### Query 1: What data tables contain Crohn's Disease information?
```cypher
MATCH (disease:MedicalEntity {name: "Crohn's Disease"})-[r:APPLICABLE_TO]->(table)
RETURN disease.name as disease, table.name as table_name, r.confidence as confidence
```

### Query 2: What medical concepts are represented in our data?
```cypher
MATCH (m:MedicalEntity)-[r:REPRESENTS_IN|APPLICABLE_TO]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN DISTINCT m.name as medical_concept, m.type as type, collect(DISTINCT d.name) as data_entities
ORDER BY m.type, m.name
```

### Query 3: Show full medical knowledge for Vitamin D
```cypher
MATCH (drug:MedicalEntity {name: "Vitamin D"})
OPTIONAL MATCH (drug)-[r1:TREATS]->(disease:MedicalEntity)
OPTIONAL MATCH (drug)-[r2]->(data)
WHERE r2.layer = 'SEMANTIC'
RETURN drug, r1, disease, r2, data
```

---

## Advanced: Multi-Hop Queries

### Find diseases, their treatments, and related data tables
```cypher
MATCH (disease:MedicalEntity {type: 'Disease'})<-[:TREATS]-(treatment:MedicalEntity {type: 'Treatment'})
MATCH (disease)-[r1:APPLICABLE_TO]->(table)
OPTIONAL MATCH (treatment)-[r2:REPRESENTS_IN|APPLICABLE_TO]->(data)
WHERE r1.layer = 'SEMANTIC' AND (r2 IS NULL OR r2.layer = 'SEMANTIC')
RETURN disease.name as disease,
       treatment.name as treatment,
       table.name as disease_table,
       data.name as treatment_data
LIMIT 20
```

---

## Current Status

**As of migration:**
- ✅ 201 Medical Entities (from FalkorDB)
- ✅ 170 Medical Relationships
- ✅ 42 Data Entities (Tables, Columns from DDAs)
- ✅ 10 Cross-Graph Relationships (SEMANTIC layer)
- ✅ All in unified Neo4j database

**Try this query first in Neo4j Browser:**
```cypher
MATCH (m:MedicalEntity)-[r]->(d)
WHERE r.layer = 'SEMANTIC'
RETURN m, r, d
```

You should see medical entities (blue) connected to data entities (other colors) with SEMANTIC relationships!
