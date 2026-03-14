import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiUrl } from '../lib/api';

interface User {
  patient_id: string;
  display_name?: string;
  email?: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  sessionToken: string | null;
  login: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  sessionToken: null,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionToken, setSessionToken] = useState<string | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem('session_token');
    setSessionToken(null);
    setUser(null);
    window.location.href = '/';
  }, []);

  const verify = useCallback(async (token: string) => {
    try {
      const res = await fetch(apiUrl('/api/auth/verify'), {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!res.ok) {
        localStorage.removeItem('session_token');
        setSessionToken(null);
        setUser(null);
        return;
      }
      const data = await res.json();
      setUser(data);
      setSessionToken(token);
    } catch {
      localStorage.removeItem('session_token');
      setSessionToken(null);
      setUser(null);
    }
  }, []);

  const login = useCallback(async (token: string) => {
    localStorage.setItem('session_token', token);
    setSessionToken(token);
    await verify(token);
  }, [verify]);

  useEffect(() => {
    const token = localStorage.getItem('session_token');
    if (token) {
      verify(token).finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [verify]);

  return (
    <AuthContext.Provider value={{
      user,
      isLoading,
      isAuthenticated: !!user,
      sessionToken,
      login,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
