"""A release's `Content` as a document, and back - ADR 0214, RFC 0037 §4.

A release of a public repository stores the repository's content as it was. This module is
the format and nothing else: no database, no session. `encode` turns a `Content` into plain
JSON data and the files it refers to; `decode` builds the `Content` again, field for field,
in the order it was written; `dumps` and `loads` are the gzipped bytes that are stored.

The format is a table of codecs, one for each field of each dataclass in a `Content`. Writing
a `Content` whose classes have a field with no codec is an error, so a release is never made
from a `Content` that has outgrown the format: it needs a codec here, and a new version if it
changes what a document holds. A document is read by the reader of its version (`READERS`);
version 1 is below, and a golden file of it in the tests keeps it readable.

What the format does with what JSON cannot say:

- ids are strings, tuples are lists, sets are sorted lists, `Decimal` is its string (so its
  scale survives), `StatValueType` is its value;
- a non-finite float is a string (`"nan"`, `"inf"`, `"-inf"`): the API stores them, standard
  JSON has no such number, and the writer is run with `allow_nan` off, so a value it forgot
  is an error and never a bare `NaN` in a document;
- a picture's or a document's bytes are not in the document: the payload holds their
  SHA-256, and the bytes are the second thing `encode` returns.
"""

import dataclasses
import gzip
import hashlib
import json
import math
import uuid
import zlib
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from lorenzo_api.models import StatValueType
from lorenzo_api.repository_content import (
    Content,
    Formula,
    InformationData,
    Links,
    PayloadData,
    StatValue,
)

FORMAT = 21

Document = dict[str, Any]
Files = dict[str, bytes]


class ReleaseDocumentError(Exception):
    """Something about a release document that its caller has to be told."""


class ContentFieldNotSerialisedError(ReleaseDocumentError):
    """A `Content`, or a part of one, has a field the format has no codec for."""


class UnknownDocumentFormatError(ReleaseDocumentError):
    """A document of a version this code has no reader for."""


class ReleaseDocumentCorruptError(ReleaseDocumentError):
    """Bytes that are not a document, or a document that does not hold together."""


# --- Codecs --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Codec:
    """How one value is written and read. `files` is where the bytes of files are put while
    writing and found while reading."""

    encode: Callable[[Any, Files], Any]
    decode: Callable[[Any, Files], Any]


_PLAIN = _Codec(lambda v, f: v, lambda v, f: v)
_ID = _Codec(lambda v, f: str(v), lambda v, f: uuid.UUID(v))
_DECIMAL = _Codec(lambda v, f: str(v), lambda v, f: Decimal(v))
_VALUE_TYPE = _Codec(lambda v, f: v.value, lambda v, f: StatValueType(v))

_NON_FINITE = {"nan": float("nan"), "inf": math.inf, "-inf": -math.inf}


def _write_float(value: float, files: Files) -> float | str:
    if math.isfinite(value):
        return value
    return "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")


def _read_float(value: float | str, files: Files) -> float:
    if isinstance(value, str):
        return _NON_FINITE[value]
    return float(value)


_FLOAT = _Codec(_write_float, _read_float)


def _optional(codec: _Codec) -> _Codec:
    return _Codec(
        lambda v, f: None if v is None else codec.encode(v, f),
        lambda v, f: None if v is None else codec.decode(v, f),
    )


def _id_map(value: _Codec) -> _Codec:
    """A dict keyed by id: a JSON object, in the order it has."""
    return _Codec(
        lambda m, f: {str(k): value.encode(v, f) for k, v in m.items()},
        lambda m, f: {uuid.UUID(k): value.decode(v, f) for k, v in m.items()},
    )


def _text_map(value: _Codec) -> _Codec:
    return _Codec(
        lambda m, f: {k: value.encode(v, f) for k, v in m.items()},
        lambda m, f: {k: value.decode(v, f) for k, v in m.items()},
    )


def _pair(first: _Codec, second: _Codec) -> _Codec:
    """A tuple of two: a list of two."""
    return _Codec(
        lambda t, f: [first.encode(t[0], f), second.encode(t[1], f)],
        lambda t, f: (first.decode(t[0], f), second.decode(t[1], f)),
    )


