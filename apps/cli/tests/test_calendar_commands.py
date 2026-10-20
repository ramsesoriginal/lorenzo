from __future__ import annotations

import io
import json

import httpx
from lorenzo_calendar.document import CalendarDocument
from test_cli import TENANT, TENANT_ID
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app

RUNNER = CliRunner()
DOCUMENT = CalendarDocument.model_validate(
    {
        "source_key": "isles",
        "name": "Isles",
        "definition": {"segments": [{"key": "spring", "name": "Spring", "days": 27}]},
        "annotations": [
            {
                "key": "diary",
                "date": {"year": 3286, "segment": "spring", "day": 16},
                "text": "A quiet evening.",
                "original_text": "A quiet evening.",
            }
        ],
    }
)
PLAN = {
    "source_key": "isles",
    "calendar_entity_id": "11111111-1111-4111-8111-111111111111",
    "token": "a" * 64,
    "changes": [{"key": "$calendar", "action": "create"}],
    "unaccepted_warnings": [],
    "ready": True,
}
RECEIPT = {
    "source_key": "isles",
    "calendar_entity_id": PLAN["calendar_entity_id"],
    "created": ["$calendar"],
    "changed": [],
    "unchanged": [],
    "kept_local": [],
    "retained": [],
}


def runtime(tmp_path, seen, *, stale=False, timed_out=False):
    def handler(request):
        seen.append(request)
        if request.method == "GET" and request.url.path == f"/tenants/{TENANT_ID}":
            return httpx.Response(200, json=TENANT)
        if request.url.path.endswith("/calendar-imports/plan"):
            return httpx.Response(200, json=PLAN)
        if request.url.path.endswith("/calendar-imports/isles/document"):
            return httpx.Response(200, json=DOCUMENT.model_dump(mode="json"))
        if request.url.path.endswith("/calendar-imports"):
            if timed_out:
                raise httpx.ReadTimeout("The read operation timed out", request=request)
            return (
                httpx.Response(412, json={"detail": "The plan is stale"})
                if stale
                else httpx.Response(200, json=RECEIPT)
            )
        raise AssertionError(str(request.url))

    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "token"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(handler),
    )


def native_file(tmp_path):
    file = tmp_path / "calendar.json"
    file.write_text(DOCUMENT.model_dump_json(), encoding="utf-8")
    return file


