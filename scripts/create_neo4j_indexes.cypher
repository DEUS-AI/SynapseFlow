// Neo4j Indexes for SynapseFlow Knowledge Graph
// Run these commands in Neo4j Browser or via cypher-shell

// ============================================================
// SESSION INDEXES (Chat History Performance)
// ============================================================

// Index on patient_id for fast session lookups per patient
CREATE INDEX idx_session_patient IF NOT EXISTS
FOR (s:ConversationSession)
ON (s.patient_id);

// Index on last_activity for sorting sessions by recency
CREATE INDEX idx_session_activity IF NOT EXISTS
FOR (s:ConversationSession)
ON (s.last_activity);

// Index on session_id for fast message lookups
CREATE INDEX idx_message_session IF NOT EXISTS
FOR (m:Message)
ON (m.session_id);

// Fulltext index on message content for search functionality
CREATE FULLTEXT INDEX idx_message_content IF NOT EXISTS
FOR (m:Message)
ON EACH [m.content];

// ============================================================
// LAYER INDEXES (Knowledge Graph Performance)
// ============================================================

// Index on layer property for layer-aware queries
CREATE INDEX idx_entity_layer IF NOT EXISTS
FOR (n)
ON (n.layer);

// Composite index on layer and extraction_confidence for PERCEPTION layer promotion
CREATE INDEX idx_perception_confidence IF NOT EXISTS
FOR (n)
ON (n.layer, n.extraction_confidence);

// Index on ontology codes for SEMANTIC layer validation
CREATE INDEX idx_ontology_codes IF NOT EXISTS
FOR (n:SemanticConcept)
ON (n.ontology_codes);

// Fulltext index on entity names for search
CREATE FULLTEXT INDEX idx_entity_names IF NOT EXISTS
FOR (n:MedicalEntity|SemanticConcept)
ON EACH [n.name, n.canonical_name, n.description];

// ============================================================
// QUERY PATTERN INDEXES (APPLICATION Layer)
// ============================================================

// Index on query frequency for APPLICATION layer caching
CREATE INDEX idx_query_frequency IF NOT EXISTS
FOR (n:QueryPattern)
ON (n.query_frequency);

// ============================================================
// VERIFICATION
// ============================================================

// Show all indexes
SHOW INDEXES;
