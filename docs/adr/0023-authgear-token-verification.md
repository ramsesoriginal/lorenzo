# 0023 - Authgear token verification

Status: accepted

## Context

[ADR 0009](0009-identity-provider-authgear.md) decided Authgear as the identity provider, with `apps/api` as a pure OIDC relying party: Authgear issues tokens through its own hosted login UI, `apps/api` only verifies them and maps the verified subject to the `app_user` row [ADR 0022](0022-user-tenant-membership.md) built. This ADR is that verification mechanism, plus how it plugs into the tenant-scoping the REST API already has ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)).

## Decision

### Library: PyJWT, not python-jose

`python-jose` is unmaintained (an unpatched algorithm-confusion CVE, a dependency on the equally unmaintained `ecdsa` package) - FastAPI's own tutorial migrated off it for exactly this reason. `pyjwt[crypto]` is the current, actively-recommended choice; its `PyJWKClient` covers JWKS fetch-and-cache with nothing extra to write.

### Config: explicit issuer/JWKS URL/audience, not dynamic discovery

`Settings` gains `authgear_issuer`, `authgear_jwks_url`, `authgear_audience` - set directly rather than fetched from `/.well-known/openid-configuration` at startup. One less moving part; Authgear's shape is stable enough that hand-configuring the two URLs isn't a real burden. **Authgear-specific gotcha, easy to get backwards**: the *access* token's `aud` claim is the project's endpoint URL, not the OIDC client id - that's only true for *ID* tokens. `authgear_audience` must be the endpoint URL.

### `get_jwks_client()`: a singleton, not built per-request

```python
@lru_cache
def get_jwks_client() -> PyJWKClient:
    return PyJWKClient(get_settings().authgear_jwks_url)
```

Mirrors `get_settings()`'s own `@lru_cache` pattern. `PyJWKClient` caches the whole JWKS response for 5 minutes internally (its own default) - building a fresh client per request would throw that cache away and pay a blocking fetch on every single request. Exposed as its own dependency (`get_jwks_client`) specifically so tests can `app.dependency_overrides[get_jwks_client] = ...` and point it at a fake server, rather than needing to monkeypatch anything.

### `verify_token`: `HTTPBearer` + explicit algorithms/audience/issuer, off the event loop

