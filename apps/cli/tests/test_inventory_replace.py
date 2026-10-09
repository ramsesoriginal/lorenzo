"""`lorenzo inventory import` for any being a GM may list, with `--replace`, and its display
(ADR 0232), against a fake API."""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
from plain import plain
from test_cli_self_service import ASHFANG, BRISK, ROPE, TENANT, TORCH, World, item, page
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.client.models import ItemInstanceOut
from lorenzo_cli.inventory.plan import deletion_order
from lorenzo_cli.main import Runtime, app

runner = CliRunner()

BASE = f"/tenants/{TENANT}"
BRISK_TWIN = uuid.UUID(int=22)


def thing(
    n: int,
    title: str,
    *,
    container: uuid.UUID | None = None,
    quantity: int | None = None,
    owner: uuid.UUID = BRISK,
    holds: bool | None = None,
) -> dict[str, Any]:
    made = item(uuid.UUID(int=1000 + n), title)
    made.update(
        owner_entity_id=str(owner),
        container_entity_id=None if container is None else str(container),
        quantity=quantity,
        slug=None,
        bound=False,
        is_container=holds,
    )
    return made


def id_of(n: int) -> uuid.UUID:
    return uuid.UUID(int=1000 + n)


class Table(World):
    """The base world, plus what an import for a GM needs: beings, what a being owns, deletes."""

    def __init__(
        self,
        *,
        gm: bool = True,
        owns: list[dict[str, Any]] | None = None,
        undeletable: set[uuid.UUID] | None = None,
        twins: bool = False,
        strangers: dict[uuid.UUID, list[dict[str, Any]]] | None = None,
        container_names: dict[uuid.UUID, str] | None = None,
    ) -> None:
        super().__init__()
        self.strangers = strangers or {}  # what others own, in a container of the being's
        self.container_names = container_names or {}
        self.gm = gm
        self.owns = owns or []
        self.undeletable = undeletable or set()
        self.beings = [(ASHFANG, "Ashfang"), (BRISK, "Brisk")]
        self.slugs = {"unsorted": uuid.UUID(int=77)}  # the placeholder the seed makes
        if twins:
            self.beings.append((BRISK_TWIN, "brisk"))
        self.created: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path == f"{BASE}/beings":
            if not self.gm:
                return httpx.Response(404, json={"title": "Not Found", "detail": "No tenant."})
            query = (request.url.params.get("q") or "").lower()
            rows = [
                {"entity_id": str(i), "name": n, "is_pc": True}
                for i, n in self.beings
                if query in n.lower()
            ]
            self.seen.append(request)
            return httpx.Response(200, json=page(rows))
        if path.startswith(f"{BASE}/item-instances/owned-by/"):
            self.seen.append(request)
            groups: dict[str | None, list[dict[str, Any]]] = {}
            for row in self.owns:
                holder = row["container_entity_id"]
                groups.setdefault(None if holder in (None, str(BRISK)) else holder, []).append(row)
            out = [
                {
                    "container": None
                    if holder is None
                    else {
                        "id": holder,
                        "name": self.container_names.get(uuid.UUID(holder), "a container"),
                    },
                    "item_instances": rows,
                }
                for holder, rows in groups.items()
            ]
            return httpx.Response(200, json={"groups": out})
        if path == f"{BASE}/item-instances" and method == "GET":
            self.seen.append(request)
            wanted = request.url.params.get("container_id")
            inside = [r for r in self.owns if r["container_entity_id"] == wanted]
            others = self.strangers.get(uuid.UUID(wanted), []) if wanted else []
            return httpx.Response(200, json=page([*inside, *others]))
        if path.startswith(f"{BASE}/item-instances/") and method == "DELETE":
            self.seen.append(request)
            target = uuid.UUID(path.rsplit("/", 1)[1])
            if target in self.undeletable:
                return httpx.Response(
                    409, json={"title": "Conflict", "detail": "It is bound to its owner."}
                )
            self.owns = [t for t in self.owns if t["entity_id"] != str(target)]
            return httpx.Response(204)
        if path == f"{BASE}/item-instances" and method == "POST":
            self.seen.append(request)
            body = json.loads(request.content)
            self.created.append(body)
            made = item(uuid.UUID(int=5000 + len(self.created)), body.get("name") or "Thing")
            made.update(
                owner_entity_id=body["owner_character_id"],
                container_entity_id=body.get("container_entity_id"),
                quantity=body.get("quantity"),
                slug=None,
                bound=False,
            )
            return httpx.Response(201, json=made)
        if path.endswith("/information") and method == "GET":
            self.seen.append(request)
            return httpx.Response(200, json=page([]))
        return super().handler(request)

    def verbs(self) -> list[str]:
        """DELETE and POST, in the order they were sent (the rest is lookups)."""
        return [
            r.method
            for r in self.seen
            if r.method in ("DELETE", "POST") and "item-instances" in r.url.path
        ]


