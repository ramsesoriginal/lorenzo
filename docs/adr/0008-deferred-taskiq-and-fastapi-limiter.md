# 0008 - Background jobs and rate limiting: taskiq + fastapi-limiter, deferred

Status: accepted (decision made, implementation deferred)

## Context

Chosen alongside the rest of apps/api's supporting-library additions (fastapi-problem, fastapi-pagination, mypy, OpenTelemetry). Both are the current best-practice picks for their concern, but both conventionally need a backing store - Redis - which nothing in this repo has yet.

## Decision

- **taskiq** for background/async job processing, once there's an actual job to run. `arq` is the library most tutorials still point to, but it's now maintenance-only (its author moved on to other projects) - taskiq is the actively-developed, async-native, FastAPI-friendly successor.
- **fastapi-limiter** for rate limiting, over the more commonly-cited `slowapi` (a Flask-limiter port that's stayed alpha-quality with many stale open issues).

Both are deferred, not built, specifically because adding a new infrastructure service (Redis) isn't justified before there's a concrete job to queue or a concrete endpoint that needs a rate limit. Recorded here so the decision doesn't get re-made or lost between now and then.

## Consequences

- When either is actually needed: add Redis to `infra/docker-compose.yml`, then wire in whichever of the two prompted it - no need to re-litigate the library choice at that point.
- Revisit if a lighter-weight alternative to a separate broker turns out to fit this project's actual scale better (e.g. Postgres-backed queuing for low-volume background work).
