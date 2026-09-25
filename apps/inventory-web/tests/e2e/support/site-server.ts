// Builds the site against the end-to-end stack and serves it (ADR 0114), run by Playwright's
// webServer. A launcher rather than `build && preview`: on Windows, pnpm is a batch file,
// and cmd doesn't come back from one to run the second command.
import { spawn, spawnSync } from 'node:child_process';
import { API_URL, AUTHGEAR_URL, CLIENT_ID, SITE_URL } from './env.ts';

const env = {
  ...process.env,
  PUBLIC_API_BASE_URL: API_URL,
  PUBLIC_AUTHGEAR_ENDPOINT: AUTHGEAR_URL,
  PUBLIC_AUTHGEAR_CLIENT_ID: CLIENT_ID,
};
const options = { env, stdio: 'inherit', shell: true } as const;

const built = spawnSync('pnpm run build', options);
if (built.status !== 0) process.exit(built.status ?? 1);

const { hostname, port } = new URL(SITE_URL);
const site = spawn(`pnpm exec astro preview --host ${hostname} --port ${port}`, options);
site.on('exit', (code) => process.exit(code ?? 0));
for (const signal of ['SIGINT', 'SIGTERM'] as const) process.on(signal, () => site.kill(signal));
