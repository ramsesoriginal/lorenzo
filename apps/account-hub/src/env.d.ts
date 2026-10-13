/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly PUBLIC_API_BASE_URL?: string;
  readonly PUBLIC_AUTHGEAR_ENDPOINT?: string;
  readonly PUBLIC_AUTHGEAR_CLIENT_ID?: string;
  readonly PUBLIC_BEINGS_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
