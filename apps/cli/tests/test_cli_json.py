"""`--json` on `apply` and `pack give` (ADR 0156): stdout is one JSON document, nothing else."""

from __future__ import annotations

import io
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from plain import plain
from test_importer_give import ALICE, PACK, answer
from test_importer_review import VALUE, item, make_plan
from typer.testing import CliRunner

from lorenzo_cli import main as main_module
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.importer.apply import ApplyReport
from lorenzo_cli.importer.plan import ImportPlan
from lorenzo_cli.importer.review import plan_json
from lorenzo_cli.main import Runtime, app

runner = CliRunner()


class FakeManifest:
    def __init__(self) -> None:
        self.saved = False

    def save(self) -> None:
        self.saved = True


def runtime(tmp_path: Path, transport: httpx.MockTransport | None = None) -> Runtime:
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=transport,
    )


class Applying:
    """Stands in for planning and writing, which have their own tests: the CLI's wiring is what
    these check."""

    def __init__(self, plan: ImportPlan, report: ApplyReport | None = None) -> None:
        self.plan = plan
        self.report = report or ApplyReport(created=2, categories=1)
        self.manifest = FakeManifest()
        self.applied = 0

    def prepare(self, *args: Any, **kwargs: Any) -> tuple[ImportPlan, FakeManifest, dict]:
        return self.plan, self.manifest, {}

    def apply(
        self,
        client: object,
        plan: ImportPlan,
        manifest: object,
        options: object,
        progress: Callable[[str], None],
    ) -> ApplyReport:
        self.applied += 1
        progress("1/2 basic-weapons-a")
        progress("2/2 basic-weapons-b")
        return self.report


def patched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, applying: Applying) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_module, "_prepare_plan", applying.prepare)
    monkeypatch.setattr(main_module, "apply_import", applying.apply)


ARGS = ["apply", "--tenant", "repo", "--base", "x.js", "--json"]


@pytest.fixture(autouse=True)
def a_base_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "x.js").write_text("")
    monkeypatch.chdir(tmp_path)


def test_apply_json_is_one_document_with_the_plan_and_what_was_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = make_plan(item("a", "create"), item("b", "create"))
    applying = Applying(plan)
    patched(monkeypatch, tmp_path, applying)

    result = runner.invoke(app, [*ARGS, "--yes"], obj=runtime(tmp_path))

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert set(document) == {"plan", "applied", "failures", "unresolved"}
    assert document["plan"] == plan_json(plan)
    assert document["applied"] == {
        "created": 2,
        "completed": 0,
        "reparented": 0,
        "categories": 1,
        "definitions": 0,
    }
    assert document["failures"] == []
    assert document["unresolved"] is False
    assert applying.manifest.saved


def test_progress_and_review_notices_stay_off_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = make_plan(item("a", "create"), item("b", "held", [VALUE]))
    patched(monkeypatch, tmp_path, Applying(plan))

    result = runner.invoke(app, [*ARGS, "--yes"], obj=runtime(tmp_path))

    json.loads(result.stdout)  # nothing but the document
    assert "1/2 basic-weapons-a" in result.stderr
    assert "need a decision" in result.stderr
    assert "Plan" not in result.stdout


def test_a_held_item_makes_it_unresolved_and_exit_1_after_the_rest_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = make_plan(item("a", "create"), item("b", "held", [VALUE]))
    patched(monkeypatch, tmp_path, Applying(plan))

    result = runner.invoke(app, [*ARGS, "--yes"], obj=runtime(tmp_path))

    document = json.loads(result.stdout)
    assert result.exit_code == 1
    assert document["unresolved"] is True
    assert document["applied"]["created"] == 2


def test_failures_are_listed_and_exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = make_plan(item("a", "create"))
    report = ApplyReport(created=0, failures=["basic-weapons-a: 409 Conflict"])
    patched(monkeypatch, tmp_path, Applying(plan, report))

    result = runner.invoke(app, [*ARGS, "--yes"], obj=runtime(tmp_path))

    assert result.exit_code == 1
    assert json.loads(result.stdout)["failures"] == ["basic-weapons-a: 409 Conflict"]
    assert "409 Conflict" in result.stderr


