/**
 * QueryIntentBadge Component
 *
 * Displays the classified query intent from the DIKWRouter.
 * Shows intent type with an icon and optional confidence indicator.
 */

import React from 'react';
import {
  HelpCircle,
  Link2,
  Lightbulb,
  Compass,
  Target,
} from 'lucide-react';
import type { RoutingInfo } from '../../types/chat';

interface QueryIntentBadgeProps {
  routing: RoutingInfo;
  compact?: boolean;
}

const intentConfig = {
  factual: {
    icon: HelpCircle,
    label: 'Factual',
    description: 'Looking up specific facts',
    color: 'bg-blue-900/50 text-blue-300 border-blue-700',
  },
  relational: {
    icon: Link2,
    label: 'Relational',
    description: 'Exploring connections',
    color: 'bg-purple-900/50 text-purple-300 border-purple-700',
  },
  inferential: {
    icon: Lightbulb,
    label: 'Inferential',
    description: 'Reasoning & analysis',
    color: 'bg-amber-900/50 text-amber-300 border-amber-700',
  },
  actionable: {
    icon: Target,
    label: 'Actionable',
    description: 'Seeking guidance',
    color: 'bg-green-900/50 text-green-300 border-green-700',
  },
  exploratory: {
    icon: Compass,
    label: 'Exploratory',
    description: 'Open exploration',
    color: 'bg-slate-700/50 text-slate-300 border-slate-600',
  },
};

export function QueryIntentBadge({ routing, compact = false }: QueryIntentBadgeProps) {
  const intent = intentConfig[routing.intent] || intentConfig.exploratory;
  const Icon = intent.icon;

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${intent.color}`}
        title={`${intent.label}: ${intent.description}`}
      >
        <Icon className="w-3 h-3" />
        {intent.label}
      </span>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-lg border ${intent.color}`}>
      <Icon className="w-4 h-4" />
      <div className="flex flex-col">
        <span className="text-xs font-medium">{intent.label}</span>
        {routing.intent_confidence && (
          <span className="text-[10px] opacity-70">
            {Math.round(routing.intent_confidence * 100)}% confidence
          </span>
        )}
      </div>
    </div>
  );
}

// Smaller inline version for message metadata
export function QueryIntentChip({ routing }: { routing: RoutingInfo }) {
  const intent = intentConfig[routing.intent] || intentConfig.exploratory;
  const Icon = intent.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] border ${intent.color}`}
      title={`Query classified as ${intent.label}: ${intent.description}`}
    >
      <Icon className="w-2.5 h-2.5" />
      {intent.label}
    </span>
  );
}
