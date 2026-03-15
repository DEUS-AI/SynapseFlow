import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiUrl, fetchWithAuth } from '../../../lib/api';

interface UsePanelQueryResult<T> {
  data: T | undefined;
  loading: boolean;
  error: string | null;
  secondsAgo: number | null;
  isStale: boolean;
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetchWithAuth(apiUrl(url));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function usePanelQuery<T>(
  key: string,
  url: string,
  intervalMs: number,
): UsePanelQueryResult<T> {
  const { data, isLoading, error, dataUpdatedAt } = useQuery<T, Error>({
    queryKey: [key],
    queryFn: () => fetchJson<T>(url),
    refetchInterval: intervalMs,
    retry: 1,
  });

  const [secondsAgo, setSecondsAgo] = useState<number | null>(null);
  const [isStale, setIsStale] = useState(false);

  useEffect(() => {
    if (!dataUpdatedAt) return;
    const ticker = setInterval(() => {
      const ago = Math.floor((Date.now() - dataUpdatedAt) / 1000);
      setSecondsAgo(ago);
      setIsStale(ago > (intervalMs / 1000) * 2);
    }, 1000);
    return () => clearInterval(ticker);
  }, [dataUpdatedAt, intervalMs]);

  return {
    data,
    loading: isLoading,
    error: error?.message ?? null,
    secondsAgo,
    isStale,
  };
}
