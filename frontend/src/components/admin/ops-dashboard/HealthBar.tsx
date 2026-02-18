import React from 'react';
import { usePolling } from './usePolling';
import type { CrystallizationHealth, AgentInfo, SystemMetrics } from './types';

interface SubsystemStatus {
  label: string;
  status: 'healthy' | 'degraded' | 'down' | 'loading';
}

const statusColors: Record<string, string> = {
  healthy: 'bg-green-500',
  degraded: 'bg-amber-500',
  down: 'bg-red-500',
  loading: 'bg-slate-600 animate-pulse',
};

const statusText: Record<string, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  down: 'Down',
  loading: '...',
};

export function HealthBar() {
  const crystHealth = usePolling<CrystallizationHealth>(
    '/api/crystallization/health',
    15000,
  );
  const agents = usePolling<AgentInfo[]>('/api/admin/agents', 10000);
  const metrics = usePolling<SystemMetrics>('/api/admin/metrics', 30000);

  const subsystems: SubsystemStatus[] = [
    {
      label: 'Neo4j',
      status: metrics.loading
        ? 'loading'
        : metrics.error
          ? 'down'
          : 'healthy',
    },
    {
      label: 'Crystallization',
      status: crystHealth.loading
        ? 'loading'
        : crystHealth.error || !crystHealth.data?.crystallization_service
          ? 'down'
          : 'healthy',
    },
    {
      label: 'Agents',
      status: agents.loading
        ? 'loading'
        : agents.error
          ? 'down'
          : !agents.data || agents.data.length === 0
            ? 'degraded'
            : agents.data.some((a) => a.status === 'active')
              ? 'healthy'
              : 'degraded',
    },
    {
      label: 'Promotion Gate',
      status: crystHealth.loading
        ? 'loading'
        : crystHealth.error || !crystHealth.data?.promotion_gate
          ? 'down'
          : 'healthy',
    },
    {
      label: 'Entity Resolver',
      status: crystHealth.loading
        ? 'loading'
        : crystHealth.error || !crystHealth.data?.entity_resolver
          ? 'down'
          : 'healthy',
    },
  ];

  return (
    <div className="flex flex-wrap gap-3 mb-6">
      {subsystems.map((s) => (
        <div
          key={s.label}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg"
        >
          <span
            className={`w-2.5 h-2.5 rounded-full ${statusColors[s.status]}`}
          />
          <span className="text-sm text-slate-300">{s.label}</span>
          <span
            className={`text-xs ${
              s.status === 'healthy'
                ? 'text-green-400'
                : s.status === 'degraded'
                  ? 'text-amber-400'
                  : s.status === 'down'
                    ? 'text-red-400'
                    : 'text-slate-500'
            }`}
          >
            {statusText[s.status]}
          </span>
        </div>
      ))}
    </div>
  );
}
