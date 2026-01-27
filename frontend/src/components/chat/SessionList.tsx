/**
 * SessionList Component - Display and manage chat sessions
 *
 * Shows patient's chat sessions grouped by time (today, yesterday, etc.)
 * with support for selecting, searching, and creating new sessions.
 */

import React, { useState, useEffect } from 'react';
import { MessageSquare, Plus, Search, Clock, AlertCircle } from 'lucide-react';

interface Session {
  session_id: string;
  patient_id: string;
  title: string;
  started_at: string;
  last_activity: string;
  message_count: number;
  status: string;
  preview_text?: string;
  primary_intent?: string;
  urgency?: string;
  topics?: string[];
  unresolved_symptoms?: string[];
}

interface SessionGroup {
  today: Session[];
  yesterday: Session[];
  this_week: Session[];
  this_month: Session[];
  older: Session[];
}

interface SessionListProps {
  patientId: string;
  currentSessionId?: string;
  onSessionSelect: (sessionId: string) => void;
  onNewSession: () => void;
}

export function SessionList({
  patientId,
  currentSessionId,
  onSessionSelect,
  onNewSession,
}: SessionListProps) {
  const [sessions, setSessions] = useState<SessionGroup>({
    today: [],
    yesterday: [],
    this_week: [],
    this_month: [],
    older: [],
  });
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, [patientId]);

  const loadSessions = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `/api/chat/sessions?patient_id=${patientId}&limit=50`
      );

      if (!response.ok) {
        throw new Error('Failed to load sessions');
      }

      const data = await response.json();

      // Sessions are already grouped in the API response
      if (data.grouped) {
        setSessions(data.grouped);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sessions');
      console.error('Error loading sessions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadSessions();
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(
        `/api/chat/sessions/search?patient_id=${patientId}&query=${encodeURIComponent(searchQuery)}`
      );

      if (!response.ok) {
        throw new Error('Search failed');
      }

      const data = await response.json();

      // Put all results in "Search Results" group
      setSessions({
        today: data.sessions,
        yesterday: [],
        this_week: [],
        this_month: [],
        older: [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const getUrgencyBadge = (urgency: string) => {
    if (urgency === 'critical' || urgency === 'high') {
      return (
        <span className="text-xs px-2 py-0.5 rounded bg-red-900/50 text-red-300 border border-red-700">
          {urgency}
        </span>
      );
    }
    return null;
  };

  const renderSession = (session: Session) => {
    const isActive = session.session_id === currentSessionId;
    const hasUnresolvedSymptoms = session.unresolved_symptoms && session.unresolved_symptoms.length > 0;

    return (
      <button
        key={session.session_id}
        onClick={() => onSessionSelect(session.session_id)}
        className={`
          w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-colors
          ${
            isActive
              ? 'bg-blue-900/50 border border-blue-700'
              : 'hover:bg-slate-700/50 border border-transparent'
          }
        `}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <MessageSquare className="w-4 h-4 text-slate-400 flex-shrink-0" />
              <h4 className="text-sm font-medium text-slate-200 truncate">
                {session.title || 'New Conversation'}
              </h4>
            </div>

            {session.preview_text && (
              <p className="text-xs text-slate-400 line-clamp-1 ml-6">
                {session.preview_text}
              </p>
            )}

            <div className="flex items-center gap-2 mt-1.5 ml-6">
              <Clock className="w-3 h-3 text-slate-500" />
              <span className="text-xs text-slate-500">
                {new Date(session.last_activity).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>

              <span className="text-xs text-slate-600">•</span>
              <span className="text-xs text-slate-500">
                {session.message_count} {session.message_count === 1 ? 'message' : 'messages'}
              </span>

              {session.urgency && getUrgencyBadge(session.urgency)}
            </div>

            {hasUnresolvedSymptoms && (
              <div className="flex items-center gap-1.5 mt-1.5 ml-6">
                <AlertCircle className="w-3 h-3 text-amber-500" />
                <span className="text-xs text-amber-400">
                  Unresolved: {session.unresolved_symptoms!.join(', ')}
                </span>
              </div>
            )}
          </div>
        </div>
      </button>
    );
  };

  const renderGroup = (title: string, sessions: Session[]) => {
    if (sessions.length === 0) return null;

    return (
      <div className="mb-4">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-3 mb-2">
          {title}
        </h3>
        <div className="space-y-0.5">
          {sessions.map(renderSession)}
        </div>
      </div>
    );
  };

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-sm text-red-400">{error}</p>
        <button
          onClick={loadSessions}
          className="mt-2 text-xs text-blue-400 hover:text-blue-300"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-slate-800 border-r border-slate-700">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <button
          onClick={onNewSession}
          className="w-full px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>

      {/* Search */}
      <div className="p-3 border-b border-slate-700">
        <div className="relative">
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full px-3 py-2 pl-9 bg-slate-700/50 border border-slate-600 rounded-lg text-sm text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
        </div>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto p-3">
        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mx-auto" />
            <p className="text-sm text-slate-400 mt-2">Loading sessions...</p>
          </div>
        ) : (
          <>
            {renderGroup('Today', sessions.today)}
            {renderGroup('Yesterday', sessions.yesterday)}
            {renderGroup('This Week', sessions.this_week)}
            {renderGroup('This Month', sessions.this_month)}
            {renderGroup('Older', sessions.older)}

            {Object.values(sessions).every((group) => group.length === 0) && (
              <div className="text-center py-8">
                <MessageSquare className="w-12 h-12 text-slate-600 mx-auto mb-2" />
                <p className="text-sm text-slate-400">No conversations yet</p>
                <p className="text-xs text-slate-500 mt-1">
                  Start a new chat to begin
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
