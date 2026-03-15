import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { FeedbackDashboard } from '../feedback/FeedbackDashboard';

export function ProtectedFeedback() {
  return (
    <ProtectedPage>
      <FeedbackDashboard />
    </ProtectedPage>
  );
}
