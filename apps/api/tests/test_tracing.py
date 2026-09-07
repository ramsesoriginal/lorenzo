from httpx import AsyncClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from lorenzo_api.main import app


async def test_request_produces_a_server_span(client: AsyncClient) -> None:
    exporter = InMemorySpanExporter()
    app.state.tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    response = await client.get("/healthz")
    assert response.status_code == 200

    server_spans = [span for span in exporter.get_finished_spans() if span.kind == SpanKind.SERVER]
    assert len(server_spans) == 1
    assert server_spans[0].name == "GET /healthz"
    assert server_spans[0].attributes is not None
    assert server_spans[0].attributes["http.route"] == "/healthz"
    assert server_spans[0].attributes["http.status_code"] == 200
