from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from lorenzo_api import app_links
from lorenzo_api.config import Settings, get_settings
from lorenzo_api.schemas.app_links import AppLinksOut

router = APIRouter(tags=["app-links"])

# Short on purpose: an operator who moves an app sees clients follow within minutes.
CACHE_CONTROL = "public, max-age=300"


@router.get("/app-links", response_model=AppLinksOut, response_model_exclude_none=True)
async def get_app_links(
    response: Response, settings: Annotated[Settings, Depends(get_settings)]
) -> dict[str, Any]:
    """The registry of app links (ADR 0273). Public: it says nothing about any library. An app or
    link a deployment has not set (`legal`, `support_url`, ADR 0439) is left out, not null."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    return app_links.document(settings)
