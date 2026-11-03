"""A joined identity never grants access or becomes a second editable manuscript."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import ManuscriptMoveConflictError
from lorenzo_api.models import ManuscriptRedirect


async def require_unjoined(session: AsyncSession, entity_id: uuid.UUID) -> None:
    if await session.get(ManuscriptRedirect, entity_id):
        raise ManuscriptMoveConflictError(
            detail="This Chapter was joined. Open its destination to edit the manuscript."
        )
