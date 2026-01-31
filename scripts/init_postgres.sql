-- SynapseFlow PostgreSQL Schema
-- Version: 1.0
-- Purpose: Relational data (sessions, feedback, metrics, audit)

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Sessions & Messages (Chat History)
-- ============================================

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_sessions_patient ON sessions(patient_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_last_activity ON sessions(last_activity DESC);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    response_id VARCHAR(255),  -- For feedback attribution
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Denormalized for query performance
    patient_id VARCHAR(255) NOT NULL
);

CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_patient ON messages(patient_id);
CREATE INDEX idx_messages_response_id ON messages(response_id);
CREATE INDEX idx_messages_created ON messages(created_at DESC);

-- ============================================
-- Feedback & RLHF Data
-- ============================================

CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    response_id VARCHAR(255) NOT NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    patient_id VARCHAR(255),

    -- Feedback data
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    thumbs_up BOOLEAN,
    feedback_type VARCHAR(50),  -- 'helpful', 'unhelpful', 'incorrect', 'partially_correct'
    correction_text TEXT,
    severity VARCHAR(20),  -- 'critical', 'high', 'medium', 'low'

    -- Context
    query_text TEXT,
    response_text TEXT,
    entities_involved JSONB DEFAULT '[]'::jsonb,
    layers_traversed JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Training data flags
    used_for_training BOOLEAN DEFAULT FALSE,
    training_batch_id VARCHAR(255)
);

CREATE INDEX idx_feedback_response ON feedback(response_id);
CREATE INDEX idx_feedback_session ON feedback(session_id);
CREATE INDEX idx_feedback_type ON feedback(feedback_type);
CREATE INDEX idx_feedback_rating ON feedback(rating);
CREATE INDEX idx_feedback_created ON feedback(created_at DESC);
CREATE INDEX idx_feedback_training ON feedback(used_for_training) WHERE NOT used_for_training;

-- ============================================
-- Documents & Quality Metrics
-- ============================================

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(255) UNIQUE,  -- e.g., "doc:abc123"
    filename VARCHAR(500) NOT NULL,
    source_path TEXT,
    category VARCHAR(100),

    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,

    -- Metrics
    size_bytes BIGINT,
    chunk_count INTEGER DEFAULT 0,
    entity_count INTEGER DEFAULT 0,
    relationship_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ingested_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Paths
    markdown_path TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_external ON documents(external_id);

