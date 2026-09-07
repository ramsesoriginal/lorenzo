# Security Policy

## Supported versions

Lorenzo is pre-1.0. `apps/api` exists as infrastructure only (no domain models, no auth yet); nothing else under `apps/` exists. Only the latest commit on `main` is supported. Once apps reach 1.0, this section will track supported versions per app.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Use GitHub's private vulnerability reporting instead: go to the [Security tab](https://github.com/ramsesoriginal/lorenzo/security) → "Report a vulnerability". Expect an initial response within a few days.

Please include:

- The component affected, if applicable
- Steps to reproduce, or a proof of concept
- The potential impact as you see it

## Scope

This is a personal, self-hosted-first project. Vulnerabilities in third-party dependencies belong upstream, unless the issue is how Lorenzo uses that dependency.
