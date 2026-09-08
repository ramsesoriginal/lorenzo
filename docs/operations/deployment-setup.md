# Deployment setup (manual, one-time)

See [ADR 0011](../adr/0011-deploy-target-cloud-run-neon.md) for why. The GCP/WIF setup below is confirmed correct — OIDC auth succeeds against a real project. `PROJECT_ID` must be globally unique across *all* of GCP, not just this repo — `lorenzo-api` was taken, `lorenzo-medici-api` wasn't; pick your own. The pipeline itself has needed a few real fixes on its first live runs (a missing `README.md` in the Docker build context, asyncpg rejecting two of Neon's default libpq-only query params, the container ignoring Cloud Run's `$PORT`) - each fixed as found, see `deploy-api.yml`'s history for specifics. Not yet marking this "confirmed end to end" until a full run completes cleanly.

## Neon (Postgres)

1. Sign up at [neon.tech](https://neon.tech), create a project. Pick a region close to whatever Cloud Run region you use below.
2. Use the default database Neon creates (or make a new one).
3. Copy the **pooled** connection string (Neon distinguishes pooled vs. direct — pooled fits a scale-to-zero app better). It looks like `postgresql://user:pass@host/dbname`.
4. **Rewrite the scheme for asyncpg**: apps/api needs `postgresql+asyncpg://...`, not plain `postgresql://...` — SQLAlchemy picks its driver from that prefix, and without `+asyncpg` it'll try to load a sync driver that isn't even installed. Just insert `+asyncpg` after `postgresql`.
5. **Leave the rest of the query string alone** — including `sslmode=require` and `channel_binding=require`, which Neon's copy-paste connection string includes by default. Both are libpq-only: asyncpg has no `channel_binding` equivalent at all, and takes `ssl` rather than `sslmode` (same values, different name). `apps/api` normalizes both automatically at startup (see `Settings._normalize_for_asyncpg` in `config.py`) — no manual edit needed here.

This becomes the `DATABASE_URL` secret below.

## Google Cloud

Variables used throughout — adjust `PROJECT_ID` (must be globally unique) and `REGION`:

```bash
export PROJECT_ID="lorenzo-api"
export REGION="europe-west1"
export REPO_NAME="lorenzo-api"
export SA_NAME="github-deployer"
export GITHUB_REPO="ramsesoriginal/lorenzo"
```

**1. Project and APIs:**

```bash
gcloud projects create "$PROJECT_ID"
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com
```

(This is also where you'll be prompted to attach a billing account — required to stay in Cloud Run's free quota since February 2026, no charge if you stay under it.)

**2. Artifact Registry** (where the built image lives):

```bash
gcloud artifacts repositories create "$REPO_NAME" --repository-format=docker --location="$REGION"
```

**3. Service account GitHub Actions will act as**, scoped to exactly three roles — not broader:

```bash
gcloud iam service-accounts create "$SA_NAME" --display-name="GitHub Actions deployer"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role"
done
```

**4. Workload Identity Federation** — trust GitHub's OIDC tokens instead of a stored key:

```bash
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

The `--attribute-condition` is what restricts this to *this exact repo* — without it, any repo with a matching provider config could impersonate the service account.

**5. Let only this repo's workflows impersonate the service account:**

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"
```

**6. Values for GitHub** — print them once everything above succeeds:

```bash
echo "GCP_PROJECT_ID=$PROJECT_ID"
echo "GCP_REGION=$REGION"
echo "GCP_SERVICE_ACCOUNT=$SA_EMAIL"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
```

**7. Make the service public**, once it exists (i.e. after the *first* deploy from `deploy-api.yml`, even if that run's final `/readyz` check failed — the service itself gets created either way):

```bash
gcloud run services update lorenzo-api --region="$REGION" --no-invoker-iam-check
```

New Cloud Run services are private by default — every request needs a Google-signed identity token, which is why the workflow's own unauthenticated `curl .../readyz` smoke test gets a `403`. This is deliberately a manual, one-time step rather than a `deploy-cloudrun` flag: [the action's own README](https://github.com/google-github-actions/deploy-cloudrun) recommends CI/CD not manage this setting, since re-deploys preserve whatever IAM state the service already has. `--no-invoker-iam-check` is Google's currently-recommended way to do this (over granting `roles/run.invoker` to `allUsers`) — see [Controlling access on an individual service](https://cloud.google.com/run/docs/securing/managing-access).

## GitHub setup

Create a `production` [Environment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment) (Settings → Environments), and add:

- **Secret**: `DATABASE_URL` — the Neon connection string from above, with `+asyncpg`.
- **Variables**: `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_SERVICE_ACCOUNT`, `GCP_WORKLOAD_IDENTITY_PROVIDER` — the four values printed in step 6. These aren't secrets (they're identifiers, not credentials), but scoping them to the same environment keeps everything deploy-related in one place.

Once these exist, `.github/workflows/deploy-api.yml` runs automatically on the next push to `main` that touches `apps/api/`.
