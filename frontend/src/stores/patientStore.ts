import { create } from 'zustand';
import type { PatientContext } from '../types/chat';
import { apiClient } from '../lib/api';

interface PatientStore {
  context: PatientContext | null;
  loading: boolean;
  error: string | null;

  loadContext: (patientId: string) => Promise<void>;
  clearContext: () => void;
}

export const usePatientStore = create<PatientStore>((set) => ({
  context: null,
  loading: false,
  error: null,

  loadContext: async (patientId: string) => {
    set({ loading: true, error: null });

    try {
      const context = await apiClient.get<PatientContext>(
        `/api/patients/${patientId}/context`
      );
      set({ context, loading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load patient context',
        loading: false
      });
    }
  },

  clearContext: () => {
    set({ context: null, error: null });
  },
}));
