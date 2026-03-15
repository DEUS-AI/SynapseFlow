import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { PatientManagement } from '../admin/PatientManagement';

export function ProtectedPatients() {
  return (
    <ProtectedPage>
      <PatientManagement />
    </ProtectedPage>
  );
}