def _pairs(first: _Codec, second: _Codec) -> _Codec:
    """A list of tuples of two, in order."""
    pair = _pair(first, second)
    return _Codec(
        lambda ts, f: [pair.encode(t, f) for t in ts],
        lambda ts, f: [pair.decode(t, f) for t in ts],
    )


def _pair_set(first: _Codec, second: _Codec) -> _Codec:
    """A set of tuples of two: a list, sorted by how its ids read."""
    pair = _pair(first, second)
    return _Codec(
        lambda ts, f: sorted((pair.encode(t, f) for t in ts), key=lambda p: (str(p[0]), str(p[1]))),
        lambda ts, f: {pair.decode(t, f) for t in ts},
    )


_ID_SET = _Codec(lambda s, f: sorted(str(v) for v in s), lambda s, f: {uuid.UUID(v) for v in s})
_TEXT_SET = _Codec(lambda s, f: sorted(s), lambda s, f: set(s))


def _keyed(value: _Codec) -> _Codec:
    """A dict keyed by two ids: a list of `[first, second, value]`, in order."""
    return _Codec(
        lambda m, f: [[str(a), str(b), value.encode(v, f)] for (a, b), v in m.items()],
        lambda rows, f: {(uuid.UUID(a), uuid.UUID(b)): value.decode(v, f) for a, b, v in rows},
    )


def _record(keys: Mapping[str, _Codec], *, name: str) -> _Codec:
    """A dict with a fixed set of keys, each with its own codec. A key the codec does not know
    is an error on writing: the dict has outgrown the format."""

    def encode(record: dict[str, Any], files: Files) -> dict[str, Any]:
        unknown = sorted(set(record) - keys.keys())
        if unknown:
            raise ContentFieldNotSerialisedError(f"{name}.{unknown[0]}")
        return {k: codec.encode(record[k], files) for k, codec in keys.items()}

    def decode(record: dict[str, Any], files: Files) -> dict[str, Any]:
        return {k: codec.decode(record[k], files) for k, codec in keys.items()}

    return _Codec(encode, decode)


def _dataclass(cls: type, table: Mapping[str, _Codec]) -> _Codec:
    """An instance of a dataclass as an object keyed by its field names. A field of the
    instance's class that the table has no codec for is an error on writing. Reading builds
    the fields the class makes with a `defaultdict` as the same, so the instance is as the
    loader makes it."""

    def encode(obj: Any, files: Files) -> dict[str, Any]:
        names = [f.name for f in dataclasses.fields(obj)]
        unknown = [n for n in names if n not in table]
        if unknown:
            raise ContentFieldNotSerialisedError(f"{type(obj).__name__}.{unknown[0]}")
        return {n: table[n].encode(getattr(obj, n), files) for n in names}

    def decode(data: dict[str, Any], files: Files) -> Any:
        values: dict[str, Any] = {}
        for f in dataclasses.fields(cls):
            value = table[f.name].decode(data[f.name], files)
            if f.default_factory is not dataclasses.MISSING:
                made = f.default_factory()
                if isinstance(made, defaultdict):
                    made.update(value)
                    value = made
            values[f.name] = value
        return cls(**values)

    return _Codec(encode, decode)


def _file(sha256: str, files: Files) -> bytes:
    try:
        return files[sha256]
    except KeyError:
        raise ReleaseDocumentCorruptError(f"the file {sha256} is not there") from None


def _payload_fields(kind: str) -> _Codec:
    """The fields of a payload of one kind: a picture's or a document's bytes become the
    SHA-256 of them, and the bytes go to the files."""
    if kind in ("picture", "document"):
        names = ("filename", "file_type") if kind == "document" else ("file_type",)
        plain = _record({n: _PLAIN for n in names}, name=f"PayloadData.fields[{kind}]")

        def encode(fields: dict[str, Any], files: Files) -> dict[str, Any]:
            rest = {k: v for k, v in fields.items() if k != "data"}
            written = plain.encode(rest, files)
            digest = hashlib.sha256(fields["data"]).hexdigest()
            files[digest] = bytes(fields["data"])
            return {"sha256": digest, **written}

        def decode(fields: dict[str, Any], files: Files) -> dict[str, Any]:
            read = plain.decode({k: v for k, v in fields.items() if k != "sha256"}, files)
            return {"data": _file(fields["sha256"], files), **read}

        return _Codec(encode, decode)
    if kind == "description":
        return _record(
            {"locale": _PLAIN, "content": _PLAIN}, name="PayloadData.fields[description]"
        )
    if kind == "number":
        return _record({"value": _DECIMAL}, name="PayloadData.fields[number]")
    raise ReleaseDocumentError(f"a payload of the kind {kind!r}")


