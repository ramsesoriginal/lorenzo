# 0011 - Deploy target: Google Cloud Run + Neon

Status: accepted

## Context

`apps/api` needs somewhere to actually run, continuously deployed from GitHub Actions, ideally free — this is a personal, low-traffic showcase project, not a funded SaaS. Free tiers in this space were cut hard through 2026: Fly.io's free tier has been dead since October 2024; Railway now offers only a one-time $5/30-day trial, not a perpetual free tier; Koyeb closed free signups after Mistral AI acquired it in February 2026; Render's free Postgres expires 30 days after creation (14-day grace, then hard-deleted) even though its free web service is still real; AWS RDS's free tier is a time-limited trial, not perpetual; ElephantSQL shut down entirely in early 2025.

## Decision

**Google Cloud Run** for compute, **Neon** for Postgres. Both have genuinely indefinite free tiers that stayed stable or improved through 2026 rather than being cut:

- Cloud Run: real "Always Free" tier (2M requests/month, 180k vCPU-seconds, 360k GiB-seconds/month), true scale-to-zero, fast cold starts, and genuine **OIDC auth from GitHub Actions** via Workload Identity Federation — no long-lived cloud credential ever stored as a GitHub secret. Since February 2026 a billing account on file is required even to stay within the free quota (no charge if you stay under it).
- Neon: real permanent free tier (100 compute-hours/month, up to 5GB storage), autoscale-to-zero after 5 minutes idle but wakes itself on the next connection — unlike Supabase, which pauses after a week of inactivity and needs a workaround (a scheduled keepalive ping) to avoid it. Standard Postgres row-level security, no gotchas for [ADR 0002](0002-multi-tenancy-shared-schema-rls.md).

Ruled out but not disqualified: **Oracle Cloud Free Tier** is still the most raw free compute available (a genuine forever VM), but it's bare infrastructure, not a platform — no Dockerfile-native deploy, self-managed via SSH, and its free ARM allowance was quietly halved in June 2026 with no announcement. **Northflank** bundles a service and a database under one free tier, which is appealing, but wasn't verified as thoroughly (RLS support, DB persistence behavior specifically) — worth a second look if Cloud Run + Neon stops fitting.

## Consequences

- Two accounts to create and maintain (Google Cloud, Neon) instead of one — accepted, since no single provider offers a genuinely permanent free bundle of both.
- `apps/api` needs a `DATABASE_URL` pointed at Neon in production, distinct from the local Docker Compose Postgres — see [docs/operations/deployment-setup.md](../operations/deployment-setup.md) for the one-time setup this requires (not verified end-to-end by the agent that wrote it — no GCP/Neon account access from that environment).
- If either free tier gets cut the way Fly.io's or Koyeb's did, the OIDC-client boundary (apps/api only needs a `DATABASE_URL` and to be deployable from a container image) keeps switching providers a config change, not a redesign.
