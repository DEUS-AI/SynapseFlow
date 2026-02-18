import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HealthBar } from './HealthBar';
import { KnowledgeGraphPanel } from './KnowledgeGraphPanel';
import { AgentsPanel } from './AgentsPanel';
import { CrystallizationPanel } from './CrystallizationPanel';
import { PromotionGatePanel } from './PromotionGatePanel';
import { OntologyQualityPanel } from './OntologyQualityPanel';
import { FeedbackPanel } from './FeedbackPanel';
import { DataSyncPanel } from './DataSyncPanel';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
    },
  },
});

export function OperationsDashboard() {
  return (
    <QueryClientProvider client={queryClient}>
    <div>
      <HealthBar />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <KnowledgeGraphPanel />
        <AgentsPanel />
        <CrystallizationPanel />
        <PromotionGatePanel />
        <OntologyQualityPanel />
        <FeedbackPanel />
        <DataSyncPanel />
      </div>

      <div className="mt-6 flex flex-wrap gap-4">
        <NavLink href="/admin/patients" color="blue" label="Manage Patients">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
          />
        </NavLink>
        <NavLink href="/admin/documents" color="purple" label="Manage Documents">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </NavLink>
        <NavLink href="/admin/feedback" color="green" label="RLHF Feedback">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </NavLink>
        <NavLink href="/admin/quality" color="orange" label="Quality Metrics">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </NavLink>
      </div>
    </div>
    </QueryClientProvider>
  );
}

const colorMap: Record<string, string> = {
  blue: 'bg-blue-600 hover:bg-blue-500',
  purple: 'bg-purple-600 hover:bg-purple-500',
  green: 'bg-green-600 hover:bg-green-500',
  orange: 'bg-orange-600 hover:bg-orange-500',
};

function NavLink({
  href,
  color,
  label,
  children,
}: {
  href: string;
  color: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      className={`inline-flex items-center px-4 py-2 text-white rounded-lg transition shadow-lg ${
        colorMap[color] ?? 'bg-slate-600 hover:bg-slate-500'
      }`}
    >
      <svg
        className="w-5 h-5 mr-2"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        {children}
      </svg>
      {label}
    </a>
  );
}