def ledger(tmp_path: Path, *lines: str, owner: str | None = None) -> Path:
    head = "format: lorenzo-ledger/1\n" + (f"owner: {owner}\n" if owner else "")
    path = tmp_path / "x.ledger.md"
    path.write_text(head + "\n## Not carried\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(world: Table, tmp_path: Path, *args: str, tty: bool = False):  # type: ignore[no-untyped-def]
    runtime = Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(world.handler),
        interactive_override=tty,
    )
    return runner.invoke(app, ["inventory", "import", *args], obj=runtime)


# --- any being, for a GM ------------------------------------------------------------------------


def test_a_gm_names_a_being_that_is_not_theirs(tmp_path: Path) -> None:
    world = Table()
    path = ledger(tmp_path, "- Rope")

    done = run(world, tmp_path, str(path), "-t", "table-one", "--owner", "brisk", "--yes")

    assert done.exit_code == 0, done.output
    assert world.created[0]["owner_character_id"] == str(BRISK)


def test_the_file_may_name_the_being_too(tmp_path: Path) -> None:
    world = Table()
    path = ledger(tmp_path, "- Rope", owner="Brisk")

    done = run(world, tmp_path, str(path), "-t", "table-one", "--yes")

    assert done.exit_code == 0, done.output
    assert world.created[0]["owner_character_id"] == str(BRISK)


def test_a_player_still_cannot_find_a_being_by_name(tmp_path: Path) -> None:
    world = Table(gm=False)
    path = ledger(tmp_path, "- Rope")

    done = run(world, tmp_path, str(path), "-t", "table-one", "--owner", "Brisk", "--yes")

    assert done.exit_code == 1
    assert "None of your characters here is called “Brisk”" in plain(done.output)
    assert world.created == []


def test_two_beings_with_one_name_are_listed_and_never_guessed(tmp_path: Path) -> None:
    world = Table(twins=True)
    path = ledger(tmp_path, "- Rope")

    done = run(world, tmp_path, str(path), "-t", "table-one", "--owner", "Brisk", "--yes")

    text = plain(done.output)
    assert done.exit_code == 1 and "More than one being is called “Brisk”" in text
    assert str(BRISK) in text and str(BRISK_TWIN) in text
    assert world.created == []


def test_your_own_character_wins_over_a_being_of_the_same_name(tmp_path: Path) -> None:
    world = Table(twins=True)
    world.mine = [(BRISK_TWIN, "Brisk")]
    path = ledger(tmp_path, "- Rope")

    done = run(world, tmp_path, str(path), "-t", "table-one", "--owner", "Brisk", "--yes")

    assert done.exit_code == 0, done.output
    assert world.created[0]["owner_character_id"] == str(BRISK_TWIN)


# --- --replace ----------------------------------------------------------------------------------


def owns_a_bag() -> list[dict[str, Any]]:
    bag = uuid.UUID(int=1001)
    return [thing(1, "Old bag"), thing(2, "Old rope", container=bag), thing(3, "Old coin")]


