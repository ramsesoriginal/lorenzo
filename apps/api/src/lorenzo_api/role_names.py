"""The words a person reads for a role and for the place it is held in (ADR 0194, RFC 0040).

A membership role is `owner`, `orga` or `author` in the API and the tables; a person reads Owner,
Organizer and Author, and a tenant of kind `play` is a library to them and one of kind `repository`
a repository. The API's own notification text goes through here, so none of it carries a raw value
or the word tenant.
"""

from lorenzo_api.models import MembershipRole, TenantKind

__all__ = ["role_label", "role_phrase", "tenant_word"]

_LABELS = {
    MembershipRole.OWNER: "an Owner",
    MembershipRole.ORGA: "an Organizer",
    MembershipRole.AUTHOR: "an Author",
}


def role_phrase(role: MembershipRole) -> str:
    """The role with its article, as a sentence wants it: "an Organizer"."""
    return _LABELS[role]


def role_label(role: MembershipRole) -> str:
    """The role on its own, capitalised: "Organizer"."""
    return _LABELS[role].split(" ", 1)[1]


def tenant_word(kind: TenantKind) -> str:
    """What a tenant is called to a person."""
    return "repository" if kind is TenantKind.REPOSITORY else "library"
