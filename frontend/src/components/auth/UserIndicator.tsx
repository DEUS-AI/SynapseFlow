import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { LogOut, User } from 'lucide-react';

export function UserIndicator() {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <div className="flex items-center gap-3 text-sm">
      <div className="flex items-center gap-2 text-slate-400">
        <User className="w-4 h-4" />
        <span>{user.display_name || user.email || user.patient_id}</span>
      </div>
      <button
        onClick={logout}
        className="flex items-center gap-1 px-2 py-1 text-slate-500 hover:text-red-400 transition"
        title="Logout"
      >
        <LogOut className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
