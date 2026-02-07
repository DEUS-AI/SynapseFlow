import React, { useState, useEffect, useRef } from 'react';
import { X, Network, Loader2, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import * as d3 from 'd3';

interface GraphNode {
  id: string;
  label: string;
  type: string;
  layer: string;
  properties?: Record<string, any>;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
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

interface PatientDetailsModalProps {
  patientId: string;
  isOpen: boolean;
  onClose: () => void;
}

const typeColors: Record<string, string> = {
  Patient: '#8b5cf6',     // Purple
  Diagnosis: '#3b82f6',   // Blue
  Medication: '#10b981',  // Green
  Allergy: '#ef4444',     // Red
  Symptom: '#f59e0b',     // Orange
  Entity: '#6b7280',      // Gray
};

export function PatientDetailsModal({ patientId, isOpen, onClose }: PatientDetailsModalProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [transform, setTransform] = useState({ k: 1, x: 0, y: 0 });

  // Fetch graph data when modal opens
  useEffect(() => {
    if (!isOpen || !patientId) return;

    async function fetchGraph() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/patients/${encodeURIComponent(patientId)}/graph?limit=100`
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
  }, [isOpen, patientId]);

  // Render graph with D3
  useEffect(() => {
    if (!graphData || !svgRef.current || !containerRef.current || graphData.nodes.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    svg.selectAll('*').remove();

    // Create container group for zoom/pan
    const g = svg.append('g');

    // Setup zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        setTransform(event.transform);
      });

    svg.call(zoom);

    // Create simulation
    const simulation = d3.forceSimulation(graphData.nodes as d3.SimulationNodeDatum[])
      .force('link', d3.forceLink(graphData.edges)
        .id((d: any) => d.id)
        .distance(100))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    // Draw edges
    const links = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(graphData.edges)
      .enter()
      .append('line')
      .attr('stroke', '#475569')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.6);

    // Draw edge labels
    const linkLabels = g.append('g')
      .attr('class', 'link-labels')
      .selectAll('text')
      .data(graphData.edges)
      .enter()
      .append('text')
      .attr('font-size', '10px')
      .attr('fill', '#64748b')
      .attr('text-anchor', 'middle')
      .text((d) => d.label);

    // Draw nodes
    const nodes = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(graphData.nodes)
      .enter()
      .append('g')
      .attr('cursor', 'pointer')
      .call(d3.drag<SVGGElement, GraphNode>()
        .on('start', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d: any) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }) as any)
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(d);
      });

    // Node circles
    nodes.append('circle')
      .attr('r', (d) => d.type === 'Patient' ? 25 : 18)
      .attr('fill', (d) => typeColors[d.type] || typeColors.Entity)
      .attr('stroke', '#1e293b')
      .attr('stroke-width', 2);

    // Node labels
    nodes.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', '11px')
      .attr('fill', '#fff')
      .attr('pointer-events', 'none')
      .text((d) => {
        const label = d.label || d.id;
        return label.length > 12 ? label.substring(0, 10) + '...' : label;
      });

    // Click on background to deselect
    svg.on('click', () => setSelectedNode(null));

    // Update positions on tick
    simulation.on('tick', () => {
      links
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      linkLabels
        .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
        .attr('y', (d: any) => (d.source.y + d.target.y) / 2);

      nodes.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
    };
  }, [graphData]);

  // Zoom controls
  const handleZoom = (factor: number) => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(300).call(
      (d3.zoom<SVGSVGElement, unknown>() as any).scaleTo,
      transform.k * factor
    );
  };

  const handleReset = () => {
    if (!svgRef.current || !containerRef.current) return;
    const svg = d3.select(svgRef.current);
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    svg.transition().duration(500).call(
      (d3.zoom<SVGSVGElement, unknown>() as any).transform,
      d3.zoomIdentity.translate(width / 2, height / 2).scale(1).translate(-width / 2, -height / 2)
    );
  };

  if (!isOpen) return null;

  // Count nodes by type
  const nodeCounts = graphData?.nodes.reduce((acc, node) => {
    acc[node.type] = (acc[node.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>) || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-slate-900 rounded-xl w-[90vw] h-[85vh] max-w-6xl flex flex-col overflow-hidden border border-slate-700">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-900/50 text-blue-400">
              <Network className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Patient Medical Graph</h2>
              <p className="text-sm text-slate-400">
                {patientId} • {graphData?.nodes.length || 0} nodes • {graphData?.edges.length || 0} relationships
              </p>
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleZoom(1.2)}
              className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200"
              title="Zoom in"
            >
              <ZoomIn className="w-5 h-5" />
            </button>
            <button
              onClick={() => handleZoom(0.8)}
              className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200"
              title="Zoom out"
            >
              <ZoomOut className="w-5 h-5" />
            </button>
            <button
              onClick={handleReset}
              className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200"
              title="Reset view"
            >
              <RotateCcw className="w-5 h-5" />
            </button>
            <div className="w-px h-6 bg-slate-700 mx-2" />
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 px-4 py-2 border-b border-slate-700/50 bg-slate-800/50">
          {Object.entries(typeColors).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5 text-xs text-slate-400">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              {type}
              {nodeCounts[type] ? ` (${nodeCounts[type]})` : ''}
            </div>
          ))}
        </div>

        {/* Graph Container */}
        <div ref={containerRef} className="flex-1 relative">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
            </div>
          ) : error ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-red-400">Error: {error}</p>
            </div>
          ) : !graphData || graphData.nodes.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-slate-500">No medical relationships found for this patient</p>
            </div>
          ) : (
            <svg ref={svgRef} className="w-full h-full" />
          )}
        </div>

        {/* Selected Node Details */}
        {selectedNode && (
          <div className="absolute bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 bg-slate-800 rounded-lg border border-slate-700 p-4 shadow-xl">
            <div className="flex items-center gap-2 mb-3">
              <span
                className="w-4 h-4 rounded-full"
                style={{ backgroundColor: typeColors[selectedNode.type] || typeColors.Entity }}
              />
              <h3 className="font-medium text-slate-100">{selectedNode.label}</h3>
              <span className="text-xs text-slate-400 ml-auto">{selectedNode.type}</span>
            </div>
            {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
              <div className="space-y-1 text-sm">
                {Object.entries(selectedNode.properties)
                  .filter(([key]) => !['id', 'name', 'label'].includes(key))
                  .slice(0, 5)
                  .map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-slate-500">{key}:</span>
                      <span className="text-slate-300 truncate ml-2 max-w-[150px]">
                        {String(value)}
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default PatientDetailsModal;