def test_json_never_asks_so_without_yes_nothing_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    applying = Applying(make_plan(item("a", "create")))
    patched(monkeypatch, tmp_path, applying)
    rt = runtime(tmp_path)
    rt.interactive_override = True  # someone is there, and still it must not ask

    result = runner.invoke(app, ARGS, obj=rt)

    assert result.exit_code == 1
    document = json.loads(result.stdout)
    assert document["applied"] is None
    assert document["plan"]["header"]["counts"]["create"] == 1
    assert "--yes" in result.stderr
    assert applying.applied == 0
    assert "Import these?" not in result.output


def test_nothing_pending_writes_nothing_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    applying = Applying(make_plan(item("a", "exists")))
    patched(monkeypatch, tmp_path, applying)

    result = runner.invoke(app, [*ARGS, "--yes"], obj=runtime(tmp_path))

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["applied"] is None
    assert applying.applied == 0


def test_a_plan_with_problems_writes_nothing_and_is_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    applying = Applying(make_plan(item("a", "create"), problems=["not seeded"]))
    patched(monkeypatch, tmp_path, applying)

    result = runner.invoke(app, [*ARGS, "--yes"], obj=runtime(tmp_path))

    document = json.loads(result.stdout)
    assert result.exit_code == 1
    assert document["applied"] is None
    assert document["unresolved"] is True
    assert document["plan"]["problems"] == ["not seeded"]
    assert applying.applied == 0


def test_json_and_teach_cannot_be_combined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patched(monkeypatch, tmp_path, Applying(make_plan()))

    result = runner.invoke(app, [*ARGS, "--yes", "--teach"], obj=runtime(tmp_path))

    assert result.exit_code == 2
    assert "--teach" in plain(result.output)


def test_without_json_apply_still_says_it_in_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patched(monkeypatch, tmp_path, Applying(make_plan(item("a", "create"))))

    result = runner.invoke(
        app, ["apply", "--tenant", "repo", "--base", "x.js", "--yes"], obj=runtime(tmp_path)
    )

    assert result.exit_code == 0, result.output
    assert "Created 2" in result.stdout
    assert "Plan" in result.stdout


# --- pack give --json ---------------------------------------------------------------------

TENANT = uuid.UUID(int=1)


def pack_api(sent: list[httpx.Request]) -> httpx.MockTransport:
    slugs = {"explorers-pack": PACK, "alice": ALICE}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/tenants/{TENANT}":
            return httpx.Response(
                200,
                json={
                    "id": str(TENANT),
                    "slug": "camp",
                    "name": "Camp",
                    "description": "",
                    "kind": "play",
                    "published_at": None,
                    "npcs_shared_with_gms": True,
                    "created_by": None,
                    "updated_by": None,
                },
            )
        if path.endswith("/entities/resolve"):
            hits = [
                {"slug": s, "entity_id": str(slugs[s]), "name": s, "kinds": ["item"]}
                for s in request.url.params.get_list("slug")
                if s in slugs
            ]
            return httpx.Response(200, json=hits)
        if path.endswith("/item-instances/from-pack"):
            sent.append(request)
            return httpx.Response(
                201, json=answer(dry_run=request.url.params.get("dry_run") == "true")
            )
        return httpx.Response(404, json={"title": "no"})

    return httpx.MockTransport(handler)


GIVE = ["pack", "give", "explorers-pack", "--tenant", str(TENANT), "--owner", "alice"]


def test_pack_give_json_is_what_the_api_made_and_nothing_else(tmp_path: Path) -> None:
    sent: list[httpx.Request] = []
    result = runner.invoke(app, [*GIVE, "--json"], obj=runtime(tmp_path, pack_api(sent)))

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["pack_id"] == str(PACK)
    assert [e["item_instance"]["title"] for e in document["created"]] == ["Backpack", "Rope"]
    assert document["created"][0]["children"][0]["item_instance"]["title"] == "Rations"
    assert "Gave" not in result.stdout


def test_pack_give_json_with_a_dry_run_has_the_same_shape(tmp_path: Path) -> None:
    sent: list[httpx.Request] = []
    result = runner.invoke(
        app, [*GIVE, "--json", "--dry-run"], obj=runtime(tmp_path, pack_api(sent))
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["dry_run"] is True
    assert sent[0].url.params["dry_run"] == "true"


def test_pack_give_without_json_still_prints_the_tree(tmp_path: Path) -> None:
    result = runner.invoke(app, GIVE, obj=runtime(tmp_path, pack_api([])))

    assert result.exit_code == 0, result.output
    assert "Backpack" in result.stdout
    assert "Gave 4 item(s)." in result.stdout
