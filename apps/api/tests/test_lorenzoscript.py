"""The server's LorenzoScript extractor against packages/lorenzoscript/SPEC.md
(ADR 0110): every example's references, the same ones the TypeScript
package must return, so the two implementations can't disagree."""

import json
from pathlib import Path

import pytest

from lorenzo_api.lorenzoscript import references

SPEC = Path(__file__).resolve().parents[3] / "packages" / "lorenzoscript" / "SPEC.md"
FENCE = "`" * 8


def _examples() -> list[tuple[str, list[dict[str, str]]]]:
    """(source, references) for every example; no references section means none."""
    found = []
    parts: list[list[str]] | None = None
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        if parts is not None and line == FENCE:
            source = "".join(f"{row}\n" for row in parts[0]).replace("␠", " ").replace("⇥", "\t")
            found.append((source, json.loads("\n".join(parts[2])) if len(parts) > 2 else []))
            parts = None
        elif parts is not None:
            if line == ".":
                parts.append([])
            else:
                parts[-1].append(line)
        elif line == f"{FENCE} example":
            parts = [[]]
    return found


EXAMPLES = _examples()


def test_the_spec_has_examples() -> None:
    assert len(EXAMPLES) > 80
    assert sum(1 for _, refs in EXAMPLES if refs) >= 9


@pytest.mark.parametrize(
    ("source", "expected"), EXAMPLES, ids=[s.split("\n")[0][:40] for s, _ in EXAMPLES]
)
def test_spec_example(source: str, expected: list[dict[str, str]]) -> None:
    assert references(source) == expected


def test_a_link_whose_text_nests_past_the_limit_is_no_reference() -> None:
    assert references(f"[{'*' * 5000}a{'*' * 5000}](ashfang)") == []
    assert references("[**a**](ashfang)") == [{"kind": "entity", "hint": "", "slug": "ashfang"}]


def test_containers_nested_past_the_limit_still_yield_their_text() -> None:
    # The 32nd level holds only text, so the link inside is still read.
    assert references(f"{'>' * 5000} [[Ashfang]]") == [
        {"kind": "entity", "hint": "", "slug": "ashfang"}
    ]


def test_hostile_input_stays_fast() -> None:
    references(f"> > > > > a\n{'b\n' * 2000}")
    references(f"{'{{.a ' * 5000}x{'}}' * 5000}")
    references("\n".join(f"[^{k}]: see[^{k + 1}] [[e{k}]]" for k in range(2000)))


def test_javascript_semantics_where_python_differs() -> None:
    # Space before a link's target is skipped. U+001C is whitespace to Python
    # but not to JavaScript, so it stays part of the target; U+FEFF the other way round.
    assert references("[x](\x1cold-sword)") == []
    assert references("[x](\N{ZERO WIDTH NO-BREAK SPACE}old-sword)") == [
        {"kind": "entity", "hint": "", "slug": "old-sword"}
    ]
    # JavaScript's Date takes year 0000; Python's datetime doesn't.
    assert references("{{date 0000-02-29}} {{date 2023-02-29}}") == [
        {"kind": "date", "date": "0000-02-29"}
    ]
    # Unicode digits aren't list markers or date digits.
    assert references("{{date ٢٠٢٦-٠٩-٢٤}}") == []


def test_line_endings_and_nul() -> None:
    assert references("a\r\n[[Ashfang]]\rb\0") == [
        {"kind": "entity", "hint": "", "slug": "ashfang"}
    ]