def test_without_a_flag_a_being_with_things_is_refused_and_told_both_ways(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())

    done = run(
        world, tmp_path, str(ledger(tmp_path, "- Rope")), "-t", "table-one", "--owner", "Brisk"
    )

    text = plain(done.output)
    assert done.exit_code == 1 and "--add" in text and "--replace" in text
    assert world.verbs() == []


def test_replace_deletes_what_the_being_owns_deepest_first_then_makes(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())
    path = ledger(tmp_path, "- Rope", "- Torch")

    done = run(
        world, tmp_path, str(path), "-t", "table-one", "--owner", "Brisk", "--replace", "--yes"
    )

    assert done.exit_code == 0, done.output
    assert world.verbs() == ["DELETE", "DELETE", "DELETE", "POST", "POST"]
    deleted = [r.url.path.rsplit("/", 1)[1] for r in world.seen if r.method == "DELETE"]
    assert deleted[0] == str(uuid.UUID(int=1002))  # the rope in the bag goes before the bag
    assert deleted.index(str(uuid.UUID(int=1001))) > deleted.index(str(uuid.UUID(int=1002)))
    assert "Deleted 3, made 2" in plain(done.output)
    assert world.owns == []


def test_replace_reads_the_whole_file_before_the_first_delete(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())
    path = ledger(tmp_path, "- 5 x Rope")  # a loose stack: a problem

    done = run(
        world, tmp_path, str(path), "-t", "table-one", "--owner", "Brisk", "--replace", "--yes"
    )

    assert done.exit_code == 1 and "a stack needs a container" in plain(done.output)
    assert world.verbs() == [] and len(world.owns) == 3


def test_replace_does_not_move_an_instance_it_is_about_to_delete(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())
    named_by_id = ledger(tmp_path, f"- Rope | ref: {uuid.UUID(int=1003)}")

    done = run(
        world,
        tmp_path,
        str(named_by_id),
        "-t",
        "table-one",
        "--owner",
        "Brisk",
        "--replace",
        "--yes",
    )

    assert done.exit_code == 0, done.output
    assert world.verbs().count("POST") == 1  # made new, not moved
    assert not any(r.method == "PUT" for r in world.seen)


def test_a_failed_delete_stops_before_anything_is_made(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag(), undeletable={uuid.UUID(int=1003)})
    path = ledger(tmp_path, "- Rope")

    done = run(
        world, tmp_path, str(path), "-t", "table-one", "--owner", "Brisk", "--replace", "--yes"
    )

    text = plain(done.output)
    assert done.exit_code == 1
    assert "Old coin: not deleted" in text and "Stopped before making anything" in text
    assert "POST" not in world.verbs()
    assert [t["title"] for t in world.owns] == ["Old coin"]  # the rest went; a rerun finishes


def test_replace_on_a_being_with_nothing_is_just_an_import(tmp_path: Path) -> None:
    world = Table()

    done = run(
        world, tmp_path, str(ledger(tmp_path, "- Rope")), "-t", "table-one", "--owner", "Brisk",
        "--replace", "--yes",
    )  # fmt: skip

    assert done.exit_code == 0 and world.verbs() == ["POST"]


def test_replace_asks_with_both_counts_and_declining_changes_nothing(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())
    path = ledger(tmp_path, "- Rope", "- Torch")
    runtime = Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(world.handler),
        interactive_override=True,
    )

    done = runner.invoke(
        app,
        ["inventory", "import", str(path), "-t", "table-one", "--owner", "Brisk", "--replace"],
        obj=runtime,
        input="n\n",
    )

    assert "Delete 3 and make 2?" in plain(done.output)
    assert done.exit_code == 1 and world.verbs() == []


def test_replace_with_nobody_to_ask_refuses_without_yes(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())

    done = run(
        world,
        tmp_path,
        str(ledger(tmp_path, "- Rope")),
        "-t",
        "table-one",
        "--owner",
        "Brisk",
        "--replace",
    )

    assert done.exit_code == 1 and "--yes" in plain(done.output)
    assert world.verbs() == []


