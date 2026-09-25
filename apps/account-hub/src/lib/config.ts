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

// Base URL the @lorenzo/brand stylesheets are linked from (ADR 0098).
// Defaults to a same-origin path - scripts/copy-branding.mjs copies the
// package's files into public/branding/ so that default works with zero
// new runtime dependency for a self-hoster. Setting this to an absolute
// URL (e.g. apps/brand's own deployed origin) opts into runtime hotlinking
// instead, for instant cross-app propagation of a branding change.
// Trailing slash stripped so call sites can always append `/<file>.css`
// without worrying whether the configured value already ends in one.
export const BRANDING_CSS_URL: string = (
  import.meta.env.PUBLIC_BRANDING_CSS_URL || '/branding'
).replace(/\/$/, '');
