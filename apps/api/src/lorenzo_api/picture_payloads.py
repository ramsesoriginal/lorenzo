"""Pictures on an entry's information (K8, ADR 0237): the upload check and the writes that
routers/information.py, routers/payloads.py and routers/entities.py share. Core mechanics only -
no auth and no commit, like profile_pictures.py, which sets the precedent for the allow-list and
the cap.
"""

import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.client_ids import insert_with_client_id
from lorenzo_api.config import get_settings
from lorenzo_api.exceptions import InvalidPictureError
from lorenzo_api.models import Payload, PayloadPicture
from lorenzo_api.profile_pictures import ALLOWED_IMAGE_CONTENT_TYPES
from lorenzo_api.svg_lint import SvgRefused, check_svg

SVG_CONTENT_TYPE = "image/svg+xml"
# What an entry's picture may be: the types of a profile picture, and an SVG that passes the lint
# (ADR 0360).
PICTURE_PAYLOAD_CONTENT_TYPES = ALLOWED_IMAGE_CONTENT_TYPES | {SVG_CONTENT_TYPE}


async def read_picture_upload(file: UploadFile) -> tuple[bytes, str]:
    """The bytes and declared content type of an uploaded picture: an allow-listed type (trusted
    as declared, as for every picture here, ADR 0017), at most `picture_max_bytes`, and for an SVG
    a document the lint accepts, else a 422.
    """
    if file.content_type not in PICTURE_PAYLOAD_CONTENT_TYPES:
        raise InvalidPictureError(
            detail=(
                f"Unsupported content type '{file.content_type}'; expected one of "
                f"{sorted(PICTURE_PAYLOAD_CONTENT_TYPES)}"
            )
        )
    max_bytes = get_settings().picture_max_bytes
    # One byte more than the cap is enough to know it is over, without reading all of a huge one.
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InvalidPictureError(detail=f"The picture exceeds the {max_bytes}-byte limit")
    if file.content_type == SVG_CONTENT_TYPE:
        try:
            check_svg(data)
        except SvgRefused as refused:
            raise InvalidPictureError(detail=refused.reason) from None
    return data, file.content_type


async def add_picture_payload(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    data: bytes,
    file_type: str,
    payload_id: uuid.UUID | None = None,
) -> Payload:
    """A picture payload at the end of the information's payloads (its `order` is appended by the
    database's trigger, under the entry's information lock the caller holds)."""
    payload = Payload(tenant_id=tenant_id, information_id=information_id)
    if payload_id is None:
        session.add(payload)
        await session.flush()
    else:
        payload.id = payload_id
        await insert_with_client_id(session, payload)
    session.add(
        PayloadPicture(payload_id=payload.id, tenant_id=tenant_id, data=data, file_type=file_type)
    )
    await session.flush()
    return payload
