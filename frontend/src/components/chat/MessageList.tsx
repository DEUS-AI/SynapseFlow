import React, { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage, MessageFeedback } from '../../types/chat';
import { FeedbackButtons } from './FeedbackButtons';
import { Avatar, TypingIndicator } from './Avatar';
import { formatRelativeTime } from '../../utils/formatTime';

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
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4">
      <div className="max-w-4xl mx-auto space-y-6">
        {messages.map((message, index) => (
          <div
            key={message.id || index}
            className={`flex items-start gap-3 ${
              message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
            }`}
          >
            {/* Avatar */}
            <Avatar role={message.role} />

            {/* Message bubble */}
            <div
              className={`max-w-[75%] shadow-lg ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white rounded-2xl rounded-br-sm'
                  : 'bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-sm'
              }`}
            >
              {/* Message content */}
              <div className="px-4 py-3">
                {message.role === 'user' ? (
                  <p className="whitespace-pre-wrap text-sm sm:text-base">{message.content}</p>
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

                {/* Timestamp */}
                <div className={`text-xs mt-2 ${
                  message.role === 'user' ? 'text-blue-200' : 'text-slate-500'
                }`}>
                  {formatRelativeTime(message.timestamp)}
                </div>
              </div>

              {/* Metadata for assistant messages */}
              {message.role === 'assistant' && (
                <div className="px-4 pb-3 pt-2 border-t border-slate-700/50 space-y-2">
                  {/* Confidence */}
                  {message.confidence !== undefined && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-400">Confidence:</span>
                      <div className="flex-1 flex items-center gap-2">
                        <div className="flex-1 max-w-[120px] bg-slate-700 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full transition-all duration-300 ${
                              message.confidence >= 0.8
                                ? 'bg-green-500'
                                : message.confidence >= 0.6
                                ? 'bg-blue-500'
                                : 'bg-orange-500'
                            }`}
                            style={{ width: `${message.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-300 font-medium">
                          {(message.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Sources */}
                  {message.sources && message.sources.length > 0 && (
                    <div className="flex items-start gap-2">
                      <span className="text-xs text-slate-400 flex-shrink-0">Sources:</span>
                      <div className="flex flex-wrap gap-1">
                        {message.sources.map((source, i) => (
                          <span
                            key={i}
                            className="text-xs text-blue-300 bg-blue-900/30 px-1.5 py-0.5 rounded"
                          >
                            {source.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Related concepts */}
                  {message.related_concepts && message.related_concepts.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {message.related_concepts.map((concept, i) => (
                        <span
                          key={i}
                          className="px-2 py-1 bg-purple-900/40 text-purple-300 rounded-full text-xs border border-purple-800/50"
                        >
                          {concept}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Feedback buttons */}
                  <div className="pt-1">
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
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Thinking indicator */}
        {isThinking && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
