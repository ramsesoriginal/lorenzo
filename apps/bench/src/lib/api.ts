import { createLorenzoClient } from '@lorenzo/api-client';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';

export type { components, paths } from '@lorenzo/api-client';
export { fetchAllPages, LorenzoApiError, MAX_PAGE_SIZE, unwrap } from '@lorenzo/api-client';

// Every request carries the viewer's token; with none it is refused before it goes out.
export const client = createLorenzoClient({ baseUrl: API_BASE_URL, getAccessToken });
