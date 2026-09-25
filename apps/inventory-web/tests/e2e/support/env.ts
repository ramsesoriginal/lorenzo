// Where the end-to-end stack listens (ADR 0114), read by the Playwright config, the fake
// Authgear, the API launcher, and the tests. 127.0.0.1 rather than localhost, so no server
// ends up on ::1 alone.
export const AUTHGEAR_URL = 'http://127.0.0.1:4400';
export const API_URL = 'http://127.0.0.1:8765';
export const SITE_URL = 'http://127.0.0.1:4331';

/** The OAuth client the site presents; the fake Authgear accepts any. */
export const CLIENT_ID = 'lorenzo-e2e';

/** The cookie on the fake Authgear's origin that names who "logs in". */
export const SUBJECT_COOKIE = 'e2e_subject';

/**
 * The privileged Postgres role: it recreates the API's database and runs its migrations.
 * The default is infra/docker-compose.yml's.
 */
export const POSTGRES_URL =
  process.env.E2E_POSTGRES_URL ?? 'postgres://lorenzo:lorenzo@127.0.0.1:55432/postgres';

/** The API's restricted role (ADR 0021), which the migrations create if it's missing. */
export const APP_POSTGRES_URL =
  process.env.E2E_APP_POSTGRES_URL ?? 'postgres://lorenzo_app:lorenzo_app@127.0.0.1:55432/postgres';

/** The API's own database, recreated for every run. */
export const DATABASE_NAME = process.env.E2E_DATABASE ?? 'lorenzo_e2e';
