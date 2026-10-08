"""Shared by the end-to-end tests."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import httpx
from typer.testing import CliRunner

from e2e.stack import Stack
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.evalworker import Engine, EvalRequest, EvalResult, WorkerEngine
from lorenzo_cli.main import Runtime, app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class CachingEngine:
    """Evaluates a request once per session and hands every later identical one a copy of the
    answer. Every plan, apply and --teach otherwise starts a worker subprocess to read the same
    handful of sheet files again; the request is keyed whole (file contents and options), so
    different input never shares a result. A few tests ask for the real engine instead
    (`run_cli(real_engine=True)`) to keep the subprocess path covered."""

    def __init__(self, inner: Engine) -> None:
        self._inner = inner
        self._results: dict[str, EvalResult] = {}

    def evaluate(self, request: EvalRequest) -> EvalResult:
        key = request.model_dump_json()
        if key not in self._results:
            self._results[key] = self._inner.evaluate(request)
        return self._results[key].model_copy(deep=True)


ENGINE = CachingEngine(WorkerEngine())


def make_tenant(stack: Stack, token: str, kind: str = "repository") -> str:
    slug = f"e2e-{uuid.uuid4().hex[:10]}"
    with stack.api(token) as api:
        response = api.post("/tenants", json={"name": slug, "slug": slug, "kind": kind})
    assert response.status_code == 201, response.text
    return slug


def run_cli(
    stack: Stack,
    token: str,
    tmp_path: Path,
    *args: str,
    answers: str | None = None,
    real_engine: bool = False,
    **env: str,
) -> Any:
    """Run the command. `answers` are typed at a terminal that is there to be asked. The sheet's
    JavaScript is evaluated through the session's cache, unless `real_engine` asks for the worker
    subprocess itself."""
    runtime = Runtime(
        env={
            "LORENZO_API_URL": stack.api_url,
            "LORENZO_TOKEN": token,
            "XDG_STATE_HOME": str(tmp_path / "state"),
            **env,
        },
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        interactive_override=answers is not None,
        engine=WorkerEngine() if real_engine else ENGINE,
    )
    return runner.invoke(app, list(args), obj=runtime, input=answers)


def tenant_id(api: httpx.Client, slug: str) -> str:
    """The id of the tenant with this slug, through every page of the listing: a session that has
    made more tenants than a page holds still finds the last."""
    page = 1
    while True:
        body = api.get("/tenants", params={"page": page, "size": 100}).json()
        for tenant in body["items"]:
            if tenant["slug"] == slug:
                return str(tenant["id"])
        if page >= body["pages"]:
            raise LookupError(f"no tenant {slug!r}")
        page += 1


def by_slug(api: httpx.Client, tid: str, slug: str) -> dict[str, Any]:
    response = api.get(f"/tenants/{tid}/entities/by-slug/{slug}")
    assert response.status_code == 200, f"{slug}: {response.text}"
    detail: dict[str, Any] = response.json()
    return detail


def own_stats(detail: dict[str, Any]) -> dict[str, Any]:
    return {s["name"]: s["value"] for s in detail["stats"] if s["own"]}


def parent_names(detail: dict[str, Any]) -> list[str]:
    return sorted(p["name"] for p in detail["prototypes"])
