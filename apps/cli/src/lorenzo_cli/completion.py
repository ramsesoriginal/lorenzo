"""Completing names from a private cache (ADR 0507).

Tab never asks the API: library slugs, and per library its systems, stat groups, stats, templates,
features and campaigns, are completed from one small file under `$XDG_CACHE_HOME/lorenzo/`. The
file is kept current by the reads and writes commands already make (`Recorder`, fed by the
client), never by a request of its own. There is one file per API address and account, created
`0600` like the stored login, and `logout` deletes it.

Imported by the root's completion path, so it imports only the standard library.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

FORMAT = 1
# The categories one library's names are kept in.
CATEGORIES = ("systems", "stat_groups", "stats", "templates", "features", "campaigns")

# operation id -> (category, the field that is the name, how the reply is read)
# "page" is a page of rows, "row" one row, "rows" a plain list, "delete" removes the row whose id
# is the path's last parameter.
_RULES: dict[str, tuple[str, str, str]] = {
    "list_tenants": ("libraries", "slug", "page"),
    "get_tenant": ("libraries", "slug", "row"),
    "create_tenant": ("libraries", "slug", "row"),
    "update_tenant": ("libraries", "slug", "row"),
    "delete_tenant": ("libraries", "slug", "delete"),
    "list_systems": ("systems", "slug", "page"),
    "get_system": ("systems", "slug", "row"),
    "create_system": ("systems", "slug", "row"),
    "update_system": ("systems", "slug", "row"),
    "delete_system": ("systems", "slug", "delete"),
    "list_stat_groups": ("stat_groups", "name", "page"),
    "get_stat_group": ("stat_groups", "name", "row"),
    "create_stat_group": ("stat_groups", "name", "row"),
    "update_stat_group": ("stat_groups", "name", "row"),
    "delete_stat_group": ("stat_groups", "name", "delete"),
    "list_stat_definitions": ("stats", "name", "page"),
    "get_stat_definition": ("stats", "name", "row"),
    "create_stat_definition": ("stats", "name", "row"),
    "update_stat_definition": ("stats", "name", "row"),
    "delete_stat_definition": ("stats", "name", "delete"),
    "list_templates": ("templates", "name", "page"),
    "matching_templates": ("templates", "name", "rows"),
    "get_template": ("templates", "name", "row"),
    "create_template": ("templates", "name", "row"),
    "replace_template": ("templates", "name", "row"),
    "delete_template": ("templates", "name", "delete"),
    "list_campaigns": ("campaigns", "slug", "page"),
    "get_campaign": ("campaigns", "slug", "row"),
    "create_campaign": ("campaigns", "slug", "row"),
    "update_campaign": ("campaigns", "slug", "row"),
    # A feature is an entry of the kind `feature`, completed by its slug.
    "export_entities": ("features", "slug", "page"),
    "get_entity": ("features", "slug", "row"),
    "delete_entity": ("features", "slug", "delete"),
}
# A page that is a complete list replaces what was cached; a filtered one only adds to it.
_PAGING = {"page", "size"}


def cache_path(env: Mapping[str, str], api_url: str, account: str) -> Path:
    base = env.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    key = hashlib.sha256(f"{api_url.rstrip('/')}\n{account}".encode()).hexdigest()[:24]
    return root / "lorenzo" / f"names-{key}.json"


def account_of(token: str | None) -> str | None:
    """Who a token is for, read without asking anyone: a JWT's issuer and subject, or for any
    other token (a personal access token) a digest of it."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) == 3:
        try:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(padded))
            if isinstance(claims, dict) and claims.get("sub"):
                return f"{claims.get('iss', '')} {claims['sub']}"
        except ValueError:
            pass
    return "token " + hashlib.sha256(token.encode()).hexdigest()


def stored_token(env: Mapping[str, str], credentials: Path) -> str | None:
    """The token a command would use, as completion can know it: `LORENZO_TOKEN`, else the stored
    login. A token piped in with `--token-stdin` is never cached."""
    if env.get("LORENZO_TOKEN"):
        return env["LORENZO_TOKEN"]
    try:
        token = json.loads(credentials.read_text(encoding="utf-8")).get("access_token")
    except OSError, ValueError, AttributeError:
        return None
    return token if isinstance(token, str) else None


