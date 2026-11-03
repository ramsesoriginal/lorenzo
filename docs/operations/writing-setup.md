# Setting up Lorenzo Writing for hosting

[Lorenzo Writing](../../apps/writing/README.md) is a static Astro app ([RFC 0047](../rfcs/0047-lorenzo-writing.md), [ADR 0327](../adr/0327-lorenzo-writing.md)). The production app is at [lorenzo-writing.pages.dev](https://lorenzo-writing.pages.dev/), the default of `WRITING_URL` in the API's settings. The following records its setup procedure. It follows the other static apps: Cloudflare Git integration builds from `main`, without a separate GitHub deployment workflow. See [deployment setup](deployment-setup.md) for shared Authgear, Cloudflare and CORS details, and [Lorenzo Sessions hosting](sessions-setup.md), which this procedure mirrors.

## Authgear

Create a separate public Single Page Application client named Lorenzo Writing in the existing Authgear project, using refresh-token sessions. Register these exact callback addresses, including their trailing slash (Cloudflare Pages redirects a bare `/auth/redirect` to the slash form), and allow the respective origins as post-logout redirect addresses:

- `https://lorenzo-writing.pages.dev/auth/redirect/`
- `http://127.0.0.1:4327/auth/redirect/` (local development; `localhost` is a different origin)

Check the provider's current client limits in its console before creating another application.

## Pages

Create a Pages project connected to `ramsesoriginal/lorenzo`, named `lorenzo-writing`, production branch `main`. Set the root to `apps/writing`, output to `dist`, and the `NODE_VERSION` environment variable to the Node major in the root `mise.toml`. Build with:

```bash
npm install --global corepack@latest && corepack enable && pnpm install --frozen-lockfile && pnpm run build
```

`pnpm run build` builds `@lorenzo/brand`, copies its files into `public/branding/` (`scripts/copy-branding.mjs`) and then runs `astro build`.

Set `PUBLIC_API_BASE_URL`, `PUBLIC_AUTHGEAR_ENDPOINT` and this app's `PUBLIC_AUTHGEAR_CLIENT_ID` in the Pages build environment. Branding is bundled locally; `PUBLIC_BRANDING_CSS_URL` is optional. These are public configuration, not client secrets.

Build watch paths follow [the rule in the deployment setup](deployment-setup.md#build-watch-paths). For this app: `apps/writing/**`, `apps/brand/**`, `packages/api-client/**`, `packages/app-shell/**`, `packages/brand/**`, `packages/information-editor/**`, `packages/lorenzoscript/**`, `packages/lorenzoscript-editor/**`, `pnpm-lock.yaml` and `tools/brand/**`.

## API and verification

Add the production origin to the API's existing space-separated `CORS_ALLOWED_ORIGINS` list and deploy the API through its normal workflow. The app registry already has the `https://lorenzo-writing.pages.dev` address; set the API/GitHub `WRITING_URL` variable for a different origin. Deployment passes an unset value through to the API's default. Preview origins need their own explicit CORS and callback authorization.

The registry's `manuscript` link template uses the library and entry identity; other apps get the address from `GET /app-links`. Call it and confirm that `apps.writing.url` is the address you deployed and that the `manuscript` link points at it.

Verify sign-in and sign-out, an Author in both a library and a repository, text and image autosave, reload recovery, a conflicting save, saved revisions and access revocation. Do not reuse a production database for the browser tests. Without `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID` the app reports that Authgear is not configured.
