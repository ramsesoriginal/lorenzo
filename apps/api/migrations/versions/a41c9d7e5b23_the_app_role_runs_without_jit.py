"""the app role runs without JIT

ADR 0285. Past the planner's `jit_above_cost` (100,000) Postgres compiles a query with LLVM before
it runs it, every time it runs it: 117 of the 147 ms of one item read in a 5,000-entry library,
and 1.5 s of one in a 20,000-entry one. The API's queries are short and many, so compiling never
pays for itself: the setting is off for the role the app connects as, and a person who needs it
for one session can still `SET jit = on`.

A setting on the role, not on the connection: a pooler in front of the database refuses startup
parameters it does not know, and the role's own settings are applied by the server itself.

Revision ID: a41c9d7e5b23
Revises: f2b8d4a1c597
Create Date: 2026-10-13 21:30:00.000000

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.engine import make_url

from lorenzo_api.config import get_settings

revision: str = "a41c9d7e5b23"
down_revision: str | None = "f2b8d4a1c597"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# The role the app connects as, named by `database_url` as in 8aced4b80842 (ADR 0021).
_app_url = make_url(get_settings().database_url)
assert _app_url.username is not None, "database_url must carry a username"
_APP_ROLE: str = '"' + _app_url.username.replace('"', '""') + '"'


def upgrade() -> None:
    op.execute(f"ALTER ROLE {_APP_ROLE} SET jit = off")


def downgrade() -> None:
    op.execute(f"ALTER ROLE {_APP_ROLE} RESET jit")
