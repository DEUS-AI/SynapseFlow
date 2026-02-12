import React, { useState, useEffect, useCallback } from 'react';
import { Clock, Brain, ChevronDown, Sparkles, RefreshCw } from 'lucide-react';

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
  /** Increment this to trigger a refresh */
  refreshTrigger?: number;
  /** Show processing indicator */
  isProcessing?: boolean;
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

export function PatientMemoriesPanel({
  patientId,
  maxVisible = 3,
  refreshTrigger = 0,
  isProcessing = false,
}: PatientMemoriesPanelProps) {
  const [memories, setMemories] = useState<PatientMemory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [newMemoryCount, setNewMemoryCount] = useState(0);

  const fetchMemories = useCallback(async (isRefresh = false) => {
    if (!patientId) return;

    if (isRefresh) {
      setIsRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const response = await fetch(
        `/api/patients/${encodeURIComponent(patientId)}/memories?limit=20`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch memories');
      }

      const data = await response.json();
      const newMemories = data.memories || [];

      // Track new memories for animation
      if (isRefresh && newMemories.length > memories.length) {
        setNewMemoryCount(newMemories.length - memories.length);
        // Reset animation flag after a delay
        setTimeout(() => setNewMemoryCount(0), 2000);
      }

      setMemories(newMemories);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [patientId, memories.length]);

  // Initial fetch on mount
  useEffect(() => {
    fetchMemories(false);
  }, [patientId]);

  // Refresh when trigger changes (after new messages)
  useEffect(() => {
    if (refreshTrigger > 0) {
      // Small delay to allow backend to process
      const timer = setTimeout(() => fetchMemories(true), 1500);
      return () => clearTimeout(timer);
    }
  }, [refreshTrigger]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <div className="animate-pulse text-slate-400 text-sm">Loading memories...</div>
      </div>
    );
  }

  // On error, show empty state instead of error message to keep sidebar visible
  if (error) {
    return (
      <div className="space-y-2">
        {isProcessing && <ProcessingIndicator />}
        {isRefreshing && <RefreshingIndicator />}
        <div className="text-center py-4">
          <Brain className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-slate-500 text-sm">No memories yet</p>
          <p className="text-slate-600 text-xs mt-1">
            As you chat, I'll learn and remember important details
          </p>
        </div>
      </div>
    );
  }

  // Processing indicator when extracting facts from conversation
  const ProcessingIndicator = () => (
    <div className="flex items-center gap-2 py-2 px-3 bg-purple-900/30 rounded-lg border border-purple-700/50 mb-2 animate-pulse">
      <Sparkles className="w-4 h-4 text-purple-400 animate-spin" />
      <span className="text-purple-300 text-sm">Extracting facts from conversation...</span>
    </div>
  );

  // Refreshing indicator
  const RefreshingIndicator = () => (
    <div className="flex items-center justify-center gap-2 py-2 text-slate-400 text-sm">
      <RefreshCw className="w-3 h-3 animate-spin" />
      <span>Checking for new memories...</span>
    </div>
  );

  // New memories notification
  const NewMemoriesNotification = () => (
    newMemoryCount > 0 ? (
      <div className="flex items-center gap-2 py-1.5 px-3 bg-green-900/30 rounded-lg border border-green-700/50 mb-2 animate-fade-in">
        <Sparkles className="w-3 h-3 text-green-400" />
        <span className="text-green-300 text-xs">
          {newMemoryCount} new {newMemoryCount === 1 ? 'memory' : 'memories'} learned!
        </span>
      </div>
    ) : null
  );

  if (memories.length === 0) {
    return (
      <div className="space-y-2">
        {isProcessing && <ProcessingIndicator />}
        {isRefreshing && <RefreshingIndicator />}
        <div className="text-center py-4">
          <Brain className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-slate-500 text-sm">No memories yet</p>
          <p className="text-slate-600 text-xs mt-1">
            As you chat, I'll learn and remember important details
          </p>
        </div>
      </div>
    );
  }

  const visibleMemories = showAll ? memories : memories.slice(0, maxVisible);
  const hiddenCount = memories.length - maxVisible;

  return (
    <div className="space-y-2">
      {/* Processing/Refreshing indicators */}
      {isProcessing && <ProcessingIndicator />}
      {isRefreshing && <RefreshingIndicator />}
      <NewMemoriesNotification />

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
