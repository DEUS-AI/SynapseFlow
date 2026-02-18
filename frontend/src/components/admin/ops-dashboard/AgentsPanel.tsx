import React from 'react';
import { Users } from 'lucide-react';
import { usePolling } from './usePolling';
import { PanelWrapper } from './PanelWrapper';
import type { AgentInfo } from './types';

const statusColors: Record<string, string> = {
  active: 'bg-green-500',
  degraded: 'bg-amber-500',
  inactive: 'bg-red-500',
  starting: 'bg-blue-500',
};

const STALE_THRESHOLD_SECONDS = 300; // 5 minutes

function formatHeartbeat(secondsAgo: number | null): string {
  if (secondsAgo === null) return 'never';
  if (secondsAgo < 60) return `${secondsAgo}s ago`;
  if (secondsAgo < 3600) return `${Math.floor(secondsAgo / 60)}m ago`;
  return `${Math.floor(secondsAgo / 3600)}h ago`;
}

export function AgentsPanel() {
  const { data, loading, error, secondsAgo, isStale } = usePolling<
    AgentInfo[]
  >('/api/admin/agents', 5000);

  return (
    <PanelWrapper
      title="Agents"
      icon={<Users className="h-4 w-4 text-blue-400" />}
      loading={loading}
      error={error}
      secondsAgo={secondsAgo}
      isStale={isStale}
    >
      {data && data.length === 0 ? (
        <div className="text-sm text-slate-400 py-4">
          <p>No agents registered.</p>
          <p className="text-xs text-slate-500 mt-1">
            Agents self-register via POST /api/agents/register
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {data?.map((agent) => {
            const heartbeatStale =
              agent.heartbeat_seconds_ago !== null &&
              agent.heartbeat_seconds_ago > STALE_THRESHOLD_SECONDS;

            return (
              <div
                key={agent.agent_id}
                className="flex items-start justify-between p-2 bg-slate-750 rounded border border-slate-700"
              >
                <div className="flex items-start gap-2 min-w-0">
                  <span
                    className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                      statusColors[agent.status] ?? 'bg-slate-500'
                    }`}
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate">
                      {agent.name}
                    </p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {agent.capabilities.slice(0, 4).map((cap) => (
                        <span
                          key={cap}
                          className="text-[10px] px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded"
                        >
                          {cap}
                        </span>
                      ))}
                      {agent.capabilities.length > 4 && (
                        <span className="text-[10px] text-slate-500">
                          +{agent.capabilities.length - 4}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <span
                  className={`text-xs flex-shrink-0 ml-2 ${
                    heartbeatStale ? 'text-amber-400' : 'text-slate-500'
                  }`}
                >
                  {formatHeartbeat(agent.heartbeat_seconds_ago)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </PanelWrapper>
  );
}
