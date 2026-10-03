"""A small in-memory stand-in for the repository routes of apps/api (ADR 0118 to 0121).

Not a copy of the API: just enough of its answers, with its problem types, for the CLI's
commands to be driven through every branch they have. The routes' real behaviour is what the
end-to-end suite checks.
"""

from __future__ import annotations

import io
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime

REPO_ID = uuid.UUID(int=10)
TARGET_ID = uuid.UUID(int=20)
STRANGER_ID = uuid.UUID(int=30)
GROUP_ID = uuid.UUID(int=41)
DEFINITION_ID = uuid.UUID(int=42)
SLUG_ID = uuid.UUID(int=43)
PUBLISHED = "2026-10-01T12:00:00Z"
COPIED = "2026-10-02T12:00:00Z"
LATER = "2026-10-03T12:00:00Z"


def tenant(
    tenant_id: uuid.UUID, slug: str, kind: str, published_at: str | None = None
) -> dict[str, Any]:
    return {
        "id": str(tenant_id),
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "description": "",
        "kind": kind,
        "published_at": published_at,
        "npcs_shared_with_gms": True,
        "created_by": None,
        "updated_by": None,
    }


def problem(status: int, kind: str, detail: str, **extra: Any) -> httpx.Response:
    return httpx.Response(
        status,
        json={"type": kind, "title": detail, "detail": detail, **extra},
        headers={"content-type": "application/problem+json"},
    )


def step(
    *, granted: bool = True, published: bool = True, copied: bool = False, repo: uuid.UUID = REPO_ID
) -> dict[str, Any]:
    return {
        "repository_id": str(repo),
        "name": "Sunken Vale",
        "granted": granted,
        "published": published,
        "already_copied": copied,
        "entities": 12,
        "stat_groups": 2,
        "stat_definitions": 5,
        "information": 7,
        "dropped": [],
    }


def collision(kind: str, source: uuid.UUID, name: str, choices: list[str]) -> dict[str, Any]:
    return {
        "repository_id": str(REPO_ID),
        "kind": kind,
        "source_id": str(source),
        "name": name,
        "local_id": str(uuid.UUID(int=99)) if kind != "slug" else None,
        "choices": choices,
    }


GROUP_COLLISION = collision("stat_group", GROUP_ID, "Physical", ["rename", "merge", "skip"])
DEFINITION_COLLISION = collision(
    "stat_definition", DEFINITION_ID, "weight", ["rename", "merge", "skip"]
)
SLUG_COLLISION = collision("slug", SLUG_ID, "longsword", ["rename", "skip"])


def field_change(name: str, state: str, **extra: Any) -> dict[str, Any]:
    return {
        "field": name,
        "label": None,
        "state": state,
        "base": "a",
        "upstream": "b",
        "local": "a" if state == "clean" else "c",
        "added": None,
        "removed": None,
        **extra,
    }


def row_change(n: int, name: str, *states: str, kind: str = "entity") -> dict[str, Any]:
    return {
        "kind": kind,
        "source_id": str(uuid.UUID(int=100 + n)),
        "local_id": str(uuid.UUID(int=200 + n)),
        "name": name,
        "fields": [field_change(f"field{i}", state) for i, state in enumerate(states)],
    }


def added(n: int, name: str, with_collision: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "kind": "entity",
        "source_id": str(uuid.UUID(int=300 + n)),
        "name": name,
        "collision": with_collision,
    }


def removed(n: int, name: str) -> dict[str, Any]:
    return {
        "kind": "entity",
        "source_id": str(uuid.UUID(int=400 + n)),
        "local_id": str(uuid.UUID(int=500 + n)),
        "name": name,
    }


