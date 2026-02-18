import React from 'react';
import { ArrowUpCircle } from 'lucide-react';
import { usePolling } from './usePolling';
import { PanelWrapper } from './PanelWrapper';
import type { PromotionStats } from './types';

const RISK_COLORS: Record<string, string> = {
  LOW: 'bg-green-500',
  MEDIUM: 'bg-amber-500',
  HIGH: 'bg-red-500',
};

export function PromotionGatePanel() {
  const { data, loading, error, secondsAgo, isStale } =
    usePolling<PromotionStats>('/api/crystallization/promotion/stats', 10000);

  return (
    <PanelWrapper
      title="Promotion Gate"
      icon={<ArrowUpCircle className="h-4 w-4 text-emerald-400" />}
      loading={loading}
      error={error}
      secondsAgo={secondsAgo}
      isStale={isStale}
    >
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <CountCard label="Evaluated" value={data.total_evaluated} />
            <CountCard label="Approved" value={data.total_approved} />
            <CountCard
              label="Pending Review"
              value={data.total_pending_review}
              highlight={data.total_pending_review > 0}
            />
            <CountCard label="Rejected" value={data.total_rejected} />
          </div>

          {Object.keys(data.by_risk_level).length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-slate-400 uppercase tracking-wide">
                By Risk Level
              </p>
              {['LOW', 'MEDIUM', 'HIGH'].map((level) => {
                const count = data.by_risk_level[level] ?? 0;
                const total = data.total_evaluated || 1;
                const pct = Math.round((count / total) * 100);
                return (
                  <div key={level} className="flex items-center gap-2">
                    <span className="text-xs text-slate-400 w-16 text-right">
                      {level}
                    </span>
                    <div className="flex-1 h-3 bg-slate-700 rounded overflow-hidden">
                      <div
                        className={`h-full ${RISK_COLORS[level] ?? 'bg-slate-500'} rounded`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-300 w-8">{count}</span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </PanelWrapper>
  );
}

function CountCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p
        className={`text-lg font-semibold ${
          highlight ? 'text-amber-400' : 'text-slate-100'
        }`}
      >
        {value.toLocaleString()}
      </p>
    </div>
  );
}
