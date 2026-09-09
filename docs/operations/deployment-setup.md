# Deployment setup (manual, one-time)

See [ADR 0011](../adr/0011-deploy-target-cloud-run-neon.md) for why and [docs/architecture/deployment.md](../architecture/deployment.md) for how the pieces connect once this is done. **Confirmed working end to end for the pre-domain-model, pre-auth baseline** (2026-09-08): a full `deploy-api.yml` run completed successfully against a real Neon project and the GCP setup below, and the deployed revision served real traffic. The domain model, RLS restricted role, and Authgear integration built since then haven't been re-verified against a live deploy — see the Authgear gap called out in "GitHub setup" below before assuming a fresh deploy today works end to end. `PROJECT_ID` must be globally unique across *all* of GCP, not just this repo — `lorenzo-api` was taken, `lorenzo-medici-api` wasn't; pick your own. Getting here took a few real fixes, each only surfaced by an actual run (a missing `README.md` in the Docker build context, asyncpg rejecting two of Neon's default libpq-only query params, the container ignoring Cloud Run's `$PORT`, new Cloud Run services being private by default) - see `deploy-api.yml`'s history for specifics.

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

## Authgear Cloud (ADR 0027)

`Settings` needs `authgear_issuer`/`authgear_jwks_url`/`authgear_audience` ([ADR 0023](../adr/0023-authgear-token-verification.md)) pointed at a real project, not the `http://localhost:4000` placeholders. Authgear Cloud, not self-hosted (ADR 0027 — self-hosting would need its own Postgres + Redis + more, no free tier fits that the way Cloud Run/Neon do):

1. Sign up at [authgear.com](https://www.authgear.com) (free tier, no card needed) and create a **production** project.
2. In the project, **Applications → New Application → OIDC Client Application** — `apps/api` never runs a login flow itself (it only verifies tokens), but registering at least one client is what lets you mint a real access token to test with later.
3. From that application's **Endpoints** section, copy the issuer URL. Fetch `<issuer>/.well-known/openid-configuration` to find `jwks_uri`.
4. This becomes `AUTHGEAR_ISSUER` and `AUTHGEAR_JWKS_URL` below. `AUTHGEAR_AUDIENCE` is the *same* issuer URL, not the client id — access tokens carry the project endpoint as `aud`, not an OIDC client id; that distinction only applies to ID tokens (see ADR 0023).

Free-tier constraints worth knowing going in: no custom domain (issuer/JWKS live on Authgear's own subdomain), 1-day log retention, and a "2 Applications" cap whose exact scope (client apps within a project, vs. a project-count ceiling) is worth confirming directly in their console rather than assuming.

## GitHub setup

Create a `production` [Environment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment) (Settings → Environments), and add:

- **Secret**: `DATABASE_URL` — the Neon connection string from above, with `+asyncpg`.
- **Variables**: `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_SERVICE_ACCOUNT`, `GCP_WORKLOAD_IDENTITY_PROVIDER` — the four values printed in step 6. `AUTHGEAR_ISSUER`, `AUTHGEAR_JWKS_URL`, `AUTHGEAR_AUDIENCE` — the values from the Authgear Cloud section above. None of these seven are secrets (they're identifiers/public URLs, not credentials), but scoping them to the same environment keeps everything deploy-related in one place.

Once these exist, `.github/workflows/deploy-api.yml` runs automatically on the next push to `main` that touches `apps/api/`. Note that a `chore`/docs-only change (like the one that first added the Authgear `env_vars` wiring) won't trigger it — the workflow's own `paths: apps/api/**` filter won't fire, so trigger it manually once (Actions → "Deploy API" → "Run workflow") to actually apply new environment variables to the live service.

## Rotating to the restricted app role (ADR 0021)

[ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md) splits one Neon role into two: a privileged one Alembic runs migrations as, and a new, restricted `lorenzo_app` (`NOSUPERUSER NOBYPASSRLS`) the deployed service actually connects as — RLS is confirmed unenforced otherwise, in production exactly as much as locally (Neon's own default/owner role is a member of `neon_superuser`, which Neon grants `BYPASSRLS`). This is a one-time manual rotation, not something CI does for you - **do this deliberately, not as a side effect of an unrelated deploy**:

1. **Add a new secret `MIGRATIONS_DATABASE_URL`**, set to today's existing `DATABASE_URL` value (the privileged connection string from the "Neon (Postgres)" section above, unchanged). This becomes what Alembic runs migrations as going forward.
2. **Pick credentials for the new restricted role** - a username (e.g. `lorenzo_app`) and a freshly generated password. You don't need to create this role in Neon's console yourself: the migration in [`8aced4b80842_create_restricted_lorenzo_app_role.py`](../../apps/api/migrations/versions/8aced4b80842_create_restricted_lorenzo_app_role.py) reads whatever username/password `database_url` carries and creates exactly that role, idempotently, the next time migrations run.
3. **Update the `DATABASE_URL` secret's value** to a connection string using those new credentials (same host/port/dbname as before - just the user and password change).
4. **Trigger a deploy** (push to `main` touching `apps/api/`, or re-run `deploy-api.yml` manually). Its migration step runs as the *privileged* role (`MIGRATIONS_DATABASE_URL`, from step 1) and creates the restricted role using the credentials named in `DATABASE_URL` (from step 3) - by the time the Cloud Run deploy step runs moments later in the same job, that role already exists and is grantable.
5. **Verify**: the deploy's own `/readyz` smoke test passing confirms the new role can connect and query at all; it doesn't by itself prove RLS is enforced under it. Confirm that separately (e.g. the same live check `test_rls_isolates_tenants_for_a_non_superuser_role` does locally, run once by hand against Neon) before considering this actually closed.
