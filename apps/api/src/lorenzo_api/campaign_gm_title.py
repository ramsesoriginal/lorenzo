"""What a campaign calls its game master - ADR 0294, RFC 0040 section 4.

A label and not a role: two texts, the singular and the plural, written together. A campaign that
has set neither says "GM" and "GMs"; the API fills that in on every read, so no client holds the
default.
"""

import re

from lorenzo_api.exceptions import CampaignGmTitleInvalidError

__all__ = ["DEFAULT_GM_TITLE", "DEFAULT_GM_TITLE_PLURAL", "MAX_GM_TITLE", "normalise_gm_titles"]

DEFAULT_GM_TITLE = "GM"
DEFAULT_GM_TITLE_PLURAL = "GMs"
MAX_GM_TITLE = 30

# Letters and digits of any script, spaces and the punctuation of a name. Nothing that reads as
# markup in HTML, Markdown or a Discord message, no control character and no line break.
_PLAIN = re.compile(r"(?:[^\W_]|[ '’\-.,&/()])+")


def _one(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) > MAX_GM_TITLE:
        raise CampaignGmTitleInvalidError(
            detail=f"A title for the GM is at most {MAX_GM_TITLE} characters"
        )
    if _PLAIN.fullmatch(text) is None:
        raise CampaignGmTitleInvalidError(
            detail="A title for the GM is plain text: letters, digits, spaces and the punctuation "
            "of a name"
        )
    return text


def normalise_gm_titles(title: str | None, plural: str | None) -> tuple[str | None, str | None]:
    """The pair to keep: both texts, trimmed, or `(None, None)` for the default. Either both are
    given or both are empty - the plural is not the singular with an `s`, so none is made up."""
    one, many = _one(title), _one(plural)
    if not one and not many:
        return None, None
    if not one or not many:
        raise CampaignGmTitleInvalidError(
            detail="Give the title for the GM and its plural together, or neither"
        )
    return one, many
