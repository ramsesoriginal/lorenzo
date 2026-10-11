# Setting up Lorenzo Beings for hosting

[`apps/beings`](../../apps/beings) is built and tested, but nothing hosts it yet: the Authgear client and the Cloudflare Pages project do not exist, and [`deploy-beings.yml`](../../.github/workflows/deploy-beings.yml) is switched off until they do ([ADR 0270](../adr/0270-beings-app.md)). This is the order to do it in, once. It is a static site, so nothing here involves a container or a database ([ADR 0004](../adr/0004-static-astro-frontend.md)); the general Cloudflare and Authgear background is in [deployment-setup.md](deployment-setup.md).

## 1. Create the Authgear client

In the Authgear Cloud console of the project the other apps use: **Applications, New Application, Single Page Application**. It is a public (PKCE) client of its own, distinct from every other app's.

1. **Name**: `Lorenzo Beings`.
2. **Authorized Redirect URIs**:
   - `https://lorenzo-beings.pages.dev/auth/redirect/` (the production address from step 2)
   - `http://127.0.0.1:4323/auth/redirect/` (local development)

   The trailing slash is required: Cloudflare Pages redirects a bare `/auth/redirect` to the slash form before the app's script runs, and the token exchange then no longer matches a registered address without it (see the note in [deployment-setup.md](deployment-setup.md) under `apps/account-hub`).
3. **Authorized Post-Logout Redirect URIs**: the same two origins, no path (`https://lorenzo-beings.pages.dev`, `http://127.0.0.1:4323`).
4. Copy the **Endpoint** (the issuer) and the **Client ID**. They are public identifiers, not secrets.
5. Check the free tier's application cap first (see the Authgear section of [deployment-setup.md](deployment-setup.md)): this is another application beside the other apps' clients.

## 2. Create the Cloudflare Pages project

The workflow uploads the built site with Wrangler ("direct upload"), so the project is created empty:

1. **Workers & Pages, Create, Pages, Upload assets** (or, from a terminal with Wrangler logged in, `npx wrangler pages project create lorenzo-beings --production-branch main`).
2. **Project name**: `lorenzo-beings`, which gives `https://lorenzo-beings.pages.dev`. The name is also in the workflow's last step; if you choose another, change it there.
3. Create an **API token** (My Profile, API Tokens) with the *Cloudflare Pages: Edit* permission on the account, and note the **Account ID** (shown on the account's overview page).

*Alternative.* The other static apps deploy through Cloudflare's own Git integration instead of a workflow ([ADR 0071's addendum](../adr/0071-account-hub-stack-auth-deploy.md#addendum-2026-09-19-cloudflare-pages-git-integration-not-wrangler-action-token-upload)). To do the same here, connect the repository in Pages with root directory `apps/beings`, build command `npm install --global corepack@latest && corepack enable && pnpm install --frozen-lockfile && pnpm run build`, output `dist`, the environment variables of step 3 below, `NODE_VERSION` 26, and build watch paths `apps/beings/**`, `packages/api-client/**`, `packages/brand/**`, `packages/lorenzoscript/**`, `packages/lorenzoscript-editor/**`, `packages/stat-values/**`. Then leave step 4 undone and delete `deploy-beings.yml`.

## 3. Set the repository's secrets and variables

Settings, Secrets and variables, Actions. The workflow's `deploy` job runs in the `production` environment, as the API's does, so put them there or at repository level:

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `CLOUDFLARE_API_TOKEN` | the token from step 2 |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | the account id from step 2 |
| Variable | `BEINGS_AUTHGEAR_ENDPOINT` | the Endpoint from step 1 |
| Variable | `BEINGS_AUTHGEAR_CLIENT_ID` | the Client ID from step 1 |
| Variable | `PUBLIC_API_BASE_URL` | optional: the API's address; the build defaults to the deployed Cloud Run API |
| Variable | `PUBLIC_INVENTORY_WEB_BASE_URL` | optional: `https://lorenzo-inventory-web.pages.dev`. Without it a being's page has no link to its inventory board |
| Variable | `PUBLIC_ACCOUNT_HUB_BASE_URL` | optional: `https://lorenzo-account-hub.pages.dev` |

The `PUBLIC_` values end up in the site's bundle, which is why they are variables.

## 4. Let the API accept the site

Add `https://lorenzo-beings.pages.dev` to the API's space-separated `CORS_ALLOWED_ORIGINS` variable (do not replace the others), then run Actions, "Deploy API", "Run workflow" once. Changing a variable does not trigger it, and until it runs the browser says "blocked by CORS policy" on every call ([ADR 0048](../adr/0048-cors-configuration.md)). A Pages preview address (`<branch>.lorenzo-beings.pages.dev`) is another origin and is not allowed unless added.

## 5. Enable the workflow

Set the repository **variable** `BEINGS_DEPLOY_ENABLED` to `true`, then run Actions, "Deploy beings", "Run workflow" once. From then on a push to `main` that touches `apps/beings` or a package it bundles deploys it. Setting the variable back to anything else switches the deploys off again; the jobs are then skipped, not failed.

To link the other apps to it, set `PUBLIC_BEINGS_BASE_URL` (the site's address) as a variable of account-hub's build; its Beings page then shows an "Open in Lorenzo Beings" link per library ([ADR 0272](../adr/0272-beings-editing-stats-and-handing-over.md)).

## Checking it

Open `https://lorenzo-beings.pages.dev`, log in, choose a library. The list of beings opens; open one. If the page says Authgear is not configured, step 3's two `BEINGS_AUTHGEAR_*` variables are missing from the build; if sign-in loops back with an error about a redirect address, step 1's list is missing the slash form.
