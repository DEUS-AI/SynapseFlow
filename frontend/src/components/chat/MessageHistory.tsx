/**
 * MessageHistory Component - Load and display messages from a previous session
 *
 * Fetches message history from the API and displays it using the existing MessageList component.
 * Supports pagination for long conversations.
 */

import React, { useState, useEffect } from 'react';
import { MessageList } from './MessageList';
import type { ChatMessage } from '../../types/chat';
import { Loader2 } from 'lucide-react';

interface MessageHistoryProps {
  sessionId: string;
  onMessagesLoaded?: (messages: ChatMessage[]) => void;
}

interface APIMessage {
  id: string;
  session_id: string;
  role: string;
  content: string;
  timestamp: string;
  patient_id?: string;
  confidence?: number;
  sources?: Array<{ type: string; name: string; snippet?: string }>;
  reasoning_trail?: string[];
  related_concepts?: string[];
  response_id?: string;
  query_time?: number;
  intent?: string;
  urgency?: string;
}

export function MessageHistory({
  sessionId,
  onMessagesLoaded,
}: MessageHistoryProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    if (sessionId) {
      loadMessages();
    }
  }, [sessionId]);

  const loadMessages = async (offset: number = 0) => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `/api/chat/sessions/${sessionId}/messages?limit=100&offset=${offset}`
      );

      if (!response.ok) {
        throw new Error('Failed to load message history');
      }

      const data = await response.json();

      // Convert API messages to ChatMessage format
      const chatMessages: ChatMessage[] = data.messages.map((msg: APIMessage) => ({
        id: msg.response_id || msg.id,  // Prefer response_id for feedback tracking
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
        timestamp: new Date(msg.timestamp),
        confidence: msg.confidence,
        sources: msg.sources || [],
        reasoning_trail: msg.reasoning_trail || [],
        related_concepts: msg.related_concepts || [],
      }));

      setMessages(chatMessages);
      setHasMore(data.has_more || false);

      // Notify parent component
      if (onMessagesLoaded) {
        onMessagesLoaded(chatMessages);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load messages');
      console.error('Error loading message history:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-2" />
          <p className="text-sm text-slate-400">Loading conversation history...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <p className="text-sm text-red-400 mb-2">{error}</p>
          <button
            onClick={() => loadMessages()}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <MessageList
      messages={messages}
      isThinking={false}
      onFeedbackSubmit={() => {
        // Feedback for historical messages - optional
      }}
    />
  );
}
