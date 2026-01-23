import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  reconnect?: boolean;
  reconnectInterval?: number;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const {
    reconnect = true,
    reconnectInterval = 3000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const maxReconnectAttempts = 10;

  // Use refs for callbacks to avoid recreating the connection on callback changes
  const onMessageRef = useRef(options.onMessage);
  const onErrorRef = useRef(options.onError);

  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = options.onMessage;
  }, [options.onMessage]);

  useEffect(() => {
    onErrorRef.current = options.onError;
  }, [options.onError]);

  useEffect(() => {
    // Only run in browser
    if (typeof window === 'undefined' || !url) {
      return;
    }

    let isMounted = true;

    const connect = () => {
      // Stop trying after max attempts
      if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
        console.error('Max reconnection attempts reached. Backend may not be running.');
        setConnectionError('Unable to connect to backend. Please ensure the backend is running on port 8000.');
        return;
      }

      // Don't connect if already connected
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        return;
      }

      try {
        console.log('WebSocket connecting to:', url);
        const ws = new WebSocket(url);

        ws.onopen = () => {
          if (!isMounted) return;
          console.log('WebSocket connected');
          setIsConnected(true);
          setConnectionError(null);
          reconnectAttemptsRef.current = 0;
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          const message = JSON.parse(event.data) as WebSocketMessage;
          setLastMessage(message);
          onMessageRef.current?.(message);
        };

        ws.onerror = (error) => {
          if (!isMounted) return;
          console.error('WebSocket error:', error);
          setConnectionError('Connection error. Retrying...');
          onErrorRef.current?.(error);
        };

        ws.onclose = (event) => {
          if (!isMounted) return;
          console.log('WebSocket disconnected', event.code, event.reason);
          setIsConnected(false);

          // Only reconnect if not intentionally closed and still mounted
          if (reconnect && event.code !== 1000 && reconnectAttemptsRef.current < maxReconnectAttempts) {
            reconnectAttemptsRef.current += 1;
            reconnectTimeoutRef.current = setTimeout(() => {
              console.log(`Reconnection attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts}...`);
              connect();
            }, reconnectInterval);
          }
        };

        wsRef.current = ws;
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        setConnectionError('Failed to create WebSocket connection');

        if (reconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
        }
      }
    };

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting'); // Clean close
      }
    };
  }, [url, reconnect, reconnectInterval]); // Only reconnect when URL changes

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    connectionError,
  };
}