def _payload(obj: PayloadData, files: Files) -> dict[str, Any]:
    unknown = [f.name for f in dataclasses.fields(obj) if f.name not in _PAYLOAD_TABLE]
    if unknown:
        raise ContentFieldNotSerialisedError(f"{type(obj).__name__}.{unknown[0]}")
    return {
        "information_id": str(obj.information_id),
        "order": obj.order,
        "kind": obj.kind,
        "fields": _payload_fields(obj.kind).encode(obj.fields, files),
    }


def _read_payload(data: dict[str, Any], files: Files) -> PayloadData:
    return PayloadData(
        information_id=uuid.UUID(data["information_id"]),
        order=data["order"],
        kind=data["kind"],
        fields=_payload_fields(data["kind"]).decode(data["fields"], files),
    )


_PAYLOAD_TABLE = frozenset({"information_id", "order", "kind", "fields"})
_PAYLOAD = _Codec(_payload, _read_payload)

_STAT_VALUE = _dataclass(
    StatValue,
    {
        "value_int": _PLAIN,
        "value_text": _PLAIN,
        "value_float": _optional(_FLOAT),
        "value_bool": _PLAIN,
    },
)

_FORMULA = _dataclass(
    Formula,
    {
        "kind": _PLAIN,
        "source": _optional(_ID),
        "multiplier": _optional(_DECIMAL),
        "offset": _optional(_DECIMAL),
        "round_mode": _PLAIN,
        "left": _optional(_ID),
        "comparator": _PLAIN,
        "right": _optional(_ID),
        "right_constant": _optional(_DECIMAL),
        "true_value": _PLAIN,
        "false_value": _PLAIN,
        "terms": _optional(
            _Codec(
                lambda terms, f: [[str(s), str(c)] for s, c in terms],
                lambda terms, f: [(uuid.UUID(s), Decimal(c)) for s, c in terms],
            )
        ),
    },
)

_INFORMATION = _dataclass(
    InformationData,
    {
        "entity_id": _ID,
        "title": _PLAIN,
        "type": _PLAIN,
        "is_public": _PLAIN,
        "order": _PLAIN,
    },
)

_LINKS = _dataclass(
    Links,
    {
        "entity": _id_map(_ID),
        "stat_group": _id_map(_ID),
        "stat_definition": _id_map(_ID),
        "origin_tenant": _id_map(_ID),
        "merged": _ID_SET,
        "deleted": _text_map(_ID_SET),
        "snapshots": _id_map(_PLAIN),
        "copies": _ID_SET,
        "attachments": _id_map(_pair_set(_ID, _ID)),
    },
)

