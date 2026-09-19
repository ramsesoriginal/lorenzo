// The API URL is public information (it's the address of a REST API, not a
// secret), so a working default ships in the bundle - PUBLIC_API_BASE_URL
// only needs setting to point at a local apps/api instead.
// `||`, not `??`: an unset .env value comes through as `""`, which should
// also fall back to the default rather than becoming an empty base URL.
export const API_BASE_URL: string =
  import.meta.env.PUBLIC_API_BASE_URL || 'https://lorenzo-api-100817212329.europe-west1.run.app';

// Authgear's client ID and endpoint are public OAuth client identifiers
// (this is a PKCE public client, no secret involved), but there's no
// working default - a real Authgear application has to exist first.
export const AUTHGEAR_ENDPOINT: string | undefined = import.meta.env.PUBLIC_AUTHGEAR_ENDPOINT;
export const AUTHGEAR_CLIENT_ID: string | undefined = import.meta.env.PUBLIC_AUTHGEAR_CLIENT_ID;
