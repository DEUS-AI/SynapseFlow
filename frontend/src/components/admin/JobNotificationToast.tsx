import React, { useEffect, useState } from 'react';
import { CheckCircle, XCircle, X, FileText, Loader2 } from 'lucide-react';

export interface JobNotification {
  id: string;
  type: 'started' | 'completed' | 'failed';
  filename: string;
  message?: string;
  timestamp: Date;
}

interface JobNotificationToastProps {
  notification: JobNotification;
  onDismiss: (id: string) => void;
  autoDismissMs?: number;
}

export function JobNotificationToast({
  notification,
  onDismiss,
  autoDismissMs = 5000,
}: JobNotificationToastProps) {
  const [isLeaving, setIsLeaving] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsLeaving(true);
      setTimeout(() => onDismiss(notification.id), 300);
    }, autoDismissMs);

    return () => clearTimeout(timer);
  }, [notification.id, autoDismissMs, onDismiss]);

  const handleDismiss = () => {
    setIsLeaving(true);
    setTimeout(() => onDismiss(notification.id), 300);
  };

  const config = {
    started: {
      icon: <Loader2 className="w-5 h-5 animate-spin" />,
      color: 'text-blue-400',
      bgColor: 'bg-blue-900/90',
      borderColor: 'border-blue-600',
      title: 'Processing Started',
    },
    completed: {
      icon: <CheckCircle className="w-5 h-5" />,
      color: 'text-green-400',
      bgColor: 'bg-green-900/90',
      borderColor: 'border-green-600',
      title: 'Processing Complete',
    },
    failed: {
      icon: <XCircle className="w-5 h-5" />,
      color: 'text-red-400',
      bgColor: 'bg-red-900/90',
      borderColor: 'border-red-600',
      title: 'Processing Failed',
    },
  };

  const { icon, color, bgColor, borderColor, title } = config[notification.type];

  return (
    <div
      className={`
        ${bgColor} ${borderColor} border rounded-lg shadow-xl p-4 min-w-[320px] max-w-md
        transform transition-all duration-300
        ${isLeaving ? 'translate-x-full opacity-0' : 'translate-x-0 opacity-100'}
      `}
    >
      <div className="flex items-start gap-3">
        <div className={color}>{icon}</div>
        <div className="flex-1 min-w-0">
          <p className={`font-medium ${color}`}>{title}</p>
          <div className="flex items-center gap-2 mt-1">
            <FileText className="w-4 h-4 text-slate-400" />
            <span className="text-sm text-slate-200 truncate">{notification.filename}</span>
          </div>
          {notification.message && (
            <p className="text-xs text-slate-400 mt-1">{notification.message}</p>
          )}
        </div>
        <button
          onClick={handleDismiss}
          className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// Toast container for multiple notifications
interface ToastContainerProps {
  notifications: JobNotification[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ notifications, onDismiss }: ToastContainerProps) {
  if (notifications.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {notifications.map((notification) => (
        <JobNotificationToast
          key={notification.id}
          notification={notification}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  );
}

// Hook for managing toast notifications
export function useJobNotifications() {
  const [notifications, setNotifications] = useState<JobNotification[]>([]);

  const addNotification = (notification: Omit<JobNotification, 'id' | 'timestamp'>) => {
    const newNotification: JobNotification = {
      ...notification,
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
    };
    setNotifications((prev) => [...prev, newNotification]);
  };

  const dismissNotification = (id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  const notifyJobStarted = (filename: string, message?: string) => {
    addNotification({ type: 'started', filename, message });
  };

  const notifyJobCompleted = (filename: string, message?: string) => {
    addNotification({ type: 'completed', filename, message });
  };

  const notifyJobFailed = (filename: string, message?: string) => {
    addNotification({ type: 'failed', filename, message });
  };

  return {
    notifications,
    dismissNotification,
    notifyJobStarted,
    notifyJobCompleted,
    notifyJobFailed,
    ToastContainer: () => (
      <ToastContainer notifications={notifications} onDismiss={dismissNotification} />
    ),
  };
}
