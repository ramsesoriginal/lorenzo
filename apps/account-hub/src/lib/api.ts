import { ApiError } from './apiError';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';

export { ApiError } from './apiError';

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
  // 204 (e.g. PUT/DELETE /me/picture) has no body - response.json() would
  // throw on the empty string. Callers expecting no content type this as
  // apiFetch<void>(...) and get undefined back.
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

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'PATCH',
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

export async function apiDelete<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'DELETE' });
}

// No Content-Type header here, deliberately - the browser sets
// multipart/form-data with the correct boundary itself; overriding it
// breaks the boundary the server needs to parse the body.
export async function apiUpload<T>(path: string, field: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append(field, file);
  return apiFetch<T>(path, { method: 'PUT', body: formData });
}
