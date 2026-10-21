import { createLorenzoClient } from '@lorenzo/api-client';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';

export type { Schema } from '@lorenzo/api-client';
export { fetchAllPages, LorenzoApiError, unwrap } from '@lorenzo/api-client';
export const client = createLorenzoClient({ baseUrl: API_BASE_URL, getAccessToken });
const files = new Set<string>();
export async function loadFile(payload: { url: string }) {
  const token = await getAccessToken();
  const response = await fetch(payload.url, {
    cache: 'no-store',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('This file is not available.');
  const url = URL.createObjectURL(await response.blob());
  files.add(url);
  return url;
}
if (typeof window !== 'undefined') {
  const clear = () => {
    for (const url of files) URL.revokeObjectURL(url);
    files.clear();
    document.querySelector('[data-page]')?.replaceChildren();
  };
  window.addEventListener('pagehide', clear);
  window.addEventListener('lorenzo:sign-out', clear);
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) location.reload();
  });
  document.addEventListener('astro:before-swap', clear);
}
