"""An imported item's identity (RFC 0025 R4, ADR 0144): its entity slug,
`<namespace>-<list>-<slugified key>`, for example `basic-weapons-longsword`.

Identity is a pure function of the input: the namespace is declared in the map (not derived from
an item's own `source`, which changes), the list is the MPMB list, and the key is the source
file's own object key. That is what makes a second run recognise what the first one made.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable

MAX_SLUG = 100
# "-" and six hex digits, appended to break a collision.
_SUFFIX = 7

# The MPMB variable's name without "List", lower-cased.
LIST_TOKENS = {
    "WeaponsList": "weapons",
    "ArmourList": "armour",
    "GearList": "gear",
    "PacksList": "packs",
    "ToolsList": "tools",
    "AmmoList": "ammo",
}


def slugify(text: str) -> str:
    """Lower-case ASCII letters and digits joined by single hyphens."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "item"


def base_slug(namespace: str, list_token: str, key: str) -> str:
    """The slug before any collision suffix. The readable part is cut short enough that a suffix
    always fits, so the same key gets the same base slug however the run turns out."""
    prefix = f"{namespace}-{list_token}-"
    room = MAX_SLUG - len(prefix) - _SUFFIX
    readable = slugify(key)[:room].rstrip("-") or "item"
    return prefix + readable


def collision_suffix(list_token: str, key: str) -> str:
    return hashlib.sha256((list_token + key).encode()).hexdigest()[:6]


def assign_slugs(
    items: Iterable[tuple[str, str, str]], taken: set[str] | None = None
) -> dict[tuple[str, str], str]:
    """`items` are `(namespace, list token, raw key)`; the result maps `(list token, key)` to its
    final slug. Only the members of a collision take a suffix, and every member does, so which one
    got there first can't matter. `taken` are slugs the tenant already holds for something else.
    """
    by_base: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for namespace, list_token, key in items:
        by_base[base_slug(namespace, list_token, key).lower()].append((list_token, key))
    slugs: dict[tuple[str, str], str] = {}
    for base, members in by_base.items():
        unique = sorted(set(members))
        clash = len(unique) > 1 or base in (taken or set())
        for list_token, key in unique:
            slugs[(list_token, key)] = (
                f"{base}-{collision_suffix(list_token, key)}" if clash else base
            )
    return slugs
