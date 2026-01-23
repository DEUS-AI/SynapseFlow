import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { Activity, Database, Clock, Users } from 'lucide-react';
import { Card } from '../ui/card';

interface SystemMetrics {
  total_queries: number;
  avg_response_time: number;
  active_sessions: number;
  total_patients: number;
  neo4j_nodes: number;
  neo4j_relationships: number;
  redis_memory_usage: string;
}

export function SystemStats() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  const { lastMessage } = useWebSocket('ws://localhost:8000/ws/admin/monitor', {
    onMessage: (data) => {
      if (data.type === 'metrics_update') {
        setMetrics(data.metrics);
      }
    },
  });

  useEffect(() => {
    // Initial fetch
    fetch('/api/admin/metrics')
      .then(res => res.json())
      .then(data => {
        setMetrics(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load metrics:', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <Card className="p-6">
        <p className="text-gray-600">Loading metrics...</p>
      </Card>
    );
  }

  if (!metrics) {
    return (
      <Card className="p-6">
        <p className="text-red-600">Failed to load metrics</p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <h2 className="text-xl font-semibold mb-4">System Metrics</h2>

      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          icon={<Activity className="h-5 w-5 text-blue-600" />}
          label="Total Queries"
          value={metrics.total_queries.toLocaleString()}
        />

        <MetricCard
          icon={<Clock className="h-5 w-5 text-green-600" />}
          label="Avg Response Time"
          value={`${metrics.avg_response_time.toFixed(2)}s`}
        />

        <MetricCard
          icon={<Users className="h-5 w-5 text-orange-600" />}
          label="Active Sessions"
          value={metrics.active_sessions.toLocaleString()}
        />

        <MetricCard
          icon={<Database className="h-5 w-5 text-purple-600" />}
          label="Total Patients"
          value={metrics.total_patients.toLocaleString()}
        />
      </div>

      <div className="mt-6 pt-6 border-t">
        <h3 className="text-sm font-semibold text-gray-600 mb-3">Neo4j Graph</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-600">Nodes</p>
            <p className="text-2xl font-bold">{metrics.neo4j_nodes.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Relationships</p>
            <p className="text-2xl font-bold">{metrics.neo4j_relationships.toLocaleString()}</p>
          </div>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t">
        <h3 className="text-sm font-semibold text-gray-600 mb-2">Redis Cache</h3>
        <p className="text-lg font-medium">{metrics.redis_memory_usage}</p>
      </div>
    </Card>
  );
}

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
}

function MetricCard({ icon, label, value }: MetricCardProps) {
  return (
    <div className="flex items-center gap-3">
      <div className="p-2 bg-gray-50 rounded">{icon}</div>
      <div>
        <p className="text-sm text-gray-600">{label}</p>
        <p className="text-xl font-semibold">{value}</p>
      </div>
    </div>
  );
}
