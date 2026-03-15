import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { OperationsDashboard } from '../admin/ops-dashboard/OperationsDashboard';
import { InviteManagement } from '../admin/InviteManagement';

export function ProtectedAdmin() {
  return (
    <ProtectedPage>
      <div className="min-h-screen bg-slate-900">
        <header className="bg-slate-800 shadow-lg border-b border-slate-700">
          <div className="max-w-7xl mx-auto px-4 py-6">
            <h1 className="text-3xl font-bold text-slate-100">Admin Dashboard</h1>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-6 space-y-8">
          <InviteManagement />
          <OperationsDashboard />
        </main>
      </div>
    </ProtectedPage>
  );
}
