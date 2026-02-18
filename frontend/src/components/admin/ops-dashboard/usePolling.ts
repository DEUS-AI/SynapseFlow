import { useState, useEffect, useRef, useCallback } from 'react';

interface UsePollingResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  secondsAgo: number | null;
  isStale: boolean;
}

export function usePolling<T>(
  url: string,
  intervalMs: number,
): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [secondsAgo, setSecondsAgo] = useState<number | null>(null);
  const [isStale, setIsStale] = useState(false);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (mountedRef.current) {
        setData(json);
        setError(null);
        setLastUpdated(new Date());
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to load');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [url]);

  // Data polling
  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const interval = setInterval(fetchData, intervalMs);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchData, intervalMs]);

  // Seconds-ago ticker (updates every second)
  useEffect(() => {
    const ticker = setInterval(() => {
      if (lastUpdated) {
        const ago = Math.floor((Date.now() - lastUpdated.getTime()) / 1000);
        setSecondsAgo(ago);
        setIsStale(ago > (intervalMs / 1000) * 2);
      }
    }, 1000);
    return () => clearInterval(ticker);
  }, [lastUpdated, intervalMs]);

  return { data, loading, error, lastUpdated, secondsAgo, isStale };
}
