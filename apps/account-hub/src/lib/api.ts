import { createLorenzoClient } from '@lorenzo/api-client';
import { getAccessToken } from './auth';
import { clearCache } from './cache';
import { API_BASE_URL } from './config';

export { unwrap } from '@lorenzo/api-client';
export const client = createLorenzoClient({ baseUrl: API_BASE_URL, getAccessToken });

// A write that went through may have changed anything a page has read, so what is held is dropped
// (lib/cache.ts) and the next read asks again.
client.use({
  onResponse({ request, response }) {
    if (request.method !== 'GET' && request.method !== 'HEAD' && response.ok) clearCache();
  },
});

// OpenAPI represents binary files as strings. The serializer sends the actual
// File as multipart data; the browser supplies its Content-Type boundary.
export function pictureUpload(file: File) {
  return {
    body: { file: file.name },
    bodySerializer: () => {
      const data = new FormData();
      data.append('file', file);
      return data;
    },
  };
}
