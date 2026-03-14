import React, { useEffect, useState } from 'react';
import { apiUrl } from '../../lib/api';
import { Loader2, AlertCircle, CheckCircle } from 'lucide-react';

export function InviteRedeem() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    async function redeem() {
      // Extract token from URL: /invite/{token}
      const segments = window.location.pathname.split('/');
      const token = segments[segments.length - 1];
      if (!token) {
        setErrorMessage('No invite token found in URL');
        setStatus('error');
        return;
      }

      try {
        const res = await fetch(apiUrl(`/api/auth/redeem/${token}`), {
          method: 'POST',
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setErrorMessage(data.detail || 'Invalid or expired invite link');
          setStatus('error');
          return;
        }

        const data = await res.json();
        localStorage.setItem('session_token', data.session_token);
        setStatus('success');

        // Brief pause to show success, then redirect
        setTimeout(() => {
          window.location.href = '/chat';
        }, 1000);
      } catch {
        setErrorMessage('Failed to connect to the server');
        setStatus('error');
      }
    }

    redeem();
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="max-w-md mx-auto px-6 text-center">
        {status === 'loading' && (
          <div>
            <Loader2 className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
            <p className="text-slate-300">Setting up your access...</p>
          </div>
        )}

        {status === 'success' && (
          <div>
            <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-slate-100 mb-2">Welcome!</h2>
            <p className="text-slate-400">Redirecting to chat...</p>
          </div>
        )}

        {status === 'error' && (
          <div>
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-slate-100 mb-2">Invalid Invite</h2>
            <p className="text-slate-400 mb-6">{errorMessage}</p>
            <a
              href="/"
              className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded transition"
            >
              Back to Home
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
