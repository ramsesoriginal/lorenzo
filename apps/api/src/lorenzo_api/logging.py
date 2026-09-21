import logging
import sys

import structlog
from opentelemetry import trace
from structlog.types import EventDict, WrappedLogger

from lorenzo_api.redaction import RedactInviteTokensFilter, redact_invite_tokens_processor


def add_trace_context(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """Injects the active span's trace_id/span_id (ADR 0018's tracing setup)
    so a log line can be correlated with the request/span that emitted it.
    No-ops outside a span (e.g. startup logging before a request exists) -
    `is_valid` is false for the no-op span `get_current_span()` returns then.
    """
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    # An invite token is a bearer credential in a URL path (ADR 0092), and
    # uvicorn's access log prints the path. `uvicorn.access` has its own
    # handler and does not propagate to the root's, so the filter goes on
    # the logger itself, where it runs before any handler sees the record.
    # Added once: configure_logging() can run more than once per process.
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactInviteTokensFilter) for f in access_logger.filters):
        access_logger.addFilter(RedactInviteTokensFilter())

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            add_trace_context,
            redact_invite_tokens_processor,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
