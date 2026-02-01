import React from 'react';
import { FileText, Loader2, CheckCircle, XCircle, Clock, X } from 'lucide-react';
import { formatElapsedTime } from '../../utils/formatTime';

export interface JobData {
  job_id: string;
  filename: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  message?: string;
  progress?: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

interface JobCardProps {
  job: JobData;
  onCancel?: (jobId: string) => void;
  compact?: boolean;
}

export function JobCard({ job, onCancel, compact = false }: JobCardProps) {
  const statusConfig = {
    queued: {
      icon: <Clock className="w-4 h-4" />,
      color: 'text-slate-400',
      bgColor: 'bg-slate-900/50',
      borderColor: 'border-slate-600',
      label: 'Queued',
    },
    processing: {
      icon: <Loader2 className="w-4 h-4 animate-spin" />,
      color: 'text-blue-400',
      bgColor: 'bg-blue-900/20',
      borderColor: 'border-blue-600',
      label: 'Processing',
    },
    completed: {
      icon: <CheckCircle className="w-4 h-4" />,
      color: 'text-green-400',
      bgColor: 'bg-green-900/20',
      borderColor: 'border-green-600',
      label: 'Completed',
    },
    failed: {
      icon: <XCircle className="w-4 h-4" />,
      color: 'text-red-400',
      bgColor: 'bg-red-900/20',
      borderColor: 'border-red-600',
      label: 'Failed',
    },
  };

  const config = statusConfig[job.status];
  const progress = job.progress ?? (job.status === 'completed' ? 100 : job.status === 'processing' ? 50 : 0);

  if (compact) {
    return (
      <div className={`flex items-center gap-3 p-2 rounded-lg ${config.bgColor}`}>
        <div className={config.color}>{config.icon}</div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 truncate">{job.filename}</p>
        </div>
        {job.status === 'processing' && (
          <span className="text-xs text-slate-400">{progress}%</span>
        )}
      </div>
    );
  }

  return (
    <div className={`rounded-lg border-l-4 ${config.borderColor} ${config.bgColor} p-4`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <div className={`p-2 rounded-lg bg-slate-800 ${config.color}`}>
            <FileText className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <p className="font-medium text-slate-200 truncate">{job.filename}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className={`flex items-center gap-1 text-xs ${config.color}`}>
                {config.icon}
                {config.label}
              </span>
              {job.started_at && job.status === 'processing' && (
                <span className="text-xs text-slate-500">
                  {formatElapsedTime(job.started_at)}
                </span>
              )}
            </div>
            {job.message && (
              <p className="text-xs text-slate-400 mt-2">{job.message}</p>
            )}
            {job.error && (
              <p className="text-xs text-red-400 mt-2">{job.error}</p>
            )}
          </div>
        </div>

        {onCancel && job.status === 'processing' && (
          <button
            onClick={() => onCancel(job.job_id)}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
            title="Cancel job"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Progress bar */}
      {(job.status === 'processing' || job.status === 'queued') && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>Progress</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                job.status === 'processing'
                  ? 'bg-blue-500'
                  : 'bg-slate-600'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