`HTTPBearer()` (FastAPI's own security scheme) extracts and validates the `Bearer` scheme - also gives Swagger UI a real "Authorize" button for free. `PyJWKClient.get_signing_key_from_jwt` and `jwt.decode` are both synchronous under the hood (stdlib `urllib`, no async support, no injectable transport) - both run through `run_in_threadpool` rather than called inline, or an occasional blocking JWKS fetch would freeze the event loop for every concurrent request. `algorithms=["RS256"]`, `audience=...`, `issuer=...` are all passed explicitly to `jwt.decode` - it silently skips the audience/issuer checks entirely if either kwarg is omitted, and never assume `algorithms` from the token's own header (the classic "alg confusion" class of vulnerability). Any `jwt.PyJWTError` (expired, bad signature, wrong audience, wrong issuer, ...) becomes a new typed `InvalidTokenError` (`fastapi_problem`'s `UnauthorisedProblem`, 401) - matching the existing typed-exception convention (`exceptions.py`).

### `get_current_user`: atomic upsert, not check-then-insert

Mapping a verified `sub` to an `app_user` row on first request needs an atomic `INSERT ... ON CONFLICT (authgear_subject_id) DO UPDATE ... RETURNING`, not a `SELECT` followed by an `INSERT` - two concurrent first-requests from a brand-new subject would otherwise race (both miss the `SELECT`, the second `INSERT` hits the `UNIQUE` constraint). The dependency commits this upsert itself - `get_db_session` has no autocommit-at-request-end of its own (every route so far has been read-only, so this has never come up before), and nothing later in a read-only route like `GET /me` would otherwise persist it.

### `get_tenant_context` gains a real membership check

Folded into the existing dependency (not a second one every route must remember, per ADR 0020's own stated reasoning), now depending on `CurrentUser` too:

```python
async def get_tenant_context(tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> uuid.UUID:
    if await session.get(Tenant, tenant_id) is None:
        raise TenantNotFoundError(...)
    if await session.get(Membership, (tenant_id, user.id)) is None:
        raise TenantNotFoundError(...)  # same class, same body - see below
    ...
```

**"Tenant doesn't exist" and "tenant exists but you're not a member" raise the exact same `TenantNotFoundError`** - same class, same body shape, not just the same status code - so a non-member can't distinguish a real tenant they're excluded from from one that was never real, the same way GitHub's private repos 404 rather than 403 for a non-collaborator. A different exception *class* with the same status would still leak the distinction through `type`/`title`, so it has to be the identical class, not just a matching status code.

**What this does *not* yet cover**: RFC 0002's full campaign-access rule (`player`/`campaign_gm`/orga-without-opt-out) needs tables that don't exist until later sub-slices. A user can validly have zero `membership` rows and still legitimately access campaigns as an ordinary player - `get_tenant_context`'s check is tenant-wide-access only, by design, not a stand-in for that fuller rule. A future `get_campaign_context` will need to implement RFC 0002's actual rule once campaign-scoped routes exist - additive, not a replacement.

### `membership`'s RLS policy gains a second, self-access condition

Discovered building `GET /me`, not anticipated up front: it needs `user.memberships` (a `membership` row set spanning *every* tenant the caller belongs to), but `membership` is RLS-protected by `tenant_id`, and `/me` is deliberately not tenant-scoped - there's no single `app.tenant_id` to set for that query. `membership`'s policy becomes:

```sql
tenant_id = current_setting('app.tenant_id', true)::uuid
OR user_id = current_setting('app.user_id', true)::uuid
```

`current_setting(name, true)` (the two-argument form) returns `NULL` rather than raising when unset - confirmed empirically - so a `NULL::uuid = tenant_id` comparison just evaluates false rather than erroring, unlike every other RLS-protected table's stricter single-argument form (which still hard-fails on a genuinely forgotten `app.tenant_id` - this change is scoped to `membership` alone). `get_current_user` sets `app.user_id` on *every* authenticated request now, tenant-scoped or not - **after** its own upsert's commit, not before: `set_config(..., is_local=true)` only lasts for the current transaction, and the commit ends the one the upsert ran in. The self-access clause can never leak another user's memberships - it's pinned to the caller's own verified `id`, not a wildcard - so this only ever narrows what a user can already legitimately see about themselves across tenants, never anyone else's data.

### `GET /me`: the one new route

Exists purely to prove the whole pipeline end-to-end over real HTTP - current user's id plus their tenant memberships - not the start of a fuller `/users` API. Lives at bare `/me`, not nested under `/tenants/{tenant_id}/...` - it's about the caller's own identity across every tenant they belong to, not scoped to one.

### Local Authgear: docker-compose service, not personally verified end-to-end

`infra/docker-compose.yml` gains an Authgear service block modeled on the reference [`authgear-example-docker-compose`](https://github.com/authgear/authgear-example-docker-compose) (its own Postgres with `pg_partman`, Redis, MinIO, nginx, the main auth server, the admin portal) - **not** part of CI (see below for why), and **not personally stood up and clicked through by this ADR's author**: doing so needs pulling several GB of images and completing the Portal's own OIDC-client-registration UI by hand, which is real, but is a one-time, human-driven local setup step, not something meaningfully provable by an automated check. What *is* fully verified is the application code's own token-verification path (next section) - that's the actual engineering risk here, and it's proven against a real (if synthetic) JWKS endpoint, not skipped.

### Testing: a real fake-JWKS server, not the full Authgear stack

Spinning up all ~7 Authgear containers per test run is heavy and isn't needed to prove the verification *code* is correct. Instead: a real RSA keypair (`cryptography`), served as a real JWKS document over a real local `http.server.HTTPServer` (a background daemon thread - simplest option, and matches `PyJWKClient`'s own synchronous nature, no event-loop coordination needed), with test tokens signed against the private half via `jwt.encode`. `PyJWKClient` does its real fetch-and-verify against this real server - only the issuer is fake, not the mechanism. `get_jwks_client` is overridden via `app.dependency_overrides` to point at it - no monkeypatching.

**Two client fixtures, not one**: the existing `client` fixture (used by ~34 existing REST API tests across `test_api_*.py`, none of which are testing auth itself) gets `get_current_user` overridden to a fixed, session-scoped test `User` - those tests add one `Membership` row per tenant they create and otherwise don't change, rather than each needing to mint and attach a real signed token for a concern they aren't testing. A new `raw_client` fixture (no override) is for this slice's own dedicated auth tests, which supply real tokens against the fake JWKS server to prove the actual mechanism - valid token, expired, wrong audience, wrong issuer, bad signature, unknown tenant, known tenant without membership (same shape as unknown), and first-request auto-provisioning.

## Consequences

- Every existing tenant-scoped REST test needs a `Membership` row alongside whatever `Tenant` it creates, or `get_tenant_context` now rejects it - a real, one-time retrofit across `test_api_entities.py`/`test_api_items.py`/`test_api_item_instances.py`/`test_api_payloads.py`.
- Actually deploying Authgear to production, and registering a real OIDC client against it, remains explicitly out of scope for this slice (see the vertical-slice plan's own stated boundary) - `authgear_issuer`/`authgear_jwks_url`/`authgear_audience` need real values before any of this works against a real instance anywhere, local or deployed.
- `PyJWKClient`'s 5-minute JWKS cache means a key rotated on the Authgear side takes up to 5 minutes to propagate here - acceptable, not addressed further.
