# 0027 - Authgear Cloud, not self-hosted

Status: accepted

Supersedes: the self-hosted decision in [ADR 0009](0009-identity-provider-authgear.md) (Authgear itself, and the OIDC relying-party design that separates identity from tenant/membership, both stand unchanged — see that ADR's own consequences: "swapping it for another OIDC-compliant provider... shouldn't require redesigning the authorization layer — only the token-verification wiring"). Also supersedes [ADR 0023](0023-authgear-token-verification.md)'s "Local Authgear: a separate doc and compose stack" subsection specifically — that ADR's actual subject, token-verification mechanics, is unaffected by hosting model and needs no other changes.

## Context

[ADR 0023](0023-authgear-token-verification.md) shipped the full token-verification side (`Settings.authgear_issuer`/`authgear_jwks_url`/`authgear_audience`, real PyJWT/`PyJWKClient` verification in `dependencies.py`) but explicitly left "actually deploying Authgear to production, and registering a real OIDC client against it... out of scope." Picking that up surfaced a real question ADR 0009 never asked: self-hosted Authgear needs its own Postgres **and Redis** (plus, per the reference [`authgear-example-docker-compose`](https://github.com/authgear/authgear-example-docker-compose) stack, MinIO, nginx, an admin portal, and init jobs - roughly seven services). [ADR 0011](0011-deploy-target-cloud-run-neon.md) chose Cloud Run + Neon specifically for their genuine, permanent free tiers, for a project explicitly framed as "personal, low-traffic... not a funded SaaS" - and Redis has no comparable serverless/scale-to-zero free tier on GCP. [ADR 0008](0008-deferred-taskiq-and-fastapi-limiter.md) already deferred unrelated work once for exactly this reason ("adding a new infrastructure service (Redis) isn't justified").

Authgear also offers **Authgear Cloud**, their hosted SaaS - not evaluated at all in ADR 0009, which only compared self-hosted identity providers against each other. Checked: Authgear Cloud has a genuinely free tier (unlimited MAU, no card required).

## Decision

Use **Authgear Cloud** for both production and local dev, not self-hosted Authgear. Nothing about the token-verification code changes - `apps/api` only ever needed an issuer URL, a JWKS URL, and an audience value; it never cared whether the service behind them was self-hosted or not. This is exactly the low-risk swap ADR 0009's own consequences anticipated.

Free-tier constraints worth recording, since they're real and durable, not just setup-time trivia:

- No custom domain - issuer/JWKS URLs live on Authgear's own subdomain, and the hosted login UI carries Authgear branding. Acceptable for this project's own low-traffic, cost-conscious posture (the same posture that chose Cloud Run/Neon over anything requiring a paid tier).
- Log retention is 1 day - a real limit if a production auth failure needs debugging after the fact, not addressed further here.
- The pricing page describes a "2 Applications" cap. Confirmed at signup: [PENDING - fill in after Step 1 of the setup, whether this means two OIDC client apps within one project or effectively caps the account to fewer usable projects than local dev + production would want].

## Consequences

- Local dev's self-hosted setup (`docs/operations/local-authgear-setup.md`, the `authgear-example-docker-compose` clone-and-run flow) is retired in favor of a Cloud dev project, provided the free-tier project limit allows a second project separate from production - per that same doc's own admission, the self-hosted flow was never personally stood up and clicked through, so nothing working is being broken.
- `infra/docker-compose.yml` needed no change either way - Authgear was deliberately never folded into it (ADR 0023), so this decision doesn't touch it.
- No new infrastructure to run, monitor, or pay for - the tradeoff is depending on a third-party-hosted identity service rather than one this project fully controls, accepted on the same basis ADR 0009 already accepted depending on Authgear's software at all.
- If Authgear Cloud's free tier ever stops fitting (traffic, feature, or policy changes), the OIDC relying-party boundary means falling back to self-hosted (ADR 0009's original design) is a config change - new issuer/JWKS/audience values - not a code change.
