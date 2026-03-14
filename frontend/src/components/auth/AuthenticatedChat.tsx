import React from 'react';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';
import { AuthGate } from './AuthGate';
import { UserIndicator } from './UserIndicator';
import { ChatInterface } from '../chat/ChatInterface';

function ChatWithAuth() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <>
      <div className="fixed top-2 right-4 z-50">
        <UserIndicator />
      </div>
      <ChatInterface patientId={user.patient_id} />
    </>
  );
}

export function AuthenticatedChat() {
  return (
    <AuthProvider>
      <AuthGate>
        <ChatWithAuth />
      </AuthGate>
    </AuthProvider>
  );
}
