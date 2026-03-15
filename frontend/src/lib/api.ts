export const API_BASE_URL = import.meta.env.PUBLIC_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

/** Prefix a path with the API base URL. Usage: fetch(apiUrl('/api/foo')) */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

/** Get the current session token from localStorage */
export function getSessionToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('session_token');
}

/** Get auth headers for API requests */
export function getAuthHeaders(): Record<string, string> {
  const token = getSessionToken();
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/** fetch() wrapper that automatically adds the Authorization header */
export async function fetchWithAuth(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = { ...getAuthHeaders(), ...(init.headers as Record<string, string> ?? {}) };
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) {
    handleUnauthorized();
  }
  return response;
}

/** Handle 401 responses by clearing session and redirecting */
function handleUnauthorized() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('session_token');
    window.location.href = '/';
  }
}

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private buildURL(path: string, params?: Record<string, string>): string {
    // When baseURL is empty (same-origin), use path directly
    const fullPath = this.baseURL ? new URL(path, this.baseURL).toString() : path;
    if (params) {
      const url = new URL(fullPath, window.location.origin);
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });
      return this.baseURL ? url.toString() : url.pathname + url.search;
    }
    return fullPath;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 401) {
      handleUnauthorized();
      throw new Error('Unauthorized');
    }
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }
    return response.json();
  }

  async get<T>(path: string, options?: FetchOptions): Promise<T> {
    const url = this.buildURL(path, options?.params);
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
        ...options?.headers,
      },
      ...options,
    });
    return this.handleResponse<T>(response);
  }

  async post<T>(path: string, data?: unknown, options?: FetchOptions): Promise<T> {
    const url = this.buildURL(path, options?.params);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
      ...options,
    });
    return this.handleResponse<T>(response);
  }

  async delete<T>(path: string, options?: FetchOptions): Promise<T> {
    const url = this.buildURL(path, options?.params);
    const response = await fetch(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
        ...options?.headers,
      },
      ...options,
    });
    return this.handleResponse<T>(response);
  }
}

export const apiClient = new APIClient(API_BASE_URL);



