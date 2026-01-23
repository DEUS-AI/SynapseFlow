import React from 'react';

interface SafetyWarningProps {
  warnings: string[];
  onDismiss: () => void;
}

export function SafetyWarning({ warnings, onDismiss }: SafetyWarningProps) {
  return (
    <div className="bg-red-50 border-l-4 border-red-600 px-6 py-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <svg className="h-5 w-5 text-red-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <h3 className="font-semibold text-red-800 mb-2">Safety Warning</h3>
              <ul className="space-y-1">
                {warnings.map((warning, i) => (
                  <li key={i} className="text-sm text-red-700">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <button
            onClick={onDismiss}
            className="text-red-600 hover:text-red-800"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