_CONTENT = _dataclass(
    Content,
    {
        "tenant_id": _ID,
        "entities": _id_map(_PLAIN),
        "kinds": _id_map(_TEXT_SET),
        "in_public_catalog": _id_map(_PLAIN),
        "slugs": _id_map(_PLAIN),
        "prototypes": _pairs(_ID, _ID),
        "groups": _id_map(
            _record(
                {"name": _PLAIN, "priority": _PLAIN, "mandatory": _PLAIN},
                name="Content.groups",
            )
        ),
        "definitions": _id_map(
            _record(
                {
                    "name": _PLAIN,
                    "value_type": _VALUE_TYPE,
                    "group": _ID,
                    "unit": _PLAIN,
                    "adjustable_in_play": _PLAIN,
                    "pin": _PLAIN,
                    "signed": _PLAIN,
                    "position": _PLAIN,
                    "hints": _record(
                        {
                            "max_hint": _optional(_ID),
                            "min_hint": _optional(_ID),
                            "resolved_hint": _optional(_ID),
                        },
                        name="Content.definitions.hints",
                    ),
                },
                name="Content.definitions",
            )
        ),
        "enum_values": _id_map(
            _Codec(
                lambda vs, f: [[value, order] for value, order in vs],
                lambda vs, f: [(value, order) for value, order in vs],
            )
        ),
        "entity_groups": _pairs(_ID, _ID),
        "stats": _keyed(_STAT_VALUE),
        "formulas": _keyed(_FORMULA),
        "containment": _id_map(_pair(_ID, _PLAIN)),
        "ownership": _id_map(_ID),
        "group_members": _pairs(_ID, _ID),
        "information": _id_map(_INFORMATION),
        "payloads": _id_map(_PAYLOAD),
        "knowledge": _pairs(_ID, _ID),
        "calendar_periods": _id_map(
            _record(
                {
                    "calendar": _ID,
                    "year": _PLAIN,
                    "segment": _PLAIN,
                    "day": _PLAIN,
                    "parent": _optional(_ID),
                },
                name="Content.calendar_periods",
            )
        ),
        "entry_dates": _pairs(_ID, _ID),
        "event_participants": _pairs(_ID, _ID),
        "event_learning": _Codec(
            lambda rows, f: [[str(a), str(b), str(i)] for a, b, i in rows],
            lambda rows, f: [(uuid.UUID(a), uuid.UUID(b), uuid.UUID(i)) for a, b, i in rows],
        ),
        "shared_event_relationships": _Codec(
            lambda rows, f: [[str(a), str(b), k] for a, b, k in rows],
            lambda rows, f: [(uuid.UUID(a), uuid.UUID(b), k) for a, b, k in rows],
        ),
        "lived_before": _Codec(
            lambda rows, f: [[str(b), str(a), str(z), shared] for b, a, z, shared in rows],
            lambda rows, f: [
                (uuid.UUID(b), uuid.UUID(a), uuid.UUID(z), shared) for b, a, z, shared in rows
            ],
        ),
        "event_relationships": _Codec(
            lambda rows, f: [[str(a), str(b), k] for a, b, k in rows],
            lambda rows, f: [(uuid.UUID(a), uuid.UUID(b), k) for a, b, k in rows],
        ),
        "calendars": _id_map(_PLAIN),
        "entity_locations": _id_map(_ID),
        "maps": _id_map(
            _record(
                {"system": _PLAIN, "subject": _optional(_ID), "theme": _optional(_PLAIN)},
                name="Content.maps",
            )
        ),
        "map_placements": _keyed(_PLAIN),
        "location_parts": _id_map(
            _record({"parent": _ID, "ordinal": _PLAIN}, name="Content.location_parts")
        ),
        "clocks": _id_map(_PLAIN),
        "clock_readings": _keyed(_PLAIN),
        "clock_relationships": _keyed(_PLAIN),
        "calendar_reckonings": _keyed(_PLAIN),
        "scene_facts": _keyed(_PLAIN),
        "scene_events": _keyed(_PLAIN),
        "scene_beings": _keyed(_PLAIN),
        "scenes": _id_map(_optional(_ID)),
        "editions": _id_map(_ID),
        "tellings": _id_map(
            _record(
                {"scene": _ID, "viewpoint": _optional(_ID), "shared": _PLAIN},
                name="Content.tellings",
            )
        ),
        "writing_biographies": _Codec(
            lambda rows, f: [str(i) for i in sorted(rows)],
            lambda rows, f: {uuid.UUID(i) for i in rows},
        ),
        "manuscript_placements": _id_map(
            _record(
                {"parent": _ID, "before": _optional(_ID), "position": _PLAIN},
                name="Content.manuscript_placements",
            )
        ),
        "observances": _id_map(
            _record({"calendar": _ID, "rule": _PLAIN}, name="Content.observances")
        ),
        "participant_entry_audiences": _Codec(
            lambda rows, f: [str(i) for i in rows], lambda rows, f: [uuid.UUID(i) for i in rows]
        ),
        "participant_information_audiences": _Codec(
            lambda rows, f: [str(i) for i in rows], lambda rows, f: [uuid.UUID(i) for i in rows]
        ),
        "entry_audiences": _id_map(_PLAIN),
        "entry_knowledge": _pairs(_ID, _ID),
        "fact_about": _pairs(_ID, _ID),
        "links": _LINKS,
    },
)


# --- Writing and reading -------------------------------------------------------------------


