# Setting up Lorenzo Sessions for hosting

[Lorenzo Sessions](../../apps/sessions/README.md) is a static Astro app ([ADR 0317](../adr/0317-sessions-scenes-and-collaborative-planning.md)). The production app is at [lorenzo-sessions.pages.dev](https://lorenzo-sessions.pages.dev/), the default of `SESSIONS_URL` in the API's settings. The following records its setup procedure. It follows the other static apps: Cloudflare Git integration builds from `main`, without a separate GitHub deployment workflow. See [deployment setup](deployment-setup.md) for shared Authgear, Cloudflare and CORS details, and [Lorenzo Calendars hosting](calendars-setup.md), which this procedure mirrors.

## Pages

Create a Pages project connected to `ramsesoriginal/lorenzo`, named `lorenzo-sessions`, production branch `main`. Set the root to `apps/sessions`, output to `dist`, and the `NODE_VERSION` environment variable to the Node major in the root `mise.toml`. Build with:

```bash
npm install --global corepack@latest && corepack enable && pnpm install --frozen-lockfile && pnpm run build
```

`pnpm run build` builds `@lorenzo/brand`, copies its files into `public/branding/` (`scripts/copy-branding.mjs`) and then runs `astro build`.

Build watch paths follow [the rule in the deployment setup](deployment-setup.md#build-watch-paths). For this app: `apps/sessions/**`, `apps/brand/**`, `packages/api-client/**`, `packages/app-shell/**`, `packages/brand/**`, `packages/information-editor/**`, `packages/lorenzoscript/**`, `packages/lorenzoscript-editor/**`, `packages/period-picker/**`, `packages/read-cache/**`, `pnpm-lock.yaml` and `tools/brand/**`.

## Authgear and public configuration

Create a public Single Page Application client named Lorenzo Sessions in the existing Authgear project. Register these exact callback addresses, including their trailing slash (Cloudflare Pages redirects a bare `/auth/redirect` to the slash form):

- `https://lorenzo-sessions.pages.dev/auth/redirect/`
- `http://127.0.0.1:4326/auth/redirect/`

Allow the respective origins as post-logout redirect addresses. Supply the Pages build's `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID`; optionally override `PUBLIC_API_BASE_URL` and `PUBLIC_BRANDING_CSS_URL` (see `apps/sessions/.env.example`). These are public configuration, not client secrets, and no client secret belongs in a static build. Check the provider's current client limits in its console before creating another application.

## API and verification

Add the production origin to the API's existing space-separated `CORS_ALLOWED_ORIGINS` list and deploy the API through its normal workflow. The app registry already has the `https://lorenzo-sessions.pages.dev` address; set the API/GitHub `SESSIONS_URL` variable for a different origin. Deployment passes an unset value through to the API's default. Preview origins need their own explicit CORS and callback authorization.

Call `GET /app-links` and confirm that `apps.sessions.url` is the address you deployed and that the `session`, `session_by_slug`, `scene`, `scene_by_slug` and `lived_order` links point at it.

Open the app and sign in as a GM. Create a Session, add players and add a Scene. Check as a player that restricted notes stay hidden and shared notes appear, and that logout works. Repeat on a phone-sized viewport. Without `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID` the app reports that Authgear is not configured.

No setting data or Session roster is seeded during deployment.
