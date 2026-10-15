"""The shared LorenzoScript syntax tree drawn for a terminal (ADR 0295).

Only the packaged parser is JavaScript. Authored text is a function argument, never executable
source. V8 has no token, network bindings or filesystem access; evaluation is bounded.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from importlib import resources
from typing import Any

from py_mini_racer import JSEvalException, JSOOMException, JSTimeoutException, MiniRacer
from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Column, Table
from rich.text import Text

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def safe(value: object) -> str:
    return _CONTROL.sub("", str(value))


class ScriptError(Exception):
    """A text cannot be rendered within the terminal renderer''s resource limits."""


class Parser:
    def __init__(self) -> None:
        self.context = MiniRacer()
        self.context.set_hard_memory_limit(64 * 1024 * 1024)
        source = resources.files("lorenzo_cli").joinpath("lorenzoscript.js").read_text("utf-8")
        self.context.eval(source, timeout_sec=5)
        self.context.eval(
            "function terminalParse(text) { const doc = LorenzoScript.parse(text); "
            "return JSON.stringify({doc, refs: LorenzoScript.references(doc)}); }"
        )

    def parse(self, text: str) -> dict[str, Any]:
        if len(text) > 1_000_000:
            raise ScriptError("Text is too long to render in the terminal.")
        try:
            result = json.loads(self.context.call("terminalParse", safe(text), timeout_sec=5))
        except (JSEvalException, JSOOMException, JSTimeoutException) as error:
            raise ScriptError("Could not render this text within the terminal limits.") from error
        return dict(result)

    def slugify(self, name: str) -> str:
        return str(self.context.call("LorenzoScript.slugify", name, timeout_sec=5))

    def close(self) -> None:
        self.context.close()


class Renderer:
    def __init__(
        self,
        doc: dict[str, Any],
        *,
        stats: Mapping[str, str] | None = None,
        entities: Mapping[str, str] | None = None,
    ) -> None:
        self.doc = doc
        self.stats = stats or {}
        self.entities = entities or {}
        self.footnotes: dict[str, int] = {}
        self.abbreviations: set[str] = set()

    def inline(self, nodes: list[dict[str, Any]], depth: int = 0) -> Text:
        result = Text()
        if depth > 32:
            return result
        for node in nodes:
            kind = node["type"]
            children = node.get("children", [])
            if kind == "text":
                for abbreviation in self.doc["abbreviations"]:
                    if re.search(r"\b" + re.escape(abbreviation["term"]) + r"\b", node["text"]):
                        self.abbreviations.add(abbreviation["term"])
            if kind in ("text", "codespan"):
                result.append(safe(node["text"]), style="cyan" if kind == "codespan" else None)
            elif kind in ("sub", "sup"):
                script_text = self.inline(children, depth + 1).plain
                result.append(
                    ("~" if kind == "sub" else "^") + script_text + ("~" if kind == "sub" else "^")
                )
            elif kind in ("em", "i", "strong", "b", "del", "span"):
                text = self.inline(children, depth + 1)
                style = {
                    "em": "italic",
                    "i": "italic",
                    "strong": "bold",
                    "b": "bold",
                    "del": "strike",
                }.get(kind)
                if style:
                    text.stylize(style)
                result.append_text(text)
            elif kind in ("link", "image"):
                text = self.inline(children, depth + 1)
                ref = node.get("ref")
                key = f"{ref['hint']}/{ref['slug']}" if ref else ""
                target = self.entities.get(key) if ref else node["url"]
                if kind == "image":
                    result.append_text(Text("Picture: ", style="dim") + text)
                else:
                    if target and (
                        ref or target.lower().startswith(("https:", "http:", "mailto:", "#"))
                    ):
                        text.stylize("underline")
                        result.append_text(text)
                        result.append(f" ({safe(target)})", style="dim")
                    else:
                        result.append_text(text)
            elif kind == "stat":
                result.append(
                    safe(self.stats.get(node["name"], "{" + node["name"] + "}")), style="bold"
                )
            elif kind == "date":
                day = date.fromisoformat(node["date"])
                result.append(f"{day.day} {day.strftime('%B')} {day.year}")
            elif kind == "calendar":
                result.append(safe(node["expression"]))
            elif kind == "math":
                result.append(safe(node["tex"]), style="cyan")
            elif kind == "break":
                result.append("\n")
            elif kind == "footnote":
                label = node["label"]
                if any(f["label"] == label for f in self.doc["footnotes"]):
                    self.footnotes.setdefault(label, len(self.footnotes) + 1)
                    result.append(f"[{self.footnotes[label]}]", style="dim")
                else:
                    result.append(f"[^{safe(label)}]")
        return result

    def blocks(self, nodes: list[dict[str, Any]], depth: int = 0) -> list[RenderableType]:
        result: list[RenderableType] = []
        if depth > 32:
            return result
        for node in nodes:
            kind = node["type"]
            if kind in ("paragraph", "heading"):
                text = self.inline(node["children"])
                if kind == "heading":
                    text.stylize("bold")
                result.extend([text, Text("")])
            elif kind == "code":
                result.append(
                    Panel(
                        Text(safe(node["text"]), style="cyan"),
                        title=Text(safe(node["lang"])) if node["lang"] else None,
                    )
                )
            elif kind == "blockquote":
                result.append(
                    Panel(Group(*self.blocks(node["children"], depth + 1)), border_style="dim")
                )
            elif kind == "div":
                result.extend(self.blocks(node["children"], depth + 1))
            elif kind == "list":
                items: list[RenderableType] = []
                for index, item in enumerate(node["items"]):
                    prefix = f"{node['start'] + index}." if node["ordered"] else "•"
                    if item["checked"] is not None:
                        prefix = "[x]" if item["checked"] else "[ ]"
                    rendered = self.blocks(item["children"], depth + 1)
                    if rendered and isinstance(rendered[0], Text):
                        rendered[0] = Text(prefix + " ") + rendered[0]
                    else:
                        rendered.insert(0, Text(prefix))
                    if (
                        node["tight"]
                        and rendered
                        and isinstance(rendered[-1], Text)
                        and not rendered[-1].plain
                    ):
                        rendered.pop()
                    items.extend(rendered)
                result.append(Padding(Group(*items), (0, 0, 0, 2)))
            elif kind == "table":
                table = Table(
                    *[Column(header=self.inline(cell)) for cell in node["head"]], box=None
                )
                for index, align in enumerate(node["align"]):
                    if align:
                        table.columns[index].justify = align
                for row in node["rows"]:
                    table.add_row(*[self.inline(cell) for cell in row])
                result.append(table)
            elif kind == "rule":
                result.append(Rule())
            elif kind == "math":
                result.append(Text(safe(node["tex"]), style="cyan"))
            elif kind == "toc":
                result.extend(self.toc(self.doc["children"]))
        return result

    def toc(self, nodes: list[dict[str, Any]]) -> list[RenderableType]:
        headings: list[RenderableType] = []
        for node in nodes:
            if node["type"] == "heading":
                headings.append(Text("  " * (node["level"] - 1)) + self.inline(node["children"]))
            elif node["type"] in ("div", "blockquote"):
                headings.extend(self.toc(node["children"]))
        return headings

    def render(self) -> Group:
        blocks = self.blocks(self.doc["children"])
        # Rendering a footnote may cite another one, so consume newly found notes too.
        drawn: set[str] = set()
        while pending := [label for label in self.footnotes if label not in drawn]:
            for label in pending:
                drawn.add(label)
                note = next(f for f in self.doc["footnotes"] if f["label"] == label)
                blocks.append(Text(f"[{self.footnotes[label]}]", style="dim"))
                blocks.extend(self.blocks(note["children"]))
        for abbreviation in self.doc["abbreviations"]:
            if abbreviation["term"] in self.abbreviations:
                blocks.append(
                    Text(safe(f"{abbreviation['term']}: {abbreviation['title']}"), style="dim")
                )
        return Group(*blocks)


def print_script(
    console: Console,
    parsed: dict[str, Any],
    *,
    stats: Mapping[str, str] | None = None,
    entities: Mapping[str, str] | None = None,
) -> None:
    console.print(Renderer(parsed["doc"], stats=stats, entities=entities).render())
