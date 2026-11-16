export const API_BASE_URL: string =
  import.meta.env.PUBLIC_API_BASE_URL || 'https://lorenzo-api-100817212329.europe-west1.run.app';
export const AUTHGEAR_ENDPOINT: string | undefined = import.meta.env.PUBLIC_AUTHGEAR_ENDPOINT;
export const AUTHGEAR_CLIENT_ID: string | undefined = import.meta.env.PUBLIC_AUTHGEAR_CLIENT_ID;
export const BRANDING_CSS_URL = (import.meta.env.PUBLIC_BRANDING_CSS_URL || '/branding').replace(
  /\/$/,
  '',
);