def test_dry_run_choices_and_saved_plan_are_reviewable_json(tmp_path):
    seen = []
    file = native_file(tmp_path)
    choices = tmp_path / "choices.json"
    choices.write_text(
        json.dumps({"annotations": {"diary": {"classification": "event", "title": "Storm"}}}),
        encoding="utf-8",
    )
    saved = tmp_path / "plan.json"
    result = RUNNER.invoke(
        app,
        [
            "calendar",
            "import",
            str(file),
            "--tenant",
            TENANT_ID,
            "--choices",
            str(choices),
            "--dry-run",
            "--json",
            "--plan-out",
            str(saved),
        ],
        obj=runtime(tmp_path, seen),
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["token"] == PLAN["token"]
    assert json.loads(seen[-1].content)["document"]["annotations"][0]["classification"] == "event"
    assert json.loads(saved.read_text())["request"]["document"]["source_key"] == "isles"
    assert not any(r.url.path.endswith("/calendar-imports") for r in seen)


def test_apply_uses_the_exact_saved_plan_and_stale_errors_are_clean(tmp_path):
    seen = []
    file = native_file(tmp_path)
    saved = tmp_path / "plan.json"
    first = RUNNER.invoke(
        app,
        [
            "calendar",
            "import",
            str(file),
            "--tenant",
            TENANT_ID,
            "--dry-run",
            "--plan-out",
            str(saved),
        ],
        obj=runtime(tmp_path, seen),
    )
    assert first.exit_code == 0, first.output
    seen.clear()
    applied = RUNNER.invoke(
        app,
        [
            "calendar",
            "import",
            str(file),
            "--tenant",
            TENANT_ID,
            "--apply-plan",
            str(saved),
            "--yes",
            "--json",
        ],
        obj=runtime(tmp_path, seen),
    )
    assert applied.exit_code == 0, applied.output
    assert json.loads(applied.stdout) == RECEIPT
    assert not any(r.url.path.endswith("/plan") for r in seen)
    assert json.loads(seen[-1].content)["token"] == PLAN["token"]
    stale = RUNNER.invoke(
        app,
        [
            "calendar",
            "import",
            str(file),
            "--tenant",
            TENANT_ID,
            "--apply-plan",
            str(saved),
            "--yes",
        ],
        obj=runtime(tmp_path, [], stale=True),
    )
    assert stale.exit_code == 1
    assert "stale" in stale.output


def test_invalid_calendar_fails_before_login_or_network_and_export_is_json(tmp_path):
    seen = []
    file = tmp_path / "invalid.json"
    file.write_text('{"format":"unknown"}', encoding="utf-8")
    invalid = RUNNER.invoke(
        app,
        ["calendar", "import", str(file), "--tenant", TENANT_ID, "--yes"],
        obj=runtime(tmp_path, seen),
    )
    assert invalid.exit_code == 1
    assert seen == []
    exported = RUNNER.invoke(
        app, ["calendar", "export", "isles", "--tenant", TENANT_ID], obj=runtime(tmp_path, seen)
    )
    assert exported.exit_code == 0, exported.output
    assert CalendarDocument.model_validate_json(exported.stdout) == DOCUMENT


def test_import_activity_is_stderr_and_bulk_wait_does_not_change_other_requests(tmp_path):
    seen = []
    result = RUNNER.invoke(
        app,
        [
            "calendar",
            "import",
            str(native_file(tmp_path)),
            "--tenant",
            TENANT_ID,
            "--yes",
            "--json",
            "--timeout",
            "180",
        ],
        obj=runtime(tmp_path, seen),
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == RECEIPT
    assert "Read calendar with 1 dated notes" in result.stderr
    assert "Planning calendar" in result.stderr
    assert "waiting for API confirmation" in result.stderr
    for request in seen:
        expected = 180 if "/calendar-imports" in request.url.path else 30
        assert request.extensions["timeout"]["read"] == expected
        assert request.extensions["timeout"]["connect"] == 30


def test_unconfirmed_apply_is_not_retried_and_explains_recovery(tmp_path):
    seen = []
    result = RUNNER.invoke(
        app,
        ["calendar", "import", str(native_file(tmp_path)), "--tenant", TENANT_ID, "--yes"],
        obj=runtime(tmp_path, seen, timed_out=True),
    )
    assert result.exit_code == 1
    assert "did not confirm the import outcome" in result.output
    assert "Do not delete the calendar" in " ".join(result.output.split())
    assert "--dry-run" in result.output
    assert "Imported" not in result.stdout
    apply = [r for r in seen if r.url.path.endswith("/calendar-imports")]
    assert len(apply) == 1
    assert apply[0].extensions["timeout"]["read"] == 300


def test_calendar_wait_must_be_positive(tmp_path):
    seen = []
    result = RUNNER.invoke(
        app,
        ["calendar", "import", str(native_file(tmp_path)), "--tenant", TENANT_ID, "--timeout", "0"],
        obj=runtime(tmp_path, seen),
    )
    assert result.exit_code == 2
    assert seen == []


def test_terminal_import_renders_activity_and_keeps_receipt_readable(tmp_path, monkeypatch):
    from rich.console import Console

    from lorenzo_cli import main

    terminal = io.StringIO()
    monkeypatch.setattr(main, "_err", Console(file=terminal, force_terminal=True, width=120))
    result = RUNNER.invoke(
        app,
        ["calendar", "import", str(native_file(tmp_path)), "--tenant", TENANT_ID, "--yes"],
        obj=runtime(tmp_path, []),
    )
    assert result.exit_code == 0, result.output
    assert "Planning calendar" in terminal.getvalue()
    assert "waiting for API confirmation" in terminal.getvalue()
    assert "Imported 1 new units" in result.stdout
