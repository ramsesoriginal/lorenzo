import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';
import type { Page } from './types';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    throw new ApiError(401, 'Not logged in.');
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${accessToken}`,
      Accept: 'application/json',
    },
  });
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new ApiError(
      response.status,
      `${response.status} ${response.statusText}${body ? `: ${body}` : ''}`,
    );
  }
  // 204 No Content (e.g. DELETE /items/{id}) has no body to parse.
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function apiDelete<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'DELETE' });
}

// Every list endpoint in this API is paginated (fastapi-pagination's own
// default Params: size defaults to 50, capped at 100 - ADR 0020) - a plain
// apiFetch<Page<T>> silently truncates to whichever page came back, with
// nothing past it ever fetched. Requests the largest allowed page size up
// front, then fetches every remaining page in parallel (page numbers are
// known from the first response's own `pages`) and flattens the result -
// for a caller that just wants "every item," not one page of them.
export async function apiFetchAllPages<T>(path: string): Promise<T[]> {
  const separator = path.includes('?') ? '&' : '?';
  const first = await apiFetch<Page<T>>(`${path}${separator}size=100`);
  if (first.pages <= 1) return first.items;
  const rest = await Promise.all(
    Array.from({ length: first.pages - 1 }, (_, i) =>
      apiFetch<Page<T>>(`${path}${separator}size=100&page=${i + 2}`),
    ),
  );
  return [first.items, ...rest.map((page) => page.items)].flat();
}
