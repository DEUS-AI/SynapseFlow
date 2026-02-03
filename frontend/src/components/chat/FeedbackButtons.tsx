import React, { useState } from 'react';
import type { MessageFeedback } from '../../types/chat';

interface FeedbackButtonsProps {
  messageId: string;
  query: string;
  response: string;
  onFeedbackSubmit?: (feedback: MessageFeedback) => void;
  initialFeedback?: MessageFeedback;
}

export function FeedbackButtons({
  messageId,
  query,
  response,
  onFeedbackSubmit,
  initialFeedback,
}: FeedbackButtonsProps) {
  const [feedback, setFeedback] = useState<MessageFeedback>(initialFeedback || {});
  const [showCorrectionModal, setShowCorrectionModal] = useState(false);
  const [correctionText, setCorrectionText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const submitThumbsFeedback = async (thumbs: 'up' | 'down') => {
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/feedback/thumbs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          response_id: messageId,
          query_text: query,
          response_text: response,
          thumbs_up: thumbs === 'up',
        }),
      });

      if (res.ok) {
        const newFeedback = { ...feedback, thumbs, submittedAt: new Date() };
        setFeedback(newFeedback);
        onFeedbackSubmit?.(newFeedback);
        setShowSuccess(true);
        setTimeout(() => setShowSuccess(false), 2000);
      }
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitCorrection = async () => {
    if (!correctionText.trim()) return;

    setIsSubmitting(true);
    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          response_id: messageId,
          query_text: query,
          response_text: response,
          rating: 2, // Low rating for corrections
          feedback_type: 'incorrect',
          correction_text: correctionText,
        }),
      });

      if (res.ok) {
        const newFeedback = {
          ...feedback,
          correctionText,
          rating: 2,
          submittedAt: new Date(),
        };
        setFeedback(newFeedback);
        onFeedbackSubmit?.(newFeedback);
        setShowCorrectionModal(false);
        setCorrectionText('');
        setShowSuccess(true);
        setTimeout(() => setShowSuccess(false), 2000);
      }
    } catch (err) {
      console.error('Failed to submit correction:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex items-center gap-2 mt-2">
        {/* Thumbs up */}
        <button
          onClick={() => submitThumbsFeedback('up')}
          disabled={isSubmitting || feedback.thumbs === 'up'}
          className={`p-1.5 rounded transition-colors ${
            feedback.thumbs === 'up'
              ? 'bg-green-600/30 text-green-400'
              : 'hover:bg-slate-700 text-slate-400 hover:text-green-400'
          } disabled:opacity-50`}
          title="Helpful response"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"
            />
          </svg>
        </button>

        {/* Thumbs down */}
        <button
          onClick={() => submitThumbsFeedback('down')}
          disabled={isSubmitting || feedback.thumbs === 'down'}
          className={`p-1.5 rounded transition-colors ${
            feedback.thumbs === 'down'
              ? 'bg-red-600/30 text-red-400'
              : 'hover:bg-slate-700 text-slate-400 hover:text-red-400'
          } disabled:opacity-50`}
          title="Unhelpful response"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5"
            />
          </svg>
        </button>

        {/* Correction button */}
        <button
          onClick={() => setShowCorrectionModal(true)}
          disabled={isSubmitting}
          className={`p-1.5 rounded transition-colors ${
            feedback.correctionText
              ? 'bg-blue-600/30 text-blue-400'
              : 'hover:bg-slate-700 text-slate-400 hover:text-blue-400'
          } disabled:opacity-50`}
          title="Suggest correction"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            />
          </svg>
        </button>

        {/* Success indicator */}
        {showSuccess && (
          <span className="text-xs text-green-400 ml-2">Feedback submitted!</span>
        )}
      </div>

      {/* Correction Modal */}
      {showCorrectionModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-6 max-w-lg w-full mx-4 border border-slate-700">
            <h3 className="text-lg font-semibold text-slate-100 mb-4">
              Suggest a Correction
            </h3>

            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-2">
                Original Response:
              </label>
              <div className="bg-slate-900 rounded p-3 text-sm text-slate-300 max-h-32 overflow-y-auto">
                {response.substring(0, 300)}
                {response.length > 300 && '...'}
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-2">
                Your Correction:
              </label>
              <textarea
                value={correctionText}
                onChange={(e) => setCorrectionText(e.target.value)}
                placeholder="What would be a better response?"
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-slate-200 placeholder-slate-500 resize-none h-32 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowCorrectionModal(false)}
                className="px-4 py-2 text-slate-400 hover:text-slate-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={submitCorrection}
                disabled={isSubmitting || !correctionText.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isSubmitting ? 'Submitting...' : 'Submit Correction'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
