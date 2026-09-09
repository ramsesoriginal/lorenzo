from opentelemetry.sdk.trace import TracerProvider

from lorenzo_api.logging import add_trace_context


def test_add_trace_context_injects_ids_inside_an_active_span() -> None:
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("test-span") as span:
        event_dict = add_trace_context(None, "info", {"event": "hello"})
        span_context = span.get_span_context()

    assert event_dict["trace_id"] == format(span_context.trace_id, "032x")
    assert event_dict["span_id"] == format(span_context.span_id, "016x")


def test_add_trace_context_is_a_noop_outside_a_span() -> None:
    """Startup/background logging with no request/span active - the no-op
    span get_current_span() returns then has an invalid context, so nothing
    is added rather than a placeholder trace_id of all zeros.
    """
    event_dict = add_trace_context(None, "info", {"event": "hello"})

    assert "trace_id" not in event_dict
    assert "span_id" not in event_dict
