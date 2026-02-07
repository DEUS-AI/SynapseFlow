import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle, Network } from 'lucide-react';
import { KnowledgeGraphViewer } from '../../graph/KnowledgeGraphViewer';

interface DocumentGraphTabProps {
  docId: string;
}

interface GraphData {
  nodes: any[];
  edges: any[];
}

export function DocumentGraphTab({ docId }: DocumentGraphTabProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadGraph() {
      try {
        setLoading(true);
        setError(null);

        // Fetch document-specific graph data
        const response = await fetch(`/api/admin/documents/${docId}/graph?limit=200`);
        if (!response.ok) {
          throw new Error('Failed to load graph data');
        }

        const data = await response.json();
        setGraphData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load graph');
      } finally {
        setLoading(false);
      }
    }

    loadGraph();
  }, [docId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <p className="text-slate-400">Loading knowledge graph...</p>
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
            <h3 className="text-lg font-medium text-slate-200">Failed to Load Graph</h3>
            <p className="text-slate-400 mt-2">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4 text-center">
          <Network className="w-12 h-12 text-slate-600" />
          <div>
            <h3 className="text-lg font-medium text-slate-200">No Graph Data</h3>
            <p className="text-slate-400 mt-2">
              No entities or relationships have been extracted from this document yet.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[600px] bg-slate-800/30 rounded-lg border border-slate-700 overflow-hidden">
      <KnowledgeGraphViewer
        initialData={graphData}
        documentFilter={docId}
      />
    </div>
  );
}
