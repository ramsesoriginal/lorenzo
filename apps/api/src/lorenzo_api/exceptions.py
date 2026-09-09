"""Typed "not found" problems - see ADR 0020 and errors.py.

fastapi-problem's own convention (see its README's "Custom Errors" section)
is to subclass its StatusProblem types with a fixed `title` per distinct
error condition, rather than raising a bare HTTPException(404, detail=...)
at every call site - the class name also drives the response's `type` field
(CamelCase -> kebab-case, "Error" suffix stripped), giving API consumers a
stable, programmatically-distinguishable value beyond the human-readable
`detail` string.
"""

from fastapi_problem.error import NotFoundProblem, UnauthorisedProblem

__all__ = [
    "EntityNotFoundError",
    "InvalidTokenError",
    "ItemInstanceNotFoundError",
    "ItemNotFoundError",
    "PayloadContentNotFoundError",
    "PayloadNotFoundError",
    "TenantNotFoundError",
]


class InvalidTokenError(UnauthorisedProblem):
    title = "Invalid or missing authentication token"


class TenantNotFoundError(NotFoundProblem):
    title = "Tenant not found"


class EntityNotFoundError(NotFoundProblem):
    title = "Entity not found"


class ItemNotFoundError(NotFoundProblem):
    title = "Item not found"


class ItemInstanceNotFoundError(NotFoundProblem):
    title = "Item instance not found"


class PayloadNotFoundError(NotFoundProblem):
    title = "Payload not found"


class PayloadContentNotFoundError(NotFoundProblem):
    title = "Payload has no binary content"
