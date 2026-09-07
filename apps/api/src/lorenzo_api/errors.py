"""RFC 9457 ("Problem Details for HTTP APIs") error responses.

Wires fastapi-problem's exception handler onto the app so HTTPException,
request-validation errors, and any unhandled exception all render as
application/problem+json instead of FastAPI's default ad hoc shapes.
"""

from fastapi import FastAPI
from fastapi_problem.handler import add_exception_handler, new_exception_handler


def register_error_handlers(app: FastAPI) -> None:
    add_exception_handler(app, new_exception_handler())
