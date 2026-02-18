import React from 'react';
import { Card } from '../../ui/card';
import { AlertCircle, Loader2 } from 'lucide-react';

interface PanelWrapperProps {
  title: string;
  icon?: React.ReactNode;
  loading: boolean;
  error: string | null;
  secondsAgo: number | null;
  isStale: boolean;
  children: React.ReactNode;
}

export function PanelWrapper({
  title,
  icon,
  loading,
  error,
  secondsAgo,
  isStale,
  children,
}: PanelWrapperProps) {
  const timeText =
    secondsAgo === null
      ? ''
      : secondsAgo < 5
        ? 'just now'
        : `${secondsAgo}s ago`;

  return (
    <Card className="p-5 bg-slate-800 border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wide">
            {title}
          </h3>
        </div>
        {timeText && (
          <span
            className={`text-xs ${isStale ? 'text-amber-400' : 'text-slate-500'}`}
          >
            {timeText}
          </span>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 text-slate-400 animate-spin" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 py-6 text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span className="text-sm">Failed to load</span>
        </div>
      ) : (
        children
      )}
    </Card>
  );
}
