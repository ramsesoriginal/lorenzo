"""Times the updates of the bridge by a library (the op whose attachment handling is quadratic)
five times, whatever R2_PATCH_LOCAL_OF says:  python -m spike_r2.patched_run 20000"""

from __future__ import annotations

import asyncio
import os
import sys

from asgi_lifespan import LifespanManager

from spike_r2.common import app, load_state, timed
from spike_r2.measure import OPS, World, set_visibility


async def run(size: int) -> None:
    w = World(load_state(size))
    async with LifespanManager(app):
        await set_visibility([w.core, w.bridge], "public")
        t = await timed("updates_stack_bridge", lambda: OPS["updates_stack_bridge"](w), reps=3)
        print("patched" if os.environ.get("R2_PATCH_LOCAL_OF") else "as is", t.as_dict())


asyncio.run(run(int(sys.argv[1])))
