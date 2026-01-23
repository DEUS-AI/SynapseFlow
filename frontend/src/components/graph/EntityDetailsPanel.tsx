import React, { useEffect, useState } from 'react';
import type { GraphNode } from '../../types/graph';

interface EntityDetailsPanelProps {
  node: GraphNode;
  onClose: () => void;
}

interface NodeDetails {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
  outgoing: Array<{ type: string; target: string; targetId: string }>;
  incoming: Array<{ type: string; source: string; sourceId: string }>;
}

export function EntityDetailsPanel({ node, onClose }: EntityDetailsPanelProps) {
  const [details, setDetails] = useState<NodeDetails | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/graph/node/${encodeURIComponent(node.id)}`)
      .then(res => res.json())
      .then(data => {
        setDetails(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load node details:', err);
        setLoading(false);
      });
  }, [node.id]);

  const layerColors: Record<string, string> = {
    perception: 'bg-blue-100 text-blue-800',
    semantic: 'bg-green-100 text-green-800',
    reasoning: 'bg-orange-100 text-orange-800',
    application: 'bg-purple-100 text-purple-800',
  };

  return (
    <div className="w-96 bg-white border-l shadow-lg overflow-y-auto">
      <div className="p-6 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h2 className="text-lg font-semibold break-words">{node.label}</h2>
            <div className="flex flex-wrap gap-2 mt-2">
              <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium">
                {node.type}
              </span>
              <span className={`px-2 py-1 rounded text-xs font-medium ${layerColors[node.layer] || 'bg-gray-100 text-gray-700'}`}>
                {node.layer}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full"></div>
          </div>
        ) : details ? (
          <>
            {/* Properties */}
            {Object.keys(details.properties).length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">Properties</h3>
                <div className="bg-gray-50 rounded p-3 space-y-2">
                  {Object.entries(details.properties).map(([key, value]) => (
                    <div key={key} className="text-sm">
                      <span className="font-medium text-gray-600">{key}:</span>{' '}
                      <span className="text-gray-900 break-words">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Outgoing Relationships */}
            {details.outgoing && details.outgoing.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">Outgoing Relationships</h3>
                <div className="space-y-2">
                  {details.outgoing.map((rel, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm p-2 bg-blue-50 rounded">
                      <svg className="h-4 w-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                      </svg>
                      <div>
                        <div className="font-medium text-blue-900">{rel.type}</div>
                        <div className="text-blue-700 text-xs">{rel.target}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Incoming Relationships */}
            {details.incoming && details.incoming.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">Incoming Relationships</h3>
                <div className="space-y-2">
                  {details.incoming.map((rel, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm p-2 bg-green-50 rounded">
                      <svg className="h-4 w-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16l-4-4m0 0l4-4m-4 4h18" />
                      </svg>
                      <div>
                        <div className="font-medium text-green-900">{rel.type}</div>
                        <div className="text-green-700 text-xs">{rel.source}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="text-center text-gray-600 py-8">
            Failed to load node details
          </div>
        )}
      </div>
    </div>
  );
}
