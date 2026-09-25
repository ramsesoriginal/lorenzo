// Builds the site against the end-to-end stack and serves it (ADR 0114), run by Playwright's
// webServer. A launcher rather than `build && preview`: on Windows, pnpm is a batch file,
// and cmd doesn't come back from one to run the second command. The preview runs Astro's
// CLI directly under node, so stopping this process stops it too; behind pnpm and a shell,
// it outlived the run and served a stale build to the next one.
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { API_URL, AUTHGEAR_URL, CLIENT_ID, SITE_URL } from './env.ts';

const env = {
  ...process.env,
  PUBLIC_API_BASE_URL: API_URL,
  PUBLIC_AUTHGEAR_ENDPOINT: AUTHGEAR_URL,
  PUBLIC_AUTHGEAR_CLIENT_ID: CLIENT_ID,
};

const built = spawnSync('pnpm run build', { env, stdio: 'inherit', shell: true });
if (built.status !== 0) process.exit(built.status ?? 1);

const astro = fileURLToPath(new URL('../../../node_modules/astro/bin/astro.mjs', import.meta.url));
const { hostname, port } = new URL(SITE_URL);
const site = spawn(process.execPath, [astro, 'preview', '--host', hostname, '--port', port], {
  env,
  stdio: 'inherit',
});
site.on('exit', (code) => process.exit(code ?? 0));
for (const signal of ['SIGINT', 'SIGTERM'] as const) process.on(signal, () => site.kill(signal));
