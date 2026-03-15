import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { KnowledgeGraphViewer } from '../graph/KnowledgeGraphViewer';

export function ProtectedGraph() {
  return (
    <ProtectedPage>
      <KnowledgeGraphViewer />
    </ProtectedPage>
  );
}
