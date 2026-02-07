import React, { useState, useEffect } from 'react';
import { Clock, Brain, ChevronDown } from 'lucide-react';

interface PatientMemory {
  id: string;
  memory: string;
  created_at: string;
  metadata?: {
    type?: string;
    session_id?: string;
    [key: string]: any;
  };
}

interface PatientMemoriesPanelProps {
  patientId: string;
  maxVisible?: number;
}

function formatRelativeTime(dateString: string): string {
  if (!dateString) return '';

  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;

    return date.toLocaleDateString();
  } catch {
    return '';
  }
}

function getMemoryTypeColor(type?: string): string {
  switch (type?.toLowerCase()) {
    case 'symptom':
      return 'bg-orange-900/50 text-orange-400';
    case 'medication':
      return 'bg-green-900/50 text-green-400';
    case 'diagnosis':
      return 'bg-blue-900/50 text-blue-400';
    case 'allergy':
      return 'bg-red-900/50 text-red-400';
    default:
      return 'bg-slate-700 text-slate-400';
  }
}

export function PatientMemoriesPanel({ patientId, maxVisible = 3 }: PatientMemoriesPanelProps) {
  const [memories, setMemories] = useState<PatientMemory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    async function fetchMemories() {
      if (!patientId) return;

      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/patients/${encodeURIComponent(patientId)}/memories?limit=20`
        );

        if (!response.ok) {
          throw new Error('Failed to fetch memories');
        }

        const data = await response.json();
        setMemories(data.memories || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    fetchMemories();
  }, [patientId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <div className="animate-pulse text-slate-400 text-sm">Loading memories...</div>
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

  if (memories.length === 0) {
    return (
      <div className="text-slate-500 text-sm py-2 text-center">
        No memories stored yet
      </div>
    );
  }

  const visibleMemories = showAll ? memories : memories.slice(0, maxVisible);
  const hiddenCount = memories.length - maxVisible;

  return (
    <div className="space-y-2">
      {visibleMemories.map((memory, index) => (
        <div
          key={memory.id || index}
          className="bg-slate-900/50 rounded-lg p-2.5 border border-slate-700/50"
        >
          <p className="text-slate-300 text-sm leading-relaxed">
            "{memory.memory}"
          </p>
          <div className="flex items-center gap-2 mt-2 text-xs">
            <span className="flex items-center gap-1 text-slate-500">
              <Clock className="w-3 h-3" />
              {formatRelativeTime(memory.created_at)}
            </span>
            {memory.metadata?.type && (
              <span className={`px-1.5 py-0.5 rounded ${getMemoryTypeColor(memory.metadata.type)}`}>
                {memory.metadata.type}
              </span>
            )}
          </div>
        </div>
      ))}

      {!showAll && hiddenCount > 0 && (
        <button
          onClick={() => setShowAll(true)}
          className="w-full flex items-center justify-center gap-1 py-2 text-sm text-slate-400 hover:text-slate-300 transition-colors"
        >
          <ChevronDown className="w-4 h-4" />
          Show {hiddenCount} more
        </button>
      )}

      {showAll && memories.length > maxVisible && (
        <button
          onClick={() => setShowAll(false)}
          className="w-full flex items-center justify-center gap-1 py-2 text-sm text-slate-400 hover:text-slate-300 transition-colors"
        >
          Show less
        </button>
      )}
    </div>
  );
}

export default PatientMemoriesPanel;
