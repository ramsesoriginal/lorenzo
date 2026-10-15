# Operations

- [GitHub repository setup](github-setup.md) — manual steps this repo's own tooling can't automate yet
- [Deployment setup](deployment-setup.md) — one-time Google Cloud + Neon setup for apps/api's and apps/loot-bot's deploy pipelines
- [Going public](public-launch.md) — what to set and in what order to switch public repositories on: the edge rule, the report address, the switch, the settings that have defaults, and how an operator delists a repository
- [Hosting Lorenzo Beings](beings-setup.md) — the one-time steps to host apps/beings: its Cloudflare Pages project (Git integration, no workflow), its Authgear client, and the API's CORS list
- [Local Authgear setup](local-authgear-setup.md) — manual, one-time setup for a real login round-trip against Authgear Cloud during interactive testing
- [Releasing](releasing.md) — how the release-please automation works
- [Exporting your tenant](exporting-your-tenant.md) — how an owner takes their tenant's data out with the existing authenticated reads, and what such an export will not contain
- [Rate-limiting the invite-link endpoints](invite-link-rate-limiting.md) — the edge rule the invite-link feature needs before the project goes live (deferred until then), the in-process backstop's settings, and how to verify both
