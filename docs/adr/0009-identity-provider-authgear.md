# 0009 - Identity provider: Authgear (self-hosted OIDC)

Status: accepted

## Context

The app needs to support social login (Google, Facebook, GitHub, Discord), passkeys (WebAuthn), and magic-link email sign-in. The obvious FastAPI-native library, `fastapi-users`, is confirmed in maintenance mode with no further features planned and never supported passkeys. Hand-rolling all three (`authlib`/`httpx-oauth` for social, `webauthn`/py_webauthn for passkeys, homegrown magic links) is technically feasible — the individual libraries are healthy and maintained — but means personally owning WebAuthn ceremony correctness, magic-link token security, and account-linking logic across six different sign-in entry points into one identity. That's a lot of security-critical surface for a solo project when dedicated identity providers already solve it.

Evaluated self-hosted options with native social+passkey+magic-link support: Authgear, FusionAuth, Keycloak, Zitadel, Ory Kratos, SuperTokens. Keycloak has the broadest social-provider list and passkeys, but no native magic links, the heaviest JVM footprint, and a 2026 critical unauthenticated-account-takeover CVE (patched). Zitadel is lightest to run but has no magic-link support. Ory needs three components (Kratos/Hydra/Oathkeeper) assembled by hand. SuperTokens has the closest Python/FastAPI integration story but its passkey support is framed under MFA, not confirmed as a standalone primary method.

## Decision

**Authgear**, self-hosted, as its own service in `infra/docker-compose.yml` (needs its own Postgres + Redis). It supports social login (including Discord and Facebook, not just Google/GitHub), passkeys, and magic links natively, with a prebuilt login UI, and had no 2026 security red flags surfaced in research.

apps/api becomes an OIDC **relying party/client**, not an auth implementer: Authgear issues tokens, apps/api verifies them (standard JWT/JWKS validation) and maps the verified identity to a `User` row. Authgear never needs to know this app's tenant/membership model exists — that's a deliberate separation, see [ADR 0010](0010-user-tenant-membership-model.md).

## Consequences

- A new service (with its own Postgres + Redis) joins local dev infra — real operational weight for a solo project, accepted as the tradeoff for not hand-rolling six auth methods.
- User identity (email, name, which social/passkey/etc. methods are linked) lives in Authgear; apps/api's own `User` table holds only what's actually domain-relevant (a local user id, tenant memberships) plus a link back to Authgear's identity (its subject id).
- If Authgear turns out to be the wrong operational fit, the OIDC-client boundary means swapping it for another OIDC-compliant provider (FusionAuth was the strong runner-up) shouldn't require redesigning the authorization layer — only the token-verification wiring.
