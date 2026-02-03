import React, { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from '../ui/button';

interface GDPRToolsProps {
  patientId: string;
  onClose: () => void;
  onDelete: () => void;
}

export function GDPRTools({ patientId, onClose, onDelete }: GDPRToolsProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    const confirmed = window.confirm(
      'This will permanently delete all patient data. This action cannot be undone. Continue?'
    );

    if (!confirmed) {
      return;
    }

    setIsDeleting(true);

    try {
      const response = await fetch(`/api/admin/patients/${patientId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        alert('Patient data deleted successfully');
        onDelete();
      } else {
        const error = await response.json();
        alert(`Failed to delete patient data: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Delete error:', error);
      alert('Failed to delete patient data due to network error');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-semibold">GDPR Data Deletion</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <div className="space-y-4">
            <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded">
              <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="font-semibold text-red-800 mb-1">Warning: Irreversible Action</h4>
                <p className="text-sm text-red-700">
                  This will permanently delete all data for patient{' '}
                  <code className="font-mono bg-red-100 px-1 rounded">{patientId}</code> from:
                </p>
                <ul className="mt-2 text-sm text-red-700 list-disc list-inside space-y-1">
                  <li>Neo4j (medical history, conversations)</li>
                  <li>Mem0 (intelligent memories)</li>
                  <li>Redis (active sessions)</li>
                </ul>
                <p className="mt-2 text-sm text-red-700 font-medium">
                  This action complies with GDPR "Right to be Forgotten" regulations.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete All Patient Data'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
