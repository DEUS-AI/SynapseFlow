import React from 'react';
import { Loader2, CheckCircle, XCircle, ListTodo, ChevronDown, ChevronUp } from 'lucide-react';
import { JobCard, type JobData } from './JobCard';

interface JobQueuePanelProps {
  jobs: JobData[];
  expanded?: boolean;
  onToggleExpand?: () => void;
  onCancelJob?: (jobId: string) => void;
  maxVisible?: number;
}

export function JobQueuePanel({
  jobs,
  expanded = false,
  onToggleExpand,
  onCancelJob,
  maxVisible = 3,
}: JobQueuePanelProps) {
  if (jobs.length === 0) {
    return null;
  }

  const processingJobs = jobs.filter((j) => j.status === 'processing');
  const queuedJobs = jobs.filter((j) => j.status === 'queued');
  const completedJobs = jobs.filter((j) => j.status === 'completed');
  const failedJobs = jobs.filter((j) => j.status === 'failed');

  const visibleJobs = expanded ? jobs : jobs.slice(0, maxVisible);
  const hiddenCount = jobs.length - maxVisible;

  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 border-b border-slate-700 cursor-pointer hover:bg-slate-800/80 transition-colors"
        onClick={onToggleExpand}
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-900/50 text-blue-400">
            <ListTodo className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-medium text-slate-200">Processing Queue</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {jobs.length} job{jobs.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Status summary */}
          <div className="flex items-center gap-3 text-xs">
            {processingJobs.length > 0 && (
              <span className="flex items-center gap-1 text-blue-400">
                <Loader2 className="w-3 h-3 animate-spin" />
                {processingJobs.length}
              </span>
            )}
            {queuedJobs.length > 0 && (
              <span className="flex items-center gap-1 text-slate-400">
                <ListTodo className="w-3 h-3" />
                {queuedJobs.length}
              </span>
            )}
            {completedJobs.length > 0 && (
              <span className="flex items-center gap-1 text-green-400">
                <CheckCircle className="w-3 h-3" />
                {completedJobs.length}
              </span>
            )}
            {failedJobs.length > 0 && (
              <span className="flex items-center gap-1 text-red-400">
                <XCircle className="w-3 h-3" />
                {failedJobs.length}
              </span>
            )}
          </div>

          {/* Expand/collapse button */}
          {jobs.length > maxVisible && (
            <button className="p-1 text-slate-400 hover:text-slate-200">
              {expanded ? (
                <ChevronUp className="w-5 h-5" />
              ) : (
                <ChevronDown className="w-5 h-5" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Job list */}
      <div className="p-4 space-y-3">
        {visibleJobs.map((job) => (
          <JobCard
            key={job.job_id}
            job={job}
            onCancel={onCancelJob}
          />
        ))}

        {/* Show more indicator */}
        {!expanded && hiddenCount > 0 && (
          <button
            onClick={onToggleExpand}
            className="w-full py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
          >
            + {hiddenCount} more job{hiddenCount !== 1 ? 's' : ''}
          </button>
        )}
      </div>
    </div>
  );
}

// Compact inline version for header/sidebar
interface JobQueueBadgeProps {
  jobs: JobData[];
  onClick?: () => void;
}

export function JobQueueBadge({ jobs, onClick }: JobQueueBadgeProps) {
  const processingCount = jobs.filter((j) => j.status === 'processing').length;
  const queuedCount = jobs.filter((j) => j.status === 'queued').length;
  const activeCount = processingCount + queuedCount;

  if (activeCount === 0) return null;

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-1.5 bg-blue-900/50 hover:bg-blue-900/70 rounded-lg transition-colors"
    >
      <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
      <span className="text-sm text-blue-300">
        {activeCount} job{activeCount !== 1 ? 's' : ''} running
      </span>
    </button>
  );
}
