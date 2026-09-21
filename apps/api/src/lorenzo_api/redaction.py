"""Keeps campaign invite tokens out of logs and traces - ADR 0092.

A token is a bearer credential and it lives in a URL *path*
(`GET /invites/{token}`, `POST /invites/{token}/redeem`), which is exactly
what access logs, OpenTelemetry HTTP spans and error records like to
capture. So anything that records a path scrubs the segment after `/invites/`
first. tests/test_invite_token_redaction.py fails if a token appears in a span
or a log line.
"""

import logging
import re
from typing import Any

from opentelemetry.trace import Span
from structlog.types import EventDict, WrappedLogger

# The segment after a root-level `/invites/`. The lookbehind exempts the
# management path `.../campaigns/{campaign_id}/invites/{invite_id}`, whose
# last segment is an id, not a secret - scrubbing it would make an audit log
# useless. (Both lookbehind pieces are fixed-width, which `re` requires.)
_INVITE_TOKEN_PATTERN = re.compile(r"(?<!/campaigns/[0-9a-fA-F-]{36})/invites/[^/\s?#\"']+")

REDACTED = "/invites/[redacted]"


def redact_invite_tokens(text: str) -> str:
    return _INVITE_TOKEN_PATTERN.sub(REDACTED, text)


class RedactInviteTokensFilter(logging.Filter):
    """For stdlib log records - notably uvicorn's access log, whose
    `%s - "%s %s HTTP/%s" %d` line carries the request path as an argument.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_invite_tokens(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_invite_tokens(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        elif isinstance(record.args, dict):
            record.args = {
                key: redact_invite_tokens(value) if isinstance(value, str) else value
                for key, value in record.args.items()
            }
        return True


def redact_invite_tokens_processor(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """A structlog processor: defence in depth for this app's own events,
    which never *intentionally* include a token but shouldn't be able to by
    accident either.
    """
    return {
        key: redact_invite_tokens(value) if isinstance(value, str) else value
        for key, value in event_dict.items()
    }


def redact_span_attributes(span: Span, scope: dict[str, Any]) -> None:
    """`server_request_hook` for the FastAPI instrumentation: the ASGI
    instrumentation records the raw request path in several attributes
    (`http.target`, `http.url`, ...). Rewrites any that carry a token.
    """
    attributes = getattr(span, "attributes", None) or {}
    for key, value in list(attributes.items()):
        if isinstance(value, str):
            redacted = redact_invite_tokens(value)
            if redacted != value:
                span.set_attribute(key, redacted)
