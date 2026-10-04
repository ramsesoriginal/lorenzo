"""A description is titled with its item's name (ADR 0165).

An item's displayed title is the title of its description (ADR 0019), so the title the CLI gives
a description is what every client shows for the item. Before ADR 0165 it was always
"Description"; this finds those and puts them right.
"""

from __future__ import annotations

from uuid import UUID

from lorenzo_cli.client.models import EntityDetailOut, InformationOut, InformationUpdate
from lorenzo_cli.client.ops import GET_INFORMATION, UPDATE_INFORMATION
from lorenzo_cli.client.transport import LorenzoClient

# The title every description the CLI wrote used to get, and the only one it will change.
PLACEHOLDER_TITLE = "Description"


def placeholder_description(detail: EntityDetailOut) -> InformationOut | None:
    """The entity's description, if it still has the placeholder title.

    Any other title is somebody's choice. An entity really named "Description" is left alone too:
    its title already is its name.
    """
    if detail.name == PLACEHOLDER_TITLE:
        return None
    return next(
        (
            info
            for info in detail.information
            if info.type == "description" and info.title == PLACEHOLDER_TITLE
        ),
        None,
    )


def retitle(client: LorenzoClient, tenant_id: UUID, information_id: UUID, title: str) -> None:
    """Change one description's title: read it for its ETag, then send only the title.

    Raises StaleResourceError if the row changed in between; the caller says so and the next run
    finds it again.
    """
    path = {"tenant_id": tenant_id, "information_id": information_id}
    current = client.call(GET_INFORMATION, path=path)
    client.call(
        UPDATE_INFORMATION, path=path, body=InformationUpdate(title=title), if_match=current.etag
    )
