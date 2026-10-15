from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from test_cli_self_service import World, page
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app

T = UUID(int=1)
G = UUID(int=40)
S = UUID(int=50)
MAX = UUID(int=51)
STAMP = "2026-10-15T00:00:00Z"


def group(name="Vitals", gid=G):
    return dict(
        id=str(gid),
        name=name,
        priority=0,
        mandatory=False,
        position=0,
        created_at=STAMP,
        updated_at=STAMP,
    )


def stat(name="stress", sid=S):
    return dict(
        id=str(sid),
        name=name,
        stat_group_id=str(G),
        value_type="int",
        enum_values=[],
        unit=None,
        adjustable_in_play=False,
        pin=False,
        signed=False,
        position=0,
        max_hint_id=None,
        min_hint_id=None,
        resolved_hint_id=None,
        created_at=STAMP,
        updated_at=STAMP,
    )


class VocabularyWorld(World):
    def __init__(self):
        super().__init__()
        self.groups = [group()]
        self.stats = [stat(), stat("maximum", MAX)]
        self.writes: list[tuple[str, dict[str, Any]]] = []
        self.deny = False

    def handler(self, request):
        base = f"/tenants/{T}"
        path = request.url.path
        if request.method in ("POST", "PATCH"):
            body = json.loads(request.content)
            self.writes.append((path, body))
            if self.deny:
                return httpx.Response(
                    403, json={"detail": "Only a library administrator can edit this."}
                )
            if path == base:
                response = super().handler(httpx.Request("GET", str(request.url)))
                return httpx.Response(200, json={**response.json(), **body})
            rows = self.groups if "/stat-groups" in path else self.stats
            if request.method == "POST":
                made = group() if "/stat-groups" in path else stat()
                made.update(body)
                rows.append(made)
                return httpx.Response(201, json=made)
            for row in rows:
                if path.endswith(row["id"]):
                    row.update(body)
                    return httpx.Response(200, json=row)
        if path == base + "/stat-groups":
            return httpx.Response(200, json=page(self.groups))
        if path == base + "/stat-definitions":
            return httpx.Response(200, json=page(self.stats))
        return super().handler(request)


def invoke(world: VocabularyWorld, tmp_path: Path, *args: str):
    runtime = Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(world.handler),
    )
    return CliRunner().invoke(app, list(args), obj=runtime)


