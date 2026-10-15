// A picture of the API that wants the token, as a `blob:` address (ADR 0300). An <img src> cannot
// send an Authorization header, so the picture is fetched with it and shown from the response: a
// private repository's picture and every cover are served to a signed-in user only.

import { LorenzoApiError } from '@lorenzo/api-client';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';

// `path` is the route, from the API's root (`/tenants/{id}/picture`). Refused with the API's status
// (404 for a repository with no picture, or one the caller cannot see) for the page to leave out.
export async function fetchPictureUrl(path: string): Promise<string> {
  const token = await getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    throw new LorenzoApiError(`Could not load a picture (${response.status}).`, response.status);
  }

  return URL.createObjectURL(await response.blob());
}
