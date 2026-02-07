/**
 * DIKWLayerBadge Component
 *
 * Displays the DIKW layers used to answer a query.
 * DIKW = Data, Information, Knowledge, Wisdom pyramid.
 * Our layers: PERCEPTION, SEMANTIC, REASONING, APPLICATION
 */

import React from 'react';
import { Eye, BookOpen, Brain, Zap, Layers } from 'lucide-react';

interface DIKWLayerBadgeProps {
  layers: string[];
  showTooltip?: boolean;
}

const layerConfig: Record<string, {
  icon: React.ElementType;
  label: string;
  color: string;
  description: string;
}> = {
  PERCEPTION: {
    icon: Eye,
    label: 'Perception',
    color: 'bg-cyan-900/50 text-cyan-300 border-cyan-700',
    description: 'Raw observations from conversations',
  },
  SEMANTIC: {
    icon: BookOpen,
    label: 'Semantic',
    color: 'bg-emerald-900/50 text-emerald-300 border-emerald-700',
    description: 'Validated knowledge with ontology mappings',
  },
  REASONING: {
    icon: Brain,
    label: 'Reasoning',
    color: 'bg-violet-900/50 text-violet-300 border-violet-700',
    description: 'Inferred knowledge from medical rules',
  },
  APPLICATION: {
    icon: Zap,
    label: 'Application',
    color: 'bg-rose-900/50 text-rose-300 border-rose-700',
    description: 'Actionable recommendations',
  },
};

export function DIKWLayerBadge({ layers, showTooltip = true }: DIKWLayerBadgeProps) {
  if (!layers || layers.length === 0) return null;

  // Sort layers by hierarchy
  const layerOrder = ['PERCEPTION', 'SEMANTIC', 'REASONING', 'APPLICATION'];
  const sortedLayers = [...layers].sort(
    (a, b) => layerOrder.indexOf(a) - layerOrder.indexOf(b)
  );

  return (
    <div className="flex items-center gap-1">
      <Layers className="w-3 h-3 text-slate-500" />
      <div className="flex items-center gap-0.5">
        {sortedLayers.map((layer, index) => {
          const config = layerConfig[layer];
          if (!config) return null;

          const Icon = config.icon;

          return (
            <span
              key={layer}
              className={`
                inline-flex items-center gap-0.5 px-1.5 py-0.5
                rounded text-[10px] border ${config.color}
                ${index > 0 ? '-ml-0.5' : ''}
              `}
              title={showTooltip ? `${config.label}: ${config.description}` : undefined}
            >
              <Icon className="w-2.5 h-2.5" />
              <span className="hidden sm:inline">{config.label}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

// Simple layer indicator dots for very compact display
export function DIKWLayerDots({ layers }: { layers: string[] }) {
  if (!layers || layers.length === 0) return null;

  const layerOrder = ['PERCEPTION', 'SEMANTIC', 'REASONING', 'APPLICATION'];
  const sortedLayers = [...layers].sort(
    (a, b) => layerOrder.indexOf(a) - layerOrder.indexOf(b)
  );

  const dotColors: Record<string, string> = {
    PERCEPTION: 'bg-cyan-400',
    SEMANTIC: 'bg-emerald-400',
    REASONING: 'bg-violet-400',
    APPLICATION: 'bg-rose-400',
  };

  return (
    <div
      className="flex items-center gap-0.5"
      title={`Layers: ${sortedLayers.join(' → ')}`}
    >
      {sortedLayers.map((layer, index) => (
        <React.Fragment key={layer}>
          <span className={`w-1.5 h-1.5 rounded-full ${dotColors[layer] || 'bg-slate-400'}`} />
          {index < sortedLayers.length - 1 && (
            <span className="text-slate-600 text-[8px]">→</span>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
