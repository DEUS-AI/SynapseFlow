import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface TrendDataPoint {
  date: string;
  value: number;
  [key: string]: string | number;
}

interface QualityTrendChartProps {
  data: TrendDataPoint[];
  dataKey?: string;
  title?: string;
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  thresholds?: { value: number; label: string; color: string }[];
  multiLine?: { key: string; color: string; label: string }[];
  formatValue?: (value: number) => string;
  formatDate?: (date: string) => string;
}

export function QualityTrendChart({
  data,
  dataKey = 'value',
  title,
  height = 300,
  showGrid = true,
  showLegend = false,
  thresholds = [],
  multiLine,
  formatValue = (v) => `${(v * 100).toFixed(0)}%`,
  formatDate = (d) => {
    const date = new Date(d);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  },
}: QualityTrendChartProps) {
  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-slate-800/50 rounded-lg border border-slate-700"
        style={{ height }}
      >
        <div className="text-slate-400 text-sm">No trend data available</div>
      </div>
    );
  }

  const lines = multiLine || [{ key: dataKey, color: '#3b82f6', label: 'Score' }];

  return (
    <div className="bg-slate-800/30 rounded-lg p-4">
      {title && (
        <h3 className="text-sm font-medium text-slate-200 mb-4">{title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={data}
          margin={{ top: 10, right: 30, left: 0, bottom: 10 }}
        >
          {showGrid && (
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          )}
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="#64748b"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            axisLine={{ stroke: '#475569' }}
          />
          <YAxis
            domain={[0, 1]}
            tickFormatter={formatValue}
            stroke="#64748b"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            axisLine={{ stroke: '#475569' }}
            width={50}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #475569',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.3)',
            }}
            labelStyle={{ color: '#e2e8f0', fontWeight: 500, marginBottom: 4 }}
            itemStyle={{ color: '#94a3b8', fontSize: 12 }}
            formatter={(value: number) => [formatValue(value), '']}
            labelFormatter={(label) => formatDate(label)}
          />
          {showLegend && (
            <Legend
              wrapperStyle={{ paddingTop: 20 }}
              iconType="line"
              formatter={(value) => (
                <span className="text-slate-300 text-xs">{value}</span>
              )}
            />
          )}
          {/* Reference lines for thresholds */}
          {thresholds.map((threshold, i) => (
            <ReferenceLine
              key={i}
              y={threshold.value}
              stroke={threshold.color}
              strokeDasharray="5 5"
              label={{
                value: threshold.label,
                position: 'right',
                fill: threshold.color,
                fontSize: 10,
              }}
            />
          ))}
          {/* Data lines */}
          {lines.map((line) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              stroke={line.color}
              strokeWidth={2}
              dot={{ fill: line.color, strokeWidth: 0, r: 3 }}
              activeDot={{ r: 5, strokeWidth: 2, stroke: '#1e293b' }}
              name={line.label}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// Period selector component
interface PeriodSelectorProps {
  periods: { value: number; label: string }[];
  selected: number;
  onChange: (days: number) => void;
}

export function PeriodSelector({ periods, selected, onChange }: PeriodSelectorProps) {
  return (
    <div className="flex gap-1 bg-slate-800 rounded-lg p-1">
      {periods.map((period) => (
        <button
          key={period.value}
          onClick={() => onChange(period.value)}
          className={`px-3 py-1 text-xs rounded-md transition-colors ${
            selected === period.value
              ? 'bg-blue-600 text-white'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
          }`}
        >
          {period.label}
        </button>
      ))}
    </div>
  );
}

// Default periods
export const DEFAULT_PERIODS = [
  { value: 7, label: '7D' },
  { value: 14, label: '14D' },
  { value: 30, label: '30D' },
  { value: 90, label: '90D' },
];

// Default thresholds for quality metrics
export const QUALITY_THRESHOLDS = [
  { value: 0.9, label: 'Excellent', color: '#10b981' },
  { value: 0.7, label: 'Good', color: '#3b82f6' },
  { value: 0.5, label: 'Acceptable', color: '#f59e0b' },
];
