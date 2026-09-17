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
  Rel(cr, image, "pulls")
  Rel(deployjob, cr, "deploys new revision")
  Rel(deployjob, neondb, "alembic upgrade head", "before deploy")
  Rel(api, neondb, "SQL", "asyncpg, TLS")
```

## apps/loot-bot

Same GCP project/region and the same Neon instance as `apps/api` above (a separate `loot_bot` role/schema, not a separate database) - a second Artifact Registry repo and Cloud Run service, reusing the same Workload Identity Federation pool/provider/service account rather than a parallel one ([ADR 0053](../../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)).

```mermaid
C4Deployment
  title Lorenzo loot-bot deployment (local dev + production)

  Deployment_Node(dev, "Developer machine", "Local dev environment"){
    Container(localbot, "apps/loot-bot", "tsx --env-file=.env watch", "Autoreload, port 8090 - /healthz /auth/callback /interactions")
  }

  Deployment_Node(gha, "GitHub Actions", "ubuntu-latest runner"){
    Container(deployjob, "deploy-loot-bot.yml deploy job", "build, migrate, deploy", "Same OIDC/WIF identity as deploy-api.yml")
  }

  Deployment_Node(gcp, "Google Cloud - lorenzo-medici-api", "europe-west1"){
    Deployment_Node(ar, "Artifact Registry", "lorenzo-loot-bot repo"){
      Container(image, "loot-bot image", "container image", "Tagged by commit SHA")
    }
    Deployment_Node(cr, "Cloud Run", "scale-to-zero, public"){
      Container(bot, "lorenzo-loot-bot service", "HTTP service, no Gateway Client", "Serves healthz, auth/callback, interactions")
    }
  }

  Deployment_Node(neon, "Neon", "Managed Postgres - same instance as apps/api"){
    ContainerDb(neondb, "Postgres", "loot_bot role/schema", "Same pooled connection host")
  }

  System_Ext(discord, "Discord", "Interactions Endpoint webhook")

  Rel(discord, bot, "POST /interactions", "Ed25519-signed webhook")
  Rel(deployjob, image, "docker push")
  Rel(cr, image, "pulls")
  Rel(deployjob, cr, "deploys new revision")
  Rel(deployjob, neondb, "tsx src/migrate.ts", "before deploy")
  Rel(bot, neondb, "SQL", "pg, TLS")
```

See [docs/architecture/deployment.md](../deployment.md) for the prose version of both, including a local-vs-deployed comparison table.
