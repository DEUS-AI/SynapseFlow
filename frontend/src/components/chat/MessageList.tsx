import React, { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage, MessageFeedback } from '../../types/chat';
import { FeedbackButtons } from './FeedbackButtons';

interface MessageListProps {
  messages: ChatMessage[];
  isThinking: boolean;
  onFeedbackSubmit?: (messageId: string, feedback: MessageFeedback) => void;
}

export function MessageList({ messages, isThinking, onFeedbackSubmit }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4">
      <div className="max-w-4xl mx-auto space-y-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 border border-slate-700'
              }`}
            >
              {message.role === 'user' ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none
                  prose-headings:text-slate-100 prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2
                  prose-h1:text-xl prose-h2:text-lg prose-h3:text-base
                  prose-p:text-slate-200 prose-p:my-2
                  prose-strong:text-slate-100 prose-strong:font-semibold
                  prose-ul:my-2 prose-ul:list-disc prose-ul:pl-5
                  prose-ol:my-2 prose-ol:list-decimal prose-ol:pl-5
                  prose-li:text-slate-200 prose-li:my-1
                  prose-code:bg-slate-700 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-blue-300
                  prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-700 prose-pre:rounded-lg
                  prose-a:text-blue-400 prose-a:underline hover:prose-a:text-blue-300
                ">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              )}

              {/* Metadata for assistant messages */}
              {message.role === 'assistant' && (
                <div className="mt-3 pt-3 border-t border-slate-600 space-y-2">
                  {/* Confidence */}
                  {message.confidence !== undefined && (
                    <div className="text-xs text-slate-400">
                      Confidence: {(message.confidence * 100).toFixed(0)}%
                      <div className="mt-1 w-full bg-slate-700 rounded-full h-1.5">
                        <div
                          className="bg-blue-500 h-1.5 rounded-full"
                          style={{ width: `${message.confidence * 100}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Sources */}
                  {message.sources && message.sources.length > 0 && (
                    <div className="text-xs text-slate-400">
                      <span className="font-semibold text-slate-300">Sources:</span>{' '}
                      {message.sources.map((s) => s.name).join(', ')}
                    </div>
                  )}

                  {/* Related concepts */}
                  {message.related_concepts && message.related_concepts.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {message.related_concepts.map((concept, i) => (
                        <span
                          key={i}
                          className="px-2 py-1 bg-blue-900/50 text-blue-300 rounded text-xs"
                        >
                          {concept}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Feedback buttons */}
                  <FeedbackButtons
                    messageId={message.id || `msg-${index}`}
                    query={message.query || messages[index - 1]?.content || ''}
                    response={message.content}
                    initialFeedback={message.feedback}
                    onFeedbackSubmit={(feedback) => {
                      onFeedbackSubmit?.(message.id || `msg-${index}`, feedback);
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Thinking indicator */}
        {isThinking && (
          <div className="flex justify-start">
            <div className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3">
              <div className="flex items-center gap-2 text-slate-400">
                <div className="animate-spin h-4 w-4 border-2 border-slate-600 border-t-blue-500 rounded-full"></div>
                <span className="text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
