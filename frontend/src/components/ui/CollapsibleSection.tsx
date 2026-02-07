import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface CollapsibleSectionProps {
  title: string;
  icon?: React.ReactNode;
  badge?: string | number;
  badgeColor?: 'red' | 'blue' | 'green' | 'orange' | 'purple' | 'slate';
  defaultExpanded?: boolean;
  children: React.ReactNode;
  className?: string;
}

const badgeColors = {
  red: 'bg-red-900/50 text-red-400',
  blue: 'bg-blue-900/50 text-blue-400',
  green: 'bg-green-900/50 text-green-400',
  orange: 'bg-orange-900/50 text-orange-400',
  purple: 'bg-purple-900/50 text-purple-400',
  slate: 'bg-slate-700 text-slate-400',
};

export function CollapsibleSection({
  title,
  icon,
  badge,
  badgeColor = 'slate',
  defaultExpanded = false,
  children,
  className = '',
}: CollapsibleSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className={`bg-slate-800/50 rounded-lg border border-slate-700 overflow-hidden ${className}`}>
      {/* Header */}
      <button
        type="button"
        className="w-full flex items-center justify-between p-3 hover:bg-slate-800/80 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {icon && (
            <div className={`p-1.5 rounded-lg ${badgeColors[badgeColor]}`}>
              {icon}
            </div>
          )}
          <span className="font-medium text-slate-200 text-sm">{title}</span>
          {badge !== undefined && (
            <span className="px-1.5 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">
              {badge}
            </span>
          )}
        </div>
        <div className="text-slate-400">
          {expanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </div>
      </button>

      {/* Content */}
      <div
        className={`transition-all duration-200 ease-in-out ${
          expanded ? 'opacity-100' : 'max-h-0 opacity-0 overflow-hidden'
        }`}
      >
        <div className="p-3 pt-0 border-t border-slate-700/50">
          {children}
        </div>
      </div>
    </div>
  );
}

export default CollapsibleSection;
