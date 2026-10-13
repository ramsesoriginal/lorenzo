"""ADR 0285: the role the app connects as runs without JIT.

Past the planner's `jit_above_cost` Postgres compiles a query with LLVM every time it runs it; for
the short queries of this API that cost more than the query did, so the role has it off.
"""

from sqlalchemy import text

from lorenzo_api.db import engine


async def test_the_app_role_runs_without_jit() -> None:
    async with engine.connect() as connection:
        assert (await connection.execute(text("SHOW jit"))).scalar_one() == "off"
