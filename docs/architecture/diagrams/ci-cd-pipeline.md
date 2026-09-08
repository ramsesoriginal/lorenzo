# CI/CD pipeline flowchart: apps/api

```mermaid
flowchart TD
    A["Push / PR opened"] --> B["ci.yml"]
    B --> B1["discover: find apps/*/mise.toml"]
    B1 --> B2["test: mise run lint + test, per app<br/>(own Postgres service)"]
    A --> B3["security.yml: CodeQL + dependency-review"]
    A --> B4["docs.yml: markdownlint + lychee"]
    B2 --> C{"ci-summary<br/>(required check)"}
    B3 --> C
    B4 --> C

    C -->|all required checks pass| D["Merge to main<br/>(real merge commit)"]

    D --> E{"Touches apps/api/**?"}
    E -->|yes| F["deploy-api.yml triggers"]
    D --> G["release.yml triggers<br/>(every push)"]

    G --> G1["release-please: open/update release PR"]

    F --> F1["verify: lint + test again"]
    F1 --> F2["auth: OIDC via Workload Identity Federation"]
    F2 --> F3["build and push image to Artifact Registry<br/>tagged by commit SHA"]
    F3 --> F4["migrate: alembic upgrade head against Neon"]
    F4 --> F5["deploy: new Cloud Run revision"]
    F5 --> F6{"curl /readyz"}
    F6 -->|200| H["Live"]
    F6 -->|non-200| I["Workflow fails -<br/>revision not confirmed healthy"]
```

Two independent triggers fire off the same push to `main`: `release.yml` (always, proposing/updating a version bump) and `deploy-api.yml` (only if the push touches `apps/api/**`). Neither depends on the other — a release PR being merged doesn't itself deploy anything, and a deploy doesn't wait for a release to be tagged. See [docs/operations/releasing.md](../../operations/releasing.md) and [docs/architecture/deployment.md](../deployment.md).