def encode(content: Content) -> tuple[Document, Files]:
    """The document, as plain JSON data, and the files it refers to by SHA-256."""
    files: Files = {}
    document: Document = _CONTENT.encode(content, files)
    return document, files


def _read_v1(document: Document, files: Mapping[str, bytes]) -> Content:
    # V1 predates fact audiences and subjects. Do not mutate a cached document.
    return _read_v2(
        {**document, "entry_audiences": {}, "entry_knowledge": [], "fact_about": []}, files
    )


def _read_v2(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v3({**document, "calendars": {}}, files)


def _read_v3(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v4({**document, "calendar_periods": {}, "entry_dates": []}, files)


def _read_v4(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v5({**document, "observances": {}}, files)


def _read_v5(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v6({**document, "event_relationships": []}, files)


def _read_v6(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v7({**document, "event_participants": []}, files)


def _read_v7(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v8({**document, "event_learning": []}, files)


def _read_v8(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v9({**document, "shared_event_relationships": []}, files)


def _read_v9(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v10(
        {**document, "participant_entry_audiences": [], "participant_information_audiences": []},
        files,
    )


def _read_v10(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v11({**document, "scenes": {}}, files)


def _read_v11(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v12({**document, "scene_facts": [], "scene_events": [], "scene_beings": []}, files)


def _read_v12(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v13({**document, "lived_before": []}, files)


def _read_v13(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v14(
        {**document, "clocks": {}, "clock_readings": [], "calendar_reckonings": []}, files
    )


def _read_v14(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v15({**document, "clock_relationships": []}, files)


def _read_v15(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v16({**document, "editions": {}, "manuscript_placements": {}}, files)


def _read_v16(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v17({**document, "tellings": {}, "writing_biographies": []}, files)


def _read_v17(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v18({**document, "location_parts": {}}, files)


def _read_v18(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v19({**document, "entity_locations": {}}, files)


def _read_v19(document: Document, files: Mapping[str, bytes]) -> Content:
    return _read_v20({**document, "maps": {}, "map_placements": []}, files)


def _read_v20(document: Document, files: Mapping[str, bytes]) -> Content:
    maps = {key: {**record, "theme": None} for key, record in document["maps"].items()}
    return _read_v21({**document, "maps": maps}, files)


def _read_v21(document: Document, files: Mapping[str, bytes]) -> Content:
    content: Content = _CONTENT.decode(document, dict(files))
    return content


# Every version this code can read. A change to `Content` or to the format above that changes
# what a document holds is a new version and a new reader; the old reader stays.
READERS: dict[int, Callable[[Document, Mapping[str, bytes]], Content]] = {
    1: _read_v1,
    2: _read_v2,
    3: _read_v3,
    4: _read_v4,
    5: _read_v5,
    6: _read_v6,
    7: _read_v7,
    8: _read_v8,
    9: _read_v9,
    10: _read_v10,
    11: _read_v11,
    12: _read_v12,
    13: _read_v13,
    14: _read_v14,
    15: _read_v15,
    16: _read_v16,
    17: _read_v17,
    18: _read_v18,
    19: _read_v19,
    20: _read_v20,
    21: _read_v21,
}


def decode(document: Document, files: Mapping[str, bytes], *, format: int = FORMAT) -> Content:  # noqa: A002
    """The `Content` of a document of a version, given the files it refers to."""
    reader = READERS.get(format)
    if reader is None:
        raise UnknownDocumentFormatError(f"no reader for release documents of format {format}")
    try:
        return reader(document, files)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ReleaseDocumentCorruptError(
            f"the document does not hold together: {error!r}"
        ) from error


def dumps(document: Document) -> bytes:
    """The document as stored: compact JSON, gzipped with no time in the header, so the same
    document is the same bytes."""
    try:
        text = json.dumps(document, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ReleaseDocumentError(f"the document cannot be written as JSON: {error}") from error
    return gzip.compress(text.encode(), mtime=0)


def loads(data: bytes) -> Document:
    try:
        loaded = json.loads(gzip.decompress(data))
    except (OSError, EOFError, zlib.error, ValueError) as error:
        raise ReleaseDocumentCorruptError(
            f"these bytes are not a release document: {error}"
        ) from error
    if not isinstance(loaded, dict):
        raise ReleaseDocumentCorruptError("these bytes are not a release document: not an object")
    return loaded
