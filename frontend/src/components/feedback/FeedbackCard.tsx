import React, { useState } from 'react';
import { ChevronDown, ChevronUp, MessageSquare, ThumbsUp, ThumbsDown, Clock } from 'lucide-react';
import { ReviewActions, type ReviewStatus } from './ReviewActions';
import { RatingVisualization } from './RatingVisualization';
import { CorrectionDiffView } from './CorrectionDiffView';
import { formatRelativeTime } from '../../utils/formatTime';

export interface FeedbackData {
  id: string;
  type: 'preference' | 'correction' | 'rating' | 'thumbs';
  query?: string;
  response?: string;
  originalResponse?: string;
  correctedResponse?: string;
  chosenResponse?: string;
  rejectedResponse?: string;
  rating?: number;
  thumbs?: 'up' | 'down';
  ratingGap?: number;
  timestamp?: string;
  status?: ReviewStatus;
  source?: string;
}

interface FeedbackCardProps {
  data: FeedbackData;
  onStatusChange?: (id: string, status: ReviewStatus) => void;
  showActions?: boolean;
}

export function FeedbackCard({ data, onStatusChange, showActions = true }: FeedbackCardProps) {
  const [expanded, setExpanded] = useState(false);

  const statusColors: Record<ReviewStatus, string> = {
    pending: 'border-l-slate-500',
    approved: 'border-l-green-500',
    rejected: 'border-l-red-500',
    flagged: 'border-l-yellow-500',
  };

  const typeIcons: Record<string, React.ReactNode> = {
    preference: <ThumbsUp className="w-4 h-4" />,
    correction: <MessageSquare className="w-4 h-4" />,
    rating: <ThumbsUp className="w-4 h-4" />,
    thumbs: data.thumbs === 'up' ? <ThumbsUp className="w-4 h-4" /> : <ThumbsDown className="w-4 h-4" />,
  };

  const typeLabels: Record<string, string> = {
    preference: 'Preference Pair',
    correction: 'Correction',
    rating: 'Rating',
    thumbs: data.thumbs === 'up' ? 'Positive' : 'Negative',
  };

  const handleStatusChange = (status: ReviewStatus) => {
    onStatusChange?.(data.id, status);
  };

  return (
    <div
      className={`bg-slate-800 rounded-lg border-l-4 ${statusColors[data.status || 'pending']} overflow-hidden transition-all duration-200`}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-750"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${
            data.type === 'correction' ? 'bg-blue-900/50 text-blue-400' :
            data.type === 'preference' ? 'bg-purple-900/50 text-purple-400' :
            data.thumbs === 'up' ? 'bg-green-900/50 text-green-400' :
            'bg-red-900/50 text-red-400'
          }`}>
            {typeIcons[data.type]}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-200">{typeLabels[data.type]}</span>
              {data.status && data.status !== 'pending' && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  data.status === 'approved' ? 'bg-green-900/50 text-green-400' :
                  data.status === 'rejected' ? 'bg-red-900/50 text-red-400' :
                  'bg-yellow-900/50 text-yellow-400'
                }`}>
                  {data.status.charAt(0).toUpperCase() + data.status.slice(1)}
                </span>
              )}
            </div>
            {data.query && (
              <p className="text-sm text-slate-400 mt-1 line-clamp-1">
                {data.query}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4">
          {data.rating !== undefined && (
            <RatingVisualization rating={data.rating} size="sm" />
          )}
          {data.ratingGap !== undefined && (
            <span className="text-xs text-slate-400">
              Gap: {data.ratingGap.toFixed(1)}
            </span>
          )}
          {data.timestamp && (
            <div className="flex items-center gap-1 text-xs text-slate-500">
              <Clock className="w-3 h-3" />
              {formatRelativeTime(data.timestamp)}
            </div>
          )}
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-slate-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-slate-400" />
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-700">
          {/* Query */}
          {data.query && (
            <div className="mt-4">
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">Query</label>
              <p className="mt-1 text-sm text-slate-200 bg-slate-900/50 p-3 rounded-lg">
                {data.query}
              </p>
            </div>
          )}

          {/* Content based on type */}
          {data.type === 'correction' && data.originalResponse && data.correctedResponse && (
            <div className="mt-4">
              <CorrectionDiffView
                original={data.originalResponse}
                corrected={data.correctedResponse}
              />
            </div>
          )}

          {data.type === 'preference' && (
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-green-400 uppercase tracking-wide flex items-center gap-1">
                  <ThumbsUp className="w-3 h-3" /> Chosen
                </label>
                <p className="mt-1 text-sm text-slate-200 bg-green-900/20 border border-green-800/50 p-3 rounded-lg max-h-40 overflow-y-auto">
                  {data.chosenResponse}
                </p>
              </div>
              <div>
                <label className="text-xs font-medium text-red-400 uppercase tracking-wide flex items-center gap-1">
                  <ThumbsDown className="w-3 h-3" /> Rejected
                </label>
                <p className="mt-1 text-sm text-slate-200 bg-red-900/20 border border-red-800/50 p-3 rounded-lg max-h-40 overflow-y-auto">
                  {data.rejectedResponse}
                </p>
              </div>
            </div>
          )}

          {(data.type === 'rating' || data.type === 'thumbs') && data.response && (
            <div className="mt-4">
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">Response</label>
              <p className="mt-1 text-sm text-slate-200 bg-slate-900/50 p-3 rounded-lg max-h-40 overflow-y-auto">
                {data.response}
              </p>
              {data.rating !== undefined && (
                <div className="mt-3">
                  <RatingVisualization rating={data.rating} size="lg" showLabel />
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          {showActions && (
            <div className="mt-4 pt-4 border-t border-slate-700">
              <ReviewActions
                currentStatus={data.status || 'pending'}
                onStatusChange={handleStatusChange}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
