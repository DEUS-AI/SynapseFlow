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
}
