"""Shared by the end-to-end tests."""

from __future__ import annotations

import io
import tempfile
import uuid
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SharedRepository:
    """The session's one seeded repository (see the `shared_repository` fixture), and the owner
    whose token reaches it. The token is signed anew on each use, since a suite can outlast one."""

    stack: Stack
    subject: str
    slug: str
    id: str

    @property
    def token(self) -> str:
        return self.stack.creator_token(self.subject)


_GOLDEN: dict[str, SharedRepository] = {}


def golden_repository(stack: Stack) -> SharedRepository:
    """The session's one seeded repository, published, built the first time something asks.

    It is what a test's tenant starts from (`copy_of_seeded`) and what the tests that only read
    or plan look at (the `shared_repository` fixture). Nothing writes to it but the grants a
    copy needs."""
    found = _GOLDEN.get(stack.api_url)
    if found is None:
        subject = "shared-repository"
        token = stack.creator_token(subject)
        slug = make_tenant(stack, token)
        work = Path(tempfile.mkdtemp(prefix="golden-"))
        for args in (("seed", "--tenant", slug, "--yes"), ("repo", "publish", "--tenant", slug)):
            built = run_cli(stack, token, work, *args)
            assert built.exit_code == 0, built.output
        with stack.api(token) as api:
            found = SharedRepository(stack, subject, slug, tenant_id(api, slug))
        _GOLDEN[stack.api_url] = found
    return found


def copy_of_seeded(stack: Stack, token: str, tmp_path: Path, kind: str = "repository") -> str:
    """A new tenant of the test's owner that starts as a copy of the seeded repository: the way a
    table gets the seed (ADR 0183), in a few requests where `lorenzo seed` makes about 130. For
    the tests of what a tenant does with a seed it has, not of the seed itself."""
    golden = golden_repository(stack)
    slug = f"e2e-{uuid.uuid4().hex[:10]}"
    with stack.api(token) as api:
        response = api.post("/tenants", json={"name": slug, "slug": slug, "kind": kind})
    assert response.status_code == 201, response.text
    granted = run_cli(
        stack,
        golden.token,
        tmp_path,
        "repo",
        "grant",
        response.json()["id"],
        "--tenant",
        golden.slug,
    )
    assert granted.exit_code == 0, granted.output
    copied = run_cli(stack, token, tmp_path, "repo", "copy", golden.slug, "--tenant", slug, "--yes")
    assert copied.exit_code == 0, copied.output
    return slug
