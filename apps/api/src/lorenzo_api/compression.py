"""gzip for the responses that are big (ADR 0262, RFC 0039 W3).

Nothing in front of the API was found to compress its responses, and the bulk entity export is
text that shrinks four to five times. Starlette's `GZipMiddleware` does the work (it honours
`Accept-Encoding`, sets `Content-Encoding` and `Vary`, and leaves a response alone when the client
did not ask); this only chooses where it applies. Not everywhere: pictures are already compressed
and most responses are a few hundred bytes.
"""

from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class GzipForPathsMiddleware:
    def __init__(self, app: ASGIApp, *, path_suffixes: tuple[str, ...], minimum_size: int = 1000):
        self._plain = app
        self._gzip = GZipMiddleware(app, minimum_size=minimum_size)
        self._suffixes = path_suffixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].endswith(self._suffixes):
            await self._gzip(scope, receive, send)
        else:
            await self._plain(scope, receive, send)
