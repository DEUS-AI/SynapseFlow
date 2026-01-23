import React, { useEffect } from 'react';
import { usePatientStore } from '../../stores/patientStore';

interface PatientContextSidebarProps {
  patientId: string;
}

export function PatientContextSidebar({ patientId }: PatientContextSidebarProps) {
  const { context, loading, loadContext } = usePatientStore();

  useEffect(() => {
    loadContext(patientId);
  }, [patientId, loadContext]);

  if (loading) {
    return (
      <div className="w-80 bg-white border-l p-6">
        <p className="text-gray-600">Loading patient context...</p>
      </div>
    );
  }

  if (!context) {
    return null;
  }

  return (
    <div className="w-80 bg-white border-l overflow-y-auto">
      <div className="p-6 space-y-6">
        <h2 className="text-lg font-semibold">Patient Context</h2>

        {/* Allergies (CRITICAL) */}
        {context.allergies.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <svg className="h-4 w-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <h3 className="font-semibold text-red-600">Allergies</h3>
            </div>
            <ul className="space-y-2">
              {context.allergies.map((allergy, i) => (
                <li key={i} className="text-sm bg-red-50 px-3 py-2 rounded border border-red-200">
                  {allergy}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Diagnoses */}
        {context.diagnoses.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <svg className="h-4 w-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="font-semibold">Diagnoses</h3>
            </div>
            <ul className="space-y-2">
              {context.diagnoses.map((dx, i) => (
                <li key={i} className="text-sm">
                  <p className="font-medium">{dx.condition}</p>
                  <p className="text-gray-600 text-xs">
                    {dx.icd10_code} • {dx.diagnosed_date}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Medications */}
        {context.medications.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <svg className="h-4 w-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
              <h3 className="font-semibold">Current Medications</h3>
            </div>
            <ul className="space-y-2">
              {context.medications.map((med, i) => (
                <li key={i} className="text-sm">
                  <p className="font-medium">{med.name}</p>
                  <p className="text-gray-600 text-xs">
                    {med.dosage} • {med.frequency}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recent symptoms */}
        {context.recent_symptoms.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <svg className="h-4 w-4 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <h3 className="font-semibold">Recent Symptoms</h3>
            </div>
            <ul className="space-y-2">
              {context.recent_symptoms.slice(0, 5).map((symptom, i) => (
                <li key={i} className="text-sm text-gray-600">
                  {symptom.text}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
