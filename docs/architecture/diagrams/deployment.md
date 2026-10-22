# Deployment diagrams

## apps/api

```mermaid
C4Deployment
  title Lorenzo API deployment (local dev + production)

  Deployment_Node(dev, "Developer machine", "Local dev environment"){
    Deployment_Node(compose, "Docker Compose", "infra/docker-compose.yml"){
      ContainerDb(localdb, "Postgres", "postgres:17-alpine", "Local dev database, port 55432")
    }
    Container(localapi, "apps/api", "uv run fastapi dev", "Autoreload, port 8000")
  }

  Deployment_Node(gha, "GitHub Actions", "ubuntu-latest runner"){
    Container(deployjob, "deploy-api.yml deploy job", "build, migrate, deploy", "OIDC auth via Workload Identity Federation")
  }

  Deployment_Node(gcp, "Google Cloud - lorenzo-medici-api", "europe-west1"){
    Deployment_Node(ar, "Artifact Registry", "Docker repo"){
      Container(image, "api image", "container image", "Tagged by commit SHA")
    }
    Deployment_Node(cr, "Cloud Run", "scale-to-zero, public"){
      Container(api, "lorenzo-api service", "FastAPI container", "Serves healthz readyz metrics")
    }
  }

  Deployment_Node(neon, "Neon", "Managed Postgres"){
    ContainerDb(neondb, "Postgres", "pooled connection", "Autoscale-to-zero after 5 min idle")
  }

  Rel(localapi, localdb, "SQL", "asyncpg")
  Rel(deployjob, image, "docker push")
  Rel(api, image, "pulls")
  Rel(deployjob, api, "deploys new revision")
  Rel(deployjob, neondb, "alembic upgrade head", "before deploy")
  Rel(api, neondb, "SQL", "asyncpg, TLS")
```

## apps/loot-bot

Same GCP project/region and the same Neon instance as `apps/api` above (a separate `loot_bot` role/schema, not a separate database) - a second Artifact Registry repo and Cloud Run service, reusing the same Workload Identity Federation pool/provider/service account rather than a parallel one ([ADR 0053](../../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)).

```mermaid
C4Deployment
  title Lorenzo loot-bot deployment (local dev + production)

  Deployment_Node(dev, "Developer machine", "Local dev environment"){
    Container(localbot, "apps/loot-bot", "tsx --env-file=.env watch", "Autoreload, port 8090 - /livez /auth/callback /interactions")
  }

  Deployment_Node(gha, "GitHub Actions", "ubuntu-latest runner"){
    Container(deployjob, "deploy-loot-bot.yml deploy job", "build, migrate, deploy", "Same OIDC/WIF identity as deploy-api.yml")
  }

  Deployment_Node(gcp, "Google Cloud - lorenzo-medici-api", "europe-west1"){
    Deployment_Node(ar, "Artifact Registry", "lorenzo-loot-bot repo"){
      Container(image, "loot-bot image", "container image", "Tagged by commit SHA")
    }
    Deployment_Node(cr, "Cloud Run", "scale-to-zero, public"){
      Container(bot, "lorenzo-loot-bot service", "HTTP service, no Gateway Client", "Serves livez, auth/callback, interactions")
    }
  }

  Deployment_Node(neon, "Neon", "Managed Postgres - same instance as apps/api"){
    ContainerDb(neondb, "Postgres", "loot_bot role/schema", "Same pooled connection host")
  }

  System_Ext(discord, "Discord", "Interactions Endpoint webhook")

  Rel(discord, bot, "POST /interactions", "Ed25519-signed webhook")
  Rel(deployjob, image, "docker push")
  Rel(bot, image, "pulls")
  Rel(deployjob, bot, "deploys new revision")
  Rel(deployjob, neondb, "tsx src/migrate.ts", "before deploy")
  Rel(bot, neondb, "SQL", "pg, TLS")
```

## Static apps on Cloudflare Pages

`apps/account-hub`, `apps/inventory-web`, `apps/beings`, `apps/bench`, `apps/calendars`, `apps/sessions` and `apps/brand` deploy the same way: a static build served by Cloudflare Pages, wired to Cloudflare's own Git integration (no GitHub Actions job, no container, no database), rebuilt on a push to `main` that touches the app or a watched package. They call the API on Cloud Run from the browser (the API's `CORS_ALLOWED_ORIGINS` has to list each origin) and sign in through Authgear with a public client of their own. Which of them are hosted today differs, as the labels below say.

```mermaid
C4Deployment
  title Lorenzo static apps deployment (Cloudflare Pages, Git integration)

  Deployment_Node(gh, "GitHub", "ramsesoriginal/lorenzo"){
    Container(repo, "main branch", "git", "A push touching an app or a watched package")
  }

  Deployment_Node(cf, "Cloudflare Pages", "One project per app, production branch main"){
    Container(hub, "lorenzo-account-hub", "astro build, dist", "apps/account-hub")
    Container(inv, "lorenzo-inventory-web", "astro build, dist", "apps/inventory-web")
    Container(bench, "lorenzo-bench", "astro build, dist", "apps/bench")
    Container(cal, "lorenzo-calendars", "astro build, dist", "apps/calendars - setup record names it as the production app")
    Container(ses, "lorenzo-sessions", "astro build, dist", "apps/sessions - runbook only, planned address")
    Container(beings, "lorenzo-beings", "astro build, dist", "apps/beings - placeholder until its setup is done")
    Container(brand, "lorenzo-brand", "no build, static files", "apps/brand - tokens.css and the preview")
  }

  Rel(repo, hub, "Cloudflare builds and publishes")
  Rel(repo, inv, "Cloudflare builds and publishes")
  Rel(repo, bench, "Cloudflare builds and publishes")
  Rel(repo, cal, "Cloudflare builds and publishes")
  Rel(repo, ses, "Cloudflare builds and publishes")
  Rel(repo, beings, "Cloudflare builds and publishes")
  Rel(repo, brand, "Cloudflare builds and publishes")
```

The apps' addresses, and the links between them, are served by the API's registry, `GET /app-links` ([ADR 0273](../../adr/0273-app-links-registry.md)); an address the registry does not set falls back to the official `https://lorenzo-<app>.pages.dev`. Setup, one app each: [deployment-setup.md](../../operations/deployment-setup.md) (account-hub, inventory-web, bench, brand), [beings-setup.md](../../operations/beings-setup.md) (the Authgear client and Pages project do not exist yet), [calendars-setup.md](../../operations/calendars-setup.md) and [sessions-setup.md](../../operations/sessions-setup.md) (the Pages project and Authgear client are created from the runbook; Sessions is not deployed by merging its pull request). See [docs/architecture/deployment.md](../deployment.md#static-apps-on-cloudflare-pages) for the prose version.

## Native apps

`apps/inventory-mobile` (Android) and `apps/inventory-ios` are not deployed anywhere: both are installed locally. Android installs a locally built debug APK; iOS builds an unsigned IPA in CI that is signed locally with AltStore Classic ([ADR 0291](../../adr/0291-inventory-mobile-native-android-app.md), [ADR 0307](../../adr/0307-inventory-ios-and-altstore-testing.md)). See [docs/architecture/deployment.md](../deployment.md#native-apps) for the prose version; the same file has a local-vs-deployed comparison table for `apps/api`.
