# Observability: apps/api

What exists today for seeing inside a running `apps/api`, and — just as important — what's deliberately not wired up yet. Every piece here was built for real and proven by a test, not just configured and hoped for; see each section for how. `apps/loot-bot` has a `/livez` route and no metrics or tracing; see [deployment.md](deployment.md#appsloot-bot). No other app has a server to observe.

## Health checks

| Endpoint | Answers | Checks |
| --- | --- | --- |
| `GET /healthz` | Is the process up at all? | Nothing else — no dependencies |
| `GET /readyz` | Can it actually serve a request right now? | Runs `SELECT 1` against the database |

These aren't wired into Cloud Run's own health probing (Cloud Run's default check is just "does something accept a TCP connection on `$PORT`"). Today, `/readyz` is used by the deploy pipeline itself — the last step of `deploy-api.yml` curls it right after deploying, so a revision that can't reach its database fails the deploy immediately instead of silently serving errors. On a `*.run.app` host Google's front end answers the literal path `/healthz` itself and never forwards it (see the comment before the `/livez` check in `deploy-loot-bot.yml`), so on Cloud Run `/readyz` is the check that reaches the API. Configuring Cloud Run's own startup/liveness probes to point at these paths is a reasonable next step, not done yet.

## Logs

`structlog`, configured in `logging.py`: structured JSON to stdout, ISO-8601 timestamps, log level, and any bound context variables merged in. Inside a request, each line also carries `trace_id` and `span_id` from the active OpenTelemetry span, so a log line can be matched to its trace. Invite tokens, which sit in a URL path, are scrubbed from log lines, including uvicorn's access log ([ADR 0092](../adr/0092-campaign-invite-links.md), [ADR 0220](../adr/0220-one-invite-table-with-kinds.md); `redaction.py`). Nothing else processes them yet — locally that's just your terminal; in Cloud Run, stdout is automatically ingested by Cloud Logging, and because it's already JSON, Cloud Logging parses the fields natively rather than treating each line as an opaque string. No log-based alerting or retention policy configured beyond Cloud Logging's own defaults.

## Metrics

`prometheus-fastapi-instrumentator`, exposed at `GET /metrics` (wired in `main.py`). Confirmed live content includes:

- HTTP request metrics: `http_requests_total` (by method/status/handler), request/response size
- Python process metrics: virtual/resident memory, CPU time, open file descriptors
- Python GC metrics: objects collected/uncollectable per generation

**Nothing scrapes this endpoint yet** — no Prometheus server, no Grafana, no Cloud Monitoring integration. It's exposed and correct, just not consumed by anything. Google Cloud Managed Service for Prometheus can scrape a Cloud Run service's `/metrics` directly without running your own Prometheus — the natural next step when this is actually needed, not before.

## Traces

OpenTelemetry, configured in `observability/tracing.py`: FastAPI (HTTP spans) and SQLAlchemy (query spans) are both auto-instrumented. Exports to the console only, on purpose — there's no trace collector anywhere in this project's infrastructure, and wiring an OTLP exporter for a collector that doesn't exist isn't something that could actually be verified. The same invite-token scrub runs on span attributes as each request span starts ([ADR 0092](../adr/0092-campaign-invite-links.md)). `tests/test_tracing.py` proves real spans are produced (attaching an in-memory span exporter via `app.state.tracer_provider`), not just that setup code runs without erroring.

In practice: locally, spans print to your terminal; in Cloud Run, they land in Cloud Logging alongside the structured logs, since both are just stdout. Neither is a substitute for a real trace backend (no trace search, no flame graphs) — when one exists, switching is adding `opentelemetry-exporter-otlp` and pointing `OTEL_EXPORTER_OTLP_ENDPOINT` at it, not a redesign.

## Versioning

`FastAPI(title="Lorenzo API", version=...)` (in `main.py`) reports the running package's own installed version — via `importlib.metadata.version("lorenzo-api")` — so it reports the installed artifact's version, visible at `/docs` or in `/openapi.json`, without needing a manual update on every release.

## What's deliberately not here yet

- No metrics scraping/dashboarding, no alerting on any signal.
- No OTLP trace collector.
- No Cloud Run-native startup/liveness probes.
- No log-based error tracking (e.g. Sentry) — `sentry-sdk` is an installed transitive dependency (pulled in by another package), not something this app initializes.
