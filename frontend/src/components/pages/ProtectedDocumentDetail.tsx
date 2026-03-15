import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { DocumentDetailView } from '../admin/DocumentDetailView';

export function ProtectedDocumentDetail() {
  // Extract docId from URL: /admin/documents/{docId}
  const segments = window.location.pathname.split('/');
  const docId = segments[segments.length - 1] || '';

  return (
    <ProtectedPage>
      <DocumentDetailView docId={docId} />
    </ProtectedPage>
  );
}
