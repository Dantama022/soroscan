/**
 * JWT Token Management Utility
 * 
 * Handles storage, retrieval, and refreshing of access and refresh tokens.
 * Enforces strict typing and avoids usage of 'any'.
 */

export interface Tokens {
  access: string;
  refresh: string;
}

export interface AuthUser {
  id: string;
  email: string;
}

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

/**
 * Retrieves the current access token from local storage.
 */
export const getAccessToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

/**
 * Retrieves the current refresh token from local storage.
 */
export const getRefreshToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

/**
 * Saves tokens to local storage.
 */
export const setTokens = (tokens: Tokens): void => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh);
};

/**
 * Clears all authentication tokens from local storage.
 */
export const clearTokens = (): void => {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

/**
 * Checks if the user is currently logged in based on the presence of an access token.
 */
export const isLoggedIn = (): boolean => {
  return !!getAccessToken();
};

/**
 * Refreshes the access token using the refresh token.
 */
export const refreshAccessToken = async (): Promise<string | null> => {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/token/refresh/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh }),
      }
    );

    if (response.ok) {
      const data: Partial<Tokens> & { access: string } = await response.json();
      const newAccess = data.access;
      const newRefresh = data.refresh || refresh;
      setTokens({ access: newAccess, refresh: newRefresh });
      return newAccess;
    } else {
      // If refresh fails, clear tokens as they are likely invalid/expired
      clearTokens();
    }
  } catch (error) {
    console.error('Failed to refresh access token:', error);
  }
  
  return null;
};

/**
 * Wrapper around native fetch that automatically injects JWT access token,
 * intercepts 401 Unauthorized errors, attempts token refresh via refreshAccessToken(),
 * retries the request with new token, and redirects to /login if refresh fails.
 */
export const authenticatedFetch = async (
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> => {
  const token = getAccessToken();

  const getHeaders = (authToken: string | null): HeadersInit => {
    const headers = new Headers(init.headers || {});
    if (authToken) {
      headers.set('Authorization', `Bearer ${authToken}`);
    }
    return headers;
  };

  let response = await fetch(input, {
    ...init,
    headers: getHeaders(token),
  });

  // If unauthorized, attempt to refresh token and retry
  if (response.status === 401) {
    console.warn('Authentication 401 received. Attempting automatic token refresh...');
    const newToken = await refreshAccessToken();

    if (newToken) {
      // Retry request with fresh access token
      response = await fetch(input, {
        ...init,
        headers: getHeaders(newToken),
      });
    } else {
      // Refresh failed — clear tokens and redirect user to /login
      clearTokens();
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        const currentPath = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `/login?callbackUrl=${currentPath}`;
      }
    }
  }

  return response;
};
