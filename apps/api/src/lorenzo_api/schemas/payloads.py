from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from lorenzo_api.models import Payload


class PayloadDescriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: Literal["description"] = "description"
    content: str
    locale: str


class PayloadNumberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: Literal["number"] = "number"
    value: Decimal


class PayloadPictureOut(BaseModel):
    kind: Literal["picture"] = "picture"
    url: str
    file_type: str


class PayloadDocumentOut(BaseModel):
    kind: Literal["document"] = "document"
    url: str
    filename: str
    file_type: str


PayloadOut = Annotated[
    PayloadDescriptionOut | PayloadNumberOut | PayloadPictureOut | PayloadDocumentOut,
    Field(discriminator="kind"),
]


def payload_to_schema(payload: Payload, request: Request) -> PayloadOut:
    """Resolves Payload's polymorphic shape (no discriminator column - see
    ADR 0017/0020) by checking which relationship is populated. Picture/
    document payloads never inline their bytes - they carry a `url` built
    from the named "payload_content" route rather than a hand-strung path.
    """
    if payload.description is not None:
        return PayloadDescriptionOut.model_validate(payload.description)
    if payload.number is not None:
        return PayloadNumberOut.model_validate(payload.number)
    if payload.picture is not None:
        url = str(
            request.url_for("payload_content", tenant_id=payload.tenant_id, payload_id=payload.id)
        )
        return PayloadPictureOut(url=url, file_type=payload.picture.file_type)
    if payload.document is not None:
        url = str(
            request.url_for("payload_content", tenant_id=payload.tenant_id, payload_id=payload.id)
        )
        return PayloadDocumentOut(
            url=url, filename=payload.document.filename, file_type=payload.document.file_type
        )
    raise ValueError(f"Payload {payload.id} has no populated concrete kind")
