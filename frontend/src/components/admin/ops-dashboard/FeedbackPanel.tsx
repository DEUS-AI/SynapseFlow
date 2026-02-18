import React from 'react';
import { MessageSquare } from 'lucide-react';
import { usePolling } from './usePolling';
import { PanelWrapper } from './PanelWrapper';
import type { FeedbackStats, ScannerStatus } from './types';

export function FeedbackPanel() {
  const feedback = usePolling<FeedbackStats>('/api/feedback/stats', 15000);
  const scanner = usePolling<ScannerStatus>(
    '/api/quality/scanner/status',
    15000,
  );

  const loading = feedback.loading || scanner.loading;
  const error = feedback.error;

  return (
    <PanelWrapper
      title="Feedback / RLHF"
      icon={<MessageSquare className="h-4 w-4 text-green-400" />}
      loading={loading}
      error={error}
      secondsAgo={feedback.secondsAgo}
      isStale={feedback.isStale}
    >
      {feedback.data && (
        <>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <p className="text-xs text-slate-400">Total</p>
              <p className="text-xl font-bold text-slate-100">
                {feedback.data.total_feedbacks.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Avg Rating</p>
              <p className="text-xl font-bold text-slate-100">
                {feedback.data.average_rating.toFixed(1)}
                <span className="text-sm text-slate-500">/5</span>
              </p>
            </div>
          </div>

          {Object.keys(feedback.data.feedback_type_distribution).length > 0 && (
            <div className="space-y-1 mb-4">
              {Object.entries(feedback.data.feedback_type_distribution).map(
                ([type, count]) => {
                  const total = feedback.data!.total_feedbacks || 1;
                  const pct = Math.round((count / total) * 100);
                  return (
                    <div
                      key={type}
                      className="flex items-center justify-between text-xs"
                    >
                      <span className="text-slate-400 capitalize">{type}</span>
                      <span className="text-slate-300">
                        {count} ({pct}%)
                      </span>
                    </div>
                  );
                },
              )}
            </div>
          )}
        </>
      )}

      {scanner.data && (
        <div className="flex items-center gap-2 pt-3 border-t border-slate-700">
          <span
            className={`w-2 h-2 rounded-full ${
              scanner.data.running
                ? 'bg-green-500'
                : scanner.data.enabled
                  ? 'bg-amber-500'
                  : 'bg-slate-500'
            }`}
          />
          <span className="text-xs text-slate-400">
            Scanner:{' '}
            <span
              className={
                scanner.data.running
                  ? 'text-green-400'
                  : scanner.data.enabled
                    ? 'text-amber-400'
                    : 'text-slate-500'
              }
            >
              {scanner.data.running
                ? 'Running'
                : scanner.data.enabled
                  ? 'Idle'
                  : 'Disabled'}
            </span>
          </span>
        </div>
      )}
    </PanelWrapper>
  );
}
