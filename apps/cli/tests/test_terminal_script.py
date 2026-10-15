from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import pytest
from rich.console import Console

from lorenzo_cli.terminal_script import Parser, Renderer


@pytest.fixture
def parser():
    value = Parser()
    try:
        yield value
    finally:
        value.close()


def draw(parser: Parser, source: str, **options) -> str:
    stream = io.StringIO()
    Console(file=stream, width=100, color_system=None).print(
        Renderer(parser.parse(source)["doc"], **options).render()
    )
    return stream.getvalue()


def test_bundle_matches_shared_parser_sources() -> None:
    root = Path(__file__).resolve().parents[3]
    source = root / "packages/lorenzoscript/src"
    digest = hashlib.sha256()
    for path in sorted(source.glob("*.ts")):
        digest.update((path.name + "\n" + path.read_text()).encode())
    bundle = root / "apps/cli/src/lorenzo_cli/lorenzoscript.js"
    assert f"source-sha256: {digest.hexdigest()}" in bundle.read_text().splitlines()[0], (
        "Run mise run //apps/cli:bundle-lorenzoscript"
    )


def test_nested_blocks_tables_tasks_footnotes_and_extensions(parser: Parser) -> None:
    text = draw(
        parser,
        "# Kit\n\n> **Carry** *carefully*.\n\n- [x] Rope\n- [ ] Torch\n\n"
        "| Item | Weight |\n| --- | ---: |\n| Rope | {weight} |\n\n"
        "~~gone~~ H~2~O x^2^\n\nA note[^1].\n\n[^1]: Remember [[Ashfang]].\n\n"
        "{{date 2026-10-15}} {{cal harptos 1492-mirtul-12}}",
        stats={"weight": "1.5 kg"},
    )
    for expected in (
        "Kit",
        "Carry carefully",
        "[x] Rope",
        "[ ] Torch",
        "Weight",
        "1.5 kg",
        "gone",
        "Remember Ashfang",
        "15 October 2026",
        "harptos 1492-mirtul-12",
    ):
        assert expected in text


def test_code_math_and_escaped_references_stay_literal(parser: Parser) -> None:
    source = (
        "`[[Ashfang]] {weight}`\n\n```js\n[[Ashfang]] {weight}\n```\n\n"
        "$\\frac{a}{b}$\n\n\\[[Ashfang]]"
    )
    parsed = parser.parse(source)
    assert parsed["refs"] == []
    text = draw(parser, source, stats={"weight": "7 kg"})
    assert "[[Ashfang]] {weight}" in text
    assert "7 kg" not in text
    assert r"\frac{a}{b}" in text


def test_links_images_missing_stats_and_unsafe_schemes(parser: Parser) -> None:
    text = draw(
        parser,
        "[[Ashfang|Friend]] [[Unknown]] [web](https://example.com) [bad](javascript:alert) "
        "![Map](https://example.com/map.png) {unknown}",
        entities={"/ashfang": "ashfang · 123"},
    )
    assert "Friend (ashfang · 123)" in text
    assert "Unknown" in text
    assert "web (https://example.com)" in text
    assert "javascript:" not in text
    assert "Picture: Map" in text
    assert "{unknown}" in text


def test_control_sequences_and_rich_markup_are_plain_text(parser: Parser) -> None:
    text = draw(parser, "\x1b]52;c;secret\x07 [bold red]plain[/bold red]")
    assert "\x1b" not in text and "\x07" not in text
    assert "[bold red]plain[/bold red]" in text


def test_toc_raw_html_and_unclosed_fence(parser: Parser) -> None:
    text = draw(parser, "{{TOC}}\n\n# Intro\n\n<script>alert(1)</script>\n\n```\nunclosed")
    assert text.count("Intro") == 2
    assert "<script>alert(1)</script>" in text
    assert "unclosed" in text


def test_every_spec_example_is_parsed_by_shared_engine(parser: Parser) -> None:
    spec = Path(__file__).resolve().parents[3] / "packages/lorenzoscript/SPEC.md"
    examples = re.findall(r"^`{8} example\n(.*?)\n`{8}$", spec.read_text(), re.M | re.S)
    assert len(examples) >= 95
    for example in examples:
        source = example.split("\n.\n")[0].replace("␠", " ").replace("⇥", "\t")
        # Exercise every block and inline from the canonical syntax fixtures, including hostile
        # links and malformed markup. The parser is the same implementation as the web's.
        draw(parser, source)


def test_stat_names_use_shared_slug_rules_and_text_limits(parser: Parser) -> None:
    from lorenzo_cli.terminal_script import ScriptError

    assert parser.slugify("Hit Points") == "hit-points"
    assert parser.slugify("Café_Weight") == "cafe-weight"
    with pytest.raises(ScriptError, match="too long"):
        parser.parse("a" * 1_000_001)


def test_nesting_abbreviations_and_sub_sup_remain_meaningful(parser: Parser) -> None:
    text = draw(
        parser, "- Outer\n  - Inner\n\nHTML H~2~O x^2^\n\n*[HTML]: Hyper Text Markup Language"
    )
    assert "    • Inner" in text
    assert "HTML: Hyper Text Markup Language" in text
    assert "H~2~O" in text and "x^2^" in text
