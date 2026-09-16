# Reference

- **API**: `apps/api`'s live OpenAPI/Swagger UI (`/docs` — every domain endpoint under `/tenants/{tenant_id}/...` plus `/me`, `/healthz`, `/readyz`, `/metrics`) is the reference while running it locally — see [docs/guides/getting-started.md](../guides/getting-started.md). A static export (`mise run //apps/api:openapi-schema`, dumped to `apps/api/openapi.json`) already exists for CI's own openapi-diff check; a version of it published here for browsing without running the API locally hasn't landed yet.
- **Config**: see [.env.example](../../.env.example) at the repo root.
