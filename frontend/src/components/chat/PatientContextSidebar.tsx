import React, { useEffect, useState } from 'react';
import { usePatientStore } from '../../stores/patientStore';
import { CollapsibleSection } from '../ui/CollapsibleSection';
import { PatientMemoriesPanel } from './PatientMemoriesPanel';
import { PatientGraphPreview } from './PatientGraphPreview';
import { PatientDetailsModal } from './PatientDetailsModal';
import {
  AlertTriangle,
  FileText,
  Pill,
  Zap,
  MessageSquare,
  Brain,
  Network,
  Maximize2,
  Sparkles,
} from 'lucide-react';

interface PatientContextSidebarProps {
  patientId: string;
  /** Increment to trigger memory refresh */
  memoryRefreshTrigger?: number;
  /** Show processing indicator while extracting facts */
  isProcessingMemory?: boolean;
}

export function PatientContextSidebar({
  patientId,
  memoryRefreshTrigger = 0,
  isProcessingMemory = false,
}: PatientContextSidebarProps) {
  const { context, loading, loadContext } = usePatientStore();
  const [showGraphModal, setShowGraphModal] = useState(false);

  useEffect(() => {
    loadContext(patientId);
  }, [patientId, loadContext]);

  if (loading) {
    return (
      <div className="w-80 bg-slate-800 border-l border-slate-700 p-6">
        <p className="text-slate-400">Loading patient context...</p>
      </div>
    );
  }

  if (!context) {
    return null;
  }

  return (
    <>
      <div className="w-80 h-full bg-slate-800 border-l border-slate-700 overflow-y-auto flex-shrink-0">
        {/* Header - Full Width */}
        <div className="sticky top-0 z-10 bg-gradient-to-r from-purple-900/80 to-blue-900/80 backdrop-blur-sm border-b border-slate-700">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-400" />
              <h2 className="text-lg font-bold text-white tracking-wide">ODIN</h2>
            </div>
            <button
              onClick={() => setShowGraphModal(true)}
              className="p-1.5 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
              title="Expand patient details"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="p-4 space-y-3">

          {/* Allergies (CRITICAL - always expanded) */}
          {context.allergies.length > 0 && (
            <CollapsibleSection
              title="Allergies"
              icon={<AlertTriangle className="w-4 h-4" />}
              badge={context.allergies.length}
              badgeColor="red"
              defaultExpanded={true}
            >
              <ul className="space-y-2">
                {context.allergies.map((allergy, i) => (
                  <li
                    key={i}
                    className="text-sm bg-red-900/30 text-red-200 px-3 py-2 rounded border border-red-800"
                  >
                    {allergy}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Diagnoses */}
          {context.diagnoses.length > 0 && (
            <CollapsibleSection
              title="Diagnoses"
              icon={<FileText className="w-4 h-4" />}
              badge={context.diagnoses.length}
              badgeColor="blue"
              defaultExpanded={true}
            >
              <ul className="space-y-2">
                {context.diagnoses.map((dx, i) => (
                  <li key={i} className="text-sm">
                    <p className="font-medium text-slate-200">{dx.condition}</p>
                    <p className="text-slate-400 text-xs">
                      {dx.icd10_code && `${dx.icd10_code} • `}
                      {dx.diagnosed_date}
                    </p>
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Medications */}
          {context.medications.length > 0 && (
            <CollapsibleSection
              title="Medications"
              icon={<Pill className="w-4 h-4" />}
              badge={context.medications.length}
              badgeColor="green"
              defaultExpanded={false}
            >
              <ul className="space-y-2">
                {context.medications.map((med, i) => (
                  <li key={i} className="text-sm">
                    <p className="font-medium text-slate-200">{med.name}</p>
                    <p className="text-slate-400 text-xs">
                      {med.dosage} • {med.frequency}
                    </p>
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Recent Symptoms */}
          {context.recent_symptoms.length > 0 && (
            <CollapsibleSection
              title="Recent Symptoms"
              icon={<Zap className="w-4 h-4" />}
              badge={context.recent_symptoms.length}
              badgeColor="orange"
              defaultExpanded={false}
            >
              <ul className="space-y-2">
                {context.recent_symptoms.slice(0, 5).map((symptom, i) => (
                  <li key={i} className="text-sm text-slate-400">
                    {symptom.text}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Memory Summary (from conversation) */}
          {context.conversation_summary && context.conversation_summary !== 'No history' && (
            <CollapsibleSection
              title="Memory Summary"
              icon={<MessageSquare className="w-4 h-4" />}
              badgeColor="purple"
              defaultExpanded={false}
            >
              <p className="text-sm text-slate-400 bg-slate-900/50 px-3 py-2 rounded">
                {context.conversation_summary}
              </p>
            </CollapsibleSection>
          )}

          {/* Memory History (NEW - from Mem0) */}
          <CollapsibleSection
            title="Memory History"
            icon={<Brain className="w-4 h-4" />}
            badgeColor="purple"
            defaultExpanded={true}
          >
            <PatientMemoriesPanel
              patientId={patientId}
              maxVisible={3}
              refreshTrigger={memoryRefreshTrigger}
              isProcessing={isProcessingMemory}
            />
          </CollapsibleSection>

          {/* Medical Graph (NEW) */}
          <CollapsibleSection
            title="Medical Graph"
            icon={<Network className="w-4 h-4" />}
            badgeColor="blue"
            defaultExpanded={true}
          >
            <PatientGraphPreview
              patientId={patientId}
              onExpandClick={() => setShowGraphModal(true)}
            />
          </CollapsibleSection>
        </div>
      </div>

      {/* Full Graph Modal */}
      <PatientDetailsModal
        patientId={patientId}
        isOpen={showGraphModal}
        onClose={() => setShowGraphModal(false)}
      />
    </>
  );
}
