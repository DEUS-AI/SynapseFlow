/**
 * TemporalContextBadge Component
 *
 * Displays the temporal context detected from the query.
 * Shows the time window and how recent data was considered.
 */

import React from 'react';
import { Clock, History, Calendar, Timer } from 'lucide-react';
import type { TemporalContextInfo } from '../../types/chat';

interface TemporalContextBadgeProps {
  temporal: TemporalContextInfo;
}

const windowConfig: Record<string, {
  icon: React.ElementType;
  label: string;
  color: string;
  description: string;
}> = {
  immediate: {
    icon: Timer,
    label: 'Now',
    color: 'bg-red-900/40 text-red-300 border-red-700',
    description: 'Last 24 hours',
  },
  recent: {
    icon: Clock,
    label: 'Recent',
    color: 'bg-orange-900/40 text-orange-300 border-orange-700',
    description: 'Last 3 days',
  },
  short_term: {
    icon: Clock,
    label: 'Short-term',
    color: 'bg-yellow-900/40 text-yellow-300 border-yellow-700',
    description: 'Last week',
  },
  medium_term: {
    icon: Calendar,
    label: 'Medium-term',
    color: 'bg-blue-900/40 text-blue-300 border-blue-700',
    description: 'Last month',
  },
  long_term: {
    icon: Calendar,
    label: 'Long-term',
    color: 'bg-indigo-900/40 text-indigo-300 border-indigo-700',
    description: 'Last 6 months',
  },
  historical: {
    icon: History,
    label: 'Historical',
    color: 'bg-slate-700/40 text-slate-300 border-slate-600',
    description: 'All time',
  },
};

function formatDuration(hours: number): string {
  if (hours < 1) {
    return `${Math.round(hours * 60)} min`;
  } else if (hours < 24) {
    return `${Math.round(hours)} hr`;
  } else if (hours < 168) {
    return `${Math.round(hours / 24)} days`;
  } else if (hours < 720) {
    return `${Math.round(hours / 168)} weeks`;
  } else {
    return `${Math.round(hours / 720)} months`;
  }
}

export function TemporalContextBadge({ temporal }: TemporalContextBadgeProps) {
  const config = windowConfig[temporal.window] || windowConfig.short_term;
  const Icon = config.icon;

  return (
    <span
      className={`
        inline-flex items-center gap-1 px-1.5 py-0.5
        rounded text-[10px] border ${config.color}
      `}
      title={`Temporal window: ${config.description}${temporal.duration_hours ? ` (${formatDuration(temporal.duration_hours)})` : ''}`}
    >
      <Icon className="w-2.5 h-2.5" />
      <span>{config.label}</span>
      {temporal.duration_hours && (
        <span className="opacity-70">
          ({formatDuration(temporal.duration_hours)})
        </span>
      )}
    </span>
  );
}

// Compact version showing just the icon
export function TemporalContextIcon({ temporal }: { temporal: TemporalContextInfo }) {
  const config = windowConfig[temporal.window] || windowConfig.short_term;
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center justify-center w-5 h-5 rounded ${config.color.replace('border-', '').split(' ')[0]}`}
      title={`Temporal window: ${config.label} - ${config.description}`}
    >
      <Icon className="w-3 h-3" />
    </span>
  );
}
