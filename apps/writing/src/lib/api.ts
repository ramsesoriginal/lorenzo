import { createLorenzoClient } from '@lorenzo/api-client';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';

export { fetchAllPages, LorenzoApiError, unwrap } from '@lorenzo/api-client';
export const client = createLorenzoClient({
  baseUrl: API_BASE_URL,
  getAccessToken,
  fetch: (input) => fetch(input, { cache: 'no-store' }),
});
const files = new Set<string>();
export async function loadFile(payload: { url: string }) {
  const url = new URL(payload.url, API_BASE_URL);
  if (url.origin !== new URL(API_BASE_URL).origin)
    throw new Error('This picture is not available.');
  const response = await fetch(url, {
    cache: 'no-store',
    headers: { Authorization: `Bearer ${await getAccessToken()}` },
  });
  if (!response.ok) throw new Error('This picture is not available.');
  const local = URL.createObjectURL(await response.blob());
  files.add(local);
  return local;
}
function clear() {
  for (const url of files) URL.revokeObjectURL(url);
  files.clear();
  document.querySelector('[data-page]')?.replaceChildren();
}
window.addEventListener('lorenzo:sign-out', clear);
window.addEventListener('pagehide', clear);
window.addEventListener('pageshow', (event) => {
  if (event.persisted) location.reload();
});