def test_create_group_and_definition_with_hints_and_enum(tmp_path):
    world = VocabularyWorld()
    result = invoke(
        world,
        tmp_path,
        "stat-group",
        "create",
        "Weapons",
        "-t",
        "table-one",
        "--priority",
        "4",
        "--mandatory",
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["priority"] == 4
    result = invoke(
        world,
        tmp_path,
        "stat-definition",
        "create",
        "condition",
        "-t",
        "table-one",
        "--group",
        "Weapons",
        "--type",
        "enum",
        "--enum-value",
        "ready",
        "--enum-value",
        "spent",
        "--max-hint",
        "maximum",
        "--pin",
        "--json",
    )
    assert result.exit_code == 0, result.output
    body = world.writes[-1][1]
    assert body["enum_values"] == ["ready", "spent"]
    assert body["max_hint_id"] == str(MAX)
    assert body["pin"] is True


def test_edit_sends_only_named_fields_and_explicit_false_and_null(tmp_path):
    world = VocabularyWorld()
    result = invoke(
        world,
        tmp_path,
        "stat-definition",
        "edit",
        "stress",
        "-t",
        "table-one",
        "--no-pin",
        "--clear-unit",
        "--clear-max-hint",
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert world.writes[-1][1] == {"pin": False, "unit": None, "max_hint_id": None}
    result = invoke(
        world,
        tmp_path,
        "stat-group",
        "edit",
        "Vitals",
        "-t",
        "table-one",
        "--no-mandatory",
        "--name",
        "Health",
    )
    assert result.exit_code == 0, result.output
    assert world.writes[-1][1] == {"name": "Health", "mandatory": False}


def test_settings_set_clear_and_read_are_one_document(tmp_path):
    world = VocabularyWorld()
    result = invoke(
        world,
        tmp_path,
        "tenant",
        "sheet-settings",
        "table-one",
        "--weapon-stat-group",
        "Vitals",
        "--ability-information-type",
        "ability",
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "being_stat_group_id": None,
        "weapon_stat_group_id": str(G),
        "ability_information_type": "ability",
    }
    result = invoke(
        world,
        tmp_path,
        "tenant",
        "sheet-settings",
        "table-one",
        "--clear-weapon-stat-group",
        "--clear-ability-information-type",
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert world.writes[-1][1] == {"weapon_stat_group_id": None, "ability_information_type": None}
    before = len(world.writes)
    result = invoke(world, tmp_path, "tenant", "sheet-settings", "table-one", "--json")
    assert result.exit_code == 0 and len(world.writes) == before


def test_conflicting_clear_no_fields_ambiguity_and_permissions(tmp_path):
    world = VocabularyWorld()
    for args in [("--unit", "kg", "--clear-unit"), ()]:
        result = invoke(
            world, tmp_path, "stat-definition", "edit", "stress", "-t", "table-one", *args
        )
        assert result.exit_code == 1
    assert not world.writes
    world.groups.append(group("vitals", UUID(int=41)))
    result = invoke(
        world, tmp_path, "stat-group", "edit", "VITALS", "-t", "table-one", "--priority", "1"
    )
    assert result.exit_code == 1 and "More than one" in result.output
    world.deny = True
    result = invoke(
        world, tmp_path, "stat-group", "edit", str(G), "-t", "table-one", "--priority", "1"
    )
    assert result.exit_code == 1 and "HTTP 403" in result.output


def test_lists_and_invalid_values(tmp_path):
    world = VocabularyWorld()
    for command in ("stat-group", "stat-definition"):
        result = invoke(world, tmp_path, command, "list", "-t", "table-one", "--json")
        assert result.exit_code == 0 and isinstance(json.loads(result.stdout), list)
    result = invoke(
        world,
        tmp_path,
        "stat-definition",
        "create",
        "bad",
        "-t",
        "table-one",
        "--group",
        "Vitals",
        "--type",
        "float",
        "--unit",
        "",
    )
    assert result.exit_code == 1 and not world.writes


def test_being_group_uses_names_or_ids_and_sends_only_its_setting(tmp_path):
    world = VocabularyWorld()
    for reference in ("Vitals", str(G)):
        result = invoke(
            world,
            tmp_path,
            "tenant",
            "sheet-settings",
            "table-one",
            "--being-stat-group",
            reference,
            "--json",
        )
        assert result.exit_code == 0, result.output
        assert world.writes[-1][1] == {"being_stat_group_id": str(G)}
        assert json.loads(result.stdout)["being_stat_group_id"] == str(G)
    cleared = invoke(
        world,
        tmp_path,
        "tenant",
        "sheet-settings",
        "table-one",
        "--clear-being-stat-group",
        "--json",
    )
    assert cleared.exit_code == 0, cleared.output
    assert world.writes[-1][1] == {"being_stat_group_id": None}
    assert json.loads(cleared.stdout)["being_stat_group_id"] is None
    before = len(world.writes)
    conflicting = invoke(
        world,
        tmp_path,
        "tenant",
        "sheet-settings",
        "table-one",
        "--being-stat-group",
        "Vitals",
        "--clear-being-stat-group",
    )
    assert conflicting.exit_code == 1 and len(world.writes) == before


def test_being_group_selection_refuses_ambiguous_names_and_permissions(tmp_path):
    world = VocabularyWorld()
    world.groups.append(group("vitals", UUID(int=41)))
    ambiguous = invoke(
        world, tmp_path, "tenant", "sheet-settings", "table-one", "--being-stat-group", "VITALS"
    )
    assert ambiguous.exit_code == 1 and not world.writes
    world.deny = True
    denied = invoke(
        world, tmp_path, "tenant", "sheet-settings", "table-one", "--being-stat-group", str(G)
    )
    assert denied.exit_code == 1 and "HTTP 403" in denied.output
