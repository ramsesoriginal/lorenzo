"""An invite token is a bearer credential that lives in a URL *path*
(`/invites/{token}`), so it is exactly the kind of secret that leaks through
things that record paths - ADR 0092's requirement (6), and it needs a test
that fails, not a hope. Covered here: OpenTelemetry spans (the FastAPI
instrumentation records the request path as several attributes), uvicorn's
access-log line, and this app's own structlog events.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import structlog
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lorenzo_api.invites import generate_token, hash_token
from lorenzo_api.logging import configure_logging
from lorenzo_api.main import app
from lorenzo_api.models import CampaignInvite
from lorenzo_api.rate_limit import reset_invite_rate_limiter
from lorenzo_api.redaction import (
    RedactInviteTokensFilter,
    redact_invite_tokens,
    redact_invite_tokens_processor,
)

SECRET = "sEcReT-tOkEn-that-must-never-be-logged_0123456789abcdefABCDEF"


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> None:
    reset_invite_rate_limiter()


def _every_recorded_string(exporter: InMemorySpanExporter) -> list[str]:
    """Every string a finished span carries: its name and every attribute
    value (including strings inside sequences).
    """
    found: list[str] = []
    for span in exporter.get_finished_spans():
        found.append(span.name)
        for value in (span.attributes or {}).values():
            if isinstance(value, str):
                found.append(value)
            elif isinstance(value, (list, tuple)):
                found.extend(v for v in value if isinstance(v, str))
    return found


async def test_spans_never_carry_the_token(client: AsyncClient) -> None:
    exporter = InMemorySpanExporter()
    app.state.tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Unknown token and a real one, both routes: the path is the same shape
    # either way, and the real one also exercises the database spans.
    assert (await client.get(f"/invites/{SECRET}")).status_code == 404
    assert (await client.post(f"/invites/{SECRET}/redeem")).status_code == 404

    recorded = _every_recorded_string(exporter)
    assert recorded, "no spans were recorded at all - the test is not exercising tracing"
    leaks = [text for text in recorded if SECRET in text]
    assert leaks == []
    # The route template is what a span should be named after.
    assert any(text == "GET /invites/{token}" for text in recorded)


async def test_spans_never_carry_a_real_tokens_path_either(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Traced")
        token = generate_token()
        session.add(
            CampaignInvite(
                tenant_id=tenant_id,
                campaign_id=campaign.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(tz=UTC) + timedelta(days=1),
            )
        )
        await session.commit()
    exporter = InMemorySpanExporter()
    app.state.tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    assert (await client.get(f"/invites/{token}")).status_code == 200

    assert [text for text in _every_recorded_string(exporter) if token in text] == []
    await delete_tenant(tenant_id)


async def test_a_rejected_attempt_is_logged_without_the_token(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    assert (await client.get(f"/invites/{SECRET}")).status_code == 404

    # Only the server's own loggers: `httpx` is this test's *client* logging
    # the URL it just requested, which no server-side change can affect.
    server_records = [
        r for r in caplog.records if not r.name.startswith(("httpx", "httpcore", "asyncio"))
    ]
    server_text = "\n".join(r.getMessage() for r in server_records)
    assert "invite_link_rejected" in server_text  # the probe is visible to an operator...
    assert SECRET not in server_text  # ...without the credential.


def test_the_access_log_line_is_redacted() -> None:
    """uvicorn's access logger formats `%s - "%s %s HTTP/%s" %d`, with the
    request path (query string included) as an argument.
    """
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:5000", "GET", f"/invites/{SECRET}?ref=x", "1.1", 404),
        exc_info=None,
    )

    assert RedactInviteTokensFilter().filter(record) is True
    assert SECRET not in record.getMessage()
    assert "/invites/[redacted]" in record.getMessage()


def test_configure_logging_attaches_the_filter_to_the_access_logger() -> None:
    configure_logging()

    access_filters = logging.getLogger("uvicorn.access").filters
    assert any(isinstance(f, RedactInviteTokensFilter) for f in access_filters)


def test_structlog_events_are_redacted_in_the_processor_chain() -> None:
    event = redact_invite_tokens_processor(
        None, "warning", {"event": f"saw /invites/{SECRET}", "path": f"/invites/{SECRET}/redeem"}
    )

    assert SECRET not in str(event)
    assert event["path"] == "/invites/[redacted]/redeem"
    assert structlog.get_logger() is not None  # structlog importable: processor is a plain callable


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"/invites/{SECRET}", "/invites/[redacted]"),
        (f"http://test/invites/{SECRET}/redeem", "http://test/invites/[redacted]/redeem"),
        (f"GET /invites/{SECRET}?x=1 HTTP/1.1", "GET /invites/[redacted]?x=1 HTTP/1.1"),
        # A management path's `/invites/{invite_id}` is an id, not a secret, and
        # is left alone - redacting it would make the log useless for auditing.
        (
            "/tenants/t/campaigns/00000000-0000-0000-0000-000000000000/invites/abc",
            "/tenants/t/campaigns/00000000-0000-0000-0000-000000000000/invites/abc",
        ),
        ("nothing to hide here", "nothing to hide here"),
    ],
)
def test_redact_invite_tokens(text: str, expected: str) -> None:
    assert redact_invite_tokens(text) == expected
