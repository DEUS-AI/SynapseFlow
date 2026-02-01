import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { GraphData, GraphNode, GraphEdge } from '../../types/graph';
import { GraphControls } from './GraphControls';
import { EntityDetailsPanel } from './EntityDetailsPanel';

type LayerType = 'all' | 'perception' | 'semantic' | 'reasoning' | 'application';

// Extended types for D3 simulation
interface SimNode extends GraphNode {
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimEdge extends GraphEdge {
  source: SimNode | string;
  target: SimNode | string;
}

interface KnowledgeGraphViewerProps {
  initialData?: GraphData;
  documentFilter?: string;
  hideControls?: boolean;
}

export function KnowledgeGraphViewer({ initialData, documentFilter, hideControls = false }: KnowledgeGraphViewerProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(initialData || null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [layout, setLayout] = useState<'force' | 'hierarchical'>('force');
  const [loading, setLoading] = useState(false);
  const [selectedLayer, setSelectedLayer] = useState<LayerType>('all');

  // Load graph data from API - fetches dynamically based on selected layer and document filter
  useEffect(() => {
    if (initialData && selectedLayer === 'all' && !documentFilter) {
      // Use initial data only for 'all' layer if provided and no document filter
      setGraphData(initialData);
      return;
    }

    setLoading(true);

    // Determine the endpoint based on whether we have a document filter
    let url: string;
    if (documentFilter) {
      // Use document-specific endpoint
      url = `/api/admin/documents/${encodeURIComponent(documentFilter)}/graph?limit=300`;
    } else {
      // Use general graph endpoint
      const params = new URLSearchParams({ limit: '300' });
      if (selectedLayer !== 'all') {
        params.set('layer', selectedLayer.toLowerCase());
      }
      url = `/api/graph/data?${params}`;
    }

    fetch(url)
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        return res.json();
      })
      .then(data => {
        // Validate data structure
        if (data && Array.isArray(data.nodes) && Array.isArray(data.edges)) {
          setGraphData(data);
        } else {
          console.warn('Invalid graph data structure:', data);
          setGraphData({ nodes: [], edges: [] });
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load graph data:', err);
        setGraphData({ nodes: [], edges: [] }); // Set empty data on error
        setLoading(false);
      });
  }, [initialData, selectedLayer, documentFilter]);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);

    // Always clear previous content first - ensures old graph
    // is removed even when switching to a layer with no data
    svg.selectAll('*').remove();

    // Exit early if no data to render
    if (!graphData?.nodes?.length) return;

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Create container group for zoom/pan
    const g = svg.append('g');

    // Setup zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom as any);

    // Layer colors
    const layerColors: Record<string, string> = {
      perception: '#3b82f6',    // blue
      semantic: '#10b981',      // green
      reasoning: '#f59e0b',     // orange
      application: '#8b5cf6',   // purple
    };

    // Create a copy of nodes for D3
    const nodes: SimNode[] = graphData.nodes.map((n) => ({ ...n }));

    // Create a set of valid node IDs for fast lookup
    const nodeIds = new Set(nodes.map((n) => n.id));

    // Filter edges to only include those where both source and target nodes exist
    // This prevents D3 force simulation errors when layer filtering removes nodes
    const edges: SimEdge[] = graphData.edges
      .filter((e) => {
        const sourceId = typeof e.source === 'string' ? e.source : e.source?.id;
        const targetId = typeof e.target === 'string' ? e.target : e.target?.id;
        return nodeIds.has(sourceId) && nodeIds.has(targetId);
      })
      .map((e) => ({ ...e }));

    // Force simulation
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(edges)
        .id((d: any) => d.id)
        .distance(100)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    // Draw edges
    const link = g.append('g')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', '#6b7280')
      .attr('stroke-opacity', 0.7)
      .attr('stroke-width', 2);

    // Draw edge labels
    const linkLabels = g.append('g')
      .selectAll('text')
      .data(edges)
      .join('text')
      .attr('font-size', '10px')
      .attr('fill', '#9ca3af')
      .attr('text-anchor', 'middle')
      .text((d: SimEdge) => d.label || d.type || '');

    // Draw nodes
    const node = g.append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', 20)
      .attr('fill', (d: SimNode) => layerColors[d.layer?.toLowerCase() ?? ''] || '#999')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('click', (event: MouseEvent, d: SimNode) => {
        event.stopPropagation();
        setSelectedNode(d);
      })
      .call(d3.drag<SVGCircleElement, SimNode>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended) as any
      );

    // Draw node labels
    const nodeLabels = g.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 35)
      .attr('font-size', '12px')
      .attr('font-weight', 'bold')
      .attr('fill', '#e5e7eb')
      .attr('pointer-events', 'none')
      .text((d: SimNode) => {
        const label = d.label || d.id || 'Unknown';
        return label.substring(0, 20) + (label.length > 20 ? '...' : '');
      });

    // Simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      linkLabels
        .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
        .attr('y', (d: any) => (d.source.y + d.target.y) / 2);

      node
        .attr('cx', (d: any) => d.x)
        .attr('cy', (d: any) => d.y);

      nodeLabels
        .attr('x', (d: any) => d.x)
        .attr('y', (d: any) => d.y);
    });

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: any) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    // Click on background to deselect
    svg.on('click', () => {
      setSelectedNode(null);
    });

    return () => {
      simulation.stop();
    };
  }, [graphData, layout]);

  // Render loading overlay content
  const renderContent = () => {
    if (loading) {
      return (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 z-20">
          <div className="text-center">
            <div className="animate-spin h-12 w-12 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            <p className="text-gray-300">Loading knowledge graph...</p>
          </div>
        </div>
      );
    }

    if (!graphData?.nodes?.length) {
      return (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <div className="text-center text-gray-400">
            <svg className="h-16 w-16 mx-auto mb-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            <p>No graph data available for this layer</p>
            <p className="text-sm mt-2 text-gray-500">Try selecting a different layer or loading more data</p>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="flex h-full bg-slate-900">
      <div className="flex-1 relative">
        {!hideControls && (
          <GraphControls
            onLayoutChange={setLayout}
            onLayerChange={setSelectedLayer}
            selectedLayer={selectedLayer}
            onReset={() => {
              // Reset zoom
              const svg = d3.select(svgRef.current);
              svg.transition().duration(750).call(
                (d3.zoom() as any).transform,
                d3.zoomIdentity
              );
            }}
            nodeCount={graphData?.nodes?.length ?? 0}
            edgeCount={graphData?.edges?.length ?? 0}
          />
        )}
        {hideControls && graphData?.nodes?.length !== undefined && (
          <div className="absolute top-4 right-4 z-10 bg-slate-800/90 px-3 py-1.5 rounded-lg text-sm text-slate-300">
            {graphData.nodes.length} nodes, {graphData.edges?.length ?? 0} edges
          </div>
        )}
        {renderContent()}
        <svg
          ref={svgRef}
          className="w-full h-full"
        />
      </div>

      {selectedNode && (
        <EntityDetailsPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