@dataclass
class World:
    """The repository `sunken-vale`, the tenant `table-one` that draws on it, and what happens."""

    published_at: str | None = PUBLISHED
    granted: bool = False
    copied: bool = False
    synced_at: str | None = None
    # Collisions a copy has to be given a choice for, until it is.
    collisions: list[dict[str, Any]] = field(default_factory=list)
    updates: dict[str, Any] = field(
        default_factory=lambda: {"changed": [], "removed": [], "deleted_locally": [], "added": []}
    )
    # What POST .../copy answers instead of copying, e.g. a problem.
    copy_answer: httpx.Response | None = None
    previous: dict[str, Any] | None = None
    repo_kind: str = "repository"
    log: list[httpx.Request] = field(default_factory=list)

    # -- the routes ------------------------------------------------------------------------------

    def writes(self) -> list[tuple[str, str]]:
        """Every request that could have changed something, as method and path."""
        return [(r.method, r.url.path) for r in self.log if r.method not in ("GET", "HEAD")]

    def bodies(self, method: str, suffix: str) -> list[dict[str, Any]]:
        return [
            json.loads(r.content) if r.content else {}
            for r in self.log
            if r.method == method and r.url.path.endswith(suffix)
        ]

    def handler(self, request: httpx.Request) -> httpx.Response:  # noqa: C901
        self.log.append(request)
        path, method = request.url.path, request.method
        repo, target = f"/tenants/{REPO_ID}", f"/tenants/{TARGET_ID}"

        if path == "/tenants" and method == "GET":
            rows = [
                {
                    "id": str(REPO_ID),
                    "slug": "sunken-vale",
                    "name": "Sunken Vale",
                    "role": "owner",
                    "kind": self.repo_kind,
                },
                {
                    "id": str(TARGET_ID),
                    "slug": "table-one",
                    "name": "Table One",
                    "role": "owner",
                    "kind": "play",
                },
            ]
            return httpx.Response(
                200, json={"items": rows, "total": 2, "page": 1, "size": 100, "pages": 1}
            )
        if path == repo and method == "GET":
            return httpx.Response(
                200, json=tenant(REPO_ID, "sunken-vale", self.repo_kind, self.published_at)
            )
        if path == target and method == "GET":
            return httpx.Response(200, json=tenant(TARGET_ID, "table-one", "play"))
        if path.startswith("/tenants/") and method == "GET" and path.count("/") == 2:
            return problem(404, "tenant-not-found", "No tenant of yours has that id.")

        # The repository's own side.
        if path == f"{repo}/published":
            self.published_at = LATER if method == "PUT" else None
            return httpx.Response(
                200, json=tenant(REPO_ID, "sunken-vale", self.repo_kind, self.published_at)
            )
        if path == f"{repo}/subscribers" and method == "GET":
            rows = (
                [
                    {
                        "tenant_id": str(TARGET_ID),
                        "name": "Table One",
                        "slug": "table-one",
                        "granted_at": PUBLISHED,
                        "granted_by": None,
                    }
                ]
                if self.granted
                else []
            )
            return httpx.Response(
                200, json={"items": rows, "total": len(rows), "page": 1, "size": 100, "pages": 1}
            )
        if path.startswith(f"{repo}/subscribers/"):
            subscriber = uuid.UUID(path.rsplit("/", 1)[1])
            if method == "PUT":
                new = not self.granted
                self.granted = True
                return httpx.Response(
                    201 if new else 200,
                    json={
                        "tenant_id": str(subscriber),
                        "name": "Table One",
                        "slug": "table-one",
                        "granted_at": PUBLISHED,
                        "granted_by": None,
                    },
                )
            self.granted = False
            return httpx.Response(204)

        # A drawing tenant's side.
        if path == f"{target}/repositories" and method == "GET":
            rows = []
            if self.granted or self.copied:
                rows.append(
                    {
                        "repository": {
                            "id": str(REPO_ID),
                            "name": "Sunken Vale",
                            "slug": "sunken-vale",
                            "description": "",
                            "published_at": self.published_at,
                        },
                        "granted_at": PUBLISHED if self.granted else None,
                        "copied_at": COPIED if self.copied else None,
                        "synced_at": self.synced_at,
                        "contributed": None,
                    }
                )
            return httpx.Response(
                200, json={"items": rows, "total": len(rows), "page": 1, "size": 100, "pages": 1}
            )
        copy_base = f"{target}/repositories/{REPO_ID}"
        if path == f"{copy_base}/copy-plan":
            return httpx.Response(
                200,
                json={
                    "steps": [step(granted=self.granted, copied=self.copied)],
                    "collisions": self.collisions,
                },
            )
        if path == f"{copy_base}/copy" and method == "POST":
            return self._copy(json.loads(request.content or b"{}"))
        if path == f"{copy_base}/updates" and method == "GET":
            return httpx.Response(200, json={"repository_id": str(REPO_ID), **self.updates})
        if path == f"{copy_base}/updates" and method == "POST":
            body = json.loads(request.content)
            kinds = [a["action"] for a in body["actions"]]
            return httpx.Response(
                200,
                json={
                    "dry_run": bool(body.get("dry_run")),
                    "applied": kinds.count("apply"),
                    "added": kinds.count("add"),
                    "detached": kinds.count("detach"),
                    "not_applied": [],
                },
            )
        return problem(404, "not-found", f"No route {method} {path} in the test world.")

    def _copy(self, body: dict[str, Any]) -> httpx.Response:
        if self.copy_answer is not None:
            return self.copy_answer
        if self.copied and not body.get("again"):
            return problem(
                409, "repository-already-copied", "This repository has already been copied"
            )
        chosen = {(r["kind"], r["source_id"]): r["action"] for r in body.get("resolutions", [])}
        for c in self.collisions:
            action = chosen.get((c["kind"], c["source_id"]))
            if action is not None and action not in c["choices"]:
                return problem(
                    422, "invalid-repository-copy-choice", "That choice can't be applied"
                )
        open_ = [c for c in self.collisions if (c["kind"], c["source_id"]) not in chosen]
        if open_:
            return problem(
                409,
                "repository-copy-needs-choices",
                "Choose rename, merge, or skip for each one",
                collisions=open_,
            )
        dry = bool(body.get("dry_run"))
        if not dry:
            self.copied = True
        return httpx.Response(
            200 if dry else 201,
            json={"steps": [step()], "dry_run": dry, "previous": self.previous},
        )


def runtime(tmp_path: Path, world: World, *, interactive: bool | None = None) -> Runtime:
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(world.handler),
        interactive_override=interactive,
    )
