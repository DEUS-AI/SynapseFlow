import React from 'react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';

interface MetricData {
  metric: string;
  value: number;
  fullMark?: number;
}

interface MetricRadarChartProps {
  data: MetricData[];
  title?: string;
  height?: number;
  color?: string;
  fillOpacity?: number;
  showLegend?: boolean;
  comparison?: {
    data: MetricData[];
    color: string;
    label: string;
  };
}

export function MetricRadarChart({
  data,
  title,
  height = 300,
  color = '#3b82f6',
  fillOpacity = 0.3,
  showLegend = false,
  comparison,
}: MetricRadarChartProps) {
  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-slate-800/50 rounded-lg border border-slate-700"
        style={{ height }}
      >
        <div className="text-slate-400 text-sm">No data available</div>
      </div>
    );
  }

  // Merge data with comparison if provided
  const chartData = data.map((item, index) => ({
    ...item,
    fullMark: item.fullMark || 1,
    ...(comparison?.data[index] ? { comparison: comparison.data[index].value } : {}),
  }));

  return (
    <div className="bg-slate-800/30 rounded-lg p-4">
      {title && (
        <h3 className="text-sm font-medium text-slate-200 mb-4 text-center">{title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
          <PolarGrid stroke="#475569" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            tickLine={{ stroke: '#475569' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 1]}
            tick={{ fontSize: 10, fill: '#64748b' }}
            tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
            axisLine={{ stroke: '#475569' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #475569',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.3)',
            }}
            labelStyle={{ color: '#e2e8f0', fontWeight: 500 }}
            formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, '']}
          />
          {showLegend && (
            <Legend
              wrapperStyle={{ paddingTop: 10 }}
              iconType="circle"
              formatter={(value) => (
                <span className="text-slate-300 text-xs">{value}</span>
              )}
            />
          )}
          <Radar
            name="Current"
            dataKey="value"
            stroke={color}
            fill={color}
            fillOpacity={fillOpacity}
            strokeWidth={2}
          />
          {comparison && (
            <Radar
              name={comparison.label}
              dataKey="comparison"
              stroke={comparison.color}
              fill={comparison.color}
              fillOpacity={fillOpacity * 0.5}
              strokeWidth={2}
              strokeDasharray="5 5"
            />
          )}
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Pre-configured radar for document quality metrics
interface DocumentQualityRadarProps {
  metrics: {
    contextualRelevancy: number;
    contextSufficiency: number;
    informationDensity: number;
    structuralClarity: number;
    entityDensity: number;
    chunkingQuality: number;
  };
  height?: number;
  title?: string;
}

export function DocumentQualityRadar({
  metrics,
  height = 280,
  title = 'Quality Metrics',
}: DocumentQualityRadarProps) {
  const data: MetricData[] = [
    { metric: 'Relevancy', value: metrics.contextualRelevancy },
    { metric: 'Sufficiency', value: metrics.contextSufficiency },
    { metric: 'Density', value: metrics.informationDensity },
    { metric: 'Structure', value: metrics.structuralClarity },
    { metric: 'Entities', value: metrics.entityDensity },
    { metric: 'Chunking', value: metrics.chunkingQuality },
  ];

  return (
    <MetricRadarChart
      data={data}
      title={title}
      height={height}
      color="#3b82f6"
    />
  );
}

// Pre-configured radar for ontology quality metrics
interface OntologyQualityRadarProps {
  metrics: {
    coverage: number;
    compliance: number;
    coherence: number;
    consistency: number;
    normalization?: number;
    interoperability?: number;
  };
  height?: number;
  title?: string;
}

export function OntologyQualityRadar({
  metrics,
  height = 280,
  title = 'Ontology Quality',
}: OntologyQualityRadarProps) {
  const data: MetricData[] = [
    { metric: 'Coverage', value: metrics.coverage },
    { metric: 'Compliance', value: metrics.compliance },
    { metric: 'Coherence', value: metrics.coherence },
    { metric: 'Consistency', value: metrics.consistency },
    ...(metrics.normalization !== undefined
      ? [{ metric: 'Normalization', value: metrics.normalization }]
      : []),
    ...(metrics.interoperability !== undefined
      ? [{ metric: 'Interop', value: metrics.interoperability }]
      : []),
  ];

  return (
    <MetricRadarChart
      data={data}
      title={title}
      height={height}
      color="#10b981"
    />
  );
}
