import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { PatientContextSidebar } from './PatientContextSidebar';
import { SafetyWarning } from './SafetyWarning';
import { SessionList } from './SessionList';
import { MessageHistory } from './MessageHistory';
import type { ChatMessage, WebSocketChatMessage, MessageFeedback } from '../../types/chat';

interface ChatInterfaceProps {
  patientId: string;
}

export function ChatInterface({ patientId }: ChatInterfaceProps) {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [safetyWarnings, setSafetyWarnings] = useState<string[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [showSessionList, setShowSessionList] = useState(true);
  const [sessionListKey, setSessionListKey] = useState(0); // For forcing SessionList refresh
  const lastUserQuery = useRef<string>('');
  const messageCounter = useRef(0);

  // Auto-load latest session on mount (auto-resume)
  useEffect(() => {
    async function autoLoadLatestSession() {
      try {
        const response = await fetch(`/api/chat/sessions/latest?patient_id=${patientId}`);
        if (response.ok) {
          const session = await response.json();
          console.log('Auto-resuming latest session:', session.session_id);
          setCurrentSessionId(session.session_id);
          setLoadingHistory(true);
        } else {
          // No existing session, create a new one
          console.log('No existing session, creating new one');
          await createNewSession();
        }
      } catch (err) {
        console.error('Error auto-loading session:', err);
        // Fallback: create new session
        await createNewSession();
      }
    }

    autoLoadLatestSession();
  }, [patientId]);

  // Create new session
  const createNewSession = async () => {
    try {
      const response = await fetch('/api/chat/sessions/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_id: patientId })
      });

      if (!response.ok) {
        throw new Error('Failed to create session');
      }

      const { session_id } = await response.json();
      console.log('Created new session:', session_id);
      setCurrentSessionId(session_id);
      setMessages([]); // Clear messages for new session
      setLoadingHistory(false);
    } catch (err) {
      console.error('Error creating session:', err);
    }
  };

  // Handle session selection from SessionList
  const handleSessionSelect = async (sessionId: string) => {
    console.log('Switching to session:', sessionId);
    setCurrentSessionId(sessionId);
    setMessages([]); // Will be loaded by MessageHistory
    setLoadingHistory(true);
  };

  // Handle messages loaded from history
  const handleMessagesLoaded = (loadedMessages: ChatMessage[]) => {
    console.log('Loaded', loadedMessages.length, 'messages from history');
    setMessages(loadedMessages);
    setLoadingHistory(false);
    messageCounter.current = loadedMessages.length;
  };

  // Construct WebSocket URL - check if window exists (client-side only)
  const wsURL = currentSessionId && typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/chat/${patientId}/${currentSessionId}`
    : ''; // Empty string for SSR or no session

  const { isConnected, sendMessage, connectionError } = useWebSocket(wsURL, {
    onMessage: (data: WebSocketChatMessage) => {
      if (data.type === 'status') {
        setIsThinking(data.status === 'thinking');
      } else if (data.type === 'message' && data.role === 'assistant') {
        messageCounter.current += 1;
        // Use response_id from backend for feedback tracking, fallback to generated ID
        const messageId = data.response_id || `${currentSessionId}-${messageCounter.current}-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          {
            id: messageId,
            role: 'assistant',
            content: data.content!,
            timestamp: new Date(),
            confidence: data.confidence,
            sources: data.sources,
            reasoning_trail: data.reasoning_trail,
            related_concepts: data.related_concepts,
            query: lastUserQuery.current,
          },
        ]);

        // Check for safety warnings in reasoning trail
        const warnings = data.reasoning_trail?.filter(
          (trail) =>
            trail.toLowerCase().includes('contraindication') ||
            trail.toLowerCase().includes('warning') ||
            trail.toLowerCase().includes('allerg')
        ) || [];

        if (warnings.length > 0) {
          setSafetyWarnings(warnings);
        }

        setIsThinking(false);

        // Note: Auto-title is now triggered from backend after 3 messages
        // and sends a 'title_updated' event via WebSocket
      } else if (data.type === 'title_updated') {
        // Session title was auto-generated or updated
        console.log('Session title updated:', data.title);
        // Refresh session list to show new title
        setSessionListKey((prev) => prev + 1);
      }
    },
  });

  const handleSendMessage = (content: string) => {
    if (!currentSessionId) {
      console.error('No active session');
      return;
    }

    // Track the last user query for feedback context
    lastUserQuery.current = content;
    messageCounter.current += 1;

    // Add user message to UI
    setMessages((prev) => [
      ...prev,
      {
        id: `${currentSessionId}-${messageCounter.current}-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date(),
      },
    ]);

    // Send via WebSocket
    sendMessage({ message: content });
  };

  const handleFeedbackSubmit = (messageId: string, feedback: MessageFeedback) => {
    // Update the message with feedback
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId ? { ...msg, feedback } : msg
      )
    );
  };

  return (
    <div className="flex h-full bg-slate-900">
      {/* Session List Sidebar */}
      {showSessionList && (
        <div className="w-80 flex-shrink-0">
          <SessionList
            key={sessionListKey} // Force refresh when title updates
            patientId={patientId}
            currentSessionId={currentSessionId || undefined}
            onSessionSelect={handleSessionSelect}
            onNewSession={createNewSession}
          />
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-slate-800 border-b border-slate-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowSessionList(!showSessionList)}
                className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
                title={showSessionList ? 'Hide sessions' : 'Show sessions'}
              >
                <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <h1 className="text-2xl font-semibold text-slate-100">Medical Assistant</h1>
            </div>
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm text-slate-400">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>

        {/* Connection error banner */}
        {connectionError && (
          <div className="bg-yellow-900/50 border-l-4 border-yellow-500 px-6 py-4">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-yellow-500 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div>
                  <h3 className="font-semibold text-yellow-300">Backend Connection Issue</h3>
                  <p className="text-sm text-yellow-200 mt-1">{connectionError}</p>
                  <p className="text-sm text-yellow-200 mt-2">
                    Make sure the backend is running: <code className="bg-slate-800 px-2 py-0.5 rounded text-xs text-yellow-300">uv run uvicorn src.application.api.main:app --reload --port 8000</code>
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Safety warnings */}
        {safetyWarnings.length > 0 && (
          <SafetyWarning
            warnings={safetyWarnings}
            onDismiss={() => setSafetyWarnings([])}
          />
        )}

        {/* Message list - Load history if switching to existing session */}
        {loadingHistory && currentSessionId ? (
          <MessageHistory
            sessionId={currentSessionId}
            onMessagesLoaded={handleMessagesLoaded}
          />
        ) : (
          <MessageList
            messages={messages}
            isThinking={isThinking}
            onFeedbackSubmit={handleFeedbackSubmit}
          />
        )}

        {/* Input */}
        <MessageInput onSend={handleSendMessage} disabled={!isConnected || !currentSessionId} />
      </div>

      {/* Patient context sidebar */}
      <PatientContextSidebar patientId={patientId} />
    </div>
  );
}
