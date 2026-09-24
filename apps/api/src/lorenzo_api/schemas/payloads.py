import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Request
from pydantic import BaseModel, Field

from lorenzo_api.models import Payload


class _PayloadOutBase(BaseModel):
    """What every payload kind shares (ADR 0101): its own `id` to address
    it by (PATCH .../payloads/{id}), its position within the Information
    bundle, and `updated_at` - the value its ETag/If-Match token derives
    from (ADR 0042).
    """

    id: uuid.UUID
    order: int
    updated_at: datetime


class PayloadDescriptionOut(_PayloadOutBase):
    kind: Literal["description"] = "description"
    content: str
    locale: str


class PayloadNumberOut(_PayloadOutBase):
    kind: Literal["number"] = "number"
    value: Decimal


class PayloadPictureOut(_PayloadOutBase):
    kind: Literal["picture"] = "picture"
    url: str
    file_type: str


class PayloadDocumentOut(_PayloadOutBase):
    kind: Literal["document"] = "document"
    url: str
    filename: str
    file_type: str


PayloadOut = Annotated[
    PayloadDescriptionOut | PayloadNumberOut | PayloadPictureOut | PayloadDocumentOut,
    Field(discriminator="kind"),
]


def description_payload_out(payload: Payload) -> PayloadDescriptionOut:
    """payload.description must be loaded and non-None."""
    assert payload.description is not None
    return PayloadDescriptionOut(
        id=payload.id,
        order=payload.order,
        updated_at=payload.updated_at,
        content=payload.description.content,
        locale=payload.description.locale,
    )


class PayloadDescriptionUpdate(BaseModel):
    """PATCH /tenants/{tenant_id}/payloads/{payload_id} - see ADR 0101.
    Description payloads only. Merge-patch semantics: an omitted field is
    left alone. `content` is opaque text - no parsing or validation
    (LorenzoScript, RFC 0027, is a client-side convention).
    """

    content: str | None = None
    locale: str | None = None


def payload_to_schema(payload: Payload, request: Request) -> PayloadOut:
    """Resolves Payload's polymorphic shape (no discriminator column - see
    ADR 0017/0020) by checking which relationship is populated. Picture/
    document payloads never inline their bytes - they carry a `url` built
    from the named "payload_content" route rather than a hand-strung path.
    """
    common = {"id": payload.id, "order": payload.order, "updated_at": payload.updated_at}
    if payload.description is not None:
        return description_payload_out(payload)
    if payload.number is not None:
        return PayloadNumberOut(**common, value=payload.number.value)
    if payload.picture is not None:
        url = str(
            request.url_for("payload_content", tenant_id=payload.tenant_id, payload_id=payload.id)
        )
        return PayloadPictureOut(**common, url=url, file_type=payload.picture.file_type)
    if payload.document is not None:
        url = str(
            request.url_for("payload_content", tenant_id=payload.tenant_id, payload_id=payload.id)
        )
        return PayloadDocumentOut(
            **common,
            url=url,
            filename=payload.document.filename,
            file_type=payload.document.file_type,
        )
    raise ValueError(f"Payload {payload.id} has no populated concrete kind")
