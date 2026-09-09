# Reference

- **API**: `apps/api`'s live OpenAPI/Swagger UI (`/docs` — every domain endpoint under `/tenants/{tenant_id}/...` plus `/me`, `/healthz`, `/readyz`, `/metrics`) is the reference while running it locally — see [docs/guides/getting-started.md](../guides/getting-started.md). A generated static export will land here once the API's surface is stable enough to be worth freezing — still read-only (`GET`) only, so likely premature.
- **Config**: see [.env.example](../../.env.example) at the repo root.
