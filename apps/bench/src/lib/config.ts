// The API's address is public, so a working default ships in the bundle; PUBLIC_API_BASE_URL only
// needs setting to point at a local apps/api. `||`, not `??`: an unset .env value is `""`.
export const API_BASE_URL: string =
  import.meta.env.PUBLIC_API_BASE_URL || 'https://lorenzo-api-100817212329.europe-west1.run.app';

// A PKCE public client's id and endpoint are public too, but there is no working default: a real
// Authgear application has to exist first (docs/operations/deployment-setup.md).
export const AUTHGEAR_ENDPOINT: string | undefined = import.meta.env.PUBLIC_AUTHGEAR_ENDPOINT;
export const AUTHGEAR_CLIENT_ID: string | undefined = import.meta.env.PUBLIC_AUTHGEAR_CLIENT_ID;
