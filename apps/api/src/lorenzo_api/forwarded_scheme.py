"""The scheme a client used, for the absolute URLs the API writes into its answers.

Behind Google's front end (Cloud Run) the API itself is spoken to over plain HTTP, so
`request.url_for` wrote `http://` into every picture and link URL, and a browser on an `https://`
page refused to load them (mixed content). uvicorn can be told to trust `X-Forwarded-Proto`, but
only by also trusting the proxy's `X-Forwarded-For`, which the rate limiter reads for itself
(`rate_limit.client_key`) and must not have rewritten for it. So only the scheme is taken here.

A caller can send the header themselves; all that changes is the scheme of the URLs in their own
answers, which they could write by hand.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

_SCHEMES = {"http": "http", "https": "https"}


class ForwardedSchemeMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for name, value in scope["headers"]:
                if name == b"x-forwarded-proto":
                    # The first entry is the client's own, the others are proxies' (RFC 7239).
                    first = value.decode("latin-1").split(",")[0].strip().lower()
                    if first in _SCHEMES:
                        scope = {**scope, "scheme": _SCHEMES[first]}
                    break
        await self.app(scope, receive, send)