def _empty() -> dict[str, Any]:
    return {"format": FORMAT, "libraries": {}, "names": {}}


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return _empty()
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        return _empty()
    return data


def save(path: Path, data: Mapping[str, Any]) -> None:
    """Written whole, `0600` from the start, in a `0700` directory, like the stored login."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.unlink(missing_ok=True)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(data, handle, separators=(",", ":"), sort_keys=True)
    temporary.replace(path)


def forget(path: Path) -> bool:
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def _field(row: Any, name: str) -> Any:
    return row.get(name) if isinstance(row, Mapping) else getattr(row, name, None)


def _is_feature(row: Any) -> bool:
    kinds = _field(row, "kinds") or []
    return any(str(getattr(kind, "value", kind)) == "feature" for kind in kinds)


class Recorder:
    """What the client saw, written to the cache once, when the client closes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] | None = None
        self.changed = False

    @property
    def data(self) -> dict[str, Any]:
        if self._data is None:
            self._data = load(self.path)
        return self._data

    def _table(self, category: str, library: str | None) -> dict[str, str] | None:
        if category == "libraries":
            table: dict[str, str] = self.data.setdefault("libraries", {})
            return table
        if library is None:
            return None
        names = self.data.setdefault("names", {}).setdefault(library, {})
        table = names.setdefault(category, {})
        return table

    def saw(
        self,
        operation_id: str,
        path: Mapping[str, object],
        query: Mapping[str, object] | None,
        value: Any,
    ) -> None:
        rule = _RULES.get(operation_id)
        if rule is None:
            return
        with self._lock:  # a command may read four at a time
            self._saw(rule, path, query, value)

    def _saw(
        self,
        rule: tuple[str, str, str],
        path: Mapping[str, object],
        query: Mapping[str, object] | None,
        value: Any,
    ) -> None:
        category, name_field, shape = rule
        library = str(path["tenant_id"]) if "tenant_id" in path else None
        table = self._table(category, library)
        if table is None:
            return
        if shape == "delete":
            gone = str(list(path.values())[-1])
            if table.pop(gone, None) is not None:
                self.changed = True
            return
        if shape == "row":
            rows = [value]
        elif shape == "rows":
            rows = list(value or [])
        else:
            rows = list(_field(value, "items") or [])
        if category == "features":
            rows = [row for row in rows if _is_feature(row)]
        seen = {
            str(_field(row, "id")): str(_field(row, name_field))
            for row in rows
            if _field(row, "id") is not None and _field(row, name_field)
        }
        complete = (
            shape == "page"
            and category != "features"
            and _field(value, "page") == 1
            and _field(value, "total") == len(rows)
            and not set(query or {}) - _PAGING
        )
        updated = seen if complete else {**table, **seen}
        if updated != table:
            table.clear()
            table.update(updated)
            self.changed = True

    def flush(self) -> None:
        if not self.changed:
            return
        try:
            save(self.path, self.data)
        except OSError:
            return  # a cache that can't be written only completes less
        self.changed = False


# --- completing ------------------------------------------------------------------------------


def _library_id(data: Mapping[str, Any], tenant: str | None) -> str | None:
    if not tenant:
        return None
    libraries: Mapping[str, str] = data.get("libraries", {})
    if tenant in libraries:
        return tenant
    return next((id_ for id_, slug in libraries.items() if slug == tenant), None)


def library_slugs(data: Mapping[str, Any], incomplete: str) -> list[str]:
    return sorted(s for s in data.get("libraries", {}).values() if s.startswith(incomplete))


def names(data: Mapping[str, Any], tenant: str | None, category: str, incomplete: str) -> list[str]:
    library = _library_id(data, tenant)
    if library is None:
        return []
    table: Mapping[str, str] = data.get("names", {}).get(library, {}).get(category, {})
    return sorted({n for n in table.values() if n.startswith(incomplete)})
