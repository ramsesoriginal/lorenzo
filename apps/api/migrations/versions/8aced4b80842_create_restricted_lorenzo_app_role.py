"""create restricted lorenzo_app role

Revision ID: 8aced4b80842
Revises: 65ef08962fe4
Create Date: 2026-09-09 00:09:24.522226

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.engine import make_url

from lorenzo_api.config import get_settings

revision: str = "8aced4b80842"
down_revision: str | None = "65ef08962fe4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# The role this migration ensures exists is whatever `database_url` (the
# app's own, now-restricted connection string) names - not a separate,
# hand-invented secret. Whoever deploys this app decides the app's role/
# password by setting DATABASE_URL; this migration just makes that role
# real. See ADR 0021.
_app_url = make_url(get_settings().database_url)
assert _app_url.username is not None, "database_url must carry a username"
assert _app_url.password is not None, "database_url must carry a password"
_APP_ROLE: str = _app_url.username
_APP_PASSWORD: str = _app_url.password


def _pg_string_literal(value: str) -> str:
    """Safely embed `value` as a single-quoted SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _pg_identifier(value: str) -> str:
    """Safely embed `value` as a double-quoted SQL identifier."""
    return '"' + value.replace('"', '""') + '"'


def upgrade() -> None:
    role_literal = _pg_string_literal(_APP_ROLE)
    password_literal = _pg_string_literal(_APP_PASSWORD)
    role_ident = _pg_identifier(_APP_ROLE)

    # CREATE ROLE has no native IF NOT EXISTS - dynamically built via
    # format()'s %I/%L (safe identifier/literal quoting) inside a DO block,
    # rather than hand-rolled string escaping, matching Postgres's own
    # idiom for this exact situation.
    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role_literal}) THEN
                EXECUTE format(
                    'CREATE ROLE %I LOGIN PASSWORD %L '
                    'NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION',
                    {role_literal}, {password_literal}
                );
            END IF;
        END $$;
    """)
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role_ident}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role_ident}"
    )
    # No "FOR ROLE ..." - defaults to the current role, which is exactly the
    # role every migration (including future ones) runs as.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role_ident}"
    )


def downgrade() -> None:
    role_literal = _pg_string_literal(_APP_ROLE)
    role_ident = _pg_identifier(_APP_ROLE)

    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {role_ident}"
    )
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role_literal}) THEN
                EXECUTE format('DROP OWNED BY %I', {role_literal});
                EXECUTE format('DROP ROLE %I', {role_literal});
            END IF;
        END $$;
    """)
