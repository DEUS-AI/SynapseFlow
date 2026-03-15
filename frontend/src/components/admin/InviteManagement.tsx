import React, { useState, useEffect, useCallback } from 'react';
import { apiUrl } from '../../lib/api';
import { Plus, Copy, Trash2, Check, AlertCircle, Loader2, RefreshCw, UserPlus } from 'lucide-react';

interface Invite {
  token: string;
  patient_id: string;
  email: string | null;
  label: string | null;
  status: 'pending' | 'redeemed' | 'revoked';
  created_at: string;
  redeemed_at: string | null;
  redeemed_by: string | null;
}

export function InviteManagement() {
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  // Form state
  const [patientId, setPatientId] = useState('');
  const [email, setEmail] = useState('');
  const [label, setLabel] = useState('');

  const fetchInvites = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(apiUrl('/api/admin/invites'));
      if (!res.ok) throw new Error('Failed to fetch invites');
      const data = await res.json();
      setInvites(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load invites');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchInvites(); }, [fetchInvites]);

  const createInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId.trim()) return;

    setCreating(true);
    try {
      const res = await fetch(apiUrl('/api/admin/invites'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: patientId.trim(),
          email: email.trim() || null,
          label: label.trim() || null,
        }),
      });
      if (!res.ok) throw new Error('Failed to create invite');
      setPatientId('');
      setEmail('');
      setLabel('');
      await fetchInvites();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create invite');
    } finally {
      setCreating(false);
    }
  };

  const revokeInvite = async (token: string) => {
    if (!confirm('Revoke this invite? The user will be logged out.')) return;
    try {
      const res = await fetch(apiUrl(`/api/admin/invites/${token}`), { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to revoke invite');
      await fetchInvites();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke invite');
    }
  };

  const copyInviteUrl = async (token: string) => {
    const url = `${window.location.origin}/invite/${token}`;
    await navigator.clipboard.writeText(url);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-500/20 text-yellow-400',
      redeemed: 'bg-green-500/20 text-green-400',
      revoked: 'bg-red-500/20 text-red-400',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-slate-600 text-slate-300'}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-100 flex items-center gap-2">
          <UserPlus className="w-5 h-5" />
          Invite Management
        </h2>
        <button
          onClick={fetchInvites}
          className="p-2 text-slate-400 hover:text-slate-200 transition"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Create invite form */}
      <form onSubmit={createInvite} className="bg-slate-800 rounded-lg border border-slate-700 p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Create New Invite</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            type="text"
            placeholder="Patient ID (required)"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            className="bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            required
          />
          <input
            type="email"
            placeholder="Email (optional)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
          />
          <input
            type="text"
            placeholder="Label (optional)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={creating || !patientId.trim()}
          className="mt-3 flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 text-white text-sm rounded transition"
        >
          {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          Create Invite
        </button>
      </form>

      {/* Invite list */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-900/50">
            <tr className="text-slate-400 text-left">
              <th className="px-4 py-3 font-medium">Patient ID</th>
              <th className="px-4 py-3 font-medium">Email / Label</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {invites.map((invite) => (
              <tr key={invite.token} className="text-slate-300 hover:bg-slate-700/30">
                <td className="px-4 py-3 font-mono text-xs">{invite.patient_id}</td>
                <td className="px-4 py-3">
                  <div>{invite.email || '-'}</div>
                  {invite.label && <div className="text-xs text-slate-500">{invite.label}</div>}
                </td>
                <td className="px-4 py-3">
                  {statusBadge(invite.status)}
                  {invite.redeemed_by && (
                    <div className="text-xs text-slate-500 mt-1">by {invite.redeemed_by}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {invite.created_at ? new Date(invite.created_at).toLocaleDateString() : '-'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => copyInviteUrl(invite.token)}
                      className="p-1.5 text-slate-400 hover:text-blue-400 transition"
                      title="Copy invite URL"
                    >
                      {copiedToken === invite.token ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                    {invite.status !== 'revoked' && (
                      <button
                        onClick={() => revokeInvite(invite.token)}
                        className="p-1.5 text-slate-400 hover:text-red-400 transition"
                        title="Revoke invite"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {invites.length === 0 && !loading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No invites yet. Create one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
