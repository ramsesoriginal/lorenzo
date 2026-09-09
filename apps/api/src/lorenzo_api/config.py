from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
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
