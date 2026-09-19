import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
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
