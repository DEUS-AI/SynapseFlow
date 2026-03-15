import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { DocumentManagement } from '../admin/DocumentManagement';

export function ProtectedDocuments() {
  return (
    <ProtectedPage>
      <DocumentManagement />
    </ProtectedPage>
  );
}
