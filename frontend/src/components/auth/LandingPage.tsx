import React, { useEffect } from 'react';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';

function LandingContent() {
  const { isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      window.location.href = '/chat';
    }
  }, [isLoading, isAuthenticated]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="max-w-md mx-auto px-6 text-center">
        <div className="mb-8">
          <div className="w-16 h-16 bg-blue-600/20 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-slate-100 mb-3">SynapseFlow</h1>
          <p className="text-slate-400 text-lg">
            Intelligent Medical Knowledge Management
          </p>
        </div>

        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <p className="text-slate-300 text-sm leading-relaxed">
            This platform is invite-only. If you received an invite link, click it to get started.
          </p>
          <p className="text-slate-500 text-xs mt-4">
            Need access? Contact your administrator.
          </p>
        </div>
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <AuthProvider>
      <LandingContent />
    </AuthProvider>
  );
}
