# Deployment diagram: apps/api

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

See [docs/architecture/deployment.md](../deployment.md) for the prose version of this, including a local-vs-deployed comparison table.
