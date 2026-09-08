from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://lorenzo:lorenzo@localhost:55432/lorenzo"

    @field_validator("database_url")
    @classmethod
    def _rewrite_sslmode_for_asyncpg(cls, v: str) -> str:
        # asyncpg's connect() takes `ssl`, not `sslmode` - SQLAlchemy's asyncpg
        # dialect passes query params through verbatim as kwargs, so Neon's
        # default `?sslmode=require` crashes with
        # "connect() got an unexpected keyword argument 'sslmode'" instead of
        # being understood. Same value vocabulary, just the wrong key name.
        url = make_url(v)
        sslmode = url.query.get("sslmode")
        if isinstance(sslmode, str):
            url = url.difference_update_query(["sslmode"]).update_query_dict({"ssl": sslmode})
        return url.render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
