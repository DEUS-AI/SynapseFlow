import React from 'react';
import { RefreshCw } from 'lucide-react';
import { usePolling } from './usePolling';
import { PanelWrapper } from './PanelWrapper';
import type { DualWriteHealth, DualWriteDataType } from './types';

const syncStatusColors: Record<string, string> = {
  synced: 'bg-green-500',
  minor_drift: 'bg-amber-500',
  out_of_sync: 'bg-red-500',
  unknown: 'bg-slate-500',
  disabled: 'bg-slate-600',
};

const syncStatusLabels: Record<string, string> = {
  synced: 'Synced',
  minor_drift: 'Minor Drift',
  out_of_sync: 'Out of Sync',
  unknown: 'Unknown',
  disabled: 'Disabled',
};

export function DataSyncPanel() {
  const { data, loading, error, secondsAgo, isStale } =
    usePolling<DualWriteHealth>('/api/admin/dual-write-health', 30000);

  const allDisabled =
    data &&
    !data.data_types.sessions.dual_write_enabled &&
    !data.data_types.feedback.dual_write_enabled &&
    !data.data_types.documents.dual_write_enabled;

  return (
    <PanelWrapper
      title="Data Sync"
      icon={<RefreshCw className="h-4 w-4 text-indigo-400" />}
      loading={loading}
      error={error}
      secondsAgo={secondsAgo}
      isStale={isStale}
    >
      {data && allDisabled ? (
        <p className="text-sm text-slate-500 py-4">
          Dual-write not enabled
        </p>
      ) : data ? (
        <div className="space-y-3">
          {(['sessions', 'feedback', 'documents'] as const).map((key) => {
            const dt: DualWriteDataType = data.data_types[key];
            return (
              <div
                key={key}
                className="flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      syncStatusColors[dt.sync_status] ?? 'bg-slate-500'
                    }`}
                  />
                  <span className="text-sm text-slate-300 capitalize">
                    {key}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400">
                    Neo4j: {dt.neo4j_count} / PG: {dt.postgres_count}
                  </span>
                  <span
                    className={`ml-2 text-xs ${
                      dt.sync_status === 'synced'
                        ? 'text-green-400'
                        : dt.sync_status === 'minor_drift'
                          ? 'text-amber-400'
                          : dt.sync_status === 'out_of_sync'
                            ? 'text-red-400'
                            : 'text-slate-500'
                    }`}
                  >
                    {syncStatusLabels[dt.sync_status] ?? dt.sync_status}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </PanelWrapper>
  );
}
