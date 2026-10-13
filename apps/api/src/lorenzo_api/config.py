import json
from functools import lru_cache
from typing import Annotated

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # What the running app itself connects as - a restricted, non-superuser
    # role (see ADR 0021) that RLS actually applies to. NOT what Alembic
    # connects as; see migrations_database_url below.
    database_url: str = "postgresql+asyncpg://lorenzo_app:lorenzo_app@localhost:55432/lorenzo"

    # What Alembic connects as - stays privileged, since creating tables/
    # roles/policies needs it. This is the same connection the app itself
    # used before ADR 0021 restricted it.
    migrations_database_url: str = "postgresql+asyncpg://lorenzo:lorenzo@localhost:55432/lorenzo"

    # Authgear (ADR 0009/0023) - apps/api is a pure OIDC relying party, these
    # three fully describe what it needs to verify tokens. Local-dev
    # placeholders; real values needed before this works against any actual
    # instance. authgear_audience is the *project endpoint* URL, not an
    # OIDC client id - that distinction only applies to ID tokens, not the
    # access tokens this app actually verifies (see ADR 0023).
    authgear_issuer: str = "http://localhost:4000"
    authgear_jwks_url: str = "http://localhost:4000/oauth2/jwks"
    authgear_audience: str = "http://localhost:4000"

    # UserInfo endpoint (ADR 0075) - the access token this app verifies
    # carries no email claim by default (only Authgear's own hook mechanism
    # can add one), so email is instead fetched here, using the caller's own
    # access token as the Bearer credential, once per user.
    authgear_userinfo_url: str = "http://localhost:4000/oauth2/userinfo"

    # The Authgear-Portal-configured role key that gates POST /tenants -
    # see ADR 0033/RFC 0012. Not fixed by this codebase beyond this one
    # setting, mirroring authgear_issuer/authgear_jwks_url/authgear_audience's
    # own pattern for IdP-adjacent config: Authgear stays the single source
    # of truth for who holds it, this app just needs to know its name.
    # Underscore, not hyphen: confirmed empirically against a real Authgear
    # project that role *keys* can't contain "-" at all - the portal silently
    # rewrites it to "_" on save, so a role named "tenant-creator" ends up
    # with the key "tenant_creator" (see ADR 0033's addendum).
    tenant_creator_role_key: str = "tenant_creator"

    # Same mechanism, gating /admin/* instead (ADR 0057) - a platform-wide
    # capability orthogonal to tenant membership, not assignable via this
    # API, mirroring tenant_creator_role_key's own precedent.
    platform_operator_role_key: str = "platform-operator"

    # CORS (ADR 0048) - space-separated exact origins in the
    # CORS_ALLOWED_ORIGINS env var, e.g. "https://a.example.com
    # https://b.example.com". Defaults to empty (no cross-origin browser
    # access at all), matching this app's other fail-closed defaults - curl/
    # server-to-server callers are unaffected either way, CORS only ever
    # restricts browser JS.
    # `NoDecode`: without it, pydantic-settings JSON-decodes this field's raw
    # env string itself, in its own env-source layer, *before* any
    # field_validator below ever runs - confirmed the hard way, not assumed
    # (a `mode="before"` validator alone did nothing; the crash traced back
    # into pydantic_settings' own EnvSettingsSource, never reaching this
    # class at all). NoDecode defers all decoding to _parse_cors_origins.
    cors_allowed_origins: Annotated[list[str], NoDecode] = []

    # The registry of app links (ADR 0273): where the Lorenzo apps live. Official Cloudflare
    # Pages addresses by default; a deployment (or a custom domain) overrides them with the
    # env variables of the same name. GET /app-links serves them, so no app carries another
    # app's address in its own variable.
    account_hub_url: str = "https://lorenzo-account-hub.pages.dev"
    inventory_web_url: str = "https://lorenzo-inventory-web.pages.dev"
    beings_url: str = "https://lorenzo-beings.pages.dev"
    bench_url: str = "https://lorenzo-bench.pages.dev"
    # Optional per-link overrides in APP_LINK_TEMPLATES: space-separated `name=template`
    # pairs (like CORS_ALLOWED_ORIGINS, no commas and no JSON, for the deploy action's sake),
    # e.g. "item=https://i.example.com/i/{tenant}/{id}". NoDecode, as cors_allowed_origins.
    app_link_templates: Annotated[dict[str, str], NoDecode] = {}

    @field_validator(
        "account_hub_url", "inventory_web_url", "beings_url", "bench_url", mode="before"
    )
    @classmethod
    def _blank_app_url_is_the_default(cls, v: object, info: ValidationInfo) -> object:
        # An unset GitHub variable reaches the container as "" (see cors_allowed_origins):
        # that must mean "the official address", not an empty one.
        if isinstance(v, str) and not v.strip():
            return cls.model_fields[info.field_name or ""].default
        return v

    @field_validator("app_link_templates", mode="before")
    @classmethod
    def _parse_app_link_templates(cls, v: object) -> object:
        if isinstance(v, str):
            pairs: dict[str, str] = {}
            for part in v.split():
                name, sep, template = part.partition("=")
                if not sep or not name or not template:
                    raise ValueError(f"APP_LINK_TEMPLATES entry {part!r} is not name=template")
                pairs[name] = template
            return pairs
        return v

    # ADR 0092's in-process backstop for the two public invite-link routes:
    # requests per minute per client address, per instance. Cloud Run runs
    # several instances, so this only limits each one separately - it is a
    # backstop, and the edge rate-limit rule (docs/operations/invite-link-
    # rate-limiting.md) is the real control. 0 disables it.
    invite_rate_limit_per_minute: int = 30
    # How many reverse proxies sit in front of this app whose
    # X-Forwarded-For entry can be trusted. 0 (the default, right for local
    # dev and tests) keys the limiter on the direct peer address. Behind
    # Cloud Run's front end this must be 1, or every caller shares one
    # bucket: the *rightmost* entry is the address that proxy actually saw,
    # whereas anything to its left is client-supplied and spoofable.
    invite_rate_limit_trusted_proxy_hops: int = 0

    # Personal access tokens (ADR 0268): the in-process backstop on the device-code routes - per
    # client address for the two unauthenticated ones, per signed-in user for the ones that look
    # up or approve a code. 0 disables a limit. Where the hub's "Connect a device" page lives
    # comes from the registry of app links (ADR 0273, `account_hub_url` above).
    device_rate_limit_per_minute: int = 60
    device_lookup_rate_limit_per_minute: int = 20

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        # Originally a JSON array (`["https://a", "https://b"]`), like every
        # other list[str] setting pydantic-settings JSON-decodes from an env
        # var. Real production use surfaced a real problem with that: more
        # than one origin means a literal `,` *inside* the value, and
        # google-github-actions/deploy-cloudrun's `env_vars` joins entries
        # with `,` too - the comma inside the value collided with the comma
        # between entries, and gcloud silently split the value at the wrong
        # place. The container received a truncated, invalid-JSON fragment
        # and crashed at Settings() construction, before ever binding to a
        # port - confirmed against a real failed deploy, not assumed. A
        # value with no comma at all sidesteps the collision entirely rather
        # than needing every layer between here and there (this action, its
        # own gcloud invocation, and gcloud's own list-argument parsing) to
        # agree on some escaping convention. Still accepts the original JSON
        # form (any existing `.env` using it keeps working) - only a plain
        # string that isn't JSON gets split on whitespace instead.
        if isinstance(v, str) and v.strip() == "":
            return []
        if isinstance(v, str) and not v.strip().startswith("["):
            return v.split()
        if isinstance(v, str):
            return json.loads(v)
        return v

    # Profile pictures (ADR 0056) - bytes are stored directly in Postgres
    # (matching payload_picture's own precedent, ADR 0017), so this caps
    # both the request body size and the row size, not a bucket quota.
    profile_picture_max_bytes: int = 2_000_000

    # Pictures on an entry's information (K8, ADR 0237): the same cap to start with, a setting of
    # its own because a cover or a map may want more than an avatar. Bytes in Postgres here too.
    picture_max_bytes: int = 2_000_000

    @field_validator("database_url", "migrations_database_url")
    @classmethod
    def _normalize_for_asyncpg(cls, v: str) -> str:
        # Neon's default pooled connection string is written for libpq-style
        # drivers. SQLAlchemy's asyncpg dialect passes query params through
        # verbatim as connect() kwargs, so two of Neon's defaults crash with
        # "connect() got an unexpected keyword argument '...'":
        #   - sslmode=require - asyncpg's own param is `ssl`, same value
        #     vocabulary (`require`, `verify-full`, ...), just a different
        #     name, so it's renamed rather than dropped.
        #   - channel_binding=require - no asyncpg connect() equivalent at
        #     all, so it's dropped.
        url = make_url(v)
        sslmode = url.query.get("sslmode")
        to_drop = [k for k in ("channel_binding", "sslmode") if k in url.query]
        if to_drop:
            url = url.difference_update_query(to_drop)
        if isinstance(sslmode, str):
            url = url.update_query_dict({"ssl": sslmode})
        return url.render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
