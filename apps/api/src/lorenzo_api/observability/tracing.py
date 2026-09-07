"""OpenTelemetry tracing.

Exports to the console by default - there is no trace collector anywhere
in this project's infrastructure yet. Point a real one at this service by
setting OTEL_EXPORTER_OTLP_ENDPOINT and adding the
opentelemetry-exporter-otlp package when that's actually available; until
then, this is deliberately just the console exporter, proven by
tests/test_tracing.py rather than eyeballed output.
"""

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from lorenzo_api.db import engine


def configure_tracing(app: FastAPI) -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({"service.name": "lorenzo-api"}))
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    # Instrumentation hooks into SQLAlchemy's event system, which fires on
    # the underlying sync engine even when using the async wrapper.
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine, tracer_provider=provider)

    return provider
