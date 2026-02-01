import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle, Tags, Search, Filter } from 'lucide-react';

interface DocumentEntitiesTabProps {
  docId: string;
}

interface Entity {
  id: string;
  name: string;
  type: string;
  layer: string;
  confidence?: number;
  properties?: Record<string, any>;
}

const layerColors: Record<string, string> = {
  perception: 'bg-blue-900/50 text-blue-400 border-blue-700',
  semantic: 'bg-green-900/50 text-green-400 border-green-700',
  reasoning: 'bg-orange-900/50 text-orange-400 border-orange-700',
  application: 'bg-purple-900/50 text-purple-400 border-purple-700',
};

const typeColors: Record<string, string> = {
  Disease: 'bg-red-900/50 text-red-400',
  Medication: 'bg-green-900/50 text-green-400',
  Symptom: 'bg-yellow-900/50 text-yellow-400',
  Treatment: 'bg-blue-900/50 text-blue-400',
  Procedure: 'bg-purple-900/50 text-purple-400',
  Anatomy: 'bg-pink-900/50 text-pink-400',
  Gene: 'bg-cyan-900/50 text-cyan-400',
  Protein: 'bg-teal-900/50 text-teal-400',
};

export function DocumentEntitiesTab({ docId }: DocumentEntitiesTabProps) {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLayer, setSelectedLayer] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);

  useEffect(() => {
    async function loadEntities() {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(`/api/admin/documents/${docId}/entities`);
        if (!response.ok) {
          throw new Error('Failed to load entities');
        }

        const data = await response.json();
        setEntities(data.entities || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load entities');
      } finally {
        setLoading(false);
      }
    }

    loadEntities();
  }, [docId]);

  // Get unique types and layers for filters
  const uniqueTypes = [...new Set(entities.map((e) => e.type))].sort();
  const uniqueLayers = [...new Set(entities.map((e) => e.layer?.toLowerCase()))].filter(Boolean).sort();

  // Filter entities
  const filteredEntities = entities.filter((entity) => {
    const matchesSearch = entity.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLayer = selectedLayer === 'all' || entity.layer?.toLowerCase() === selectedLayer;
    const matchesType = selectedType === 'all' || entity.type === selectedType;
    return matchesSearch && matchesLayer && matchesType;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <p className="text-slate-400">Loading entities...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="w-12 h-12 text-red-500" />
          <div>
            <h3 className="text-lg font-medium text-slate-200">Failed to Load Entities</h3>
            <p className="text-slate-400 mt-2">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (entities.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4 text-center">
          <Tags className="w-12 h-12 text-slate-600" />
          <div>
            <h3 className="text-lg font-medium text-slate-200">No Entities Found</h3>
            <p className="text-slate-400 mt-2">
              No entities have been extracted from this document yet.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-6">
      {/* Entity list */}
      <div className="flex-1">
        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search entities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <select
            value={selectedLayer}
            onChange={(e) => setSelectedLayer(e.target.value)}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Layers</option>
            {uniqueLayers.map((layer) => (
              <option key={layer} value={layer}>
                {layer.charAt(0).toUpperCase() + layer.slice(1)}
              </option>
            ))}
          </select>
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Types</option>
            {uniqueTypes.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>

        {/* Results count */}
        <div className="text-sm text-slate-400 mb-4">
          Showing {filteredEntities.length} of {entities.length} entities
        </div>

        {/* Entity table */}
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-800">
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Layer
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Confidence
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {filteredEntities.map((entity) => (
                <tr
                  key={entity.id}
                  className={`hover:bg-slate-800/80 cursor-pointer transition-colors ${
                    selectedEntity?.id === entity.id ? 'bg-slate-800' : ''
                  }`}
                  onClick={() => setSelectedEntity(entity)}
                >
                  <td className="px-4 py-3 text-sm text-slate-200 font-medium">
                    {entity.name}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs ${
                      typeColors[entity.type] || 'bg-slate-700 text-slate-300'
                    }`}>
                      {entity.type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded border text-xs ${
                      layerColors[entity.layer?.toLowerCase()] || 'bg-slate-700 text-slate-300 border-slate-600'
                    }`}>
                      {entity.layer}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-400">
                    {entity.confidence !== undefined
                      ? `${(entity.confidence * 100).toFixed(0)}%`
                      : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Entity details sidebar */}
      {selectedEntity && (
        <div className="w-80 flex-shrink-0">
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 sticky top-4">
            <h3 className="font-medium text-slate-200 mb-4">Entity Details</h3>
            <dl className="space-y-3">
              <div>
                <dt className="text-xs text-slate-400">Name</dt>
                <dd className="text-sm text-slate-200 font-medium mt-1">
                  {selectedEntity.name}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Type</dt>
                <dd className="mt-1">
                  <span className={`px-2 py-1 rounded text-xs ${
                    typeColors[selectedEntity.type] || 'bg-slate-700 text-slate-300'
                  }`}>
                    {selectedEntity.type}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Layer</dt>
                <dd className="mt-1">
                  <span className={`px-2 py-1 rounded border text-xs ${
                    layerColors[selectedEntity.layer?.toLowerCase()] || 'bg-slate-700 text-slate-300 border-slate-600'
                  }`}>
                    {selectedEntity.layer}
                  </span>
                </dd>
              </div>
              {selectedEntity.confidence !== undefined && (
                <div>
                  <dt className="text-xs text-slate-400">Confidence</dt>
                  <dd className="text-sm text-slate-200 mt-1">
                    {(selectedEntity.confidence * 100).toFixed(1)}%
                  </dd>
                </div>
              )}
              {selectedEntity.properties && Object.keys(selectedEntity.properties).length > 0 && (
                <div>
                  <dt className="text-xs text-slate-400 mb-2">Properties</dt>
                  <dd className="space-y-1">
                    {Object.entries(selectedEntity.properties).map(([key, value]) => (
                      <div key={key} className="text-xs bg-slate-800 rounded p-2">
                        <span className="text-slate-400">{key}:</span>{' '}
                        <span className="text-slate-200">
                          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </span>
                      </div>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}
