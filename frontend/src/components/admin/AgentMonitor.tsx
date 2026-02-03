import React, { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { CheckCircle, XCircle, Clock } from 'lucide-react';

interface Agent {
  id: string;
  name: string;
  status: 'running' | 'stopped' | 'error';
  port: number;
  uptime: number;
  tasks_completed: number;
}

export function AgentMonitor() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAgents = () => {
      fetch('/api/admin/agents')
        .then(res => res.json())
        .then(data => {
          setAgents(data);
          setLoading(false);
        })
        .catch(err => {
          console.error('Failed to load agents:', err);
          setLoading(false);
        });
    };

    fetchAgents();

    // Poll every 5 seconds
    const interval = setInterval(fetchAgents, 5000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">Agent Status</h2>
        <p className="text-gray-600">Loading agents...</p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <h2 className="text-xl font-semibold mb-4">Agent Status</h2>

      <div className="space-y-3">
        {agents.length === 0 ? (
          <p className="text-gray-600">No agents running</p>
        ) : (
          agents.map(agent => (
            <div key={agent.id} className="flex items-center justify-between p-3 bg-gray-50 rounded">
              <div className="flex items-center gap-3">
                {agent.status === 'running' ? (
                  <CheckCircle className="h-5 w-5 text-green-600" />
                ) : agent.status === 'stopped' ? (
                  <Clock className="h-5 w-5 text-gray-400" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-600" />
                )}

                <div>
                  <p className="font-medium">{agent.name}</p>
                  <p className="text-sm text-gray-600">Port {agent.port}</p>
                </div>
              </div>

              <div className="text-right">
                <p className="text-sm font-medium">{agent.tasks_completed} tasks</p>
                <p className="text-xs text-gray-600">
                  Uptime: {formatUptime(agent.uptime)}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}
