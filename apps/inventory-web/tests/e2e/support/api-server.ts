// Starts the real apps/api for the end-to-end tests (ADR 0114), run by Playwright's
// webServer: a fresh database, migrated with Alembic, then uvicorn, trusting the fake
// Authgear and the built site's origin.
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import pg from 'pg';
import {
  API_URL,
  APP_POSTGRES_URL,
  AUTHGEAR_URL,
  DATABASE_NAME,
  POSTGRES_URL,
  SITE_URL,
} from './env.ts';

// Guards the drop below against pointing it at a database someone cares about.
if (!DATABASE_NAME.endsWith('_e2e')) {
  throw new Error(`Refusing to recreate ${DATABASE_NAME}: its name must end in _e2e.`);
}
const admin = new pg.Client({ connectionString: POSTGRES_URL });
await admin.connect();
await admin.query(`DROP DATABASE IF EXISTS "${DATABASE_NAME}" WITH (FORCE)`);
await admin.query(`CREATE DATABASE "${DATABASE_NAME}"`);
await admin.end();

/** A postgres:// URL as SQLAlchemy's asyncpg URL for the e2e database. */
function asyncpg(url: string): string {
  const parsed = new URL(url);
  parsed.pathname = `/${DATABASE_NAME}`;
  return parsed.href.replace(/^postgres(ql)?:/, 'postgresql+asyncpg:');
}

const env = {
  ...process.env,
  DATABASE_URL: asyncpg(APP_POSTGRES_URL),
  MIGRATIONS_DATABASE_URL: asyncpg(POSTGRES_URL),
  AUTHGEAR_ISSUER: AUTHGEAR_URL,
  AUTHGEAR_AUDIENCE: AUTHGEAR_URL,
  AUTHGEAR_JWKS_URL: `${AUTHGEAR_URL}/oauth2/jwks`,
  AUTHGEAR_USERINFO_URL: `${AUTHGEAR_URL}/oauth2/userinfo`,
  CORS_ALLOWED_ORIGINS: SITE_URL,
  // The API prints every trace span to the console; that would bury the test output.
  OTEL_SDK_DISABLED: 'true',
};
const cwd = fileURLToPath(new URL('../../../../api/', import.meta.url));

const migrated = spawnSync('uv', ['run', 'alembic', 'upgrade', 'head'], {
  cwd,
  env,
  stdio: 'inherit',
});
if (migrated.status !== 0) process.exit(migrated.status ?? 1);

const { hostname, port } = new URL(API_URL);
const api = spawn(
  'uv',
  ['run', 'uvicorn', 'lorenzo_api.main:app', '--host', hostname, '--port', port],
  {
    cwd,
    env,
    stdio: 'inherit',
  },
);
api.on('exit', (code) => process.exit(code ?? 0));
for (const signal of ['SIGINT', 'SIGTERM'] as const) process.on(signal, () => api.kill(signal));
