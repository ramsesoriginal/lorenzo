# Setting up Lorenzo Beings for hosting

[`apps/beings`](../../apps/beings) is built and tested, but nothing hosts it yet: the Authgear client and the Cloudflare Pages project do not exist ([ADR 0270](../adr/0270-beings-app.md)). It deploys the way the other static apps do, through Cloudflare's own Git integration ([ADR 0071's addendum](../adr/0071-account-hub-stack-auth-deploy.md#addendum-2026-09-19-cloudflare-pages-git-integration-not-wrangler-action-token-upload)): there is no deploy workflow, Pages builds and publishes every push to `main` itself. This is the order to do it in, once. It is a static site, so nothing here involves a container or a database ([ADR 0004](../adr/0004-static-astro-frontend.md)); the general Cloudflare and Authgear background is in [deployment-setup.md](deployment-setup.md).

## 1. Create the Cloudflare Pages project

1. **Workers & Pages, Create, Pages, Connect to Git**, select `ramsesoriginal/lorenzo`.
2. **Project name**: `lorenzo-beings` (this gives `https://lorenzo-beings.pages.dev`). **Production branch**: `main`.
3. **Build settings**, as for `apps/inventory-web` ([deployment-setup.md](deployment-setup.md)):
   - **Root directory**: `apps/beings`
   - **Build command**: `npm install --global corepack@latest && corepack enable && pnpm install --frozen-lockfile && pnpm run build`
   - **Build output directory**: `dist`
   - **Node version**: the environment variable `NODE_VERSION` set to the major in `mise.toml` (26).
4. **Build watch paths** (Settings, Builds & deployments): `apps/beings/**`, `packages/api-client/**`, `packages/brand/**`, `packages/lorenzoscript/**`, `packages/lorenzoscript-editor/**` and `packages/stat-values/**` (double star).

## 2. Create the Authgear client

In the Authgear Cloud console of the project the other apps use: **Applications, New Application, Single Page Application**. It is a public (PKCE) client of its own, distinct from every other app's.

1. **Name**: `Lorenzo Beings`.
2. **Authorized Redirect URIs**:
   - `https://lorenzo-beings.pages.dev/auth/redirect/`
   - `http://127.0.0.1:4323/auth/redirect/` (local development)

   The trailing slash is required: Cloudflare Pages redirects a bare `/auth/redirect` to the slash form before the app's script runs, and the token exchange then no longer matches a registered address without it (see the note in [deployment-setup.md](deployment-setup.md) under `apps/account-hub`).
3. **Authorized Post-Logout Redirect URIs**: the same two origins, no path (`https://lorenzo-beings.pages.dev`, `http://127.0.0.1:4323`).
4. Copy the **Endpoint** (the issuer) and the **Client ID**. They are public identifiers, not secrets.
5. Check the free tier's application cap first (see the Authgear section of [deployment-setup.md](deployment-setup.md)): this is another application beside the other apps' clients.

## 3. Give the Pages project its variables

In the Pages project's **Settings, Environment variables** (Production): `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID` from step 2, and optionally `PUBLIC_API_BASE_URL` (the API's address; the build defaults to the deployed Cloud Run API). Then retry the first deployment.

Where the other Lorenzo apps live is not a variable of this project: the app asks the API's app-links registry ([ADR 0273](../adr/0273-app-links-registry.md)).

## 4. Let the API accept the site

Add `https://lorenzo-beings.pages.dev` to the API's space-separated `CORS_ALLOWED_ORIGINS` variable (do not replace the others), then run Actions, "Deploy API", "Run workflow" once. Changing a variable does not trigger it, and until it runs the browser says "blocked by CORS policy" on every call ([ADR 0048](../adr/0048-cors-configuration.md)). A Pages preview address (`<branch>.lorenzo-beings.pages.dev`) is another origin and is not allowed unless added.

## Checking it

Open `https://lorenzo-beings.pages.dev`, log in, choose a library. The list of beings opens; open one. If the page says Authgear is not configured, the two `PUBLIC_AUTHGEAR_*` variables are missing from the project; if sign-in loops back with an error about a redirect address, step 2's list is missing the slash form.
