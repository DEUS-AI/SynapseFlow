import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { QualityDashboard } from '../admin/QualityDashboard';

export function ProtectedQuality() {
  return (
    <ProtectedPage>
      <QualityDashboard />
    </ProtectedPage>
  );
}
