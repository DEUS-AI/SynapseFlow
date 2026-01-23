export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  confidence?: number;
  sources?: Source[];
  reasoning_trail?: string[];
  related_concepts?: string[];
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
  type: 'status' | 'message';
  status?: 'thinking' | 'idle';
  role?: 'user' | 'assistant';
  content?: string;
  confidence?: number;
  sources?: Source[];
  reasoning_trail?: string[];
  related_concepts?: string[];
}