CREATE TABLE IF NOT EXISTS document_quality (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Overall
    overall_score DECIMAL(5,4),
    quality_level VARCHAR(20),  -- 'excellent', 'good', 'acceptable', 'poor', 'critical'

    -- Contextual Relevancy
    context_precision DECIMAL(5,4),
    context_recall DECIMAL(5,4),
    context_f1 DECIMAL(5,4),

    -- Sufficiency
    topic_coverage DECIMAL(5,4),
    completeness DECIMAL(5,4),

    -- Density
    facts_per_chunk DECIMAL(8,4),
    redundancy_ratio DECIMAL(5,4),
    signal_to_noise DECIMAL(5,4),

    -- Structure
    heading_hierarchy_score DECIMAL(5,4),
    section_coherence DECIMAL(5,4),

    -- Entity
    entity_extraction_rate DECIMAL(5,4),
    entity_consistency DECIMAL(5,4),

    -- Chunking
    boundary_coherence DECIMAL(5,4),
    retrieval_quality DECIMAL(5,4),

    -- Recommendations
    recommendations JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    assessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_doc_quality_document ON document_quality(document_id);
CREATE INDEX idx_doc_quality_level ON document_quality(quality_level);
CREATE INDEX idx_doc_quality_score ON document_quality(overall_score DESC);

-- ============================================
-- Ontology Quality Metrics
-- ============================================

CREATE TABLE IF NOT EXISTS ontology_quality (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id VARCHAR(50) NOT NULL,
    ontology_name VARCHAR(100) NOT NULL,

    -- Overall
    overall_score DECIMAL(5,4),
    quality_level VARCHAR(20),

    -- Coverage
    coverage_ratio DECIMAL(5,4),
    odin_coverage DECIMAL(5,4),
    schema_org_coverage DECIMAL(5,4),

    -- Compliance
    compliance_ratio DECIMAL(5,4),
    fully_compliant INTEGER,
    non_compliant INTEGER,

    -- Taxonomy
    coherence_ratio DECIMAL(5,4),
    orphan_nodes INTEGER,

    -- Consistency
    consistency_ratio DECIMAL(5,4),

    -- Metadata
    entity_count INTEGER,
    relationship_count INTEGER,

    -- Issues
    critical_issues JSONB DEFAULT '[]'::jsonb,
    recommendations JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    assessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ontology_quality_name ON ontology_quality(ontology_name);
CREATE INDEX idx_ontology_quality_assessed ON ontology_quality(assessed_at DESC);

-- ============================================
-- Audit Logs
-- ============================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Event info
    event_type VARCHAR(100) NOT NULL,  -- 'layer_transition', 'entity_created', 'feedback_submitted'
    event_source VARCHAR(100),  -- 'api', 'agent', 'system'

    -- Entity info
    entity_id VARCHAR(255),
    entity_type VARCHAR(100),

    -- Change details
    action VARCHAR(50) NOT NULL,  -- 'create', 'update', 'delete', 'promote'
    old_values JSONB,
    new_values JSONB,

    -- Context
    user_id VARCHAR(255),
    session_id UUID,
    agent_name VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_entity ON audit_logs(entity_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs(action);

-- ============================================
-- Query Analytics
-- ============================================

CREATE TABLE IF NOT EXISTS query_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Query info
    query_hash VARCHAR(64) NOT NULL,  -- SHA256 of normalized query
    query_text TEXT NOT NULL,
    query_type VARCHAR(50),  -- 'drug_interaction', 'symptom', 'treatment', etc.

    -- Execution stats
    execution_count INTEGER DEFAULT 1,
    total_execution_time_ms BIGINT DEFAULT 0,
    avg_execution_time_ms DECIMAL(10,2),

    -- Layer usage
    layers_used JSONB DEFAULT '[]'::jsonb,
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,

    -- Quality
    avg_confidence DECIMAL(5,4),
    feedback_score DECIMAL(5,4),

    -- Timestamps
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_query_hash ON query_analytics(query_hash);
CREATE INDEX idx_query_type ON query_analytics(query_type);
CREATE INDEX idx_query_count ON query_analytics(execution_count DESC);
CREATE INDEX idx_query_last_seen ON query_analytics(last_seen DESC);

-- ============================================
-- Feature Flags (for migration control)
-- ============================================

CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT FALSE,
    description TEXT,

    -- Rollout control
    rollout_percentage INTEGER DEFAULT 0 CHECK (rollout_percentage >= 0 AND rollout_percentage <= 100),

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default feature flags for migration
INSERT INTO feature_flags (name, enabled, description) VALUES
    ('use_postgres_sessions', FALSE, 'Store sessions in PostgreSQL instead of Neo4j'),
    ('use_postgres_feedback', FALSE, 'Store feedback in PostgreSQL instead of Neo4j'),
    ('use_postgres_documents', FALSE, 'Store document metadata in PostgreSQL'),
    ('dual_write_sessions', FALSE, 'Write sessions to both Neo4j and PostgreSQL'),
    ('dual_write_feedback', FALSE, 'Write feedback to both Neo4j and PostgreSQL'),
    ('enable_query_analytics', TRUE, 'Track query patterns and performance')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- Helper Functions
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_feature_flags_updated_at
    BEFORE UPDATE ON feature_flags
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Views for common queries
-- ============================================

-- Session summary view
CREATE OR REPLACE VIEW session_summary AS
SELECT
    s.id,
    s.patient_id,
    s.title,
    s.status,
    s.message_count,
    s.created_at,
    s.last_activity,
    COALESCE(f.feedback_count, 0) as feedback_count,
    COALESCE(f.avg_rating, 0) as avg_rating
FROM sessions s
LEFT JOIN (
    SELECT
        session_id,
        COUNT(*) as feedback_count,
        AVG(rating) as avg_rating
    FROM feedback
    WHERE rating IS NOT NULL
    GROUP BY session_id
) f ON s.id = f.session_id;

-- Feedback statistics view
CREATE OR REPLACE VIEW feedback_stats AS
SELECT
    COUNT(*) as total_feedback,
    SUM(CASE WHEN thumbs_up = TRUE THEN 1 ELSE 0 END) as positive_count,
    SUM(CASE WHEN thumbs_up = FALSE THEN 1 ELSE 0 END) as negative_count,
    SUM(CASE WHEN correction_text IS NOT NULL THEN 1 ELSE 0 END) as correction_count,
    AVG(rating) as avg_rating,
    COUNT(DISTINCT session_id) as sessions_with_feedback
FROM feedback;
