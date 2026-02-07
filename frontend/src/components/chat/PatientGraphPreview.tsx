import React, { useState, useEffect, useRef } from 'react';
import { Network, ExternalLink, Loader2 } from 'lucide-react';
import * as d3 from 'd3';

interface GraphNode {
  id: string;
  label: string;
  type: string;
  layer: string;
  x?: number;
  y?: number;
}

interface GraphEdge {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  label: string;
  type: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface PatientGraphPreviewProps {
  patientId: string;
  onExpandClick?: () => void;
}

const typeColors: Record<string, string> = {
  Patient: '#8b5cf6',     // Purple
  Diagnosis: '#3b82f6',   // Blue
  Medication: '#10b981',  // Green
  Allergy: '#ef4444',     // Red
  Symptom: '#f59e0b',     // Orange
  Entity: '#6b7280',      // Gray
};

export function PatientGraphPreview({ patientId, onExpandClick }: PatientGraphPreviewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch graph data
  useEffect(() => {
    async function fetchGraph() {
      if (!patientId) return;

      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/patients/${encodeURIComponent(patientId)}/graph?limit=30`
        );

        if (!response.ok) {
          throw new Error('Failed to fetch graph');
        }

        const data = await response.json();
        setGraphData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    fetchGraph();
  }, [patientId]);

  // Render mini graph
  useEffect(() => {
    if (!graphData || !svgRef.current || graphData.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const width = 220;
    const height = 120;

    svg.selectAll('*').remove();

    // Create a group for the graph
    const g = svg.append('g');

    // Create simulation
    const simulation = d3.forceSimulation(graphData.nodes as d3.SimulationNodeDatum[])
      .force('link', d3.forceLink(graphData.edges)
        .id((d: any) => d.id)
        .distance(40))
      .force('charge', d3.forceManyBody().strength(-80))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(15));

    // Draw edges
    const links = g.append('g')
      .selectAll('line')
      .data(graphData.edges)
      .enter()
      .append('line')
      .attr('stroke', '#475569')
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.6);

    // Draw nodes
    const nodes = g.append('g')
      .selectAll('circle')
      .data(graphData.nodes)
      .enter()
      .append('circle')
      .attr('r', (d) => d.type === 'Patient' ? 10 : 6)
      .attr('fill', (d) => typeColors[d.type] || typeColors.Entity)
      .attr('stroke', '#1e293b')
      .attr('stroke-width', 1);

    // Update positions on tick
    simulation.on('tick', () => {
      links
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      nodes
        .attr('cx', (d: any) => Math.max(10, Math.min(width - 10, d.x)))
        .attr('cy', (d: any) => Math.max(10, Math.min(height - 10, d.y)));
    });

    // Stop simulation after settling
    setTimeout(() => simulation.stop(), 1500);

    return () => {
      simulation.stop();
    };
  }, [graphData]);

  // Count nodes by type
  const nodeCounts = graphData?.nodes.reduce((acc, node) => {
    acc[node.type] = (acc[node.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>) || {};

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-400 text-sm py-2">
        Error: {error}
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="text-slate-500 text-sm py-4 text-center">
        No medical relationships found
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Mini graph visualization */}
      <div className="bg-slate-900/50 rounded-lg border border-slate-700/50 overflow-hidden">
        <svg
          ref={svgRef}
          width="100%"
          height="120"
          viewBox="0 0 220 120"
          className="block"
        />
      </div>

      {/* Node counts */}
      <div className="flex flex-wrap gap-2 text-xs">
        {nodeCounts.Diagnosis && nodeCounts.Diagnosis > 0 && (
          <span className="flex items-center gap-1 px-2 py-1 rounded bg-blue-900/30 text-blue-400">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            {nodeCounts.Diagnosis} Diagnosis{nodeCounts.Diagnosis > 1 ? 'es' : ''}
          </span>
        )}
        {nodeCounts.Medication && nodeCounts.Medication > 0 && (
          <span className="flex items-center gap-1 px-2 py-1 rounded bg-green-900/30 text-green-400">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            {nodeCounts.Medication} Med{nodeCounts.Medication > 1 ? 's' : ''}
          </span>
        )}
        {nodeCounts.Allergy && nodeCounts.Allergy > 0 && (
          <span className="flex items-center gap-1 px-2 py-1 rounded bg-red-900/30 text-red-400">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            {nodeCounts.Allergy} Allerg{nodeCounts.Allergy > 1 ? 'ies' : 'y'}
          </span>
        )}
      </div>

      {/* View full graph button */}
      {onExpandClick && (
        <button
          onClick={onExpandClick}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-slate-700/50 hover:bg-slate-700 text-slate-300 hover:text-slate-100 transition-colors text-sm"
        >
          <Network className="w-4 h-4" />
          View Full Graph
          <ExternalLink className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}

export default PatientGraphPreview;
