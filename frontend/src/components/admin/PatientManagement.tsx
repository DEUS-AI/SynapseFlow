import React, { useState, useEffect } from 'react';
import { Search, Trash2, Eye } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { GDPRTools } from './GDPRTools';

interface Patient {
  patient_id: string;
  created_at: string;
  diagnoses_count: number;
  medications_count: number;
  sessions_count: number;
  consent_given: boolean;
}

export function PatientManagement() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPatient, setSelectedPatient] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/admin/patients')
      .then(res => res.json())
      .then(data => {
        setPatients(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load patients:', err);
        setLoading(false);
      });
  }, []);

  const filteredPatients = patients.filter(p =>
    p.patient_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleDelete = () => {
    if (selectedPatient) {
      setPatients(patients.filter(p => p.patient_id !== selectedPatient));
      setSelectedPatient(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Patient Management</h1>

        <div className="mb-6">
          <div className="flex gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <Input
                placeholder="Search patients..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-gray-600">Loading patients...</p>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Patient ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Diagnoses</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Medications</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sessions</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredPatients.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-4 text-center text-gray-600">
                      No patients found
                    </td>
                  </tr>
                ) : (
                  filteredPatients.map(patient => (
                    <tr key={patient.patient_id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{patient.patient_id}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {new Date(patient.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">{patient.diagnoses_count}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">{patient.medications_count}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">{patient.sessions_count}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => window.location.href = `/chat/${patient.patient_id}`}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setSelectedPatient(patient.patient_id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {selectedPatient && (
          <GDPRTools
            patientId={selectedPatient}
            onClose={() => setSelectedPatient(null)}
            onDelete={handleDelete}
          />
        )}
      </div>
    </div>
  );
}
