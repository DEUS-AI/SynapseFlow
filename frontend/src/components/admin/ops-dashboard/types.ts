// API response types for operations dashboard panels

export interface SystemMetrics {
  total_queries: number;
  avg_response_time: number;
  active_sessions: number;
  total_patients: number;
  neo4j_nodes: number;
  neo4j_relationships: number;
  redis_memory_usage: string;
}

export interface LayerStats {
  layers: Record<string, number>;
  total: number;
  unassigned: number;
  dikw_mapping: Record<string, number>;
}

export interface AgentInfo {
  agent_id: string;
  name: string;
  status: 'active' | 'inactive' | 'degraded' | 'starting';
  capabilities: string[];
  last_heartbeat: string | null;
  heartbeat_seconds_ago: number | null;
  tier: 'core' | 'optional';
  description: string;
  version: string;
}

export interface CrystallizationStats {
  mode: string;
  running: boolean;
  last_crystallization: string | null;
  pending_entities: number;
  batch_counter: number;
  total_crystallized: number;
  total_merged: number;
  total_promotions: number;
  errors: number;
}

export interface CrystallizationHealth {
  crystallization_service: boolean;
  promotion_gate: boolean;
  entity_resolver: boolean;
  healthy: boolean;
  crystallization_running?: boolean;
  crystallization_mode?: string;
}

export interface PromotionStats {
  total_evaluated: number;
  total_approved: number;
  total_pending_review: number;
  total_rejected: number;
  by_risk_level: Record<string, number>;
  by_entity_type: Record<string, number>;
}

export interface OntologyQualityResponse {
  has_assessment: boolean;
  total_assessments: number;
  latest?: {
    assessment_id: string;
    overall_score: number;
    quality_level: string;
    coverage_ratio: number;
    compliance_ratio: number;
    coherence_ratio: number;
    consistency_ratio: number;
    entity_count: number;
    relationship_count: number;
    orphan_nodes: number;
    critical_issues: string[];
    recommendations: string[];
    assessed_at: string;
  };
  by_quality_level: Record<string, number>;
}

export interface FeedbackStats {
  total_feedbacks: number;
  average_rating: number;
  rating_distribution: Record<string, number>;
  feedback_type_distribution: Record<string, number>;
  layer_performance: Record<string, unknown>;
  recent_trends: Record<string, unknown>;
}

export interface ScannerStatus {
  enabled: boolean;
  running: boolean;
  last_document_scan: string | null;
  last_ontology_scan: string | null;
  scan_interval_seconds: number;
  documents_scanned_total: number;
  ontology_scans_total: number;
}

export interface DualWriteDataType {
  dual_write_enabled: boolean;
  use_postgres: boolean;
  neo4j_count: number;
  postgres_count: number;
  sync_status: 'unknown' | 'synced' | 'minor_drift' | 'out_of_sync' | 'disabled';
}

export interface DualWriteHealth {
  status: 'healthy' | 'warning';
  data_types: {
    sessions: DualWriteDataType;
    feedback: DualWriteDataType;
    documents: DualWriteDataType;
  };
  sync_issues: string[];
  recommendations: string[];
}
