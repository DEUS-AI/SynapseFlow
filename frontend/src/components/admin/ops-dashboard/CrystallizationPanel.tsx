import React from 'react';
import { Layers } from 'lucide-react';
import { usePolling } from './usePolling';
import { PanelWrapper } from './PanelWrapper';
import type { CrystallizationStats } from './types';

export function CrystallizationPanel() {
  const { data, loading, error, secondsAgo, isStale } =
    usePolling<CrystallizationStats>('/api/crystallization/stats', 10000);

  return (
    <PanelWrapper
      title="Crystallization Pipeline"
      icon={<Layers className="h-4 w-4 text-cyan-400" />}
      loading={loading}
      error={error}
      secondsAgo={secondsAgo}
      isStale={isStale}
    >
      {data && (
        <>
          <div className="flex items-center gap-2 mb-3">
            <span
              className={`w-2 h-2 rounded-full ${
                data.running ? 'bg-green-500' : 'bg-slate-500'
              }`}
            />
            <span
              className={`text-sm ${
                data.running ? 'text-green-400' : 'text-slate-400'
              }`}
            >
              {data.running ? 'Running' : 'Stopped'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Metric label="Pending" value={data.pending_entities} />
            <Metric label="Crystallized" value={data.total_crystallized} />
            <Metric label="Merged" value={data.total_merged} />
            <Metric label="Promotions" value={data.total_promotions} />
            <Metric
              label="Errors"
              value={data.errors}
              warn={data.errors > 0}
            />
          </div>
        </>
      )}
    </PanelWrapper>
  );
}

function Metric({
  label,
  value,
  warn,
}: {
  label: string;
  value: number;
  warn?: boolean;
}) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p
        className={`text-lg font-semibold ${
          warn ? 'text-red-400' : 'text-slate-100'
        }`}
      >
        {value.toLocaleString()}
      </p>
    </div>
  );
}
