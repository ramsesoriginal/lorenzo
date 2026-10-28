# Setting up Lorenzo Calendars for hosting

[Lorenzo Calendars](../../apps/calendars/README.md) is a static Astro app. The production app is at [lorenzo-calendars.pages.dev](https://lorenzo-calendars.pages.dev/). The following records its setup procedure. It follows the other static apps: Cloudflare Git integration builds from `main`, without a separate GitHub deployment workflow. See [deployment setup](deployment-setup.md) for shared Authgear, Cloudflare and CORS details.

## Pages

Create a Pages project connected to `ramsesoriginal/lorenzo`, named `lorenzo-calendars`, production branch `main`. Set the root to `apps/calendars`, output to `dist`, and Node major to the root `mise.toml` (currently 26). Build with:

```bash
npm install --global corepack@latest && corepack enable && pnpm install --frozen-lockfile && pnpm run build
```

Watch `apps/calendars/**`, `packages/api-client/**`, `packages/brand/**`, `apps/brand/**`, `packages/lorenzoscript/**`, `packages/lorenzoscript-editor/**`, `packages/information-editor/**`, `pnpm-lock.yaml` and `tools/brand/**`.

## Authgear and public configuration

Create a public Single Page Application client named Lorenzo Calendars in the existing Authgear project. Register these exact callback addresses, including their trailing slash:

- `https://lorenzo-calendars.pages.dev/auth/redirect/`
- `http://127.0.0.1:4325/auth/redirect/`

Allow the respective origins as post-logout redirect addresses. Supply the Pages build's `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID`; optionally override `PUBLIC_API_BASE_URL`. These are public configuration, not client secrets. Check the provider's current client limits in its console before creating another application.

## API and verification

Add the production origin to the API's existing space-separated `CORS_ALLOWED_ORIGINS` list and deploy the API through its normal workflow. The app registry already has the `https://lorenzo-calendars.pages.dev` address; set the API/GitHub `CALENDARS_URL` variable for a different origin. Deployment passes an unset value through to the API's default. Preview origins need their own explicit CORS and callback authorization.

Open the app, log in and choose a library. Create and preview a calendar, save it, and open a year. Import a reviewed native file through the CLI and confirm dates, moons and authored notes. Merely opening a year must not create saved date entries. Check an ordinary participant separately: public entry identity must not expose restricted Information. A missing Authgear setup produces a readable unavailable-sign-in message.
