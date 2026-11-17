"""The library document's own checks, before any library is read (ADR 0484)."""

from __future__ import annotations

import pytest

from lorenzo_cli.library.document import DocumentError, json_schema, parse

SMALL = """
format = 1
name = "ds"
requires = ["neutral"]

[system]
slug = "ds"
name = "Dust and Sun"
root = "ds-root"

[[group]]
name = "ds_vitals"
system = true

[[stat]]
name = "ds_stamina"
group = "ds_vitals"
type = "int"
min = 0
max = 20

[[stat]]
name = "ds_bite"
group = "ds_vitals"
type = "dice"

[[entry]]
slug = "ds-root"
name = "Dust and Sun"

[[entry]]
slug = "ds-hunter"
name = "Hunter"
parents = ["ds-root"]
stats = { ds_stamina = 12, ds_bite = "1d6" }
"""


def test_a_small_system_reads() -> None:
    doc = parse(SMALL)
    assert doc.system is not None and doc.system.slug == "ds"
    assert [s.name for s in doc.stat] == ["ds_stamina", "ds_bite"]
    assert doc.entry_named("ds-hunter") is not None
    assert doc.entry[0].kinds == ["item"]


@pytest.mark.parametrize(
    ("change", "said"),
    [
        (('name = "ds_stamina"', 'name = "stamina"'), "ds_stamina"),
        (('type = "dice"', 'type = "dice"\nunit = "d"'), "has no unit"),
        (("min = 0", 'min = 0\nrole = "hp"'), "no system"),
        (("max = 20", "max = -1"), "min is above max"),
        (('slug = "ds"\nname', 'slug = "Ds"\nname'), "slug"),
        (("format = 1", "format = 2"), "format"),
        (('[[entry]]\nslug = "ds-hunter"', '[[entry]]\nslug = "ds-root"'), "more than one entry"),
        (("[[group]]", "[[group]]\nunknown = 1"), "unknown"),
    ],
)
def test_what_a_document_cannot_say_is_refused_before_any_request(
    change: tuple[str, str], said: str
) -> None:
    with pytest.raises(DocumentError) as raised:
        parse(SMALL.replace(*change, 1))
    assert said.lower() in str(raised.value).lower()


def test_not_toml_says_so() -> None:
    with pytest.raises(DocumentError, match="not TOML"):
        parse("format = ", source="ds.toml")


def test_an_enum_needs_values_and_only_an_enum_has_them() -> None:
    enum = 'format = 1\nname = "x"\n[[stat]]\nname = "size"\ngroup = "g"\ntype = "enum"\n'
    with pytest.raises(DocumentError, match="needs its `values`"):
        parse(enum)
    assert parse(enum + 'values = ["small", "large"]\n').stat[0].values == ["small", "large"]


def test_the_schema_describes_every_table() -> None:
    schema = json_schema()
    assert schema["title"] == "Lorenzo library document"
    assert {"system", "group", "stat", "entry", "attach"} <= set(schema["properties"])
