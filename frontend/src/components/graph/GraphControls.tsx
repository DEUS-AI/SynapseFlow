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
}

const layers: { id: LayerType; label: string; color: string; bgColor: string }[] = [
  { id: 'all', label: 'All Layers', color: 'bg-gray-600', bgColor: 'bg-gray-100' },
  { id: 'perception', label: 'Perception', color: 'bg-blue-600', bgColor: 'bg-blue-100' },
  { id: 'semantic', label: 'Semantic', color: 'bg-green-600', bgColor: 'bg-green-100' },
  { id: 'reasoning', label: 'Reasoning', color: 'bg-orange-600', bgColor: 'bg-orange-100' },
  { id: 'application', label: 'Application', color: 'bg-purple-600', bgColor: 'bg-purple-100' },
];

export function GraphControls({ onLayoutChange, onReset, onLayerChange, selectedLayer, nodeCount, edgeCount }: GraphControlsProps) {
  return (
    <>
      {/* Main controls panel */}
      <div className="absolute top-4 left-4 z-10 bg-white rounded-lg shadow-lg p-4 space-y-3">
        <div className="text-sm font-semibold text-gray-700">Graph Controls</div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <span>Nodes:</span>
            <span className="font-semibold">{nodeCount}</span>
          </div>
          <div className="flex items-center justify-between text-xs text-gray-600">
            <span>Edges:</span>
            <span className="font-semibold">{edgeCount}</span>
          </div>
        </div>

        <div className="pt-2 border-t space-y-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onReset}
            className="w-full"
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
              flex items-center gap-2 px-4 py-2 rounded-lg shadow-lg transition-all duration-200
              ${selectedLayer === layer.id
                ? `${layer.bgColor} ring-2 ring-offset-2 ring-gray-400`
                : 'bg-white hover:bg-gray-50'
              }
            `}
          >
            <div className={`w-3 h-3 rounded-full ${layer.color}`}></div>
            <span className={`text-sm font-medium ${selectedLayer === layer.id ? 'text-gray-900' : 'text-gray-600'}`}>
              {layer.label}
            </span>
          </button>
        ))}
      </div>
    </>
  );
}