def test_add_and_replace_are_alternatives_and_backup_needs_replace(tmp_path: Path) -> None:
    world = Table()
    path = str(ledger(tmp_path, "- Rope"))

    both = run(world, tmp_path, path, "-t", "table-one", "--add", "--replace", "--yes")
    lonely = run(world, tmp_path, path, "-t", "table-one", "--backup", "b.md", "--yes")

    assert both.exit_code == 2 and "alternatives" in plain(both.output)
    assert lonely.exit_code == 2 and "--backup goes with --replace" in plain(lonely.output)
    assert world.verbs() == []


def test_a_backup_is_written_before_anything_is_deleted(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())
    backup = tmp_path / "before.ledger.md"

    done = run(
        world, tmp_path, str(ledger(tmp_path, "- Rope")), "-t", "table-one", "--owner", "Brisk",
        "--replace", "--backup", str(backup), "--yes",
    )  # fmt: skip

    assert done.exit_code == 0, done.output
    text = backup.read_text(encoding="utf-8")
    assert text.startswith("format: lorenzo-ledger/1\n")
    assert "Old bag" in text and "Old coin" in text
    assert "Saved what Brisk has now" in plain(done.output)


# --- the display --------------------------------------------------------------------------------


def test_a_dry_run_shows_what_would_be_made_as_a_tree_and_does_nothing(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())
    lines = ["- Backpack", "  - 3 x Torch | note: x", "  - Hydra tooth"]
    path = ledger(tmp_path, "- Rope", *lines)

    done = run(
        world, tmp_path, str(path), "-t", "table-one", "--owner", "Brisk", "--replace", "--dry-run"
    )

    text = done.output
    assert done.exit_code == 0, text
    assert "3 to delete first" in plain(text)
    assert "Not carried" in text and "Hydra tooth" in text and "unsorted" in text
    assert "title: Rope" in plain(text)
    assert world.verbs() == []


def test_the_summary_is_on_standard_output_and_the_bar_is_not(tmp_path: Path) -> None:
    world = Table(owns=owns_a_bag())

    done = run(
        world, tmp_path, str(ledger(tmp_path, "- Rope")), "-t", "table-one", "--owner", "Brisk",
        "--replace", "--yes",
    )  # fmt: skip

    assert "Deleted 3, made 1" in done.stdout
    assert "Deleting" not in done.stdout


# --- the order of a delete ----------------------------------------------------------------------


def as_out(row: dict[str, Any]) -> ItemInstanceOut:
    return ItemInstanceOut.model_validate(row)


def test_deletion_order_puts_what_is_inside_before_what_holds_it() -> None:
    bag, box = uuid.UUID(int=1001), uuid.UUID(int=1002)
    things = [
        as_out(thing(1, "Bag")),
        as_out(thing(2, "Box", container=bag)),
        as_out(thing(3, "Coin", container=box)),
        as_out(thing(4, "Alone")),
    ]

    assert [d.name for d in deletion_order(things)] == ["Coin", "Box", "Alone", "Bag"]


def test_deletion_order_survives_a_loop() -> None:
    a, b = uuid.UUID(int=1001), uuid.UUID(int=1002)
    loop = [as_out(thing(1, "A", container=b)), as_out(thing(2, "B", container=a))]

    assert sorted(d.name for d in deletion_order(loop)) == ["A", "B"]


_ = (ROPE, TORCH)  # the base world's catalog, matched by title


# --- what is left alone -------------------------------------------------------------------------

ALICE = ASHFANG  # someone else's character, owning what sits in the being's things
FRIENDS_CHEST = uuid.UUID(int=9001)


def deleted_ids(world: Table) -> set[uuid.UUID]:
    return {uuid.UUID(r.url.path.rsplit("/", 1)[1]) for r in world.seen if r.method == "DELETE"}


