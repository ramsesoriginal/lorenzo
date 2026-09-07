from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.db import get_db_session

router = APIRouter(tags=["observability"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, str]:
    """Liveness: is the process up? No dependencies checked on purpose."""
    return {"status": "ok"}


@router.get("/readyz", status_code=status.HTTP_200_OK)
async def readyz(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    """Readiness: can we actually reach the database?"""
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
