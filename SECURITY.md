# Security Policy

## Supported versions

Lorenzo is pre-1.0. `apps/api` has infrastructure plus the full domain model, a read-only REST API, and Authgear-backed auth; nothing else under `apps/` exists. Only the latest commit on `main` is supported. Once apps reach 1.0, this section will track supported versions per app.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Use GitHub's private vulnerability reporting instead: go to the [Security tab](https://github.com/ramsesoriginal/lorenzo/security) → "Report a vulnerability". Expect an initial response within a few days.

Please include:

- The component affected, if applicable
- Steps to reproduce, or a proof of concept
- The potential impact as you see it

## Scope

This is a personal, self-hosted-first project. Vulnerabilities in third-party dependencies belong upstream, unless the issue is how Lorenzo uses that dependency.

**Historical issue, now fixed**: the app's own database role used to be a superuser, which bypasses PostgreSQL row-level security unconditionally regardless of any RLS policy being correctly written (multi-tenant isolation, [ADR 0002](docs/adr/0002-multi-tenancy-shared-schema-rls.md)). Fixed by a restricted, non-superuser role ([ADR 0021](docs/adr/0021-restricted-app-role-for-rls-enforcement.md)) - the production Neon role rotation is done and confirmed directly against production (its privilege flags and `FORCE ROW LEVEL SECURITY` checked, not assumed), not just deployed. No need to report this one.
