import React from 'react';
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

interface SparklineChartProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  showTooltip?: boolean;
  className?: string;
}

interface DataPoint {
  value: number;
  index: number;
}

export function SparklineChart({
  data,
  width = 60,
  height = 20,
  color = '#3b82f6',
  showTooltip = true,
  className = '',
}: SparklineChartProps) {
  // Convert array to chart data format
  const chartData: DataPoint[] = data.map((value, index) => ({
    value,
    index,
  }));

  if (chartData.length === 0) {
    return (
      <div
        className={`bg-slate-700/50 rounded ${className}`}
        style={{ width, height }}
      />
    );
  }

  // Calculate trend direction
  const trend = data.length >= 2 ? data[data.length - 1] - data[0] : 0;
  const trendColor = trend > 0 ? '#10b981' : trend < 0 ? '#ef4444' : color;

  return (
    <div className={className} style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`sparklineGradient-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={trendColor} stopOpacity={0.3} />
              <stop offset="95%" stopColor={trendColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          {showTooltip && (
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="bg-slate-800 border border-slate-600 px-2 py-1 rounded text-xs text-slate-200 shadow-lg">
                      {(payload[0].value as number).toFixed(2)}
                    </div>
                  );
                }
                return null;
              }}
            />
          )}
          <Area
            type="monotone"
            dataKey="value"
            stroke={trendColor}
            strokeWidth={1.5}
            fill={`url(#sparklineGradient-${color.replace('#', '')})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Inline sparkline with label
interface SparklineWithLabelProps extends SparklineChartProps {
  label: string;
  currentValue: number;
  format?: (value: number) => string;
}

export function SparklineWithLabel({
  label,
  currentValue,
  data,
  format = (v) => `${(v * 100).toFixed(0)}%`,
  ...props
}: SparklineWithLabelProps) {
  const trend = data.length >= 2 ? data[data.length - 1] - data[0] : 0;
  const trendIcon = trend > 0 ? '↑' : trend < 0 ? '↓' : '→';
  const trendColor = trend > 0 ? 'text-green-400' : trend < 0 ? 'text-red-400' : 'text-slate-400';

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1">
        <div className="text-xs text-slate-400">{label}</div>
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-slate-100">
            {format(currentValue)}
          </span>
          <span className={`text-xs ${trendColor}`}>{trendIcon}</span>
        </div>
      </div>
      <SparklineChart data={data} {...props} />
    </div>
  );
}
