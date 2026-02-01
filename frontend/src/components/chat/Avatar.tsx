import React from 'react';
import { Bot, User } from 'lucide-react';

interface AvatarProps {
  role: 'user' | 'assistant';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'w-6 h-6',
  md: 'w-8 h-8',
  lg: 'w-10 h-10',
};

const iconSizes = {
  sm: 'w-3.5 h-3.5',
  md: 'w-5 h-5',
  lg: 'w-6 h-6',
};

export function Avatar({ role, size = 'md', className = '' }: AvatarProps) {
  if (role === 'assistant') {
    return (
      <div
        className={`${sizeClasses[size]} rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg ${className}`}
      >
        <Bot className={`${iconSizes[size]} text-white`} />
      </div>
    );
  }

  return (
    <div
      className={`${sizeClasses[size]} rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0 ${className}`}
    >
      <User className={`${iconSizes[size]} text-slate-300`} />
    </div>
  );
}

// Typing indicator with avatar
export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <Avatar role="assistant" />
      <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-sm px-4 py-3">
        <div className="flex gap-1.5">
          <span
            className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
            style={{ animationDelay: '0ms', animationDuration: '1s' }}
          />
          <span
            className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
            style={{ animationDelay: '150ms', animationDuration: '1s' }}
          />
          <span
            className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
            style={{ animationDelay: '300ms', animationDuration: '1s' }}
          />
        </div>
      </div>
    </div>
  );
}
