import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { PatientContextSidebar } from './PatientContextSidebar';
import { SafetyWarning } from './SafetyWarning';
import { SessionList } from './SessionList';
import { MessageHistory } from './MessageHistory';
import type { ChatMessage, WebSocketChatMessage, MessageFeedback } from '../../types/chat';
import { Menu, X, Wifi, WifiOff } from 'lucide-react';

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
  const [sessionListKey, setSessionListKey] = useState(0);
  // Memory refresh state for real-time updates
  const [memoryRefreshTrigger, setMemoryRefreshTrigger] = useState(0);
  const [isProcessingMemory, setIsProcessingMemory] = useState(false);
  const lastUserQuery = useRef<string>('');
  const messageCounter = useRef(0);

  // Auto-load latest session on mount
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
          console.log('No existing session, creating new one');
          await createNewSession();
        }
      } catch (err) {
        console.error('Error auto-loading session:', err);
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
      setMessages([]);
      setLoadingHistory(false);
    } catch (err) {
      console.error('Error creating session:', err);
    }
  };

  // Handle session selection
  const handleSessionSelect = async (sessionId: string) => {
    console.log('Switching to session:', sessionId);
    setCurrentSessionId(sessionId);
    setMessages([]);
    setLoadingHistory(true);
    // Close sidebar on mobile after selection
    if (window.innerWidth < 768) {
      setShowSessionList(false);
    }
  };

  // Handle messages loaded from history
  const handleMessagesLoaded = (loadedMessages: ChatMessage[]) => {
    console.log('Loaded', loadedMessages.length, 'messages from history');
    setMessages(loadedMessages);
    setLoadingHistory(false);
    messageCounter.current = loadedMessages.length;
  };

  // WebSocket URL
  const wsURL = currentSessionId && typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/chat/${patientId}/${currentSessionId}`
    : '';

  const { isConnected, sendMessage, connectionError } = useWebSocket(wsURL, {
    onMessage: (data: WebSocketChatMessage) => {
      if (data.type === 'status') {
        const thinking = data.status === 'thinking';
        setIsThinking(thinking);
        // Show memory processing indicator when thinking starts
        if (thinking) {
          setIsProcessingMemory(true);
        }
      } else if (data.type === 'message' && data.role === 'assistant') {
        messageCounter.current += 1;
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
            // Phase 6: Enhanced metadata from Crystallization Pipeline
            medical_alerts: data.medical_alerts,
            routing: data.routing,
            temporal_context: data.temporal_context,
            entities: data.entities,
          },
        ]);

        // Check for safety warnings from reasoning trail (legacy)
        const warnings = data.reasoning_trail?.filter(
          (trail) =>
            trail.toLowerCase().includes('contraindication') ||
            trail.toLowerCase().includes('warning') ||
            trail.toLowerCase().includes('allerg')
        ) || [];

        // Also check for critical/high medical alerts
        const criticalAlerts = data.medical_alerts?.filter(
          (alert) => alert.severity === 'CRITICAL' || alert.severity === 'HIGH'
        ) || [];

        if (warnings.length > 0 || criticalAlerts.length > 0) {
          const alertMessages = criticalAlerts.map(a => `${a.severity}: ${a.message}`);
          setSafetyWarnings([...warnings, ...alertMessages]);
        }

        setIsThinking(false);
        // Stop processing indicator and trigger memory refresh
        setIsProcessingMemory(false);
        setMemoryRefreshTrigger((prev) => prev + 1);
      } else if (data.type === 'title_updated') {
        console.log('Session title updated:', data.title);
        setSessionListKey((prev) => prev + 1);
      }
    },
  });

  const handleSendMessage = (content: string) => {
    if (!currentSessionId) {
      console.error('No active session');
      return;
    }

    lastUserQuery.current = content;
    messageCounter.current += 1;

    setMessages((prev) => [
      ...prev,
      {
        id: `${currentSessionId}-${messageCounter.current}-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date(),
      },
    ]);

    sendMessage({ message: content });
  };

  const handleFeedbackSubmit = (messageId: string, feedback: MessageFeedback) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId ? { ...msg, feedback } : msg
      )
    );
  };

  return (
    <div className="flex h-full bg-slate-900 relative">
      {/* Mobile overlay backdrop */}
      {showSessionList && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setShowSessionList(false)}
        />
      )}

      {/* Session List Sidebar */}
      <div
        className={`
          fixed inset-y-0 left-0 z-30 w-80 transform transition-transform duration-300 ease-in-out
          md:relative md:transform-none md:z-0
          ${showSessionList ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:hidden'}
        `}
      >
        {showSessionList && (
          <div className="h-full relative">
            {/* Close button for mobile */}
            <button
              onClick={() => setShowSessionList(false)}
              className="absolute top-4 right-4 p-2 bg-slate-700 hover:bg-slate-600 rounded-lg z-10 md:hidden"
            >
              <X className="w-5 h-5 text-slate-300" />
            </button>
            <SessionList
              key={sessionListKey}
              patientId={patientId}
              currentSessionId={currentSessionId || undefined}
              onSessionSelect={handleSessionSelect}
              onNewSession={createNewSession}
            />
          </div>
        )}
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="bg-slate-800 border-b border-slate-700 px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowSessionList(!showSessionList)}
                className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
                title={showSessionList ? 'Hide sessions' : 'Show sessions'}
              >
                <Menu className="w-5 h-5 text-slate-400" />
              </button>
              <h1 className="text-lg sm:text-2xl font-semibold text-slate-100">
                Medical Assistant
              </h1>
            </div>
            <div className="flex items-center gap-2">
              {isConnected ? (
                <Wifi className="w-4 h-4 text-green-500" />
              ) : (
                <WifiOff className="w-4 h-4 text-red-500" />
              )}
              <span className="text-xs sm:text-sm text-slate-400 hidden sm:inline">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>

        {/* Connection error banner */}
        {connectionError && (
          <div className="bg-yellow-900/50 border-l-4 border-yellow-500 px-4 sm:px-6 py-3 sm:py-4">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-yellow-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div className="min-w-0">
                  <h3 className="font-semibold text-yellow-300 text-sm sm:text-base">Backend Connection Issue</h3>
                  <p className="text-xs sm:text-sm text-yellow-200 mt-1">{connectionError}</p>
                  <p className="text-xs text-yellow-200 mt-2 hidden sm:block">
                    Make sure the backend is running: <code className="bg-slate-800 px-2 py-0.5 rounded text-yellow-300">uv run uvicorn src.application.api.main:app --reload --port 8000</code>
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

        {/* Message list */}
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

      {/* Patient context sidebar - hidden on mobile and tablet */}
      <div className="hidden lg:block flex-shrink-0">
        <PatientContextSidebar
          patientId={patientId}
          memoryRefreshTrigger={memoryRefreshTrigger}
          isProcessingMemory={isProcessingMemory}
        />
      </div>
    </div>
  );
}
