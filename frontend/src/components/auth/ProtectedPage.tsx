import React from 'react';
import { AuthProvider } from '../../contexts/AuthContext';
import { AuthGate } from './AuthGate';
import { UserIndicator } from './UserIndicator';

interface ProtectedPageProps {
  children: React.ReactNode;
  showUserIndicator?: boolean;
}

export function ProtectedPage({ children, showUserIndicator = true }: ProtectedPageProps) {
  return (
    <AuthProvider>
      <AuthGate>
        {showUserIndicator && (
          <div className="fixed top-2 right-4 z-50">
            <UserIndicator />
          </div>
        )}
        {children}
      </AuthGate>
    </AuthProvider>
  );
}
