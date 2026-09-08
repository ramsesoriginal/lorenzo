from fastapi import APIRouter, status
from sqlalchemy import text

from lorenzo_api.dependencies import SessionDep

router = APIRouter(tags=["observability"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, str]:
    """Liveness: is the process up? No dependencies checked on purpose."""
    return {"status": "ok"}


@router.get("/readyz", status_code=status.HTTP_200_OK)
async def readyz(session: SessionDep) -> dict[str, str]:
    """Readiness: can we actually reach the database?"""
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
