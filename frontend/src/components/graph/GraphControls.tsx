import React from 'react';
import { Button } from '../ui/button';

type LayerType = 'all' | 'perception' | 'semantic' | 'reasoning' | 'application';

interface GraphControlsProps {
  onLayoutChange: (layout: 'force' | 'hierarchical') => void;
  onReset: () => void;
  onLayerChange: (layer: LayerType) => void;
  selectedLayer: LayerType;
  nodeCount: number;
  edgeCount: number;
  limit: number;
  onLimitChange: (limit: number) => void;
}

const layers: { id: LayerType; label: string; color: string; bgColor: string }[] = [
  { id: 'all', label: 'All Layers', color: 'bg-gray-600', bgColor: 'bg-gray-100' },
  { id: 'perception', label: 'Perception', color: 'bg-blue-600', bgColor: 'bg-blue-100' },
  { id: 'semantic', label: 'Semantic', color: 'bg-green-600', bgColor: 'bg-green-100' },
  { id: 'reasoning', label: 'Reasoning', color: 'bg-orange-600', bgColor: 'bg-orange-100' },
  { id: 'application', label: 'Application', color: 'bg-purple-600', bgColor: 'bg-purple-100' },
];

const limitOptions = [50, 100, 200, 300, 500, 1000];

export function GraphControls({ onLayoutChange, onReset, onLayerChange, selectedLayer, nodeCount, edgeCount, limit, onLimitChange }: GraphControlsProps) {
  return (
    <>
      {/* Main controls panel */}
      <div className="absolute top-4 left-4 z-10 bg-slate-800 rounded-lg shadow-lg p-4 space-y-3 border border-slate-700">
        <div className="text-sm font-semibold text-gray-200">Graph Controls</div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Nodes:</span>
            <span className="font-semibold text-gray-200">{nodeCount}</span>
          </div>
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Edges:</span>
            <span className="font-semibold text-gray-200">{edgeCount}</span>
          </div>
        </div>

        <div className="pt-2 border-t border-slate-600 space-y-2">
          <div className="space-y-1">
            <label className="text-xs text-gray-400">Query Limit</label>
            <select
              value={limit}
              onChange={(e) => onLimitChange(Number(e.target.value))}
              className="w-full px-2 py-1.5 bg-slate-700 border border-slate-600 text-gray-200 text-sm rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {limitOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt} nodes
                </option>
              ))}
            </select>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={onReset}
            className="w-full border-slate-600 text-gray-200 hover:bg-slate-700"
          >
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Reset View
          </Button>
        </div>
      </div>

      {/* Floating layer filter buttons */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
        {layers.map((layer) => (
          <button
            key={layer.id}
            onClick={() => onLayerChange(layer.id)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg shadow-lg transition-all duration-200 border
              ${selectedLayer === layer.id
                ? `bg-slate-700 border-slate-500 ring-2 ring-offset-2 ring-offset-slate-900 ring-slate-400`
                : 'bg-slate-800 border-slate-700 hover:bg-slate-700'
              }
            `}
          >
            <div className={`w-3 h-3 rounded-full ${layer.color}`}></div>
            <span className={`text-sm font-medium ${selectedLayer === layer.id ? 'text-white' : 'text-gray-300'}`}>
              {layer.label}
            </span>
          </button>
        ))}
      </div>
    </>
  );
}