def test_a_container_holding_someone_elses_thing_is_kept_with_what_is_around_it(
    tmp_path: Path,
) -> None:
    chest, bag = id_of(1), id_of(2)
    world = Table(
        owns=[
            thing(1, "Chest", holds=True),
            thing(2, "Bag", container=chest, holds=True),
            thing(3, "Rope", container=bag),
            thing(4, "Coin"),
        ],
        strangers={bag: [thing(50, "Alice's potion", container=bag, owner=ALICE)]},
    )

    done = run(
        world, tmp_path, str(ledger(tmp_path, "- Torch")), "-t", "table-one", "--owner", "Brisk",
        "--replace", "--yes",
    )  # fmt: skip

    text = plain(done.output)
    assert done.exit_code == 0, done.output
    assert deleted_ids(world) == {
        id_of(3),
        id_of(4),
    }  # the rope in the bag goes; bag and chest stay
    assert {t["title"] for t in world.owns} == {"Chest", "Bag"}
    assert "2 left alone" in text and "Bag: holds Alice's potion, which isn't theirs" in text
    assert "Chest: holds something that stays" in text
    assert "Deleted 2, made 1" in text


def test_a_thing_of_the_beings_in_someone_elses_container_is_kept_with_what_is_in_it(
    tmp_path: Path,
) -> None:
    pouch = id_of(2)
    world = Table(
        owns=[
            thing(1, "Sword", container=FRIENDS_CHEST),
            thing(2, "Pouch", container=FRIENDS_CHEST, holds=True),
            thing(3, "Coin", container=pouch),
            thing(4, "Loose rope"),
        ],
        container_names={FRIENDS_CHEST: "Alice's chest"},
    )

    done = run(
        world, tmp_path, str(ledger(tmp_path, "- Torch")), "-t", "table-one", "--owner", "Brisk",
        "--replace", "--yes",
    )  # fmt: skip

    text = plain(done.output)
    assert done.exit_code == 0, done.output
    assert deleted_ids(world) == {id_of(4)}  # only what is wholly the being's own
    assert text.count("is in Alice's chest, which isn't theirs") == 3  # sword, pouch, coin
    assert "3 left alone" in text


def test_a_dry_run_names_what_it_would_leave_alone_and_deletes_nothing(tmp_path: Path) -> None:
    world = Table(
        owns=[thing(1, "Sword", container=FRIENDS_CHEST), thing(2, "Coin")],
        container_names={FRIENDS_CHEST: "Alice's chest"},
    )

    done = run(
        world, tmp_path, str(ledger(tmp_path, "- Torch")), "-t", "table-one", "--owner", "Brisk",
        "--replace", "--dry-run",
    )  # fmt: skip

    text = plain(done.output)
    assert done.exit_code == 0 and "1 to delete first" in text
    assert "Sword: is in Alice's chest, which isn't theirs" in text
    assert world.verbs() == []


def test_split_keeps_everything_around_a_kept_container_and_survives_a_loop() -> None:
    from lorenzo_cli.inventory.plan import split_replacement

    box, bag = id_of(1), id_of(2)
    things = [
        as_out(thing(1, "Box", holds=True)),
        as_out(thing(2, "Bag", container=box, holds=True)),
        as_out(thing(3, "Loose")),
    ]
    doomed, kept = split_replacement(BRISK, things, {}, {bag: ["Potion"]})

    assert [d.name for d in doomed] == ["Loose"]
    assert [(k.name, k.why) for k in kept] == [
        ("Bag", "holds Potion, which isn't theirs"),
        ("Box", "holds something that stays"),
    ]
    loop = [
        as_out(thing(1, "A", container=id_of(2), holds=True)),
        as_out(thing(2, "B", container=id_of(1), holds=True)),
    ]
    doomed, kept = split_replacement(BRISK, loop, {}, {id_of(1): ["Potion"]})
    assert doomed == [] and {k.name for k in kept} == {"A", "B"}
