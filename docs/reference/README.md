# Reference

- **API**: `apps/api`'s live OpenAPI/Swagger UI (`/docs` — tenant-scoped domain routes plus user, device authorization, app links, public repository, Discover, invite, administrative and observability routes) is the reference while running it locally — see [docs/guides/getting-started.md](../guides/getting-started.md). A static export (`mise run //apps/api:openapi-schema`, dumped to `apps/api/openapi.json`) can be generated for CI's own openapi-diff check; a version of it published here for browsing without running the API locally hasn't landed yet.
- **Config**: see the repo root [.env.example](../../.env.example) (apps/api and apps/loot-bot) and the `.env.example` of each web app; API settings are defined in [`config.py`](../../apps/api/src/lorenzo_api/config.py).
- **Well-known stats**: [well-known-stats.md](well-known-stats.md), the stat names the API and the entry cards read, and the weight recipe built on `sum` and `contents` formulas.
