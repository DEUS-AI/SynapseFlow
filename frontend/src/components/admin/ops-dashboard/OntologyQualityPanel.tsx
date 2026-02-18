import React from 'react';
import { Shield } from 'lucide-react';
import { usePanelQuery } from './usePanelQuery';
import { PanelWrapper } from './PanelWrapper';
import type { OntologyQualityResponse } from './types';

const LEVEL_COLORS: Record<string, string> = {
  excellent: 'bg-green-500 text-green-100',
  good: 'bg-emerald-600 text-emerald-100',
  acceptable: 'bg-amber-600 text-amber-100',
  poor: 'bg-red-600 text-red-100',
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

export function OntologyQualityPanel() {
  const { data, loading, error, secondsAgo, isStale } =
    usePanelQuery<OntologyQualityResponse>('ontology-quality', '/api/ontology/quality', 60000);

  return (
    <PanelWrapper
      title="Ontology Quality"
      icon={<Shield className="h-4 w-4 text-orange-400" />}
      loading={loading}
      error={error}
      secondsAgo={secondsAgo}
      isStale={isStale}
    >
      {data && !data.has_assessment ? (
        <div className="text-sm text-slate-400 py-4">
          <p>No assessment available.</p>
          <a
            href="/admin/quality"
            className="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block"
          >
            Run an assessment &rarr;
          </a>
        </div>
      ) : data?.latest ? (
        <>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl font-bold text-slate-100">
              {(data.latest.overall_score * 100).toFixed(0)}
            </span>
            <div>
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  LEVEL_COLORS[data.latest.quality_level] ??
                  'bg-slate-600 text-slate-200'
                }`}
              >
                {data.latest.quality_level}
              </span>
              <p className="text-xs text-slate-500 mt-1">
                assessed {formatTimestamp(data.latest.assessed_at)}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <DimScore label="Coverage" value={data.latest.coverage_ratio} />
            <DimScore label="Compliance" value={data.latest.compliance_ratio} />
            <DimScore label="Coherence" value={data.latest.coherence_ratio} />
            <DimScore
              label="Consistency"
              value={data.latest.consistency_ratio}
            />
          </div>

          {data.latest.critical_issues.length > 0 && (
            <p className="text-xs text-red-400 mt-3">
              {data.latest.critical_issues.length} critical issue
              {data.latest.critical_issues.length !== 1 ? 's' : ''}
            </p>
          )}
        </>
      ) : null}
    </PanelWrapper>
  );
}

function DimScore({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 85
      ? 'text-green-400'
      : pct >= 70
        ? 'text-amber-400'
        : 'text-red-400';
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-slate-400">{label}</span>
      <span className={`text-sm font-medium ${color}`}>{pct}%</span>
    </div>
  );
}
