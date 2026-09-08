# Security Policy

## Supported versions

Lorenzo is pre-1.0. `apps/api` has infrastructure plus a first, minimal domain table (no auth yet); nothing else under `apps/` exists. Only the latest commit on `main` is supported. Once apps reach 1.0, this section will track supported versions per app.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Use GitHub's private vulnerability reporting instead: go to the [Security tab](https://github.com/ramsesoriginal/lorenzo/security) → "Report a vulnerability". Expect an initial response within a few days.

Please include:

- The component affected, if applicable
- Steps to reproduce, or a proof of concept
- The potential impact as you see it

## Scope

This is a personal, self-hosted-first project. Vulnerabilities in third-party dependencies belong upstream, unless the issue is how Lorenzo uses that dependency.

**Known, already-tracked issue**: the app's own database role is currently a superuser, which bypasses PostgreSQL row-level security unconditionally — multi-tenant isolation (see [ADR 0002](docs/adr/0002-multi-tenancy-shared-schema-rls.md)) is not actually enforced yet, independent of any RLS policy being correctly written. No real multi-tenant data exists yet. Tracked as a required fix before this holds anything real — no need to report this specific one.
