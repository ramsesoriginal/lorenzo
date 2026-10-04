import { createLorenzoClient } from '@lorenzo/api-client';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';

export { unwrap } from '@lorenzo/api-client';
export const client = createLorenzoClient({ baseUrl: API_BASE_URL, getAccessToken });

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
