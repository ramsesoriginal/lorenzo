/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly PUBLIC_API_BASE_URL?: string;
  readonly PUBLIC_AUTHGEAR_ENDPOINT?: string;
  readonly PUBLIC_AUTHGEAR_CLIENT_ID?: string;
  readonly PUBLIC_BRANDING_CSS_URL?: string;
  readonly PUBLIC_INVENTORY_WEB_BASE_URL?: string;
  readonly PUBLIC_ACCOUNT_HUB_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
