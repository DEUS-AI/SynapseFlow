export interface GraphNode {
  id: string;
  label: string;
  type: 'Entity' | 'Concept' | 'Table' | 'Column' | 'Diagnosis' | 'Medication';
  layer: 'perception' | 'semantic' | 'reasoning' | 'application';
  properties: Record<string, any>;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface GraphEdge {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  label: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphViewState {
  selectedNode: GraphNode | null;
  hoveredNode: GraphNode | null;
  zoomLevel: number;
  layout: 'force' | 'hierarchical';
}
