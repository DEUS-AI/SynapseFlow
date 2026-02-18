import React from 'react';
import { Database } from 'lucide-react';
import { usePolling } from './usePolling';
import { PanelWrapper } from './PanelWrapper';
import type { SystemMetrics, LayerStats } from './types';

const LAYER_COLORS: Record<string, string> = {
  PERCEPTION: 'bg-blue-500',
  SEMANTIC: 'bg-emerald-500',
  REASONING: 'bg-purple-500',
  APPLICATION: 'bg-amber-500',
};

const LAYER_ORDER = ['APPLICATION', 'REASONING', 'SEMANTIC', 'PERCEPTION'];

export function KnowledgeGraphPanel() {
  const metrics = usePolling<SystemMetrics>('/api/admin/metrics', 30000);
  const layers = usePolling<LayerStats>('/api/admin/layer-stats', 30000);

  const loading = metrics.loading || layers.loading;
  const error = metrics.error || layers.error;

  return (
    <PanelWrapper
      title="Knowledge Graph"
      icon={<Database className="h-4 w-4 text-purple-400" />}
      loading={loading}
      error={error}
      secondsAgo={metrics.secondsAgo}
      isStale={metrics.isStale}
    >
      {metrics.data && (
        <div className="grid grid-cols-3 gap-4 mb-4">
          <Stat label="Nodes" value={metrics.data.neo4j_nodes} />
          <Stat label="Relationships" value={metrics.data.neo4j_relationships} />
          <Stat label="Patients" value={metrics.data.total_patients} />
        </div>
      )}

      {layers.data && (
        <div className="space-y-2">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">
            DIKW Layers
          </p>
          {LAYER_ORDER.map((layer) => {
            const count = layers.data!.layers[layer] ?? 0;
            const total = layers.data!.total || 1;
            const pct = Math.round((count / total) * 100);
            return (
              <div key={layer} className="flex items-center gap-2">
                <span className="text-xs text-slate-400 w-24 text-right">
                  {layer}
                </span>
                <div className="flex-1 h-4 bg-slate-700 rounded overflow-hidden">
                  <div
                    className={`h-full ${LAYER_COLORS[layer] ?? 'bg-slate-500'} rounded`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-xs text-slate-300 w-16">
                  {count.toLocaleString()}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </PanelWrapper>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-xl font-bold text-slate-100">
        {value.toLocaleString()}
      </p>
    </div>
  );
}
