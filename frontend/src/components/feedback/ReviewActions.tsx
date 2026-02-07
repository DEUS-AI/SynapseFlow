import React from 'react';
import { Check, X, Flag, RotateCcw } from 'lucide-react';

export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'flagged';

interface ReviewActionsProps {
  currentStatus: ReviewStatus;
  onStatusChange: (status: ReviewStatus) => void;
  disabled?: boolean;
  size?: 'sm' | 'md';
}

export function ReviewActions({
  currentStatus,
  onStatusChange,
  disabled = false,
  size = 'md',
}: ReviewActionsProps) {
  const sizeClasses = {
    sm: 'px-2 py-1 text-xs gap-1',
    md: 'px-3 py-1.5 text-sm gap-1.5',
  };

  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-4 h-4';

  const buttons: { status: ReviewStatus; icon: React.ReactNode; label: string; activeClass: string; hoverClass: string }[] = [
    {
      status: 'approved',
      icon: <Check className={iconSize} />,
      label: 'Approve',
      activeClass: 'bg-green-600 text-white border-green-600',
      hoverClass: 'hover:bg-green-900/50 hover:text-green-400 hover:border-green-700',
    },
    {
      status: 'rejected',
      icon: <X className={iconSize} />,
      label: 'Reject',
      activeClass: 'bg-red-600 text-white border-red-600',
      hoverClass: 'hover:bg-red-900/50 hover:text-red-400 hover:border-red-700',
    },
    {
      status: 'flagged',
      icon: <Flag className={iconSize} />,
      label: 'Flag',
      activeClass: 'bg-yellow-600 text-white border-yellow-600',
      hoverClass: 'hover:bg-yellow-900/50 hover:text-yellow-400 hover:border-yellow-700',
    },
  ];

  return (
    <div className="flex items-center gap-2">
      {buttons.map((btn) => (
        <button
          key={btn.status}
          onClick={() => onStatusChange(btn.status === currentStatus ? 'pending' : btn.status)}
          disabled={disabled}
          className={`
            flex items-center ${sizeClasses[size]} rounded-lg border transition-colors
            ${currentStatus === btn.status
              ? btn.activeClass
              : `border-slate-600 text-slate-400 ${btn.hoverClass}`
            }
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
          title={currentStatus === btn.status ? `Remove ${btn.label.toLowerCase()}` : btn.label}
        >
          {btn.icon}
          <span>{btn.label}</span>
        </button>
      ))}

      {currentStatus !== 'pending' && (
        <button
          onClick={() => onStatusChange('pending')}
          disabled={disabled}
          className={`
            flex items-center ${sizeClasses[size]} rounded-lg border border-slate-600 text-slate-400
            hover:bg-slate-700 hover:text-slate-200 transition-colors
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
          title="Reset to pending"
        >
          <RotateCcw className={iconSize} />
          <span>Reset</span>
        </button>
      )}
    </div>
  );
}

// Quick action buttons for inline use
interface QuickActionsProps {
  onApprove: () => void;
  onReject: () => void;
  disabled?: boolean;
}

export function QuickActions({ onApprove, onReject, disabled = false }: QuickActionsProps) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={onApprove}
        disabled={disabled}
        className="p-1.5 rounded-lg text-slate-400 hover:bg-green-900/50 hover:text-green-400 transition-colors disabled:opacity-50"
        title="Approve"
      >
        <Check className="w-4 h-4" />
      </button>
      <button
        onClick={onReject}
        disabled={disabled}
        className="p-1.5 rounded-lg text-slate-400 hover:bg-red-900/50 hover:text-red-400 transition-colors disabled:opacity-50"
        title="Reject"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
