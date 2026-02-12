export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  confidence?: number;
  sources?: Source[];
  reasoning_trail?: string[];
  related_concepts?: string[];
  query?: string;  // The original user query (for assistant messages)
  feedback?: MessageFeedback;
  // Phase 6: Enhanced metadata from Crystallization Pipeline
  medical_alerts?: MedicalAlert[];
  routing?: RoutingInfo;
  temporal_context?: TemporalContextInfo;
  entities?: EntityInfo[];
}

// Medical safety alerts from MedicalRulesEngine
export interface MedicalAlert {
  severity: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW' | 'INFO';
  category: 'drug_interaction' | 'contraindication' | 'allergy' | 'symptom_pattern';
  message: string;
  recommendation?: string;
  triggered_by?: string[];
  rule_id?: string;
}

// Query routing info from DIKWRouter
export interface RoutingInfo {
  intent: 'factual' | 'relational' | 'inferential' | 'actionable' | 'exploratory';
  intent_confidence: number;
  layers: string[];  // DIKW layers used
  matched_patterns?: string[];
  requires_inference?: boolean;
}

// Temporal context from TemporalScoringService
export interface TemporalContextInfo {
  window: 'immediate' | 'recent' | 'short_term' | 'medium_term' | 'long_term' | 'historical';
  duration_hours?: number;
  confidence: number;
}

// Enhanced entity info with temporal scores
export interface EntityInfo {
  id: string;
  name: string;
  entity_type: string;
  dikw_layer?: string;
  temporal_score?: number;
  last_observed?: string;
  observation_count?: number;
}

export interface MessageFeedback {
  rating?: number;
  thumbs?: 'up' | 'down';
  correctionText?: string;
  submittedAt?: Date;
}

export interface Source {
  type: 'PDF' | 'Table' | 'KnowledgeGraph';
  name: string;
  snippet?: string;
}

export interface PatientContext {
  patient_id: string;
  diagnoses: Diagnosis[];
  medications: Medication[];
  allergies: string[];
  recent_symptoms: Symptom[];
  conversation_summary: string;
  last_updated: string;
}

export interface Diagnosis {
  condition: string;
  icd10_code: string;
  diagnosed_date: string;
  status: 'active' | 'resolved';
}

export interface Medication {
  name: string;
  dosage: string;
  frequency: string;
  status: 'active' | 'stopped';
}

export interface Symptom {
  text: string;
  timestamp: string;
}

export interface WebSocketChatMessage {
  type: 'status' | 'message' | 'title_updated' | 'error';
  status?: 'thinking' | 'idle';
  role?: 'user' | 'assistant';
  content?: string;
  confidence?: number;
  sources?: Source[];
  reasoning_trail?: string[];
  related_concepts?: string[];
  response_id?: string;  // For feedback tracking
  session_id?: string;   // For title_updated events
  title?: string;        // For title_updated events
  message?: string;      // For error events
  // Phase 6: Enhanced metadata from Crystallization Pipeline
  medical_alerts?: MedicalAlert[];
  routing?: RoutingInfo;
  temporal_context?: TemporalContextInfo;
  entities?: EntityInfo[];
}
