from pydantic import BaseModel

__all__ = ["LibraryCountOut"]


class LibraryCountOut(BaseModel):
    """GET .../libraries - ADR 0386: how many libraries hold a copy of the row. A number, never
    a name."""

    count: int
