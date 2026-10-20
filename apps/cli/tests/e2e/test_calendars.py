"""Native calendar import/export/retry through the CLI and real API (ADR 0311)."""

from __future__ import annotations

import json
from pathlib import Path

from lorenzo_calendar.document import CalendarDocument

from e2e.helpers import make_tenant, run_cli, tenant_id
from e2e.stack import Stack


def test_calendar_import_choices_reload_export_and_retry(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("calendar-importer")
    slug = make_tenant(stack, token)
    document = {
        "source_key": "isles",
        "name": "Isles",
        "definition": {"segments": [{"key": "spring", "name": "Spring", "days": 27}]},
        "annotations": [
            {
                "key": "storm-a",
                "date": {"year": 3286, "segment": "spring", "day": 16},
                "text": "The storm begins.",
                "original_text": "The storm begins.",
            },
            {
                "key": "storm-b",
                "date": {"year": 3286, "segment": "spring", "day": 17},
                "text": "The storm ends.",
                "original_text": "The storm ends.",
            },
        ],
    }
    file = tmp_path / "calendar.json"
    file.write_text(json.dumps(document), encoding="utf-8")
    choices = tmp_path / "choices.json"
    choices.write_text(
        json.dumps(
            {
                "annotations": {
                    key: {"classification": "event", "group": "storm", "title": "Storm"}
                    for key in ["storm-a", "storm-b"]
                }
            }
        ),
        encoding="utf-8",
    )
    args = ["calendar", "import", str(file), "--tenant", slug, "--choices", str(choices)]
    preview = run_cli(stack, token, tmp_path, *args, "--dry-run", "--json")
    assert preview.exit_code == 0, preview.output
    assert json.loads(preview.stdout)["ready"]
    imported = run_cli(stack, token, tmp_path, *args, "--yes", "--json")
    assert imported.exit_code == 0, imported.output
    repeated = run_cli(stack, token, tmp_path, *args, "--yes", "--json")
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.stdout)["created"] == []
    exported = run_cli(stack, token, tmp_path, "calendar", "export", "isles", "--tenant", slug)
    assert exported.exit_code == 0, exported.output
    native = CalendarDocument.model_validate_json(exported.stdout)
    assert [a.classification for a in native.annotations] == ["event", "event"]
    with stack.api(token) as api:
        tid = tenant_id(api, slug)
        events = api.get(f"/tenants/{tid}/entities", params={"kind": "event"}).json()
        assert events["total"] == 1
        event = events["items"][0]
        dates = api.get(f"/tenants/{tid}/entities/{event['id']}/dates").json()
        assert {d["day"] for d in dates} == {16, 17}


def test_forty_ordinary_notes_are_saved_with_the_calendar_and_survive_retry(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token("forty-calendar-notes")
    slug = make_tenant(stack, token)
    annotations = [
        {
            "key": f"note-{i}",
            "date": {"year": 3286, "segment": "spring", "day": i},
            "text": f"Harbour log {i}.",
            "original_text": f"Harbour log {i}.",
        }
        for i in range(1, 41)
    ]
    document = {
        "source_key": "harbour",
        "name": "Harbour calendar",
        "definition": {"segments": [{"key": "spring", "name": "Spring", "days": 50}]},
        "annotations": annotations,
    }
    file = tmp_path / "calendar.json"
    file.write_text(json.dumps(document), encoding="utf-8")
    args = ["calendar", "import", str(file), "--tenant", slug, "--yes", "--json"]
    imported = run_cli(stack, token, tmp_path, *args)
    assert imported.exit_code == 0, imported.output
    receipt = json.loads(imported.stdout)
    assert len(receipt["created"]) == 41
    with stack.api(token) as api:
        tid = tenant_id(api, slug)
        calendar = receipt["calendar_entity_id"]
        periods = api.get(
            f"/tenants/{tid}/calendars/{calendar}/periods", params={"year": 3286, "size": 100}
        ).json()["items"]
        days = [p for p in periods if p["day"] is not None]
        assert len(days) == 40
        for period in days:
            entry = api.get(f"/tenants/{tid}/entities/{period['entity_id']}").json()
            assert len(entry["information"]) == 1
            assert (
                entry["information"][0]["payloads"][0]["content"] == f"Harbour log {period['day']}."
            )
    repeated = run_cli(stack, token, tmp_path, *args)
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.stdout)["created"] == []
    assert len(json.loads(repeated.stdout)["unchanged"]) == 41
