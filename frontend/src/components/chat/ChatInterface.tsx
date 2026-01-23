import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { PatientContextSidebar } from './PatientContextSidebar';
import { SafetyWarning } from './SafetyWarning';
import type { ChatMessage, WebSocketChatMessage } from '../../types/chat';

interface ChatInterfaceProps {
  patientId: string;
  sessionId: string;
}

export function ChatInterface({ patientId, sessionId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [safetyWarnings, setSafetyWarnings] = useState<string[]>([]);

  // Construct WebSocket URL - check if window exists (client-side only)
  const wsURL = typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/chat/${patientId}/${sessionId}`
    : ''; // Empty string for SSR, will be set on client

  const { isConnected, sendMessage, connectionError } = useWebSocket(wsURL, {
    onMessage: (data: WebSocketChatMessage) => {
      if (data.type === 'status') {
        setIsThinking(data.status === 'thinking');
      } else if (data.type === 'message' && data.role === 'assistant') {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.content!,
            timestamp: new Date(),
            confidence: data.confidence,
            sources: data.sources,
            reasoning_trail: data.reasoning_trail,
            related_concepts: data.related_concepts,
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
      }
    },
  });

  const handleSendMessage = (content: string) => {
    // Add user message to UI
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content,
        timestamp: new Date(),
      },
    ]);

    // Send via WebSocket
    sendMessage({ message: content });
  };

  return (
    <div className="flex h-full bg-gray-50">
      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-semibold">Medical Assistant</h1>
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm text-gray-600">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>

        {/* Connection error banner */}
        {connectionError && (
          <div className="bg-yellow-50 border-l-4 border-yellow-600 px-6 py-4">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-yellow-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div>
                  <h3 className="font-semibold text-yellow-800">Backend Connection Issue</h3>
                  <p className="text-sm text-yellow-700 mt-1">{connectionError}</p>
                  <p className="text-sm text-yellow-700 mt-2">
                    Make sure the backend is running: <code className="bg-yellow-100 px-2 py-0.5 rounded text-xs">uv run uvicorn src.application.api.main:app --reload --port 8000</code>
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
        <MessageList messages={messages} isThinking={isThinking} />

        {/* Input */}
        <MessageInput onSend={handleSendMessage} disabled={!isConnected} />
      </div>

      {/* Patient context sidebar */}
      <PatientContextSidebar patientId={patientId} />
    </div>
  );
}
