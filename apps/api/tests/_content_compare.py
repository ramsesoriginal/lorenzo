"""A strict deep comparison of two values that should be the same, for the release document
tests (ADR 0214): not `==`, which a list equals a list of the same things in another order of
nothing, and a `Decimal("1.50")` equals a `Decimal("1.5")`.
"""

import dataclasses
import math
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any

_LIMIT = 20


def differences(a: Any, b: Any, path: str = "$", out: list[str] | None = None) -> list[str]:
    """Where `a` and `b` differ, in class or value; empty when they are the same. The same
    means the same class of every container and scalar (a `defaultdict` is not a `dict`, a
    tuple is not a list, a set is not a list, `True` is not `1`), the same `Decimal` scale, the
    same order of every list and dict, and a NaN where there is a NaN. A `UUID` is any class
    of it: the database driver hands back its own subclass."""
    found: list[str] = [] if out is None else out
    if len(found) >= _LIMIT:
        return found
    if isinstance(a, uuid.UUID) and isinstance(b, uuid.UUID):
        if a != b or str(a) != str(b) or hash(a) != hash(b):
            found.append(f"{path}: {a} != {b}")
        return found
    if type(a) is not type(b):
        found.append(f"{path}: class {type(a).__name__} != {type(b).__name__}")
        return found
    if dataclasses.is_dataclass(a):
        for f in dataclasses.fields(a):
            differences(getattr(a, f.name), getattr(b, f.name), f"{path}.{f.name}", found)
    elif isinstance(a, defaultdict):
        if type(a.default_factory()) is not type(b.default_factory()):  # type: ignore[misc]
            found.append(f"{path}: the default factory makes another class")
        _mapping(a, b, path, found)
    elif isinstance(a, dict):
        _mapping(a, b, path, found)
    elif isinstance(a, list | tuple):
        if len(a) != len(b):
            found.append(f"{path}: {len(a)} items != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b, strict=False)):
            differences(x, y, f"{path}[{i}]", found)
    elif isinstance(a, set | frozenset):
        if a != b:
            found.append(f"{path}: the sets differ")
    elif isinstance(a, Decimal):
        if str(a) != str(b):
            found.append(f"{path}: {a!r} != {b!r}")
    elif isinstance(a, float):
        if not (a == b or (math.isnan(a) and math.isnan(b))):
            found.append(f"{path}: {a!r} != {b!r}")
    elif a != b:
        found.append(f"{path}: {a!r} != {b!r}"[:200])
    return found


def _mapping(a: dict[Any, Any], b: dict[Any, Any], path: str, found: list[str]) -> None:
    if set(a) == set(b) and list(a) != list(b):
        found.append(f"{path}: the same keys in another order")
    for key in a:
        if key not in b:
            found.append(f"{path}[{key!r}]: missing")
        else:
            differences(a[key], b[key], f"{path}[{key!r}]", found)
    for key in b:
        if key not in a:
            found.append(f"{path}[{key!r}]: extra")
