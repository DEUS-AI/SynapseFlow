Cypher Queries for FalkorDB Metadata Exploration
====================================================
Note: Run each query separately in the FalkorDB UI. Copy one query at a time.

════════════════════════════════════════════════════════════════════════
QUERY 1: Count all node types
════════════════════════════════════════════════════════════════════════

MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label


════════════════════════════════════════════════════════════════════════
QUERY 2: Show first 20 tables with their parent schemas
════════════════════════════════════════════════════════════════════════

MATCH (sch:schema)<-[:belongs_to]-(tbl:table) RETURN sch.name AS schema, tbl.name AS table, tbl.description AS description LIMIT 20


════════════════════════════════════════════════════════════════════════
QUERY 3: Show columns for a specific table (replace 'patient' with your table)
════════════════════════════════════════════════════════════════════════

MATCH (tbl:table)<-[:belongs_to]-(col:column) WHERE tbl.id = 'patient' RETURN col.name AS column, col.description AS description


════════════════════════════════════════════════════════════════════════
QUERY 4: Show complete hierarchy (catalog → schema → table → column)
════════════════════════════════════════════════════════════════════════

MATCH (cat:catalog)<-[:belongs_to]-(sch:schema)<-[:belongs_to]-(tbl:table)<-[:belongs_to]-(col:column) RETURN cat.name AS catalog, sch.name AS schema, tbl.name AS table, col.name AS column LIMIT 30


════════════════════════════════════════════════════════════════════════
QUERY 5: Show all catalogs with their domain information
════════════════════════════════════════════════════════════════════════

MATCH (cat:catalog) RETURN cat.name AS catalog, cat.description AS description, cat.domain AS domain


════════════════════════════════════════════════════════════════════════
QUERY 6: Visual graph - one catalog with its schemas and tables
════════════════════════════════════════════════════════════════════════

    MATCH path = (cat:catalog)<-[:belongs_to]-(sch:schema)<-[:belongs_to]-(tbl:table) WHERE cat.id = 'vasculitis_management_catalog' RETURN path LIMIT 10


════════════════════════════════════════════════════════════════════════
QUERY 7: Find all tables with 'patient' in the name
════════════════════════════════════════════════════════════════════════

MATCH (tbl:table) WHERE tbl.name CONTAINS 'patient' RETURN tbl.name AS table, tbl.description AS description


════════════════════════════════════════════════════════════════════════
QUERY 8: Count tables and columns per schema
════════════════════════════════════════════════════════════════════════

MATCH (sch:schema)<-[:belongs_to]-(tbl:table)<-[:belongs_to]-(col:column) RETURN sch.name AS schema, count(DISTINCT tbl.id) AS tables, count(DISTINCT col.id) AS columns ORDER BY schema

