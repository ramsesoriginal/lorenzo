# Operations

- [GitHub repository setup](github-setup.md) — manual steps this repo's own tooling can't automate yet
- [Deployment setup](deployment-setup.md) — one-time Neon, Google Cloud and Authgear setup for the deploy pipelines of apps/api and apps/loot-bot, plus the Cloudflare Pages projects of apps/account-hub, apps/inventory-web, apps/bench and apps/brand, the Authgear clients of the first three, and the command line's Authgear client
- [Going public](public-launch.md) — what to set and in what order to switch public repositories on: the edge rule, the report address, the switch, the settings that have defaults, and how an operator delists a repository
- [Hosting Lorenzo Beings](beings-setup.md) — the one-time steps to host apps/beings: its Cloudflare Pages project (Git integration, no workflow), its Authgear client, and the API's CORS list
- [Hosting Lorenzo Calendars](calendars-setup.md) — the one-time steps to host apps/calendars: its Cloudflare Pages project (Git integration, no workflow), its Authgear client, the API's CORS list and `CALENDARS_URL`
- [Hosting Lorenzo Sessions](sessions-setup.md) — the same for apps/sessions: its Cloudflare Pages project, Authgear client, the API's CORS list and `SESSIONS_URL`
- [Hosting Lorenzo Writing](writing-setup.md) — its Cloudflare Pages project, Authgear client, the API's CORS list and `WRITING_URL`
- [Hosting Lorenzo Maps](maps-setup.md) — the same for apps/maps: its Cloudflare Pages project, Authgear client, the API's CORS list and `MAPS_URL`
- [Local Authgear setup](local-authgear-setup.md) — manual, one-time setup for a real login round-trip against Authgear Cloud during interactive testing
- [Releasing](releasing.md) — how the release-please automation works
- [Exporting your tenant](exporting-your-tenant.md) — how an owner takes their tenant's data out with the existing authenticated reads, and what such an export will not contain
- [Rate-limiting the invite-link endpoints](invite-link-rate-limiting.md) — the edge rule the invite-link feature needs before the project goes live (deferred until then), the in-process backstop's settings, and how to verify both
