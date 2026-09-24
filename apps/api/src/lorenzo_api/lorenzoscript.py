"""LorenzoScript's references, found on the server - see RFC 0027 §6 and ADR 0110.

A port of packages/lorenzoscript's `parse` and `references`: blocks, then
inlines with CommonMark's emphasis algorithm, into the same syntax tree.
Emphasis can't be skipped, because the nesting limit counts it and a link
nested past that limit isn't one. Rendering, heading ids, and TeX are left
out. packages/lorenzoscript/SPEC.md's examples are this module's tests too
(tests/test_lorenzoscript.py), so the two implementations can't drift.

Where Python and JavaScript differ, this follows JavaScript: its whitespace
set for `\\s` and `trim`, ASCII `\\d` and `\\w`, `.` stopping at every line
terminator, `$` only at the very end, and UTF-16 code units when a delimiter
run's neighbours are classified. The node shapes are the TypeScript ones,
as plain dicts; comments say which function each part mirrors.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterator
from typing import Any

Node = dict[str, Any]
Lines = list[str]

# Blocks and inline elements each nest at most this deep (inline.ts).
MAX_NESTING = 32

# --- JavaScript's character classes -------------------------------------------

# `\s` and String.prototype.trim: WhiteSpace plus LineTerminator.
_WS = "".join(
    map(chr, [9, 10, 11, 12, 13, 32, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029])
) + "".join(map(chr, [0x202F, 0x205F, 0x3000, 0xFEFF]))
_WS_CLASS = "".join(f"\\u{ord(c):04x}" for c in _WS)
_S = f"[{_WS_CLASS}]"
# `.` without the s flag: anything but a line terminator.
_DOT = r"[^\n\r\u2028\u2029]"
_ASCII_PUNCT = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def _trim(s: str) -> str:
    return s.strip(_WS)


def _blank(line: str) -> bool:
    return _trim(line) == ""


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(_WS))


def _space(s: str) -> bool:
    return any(c in _WS for c in s)


# --- Shared syntax (inline.ts) --------------------------------------------------

ATTR_LIST = r"[.#][A-Za-z][A-Za-z0-9_-]*(?:[ \t]+[.#][A-Za-z][A-Za-z0-9_-]*)*"
_ATTRS = re.compile(rf"\{{[ \t]*({ATTR_LIST})[ \t]*\}}")
_SPAN_OPEN = re.compile(rf"\{{\{{({ATTR_LIST})(?:[ \t]+|(?=\}}\}}))")
_AUTOLINK = re.compile(rf"<([A-Za-z][A-Za-z0-9+.-]{{1,31}}:[^{_WS_CLASS}<>]*)>")
_EMAIL = re.compile(
    r"<([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)>"
)
_FOOTNOTE_REF = re.compile(rf"\[\^([^\]{_WS_CLASS}][^\]]*)\]")
_WIKILINK = re.compile(r"\[\[([^\[\]|\n]+)(?:\|([^\[\]\n]+))?\]\]")
_ENTITY_TARGET = re.compile(r"(?:([a-z_]+)/)?([A-Za-z0-9][A-Za-z0-9_-]*)")
_HINTED = re.compile(rf"([a-z_]+)/({_DOT}+)")
_DIRECTIVE = re.compile(r"\{\{([A-Za-z]+)[ \t]+([^{}\n]*?)[ \t]*\}\}")
_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_UNESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")

# What a matched run of each delimiter character becomes, by how many characters it uses.
_DELIMS: dict[str, tuple[list[str], bool, bool]] = {
    # tags, strict (`_` never opens or closes inside a word), exact (same-length runs only)
    "*": (["em", "strong"], False, False),
    "_": (["i", "b"], True, False),
    "~": (["sub", "del"], False, True),
    "^": (["sup"], False, True),
}
_SPACELESS = frozenset({"sub", "sup"})


def attributes(tokens: str) -> Node:
    attrs: Node = {"id": "", "classes": []}
    for token in (t for t in re.split(r"[ \t]+", tokens) if t):
        if token.startswith("#"):
            attrs["id"] = token[1:]
        else:
            attrs["classes"].append(token[1:])
    return attrs


def normalize_label(label: str) -> str:
    return re.sub(f"{_S}+", " ", _trim(label)).lower()


def slugify(s: str) -> str:
    """Heading ids and `[[wikilink]]` slugs: ASCII, lowercase, hyphenated."""
    unmarked = "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.category(c).startswith("M")
    )
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", unmarked.lower()))


def plain_text(nodes: list[Node]) -> str:
    return "".join(_plain_of(n) for n in nodes)


def _plain_of(n: Node) -> str:
    if "children" in n:
        return plain_text(n["children"])
    return {
        "text": n.get("text"),
        "codespan": n.get("text"),
        "math": n.get("tex"),
        "date": n.get("date"),
        "calendar": n.get("expression"),
        "break": " ",
    }.get(n["type"]) or ""


def _is_date(iso: str) -> bool:
    """A day that exists, in JavaScript's proleptic calendar, where year 0000 is one."""
    m = _ISO_DATE.fullmatch(iso)
    if not m:
        return False
    year, month, day = (int(g) for g in m.groups())
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return 1 <= month <= 12 and 1 <= day <= days[month - 1]


def _text(s: str) -> Node:
    return {"type": "text", "text": s}


def _depth_of(nodes: list[Node]) -> int:
    return max((n.get("depth", 0) for n in nodes), default=0)


def _nest(node: Node) -> Node:
    node["depth"] = _depth_of(node["children"]) + 1
    return node


def _parent(fields: Node) -> Callable[[list[Node]], Node]:
    """What `_Inline.close` makes of the nodes it gathers: `fields`, plus them as children."""
    return lambda children: {**fields, "children": children}


# --- The inline pass (inline.ts parseInline) -----------------------------------


class _Inline:
    def __init__(self, src: str) -> None:
        self.src = src
        self.nodes: list[Node] = []
        self.brackets: list[Node] = []  # {at, image, active}
        self.spans: list[Node] = []  # {at, attrs}
        self.text = ""

    def flush(self) -> None:
        if self.text:
            self.nodes.append(_text(self.text))
        self.text = ""

    def push(self, node: Node) -> None:
        self.flush()
        self.nodes.append(node)

    def close(self, at: int, make: Callable[[list[Node]], Node], closing: str) -> bool:
        """Replaces the opener at `at` with `make(everything after it)`, unless too deep."""
        self.flush()
        children = _literal(_resolve_emphasis(self.nodes[at + 1 :]))
        del self.nodes[at + 1 :]
        # Openers of either kind left open inside can no longer close.
        while self.brackets and self.brackets[-1]["at"] > at:
            self.brackets.pop()
        while self.spans and self.spans[-1]["at"] > at:
            self.spans.pop()
        if _depth_of(children) >= MAX_NESTING:
            self.nodes.extend([*children, _text(closing)])
            return False
        self.nodes[at] = _nest(make(children))
        return True

    def deactivate_links(self) -> None:
        for b in self.brackets:
            if not b["image"]:
                b["active"] = False

    def parse(self) -> list[Node]:
        src = self.src
        i = 0
        while i < len(src):
            c = src[i]
            nxt = src[i + 1] if i + 1 < len(src) else ""
            if c == "\\" and (nxt == "\n" or nxt in _ASCII_PUNCT):
                if nxt == "\n":
                    self.push({"type": "break"})
                else:
                    self.text += nxt
                i += 2
            elif c == "\n":
                hard = re.search(r" {2,}\Z", self.text) is not None
                self.text = re.sub(r" +\Z", "", self.text)
                self.push({"type": "break"} if hard else _text("\n"))
                i += 1
            elif c == "`":
                run = len(src) - len(src[i:].lstrip("`")) - i
                end = _closing_run(src, i + run, run)
                if end < 0:
                    self.text += "`" * run
                    i += run
                else:
                    self.push({"type": "codespan", "text": _code_text(src[i + run : end])})
                    i = end + run
            elif c in _DELIMS:
                start = i
                while i < len(src) and src[i] == c:
                    i += 1
                before = src[start - 1] if start > 0 else "\n"
                after = src[i] if i < len(src) else "\n"
                self.push(_delim(c, i - start, before, after))
            elif c == "[" or (c == "!" and nxt == "["):
                token = (_footnote_ref(src, i) or _wikilink(src, i)) if c == "[" else None
                if token:
                    node, length = token
                    self.push(node)
                    # A wikilink is a link, so no earlier `[` can become one around it.
                    if node["type"] == "link":
                        self.deactivate_links()
                    i += length
                    continue
                image = c == "!"
                self.flush()
                self.brackets.append({"at": len(self.nodes), "image": image, "active": True})
                self.nodes.append(_text("![" if image else "["))
                i += 2 if image else 1
            elif c == "]":
                bracket = self.brackets.pop() if self.brackets else None
                dest = _destination(src, i + 1) if bracket and bracket["active"] else None
                if not bracket or not dest:
                    self.text += "]"
                    i += 1
                    continue
                url, end = dest
                link: Node = {"type": "image" if bracket["image"] else "link"}
                if ref := _entity_ref(url):
                    link["ref"] = ref
                linked = self.close(bracket["at"], _parent(link), src[i:end])
                # No links inside links: every earlier `[` can no longer become one.
                if linked and not bracket["image"]:
                    self.deactivate_links()
                i = end
            elif c == "{" and nxt == "{":
                m = _SPAN_OPEN.match(src, i)
                token = None if m else _directive(src, i)
                if m:
                    self.flush()
                    self.spans.append({"at": len(self.nodes), "attrs": attributes(m[1])})
                    self.nodes.append(_text(m[0]))
                    i += len(m[0])
                elif token:
                    self.push(token[0])
                    i += token[1]
                else:
                    self.text += "{{"
                    i += 2
            elif c == "}" and nxt == "}" and self.spans:
                opener = self.spans.pop()
                self.close(opener["at"], _parent({"type": "span", "attrs": opener["attrs"]}), "}}")
                i += 2
            else:
                token = (
                    _autolink(src, i)
                    if c == "<"
                    else _math(src, i)
                    if c == "$"
                    else _pending(src, i)
                    if c == "{"
                    else None
                )
                if token:
                    self.push(token[0])
                    i += token[1]
                else:
                    self.text += c
                    i += 1
        self.flush()
        return _literal(_resolve_emphasis(self.nodes))


def parse_inline(src: str) -> list[Node]:
    return _Inline(src).parse()


Token = tuple[Node, int] | None


def _footnote_ref(src: str, i: int) -> Token:
    m = _FOOTNOTE_REF.match(src, i)
    return ({"type": "footnote", "label": m[1]}, len(m[0])) if m else None


def _wikilink(src: str, i: int) -> Token:
    """`[[Name]]` links to the name's slug. No slug, no link."""
    m = _WIKILINK.match(src, i)
    target = _trim(m[1]) if m else ""
    hinted = _HINTED.fullmatch(target)
    name = hinted[2] if hinted else target
    slug = slugify(name)
    if not m or not slug:
        return None
    ref = {"hint": hinted[1] if hinted else "", "slug": slug}
    children = [_text(_trim(m[2] if m[2] is not None else name))]
    return _nest({"type": "link", "ref": ref, "children": children}), len(m[0])


def _entity_ref(url: str) -> Node | None:
    m = _ENTITY_TARGET.fullmatch(url)
    return {"hint": m[1] or "", "slug": m[2]} if m else None


def _directive(src: str, i: int) -> Token:
    """`{{date YYYY-MM-DD}}` or `{{cal …}}`; any other name, or no arguments, stays text."""
    m = _DIRECTIVE.match(src, i)
    if not m:
        return None
    name, args = m[1].lower(), m[2]
    if name == "date" and _is_date(args):
        return {"type": "date", "date": args}, len(m[0])
    if name == "cal" and args:
        return {"type": "calendar", "expression": args}, len(m[0])
    return None


def _autolink(src: str, i: int) -> Token:
    m = _AUTOLINK.match(src, i) or _EMAIL.match(src, i)
    return ({"type": "link", "children": [_text(m[1])]}, len(m[0])) if m else None


def _math(src: str, i: int) -> Token:
    """`$…$` or `$$…$$`. Inline math can't start or end with a space or precede a digit."""
    display = src[i + 1 : i + 2] == "$"
    fence = "$$" if display else "$"
    start = i + len(fence)
    k = start
    while k < len(src) and not src.startswith(fence, k):
        k += 2 if src[k] == "\\" else 1
    tex = src[start:k]
    if k >= len(src) or not _trim(tex):
        return None
    digit_after = src[k + 1 : k + 2] in tuple("0123456789")
    if not display and (tex[0] in _WS or tex[-1] in _WS or digit_after):
        return None
    return {"type": "math", "tex": _trim(tex)}, k + len(fence) - i


def _pending(src: str, i: int) -> Token:
    m = _ATTRS.match(src, i)
    return ({"type": "attrs", "attrs": attributes(m[1]), "raw": m[0]}, len(m[0])) if m else None


def _closing_run(src: str, start: int, length: int) -> int:
    """Index of the next backtick run of exactly `length`, or -1."""
    for m in re.finditer(r"`+", src[start:]):
        if len(m[0]) == length:
            return start + m.start()
    return -1


def _code_text(raw: str) -> str:
    s = raw.replace("\n", " ")
    return s[1:-1] if re.fullmatch(rf" {_DOT}*[^ ]{_DOT}* ", s) else s


def _flanking(ch: str) -> tuple[bool, bool]:
    """Whether `ch` is whitespace, and whether punctuation or a symbol, as JavaScript
    sees it next to a delimiter run: outside the BMP, as half a surrogate pair, neither."""
    if ord(ch) > 0xFFFF:
        return False, False
    return ch in _WS, unicodedata.category(ch)[0] in "PS"


def _delim(ch: str, n: int, before: str, after: str) -> Node:
    ws_before, pn_before = _flanking(before)
    ws_after, pn_after = _flanking(after)
    left = not ws_after and (not pn_after or ws_before or pn_before)
    right = not ws_before and (not pn_before or ws_after or pn_after)
    strict = _DELIMS[ch][1]
    opens = left and (not right or pn_before) if strict else left
    closes = right and (not left or pn_after) if strict else right
    return {"type": "delim", "ch": ch, "n": n, "orig": n, "open": opens, "close": closes}


def _destination(src: str, j: int) -> tuple[str, int] | None:
    """`(url "title")` at `src[j]`: the unescaped url and the index after `)`."""
    if src[j : j + 1] != "(":
        return None
    k = _skip_space(src, j + 1)
    if src[k : k + 1] == "<":
        end = src.find(">", k)
        if end < 0 or re.search(r"[\n<]", src[k + 1 : end]):
            return None
        url = src[k + 1 : end]
        k = end + 1
    else:
        start = k
        depth = 0
        while k < len(src):
            ch = src[k]
            if ch == "\\" and src[k + 1 : k + 2] in _ASCII_PUNCT:
                k += 1
            elif ch in _WS or (ch == ")" and depth == 0):
                break
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            k += 1
        url = src[start:k]
    after_url = k
    k = _skip_space(src, k)
    quote = src[k : k + 1]
    if k > after_url and quote in ('"', "'", "("):
        close = ")" if quote == "(" else quote
        end = k + 1
        while end < len(src) and src[end] != close:
            end += 2 if src[end] == "\\" else 1
        if end >= len(src):
            return None
        k = _skip_space(src, end + 1)
    if src[k : k + 1] != ")":
        return None
    return _UNESCAPE.sub(r"\1", url), k + 1


def _skip_space(src: str, k: int) -> int:
    while k < len(src) and src[k] in _WS:
        k += 1
    return k


def _odd_match(opener: Node, closer: Node) -> bool:
    """CommonMark's "rule of 3"."""
    return bool(
        (opener["close"] or closer["open"])
        and (opener["orig"] + closer["orig"]) % 3 == 0
        and not (opener["orig"] % 3 == 0 and closer["orig"] % 3 == 0)
    )


def _has_space(n: Node) -> bool:
    return n["type"] == "break" or (n["type"] not in ("delim", "attrs") and _space(plain_text([n])))


def _opens(node: Node | None, closer: Node) -> bool:
    if node is None or node["type"] != "delim" or node["ch"] != closer["ch"] or not node["open"]:
        return False
    tags, _, exact = _DELIMS[closer["ch"]]
    if exact:
        return bool(node["n"] == closer["n"] and closer["n"] <= len(tags))
    return not _odd_match(node, closer)


def _resolve_emphasis(nodes: list[Node]) -> list[Node]:
    """Pairs delimiter runs into spans, in linear time (inline.ts resolveEmphasis)."""
    out: list[Node] = []
    bottom: dict[tuple[str, bool, int], int] = {}
    for closer in nodes:
        if closer["type"] != "delim" or not closer["close"]:
            out.append(closer)
            continue
        key = (closer["ch"], closer["open"], closer["orig"] % 3)
        tags = _DELIMS[closer["ch"]][0]
        while closer["n"] > 0:
            floor = min(bottom.get(key, 0), len(out))
            o = len(out) - 1
            while o >= floor and not _opens(out[o], closer):
                o -= 1
            opener = out[o] if o >= 0 else None
            is_delim = opener is not None and opener["type"] == "delim"
            use = min(opener["n"], closer["n"], len(tags)) if opener and is_delim else 0
            tag = tags[use - 1] if use > 0 else None
            # As in Pandoc, sub- and superscripts hold no spaces.
            spaced = tag in _SPACELESS and any(_has_space(n) for n in out[o + 1 :])
            if o < floor or opener is None or not is_delim or spaced:
                bottom[key] = len(out)
                break
            opener["n"] -= use
            closer["n"] -= use
            children = _literal(out[o + 1 :])
            del out[o + 1 :]
            if not opener["n"]:
                out.pop()
            if _depth_of(children) < MAX_NESTING:
                out.append(_nest({"type": tag, "children": children}))
            else:
                marks = _text(closer["ch"] * use)
                out.extend([marks, *children, dict(marks)])
        if closer["n"] > 0:
            out.append(closer)
    return out


def _literal(nodes: list[Node]) -> list[Node]:
    """Unmatched delimiters become text, a pending `{…}` attaches to the element before
    it (or becomes its text), and neighbouring text merges."""
    out: list[Node] = []
    for n in nodes:
        last = out[-1] if out else None
        if (
            n["type"] == "attrs"
            and last is not None
            and last["type"] not in ("text", "break", "footnote")
            and "attrs" not in last
        ):
            last["attrs"] = n["attrs"]
            continue
        node = (
            _text(n["ch"] * n["n"])
            if n["type"] == "delim"
            else _text(n["raw"])
            if n["type"] == "attrs"
            else n
        )
        if node["type"] == "text" and last is not None and last["type"] == "text":
            last["text"] += node["text"]
        else:
            out.append(dict(node) if node["type"] == "text" else node)
    return out


# --- The block pass (block.ts) ------------------------------------------------------

_FENCE = re.compile(rf"( {{0,3}})(`{{3,}}(?=[^`]*\Z)|~{{3,}})({_DOT}*)\Z")
_HEADING = re.compile(rf" {{0,3}}(#{{1,6}})(?=[ \t]|\Z)({_DOT}*)\Z")
_RULE = re.compile(r" {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*\Z")
_QUOTE = re.compile(r" {0,3}> ?")
_LIST = re.compile(r"( {0,3})(?:([-+*])|([0-9]{1,9})([.)]))([ \t]+|\Z)")
_TASK = re.compile(r"\[([ xX])\](?:[ \t]+|\Z)")
_MATH = re.compile(rf" {{0,3}}\$\$(?:[ \t]*|((?:(?!\$\$){_DOT})+)\$\$[ \t]*)\Z")
_MATH_CLOSE = re.compile(r" {0,3}\$\$[ \t]*\Z")
_TOC = re.compile(r" {0,3}\{\{toc\}\}[ \t]*\Z", re.IGNORECASE | re.ASCII)
_DIV_OPEN = re.compile(rf" {{0,3}}\{{\{{({ATTR_LIST})[ \t]*\Z")
_DIV_CLOSE = re.compile(r" {0,3}\}\}[ \t]*\Z")
_FOOTNOTE = re.compile(rf" {{0,3}}\[\^([^\]]+)\]:[ \t]*({_DOT}*)\Z")
_ABBREVIATION = re.compile(rf" {{0,3}}\*\[([^\]]+)\]:[ \t]*({_DOT}*)\Z")
_TABLE_DELIM = re.compile(r" {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*\Z")
_TRAILING_ATTRS = re.compile(rf"(?:^|[ \t]+)\{{[ \t]*({ATTR_LIST})[ \t]*\}}\Z")
_EXPAND = re.compile(r"[ \t]*")

Match = re.Match[str]
Rule = tuple[
    Callable[[Lines, int], Match | None],
    Callable[[Match], bool],
    str,  # the Parser method that parses the block
]


def _on(pattern: re.Pattern[str]) -> Callable[[Lines, int], Match | None]:
    return lambda lines, i: pattern.match(lines[i])


def _always(_: Match) -> bool:
    return True


def _list_interrupts(m: Match) -> bool:
    """Only a non-empty item, and only an ordered one starting at 1, may end a paragraph."""
    return not _blank(m.string[m.end() :]) and (m[3] is None or int(m[3]) == 1)


def _cells(line: str) -> list[str]:
    """A table row's cells: outer pipes dropped, split on unescaped `|`."""
    row = _trim(line)
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return [_trim(cell).replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", row)]


def _table_start(lines: Lines, i: int) -> Match | None:
    """A header row directly above a delimiter row with as many cells starts a table."""
    delimiters = lines[i + 1] if i + 1 < len(lines) else None
    if delimiters is None or "|" not in delimiters or not _TABLE_DELIM.match(delimiters):
        return None
    header = lines[i]
    return re.match("", header) if len(_cells(header)) == len(_cells(delimiters)) else None


_RULES: list[Rule] = [
    (_on(re.compile(r" {4}")), lambda _: False, "indented_code"),
    (_on(_FENCE), _always, "fenced_code"),
    (_on(_MATH), _always, "math_block"),
    (_on(_HEADING), _always, "heading"),
    (_on(_RULE), _always, "rule"),
    (_on(_QUOTE), _always, "blockquote"),
    (_on(_TOC), _always, "toc"),
    (_on(_DIV_OPEN), _always, "div"),
    (_on(_FOOTNOTE), _always, "footnote"),
    (_on(_ABBREVIATION), _always, "abbreviation"),
    (_on(_LIST), _list_interrupts, "list_block"),
    (_table_start, _always, "table"),
]


def _match(lines: Lines, i: int) -> tuple[Rule, Match] | None:
    for rule in _RULES:
        m = rule[0](lines, i)
        if m:
            return rule, m
    return None


def _interrupts(lines: Lines, i: int) -> bool:
    found = _match(lines, i)
    return found[0][1](found[1]) if found else False


def _marker(text: str) -> Match | None:
    return _QUOTE.match(text) or (None if _RULE.match(text) else _LIST.match(text))


def _innermost(line: str) -> str:
    """A line without any of its nested quote and list markers."""
    text = line
    for _ in range(MAX_NESTING):
        m = _marker(text)
        if not m:
            break
        text = text[m.end() :]
    return text


class _Content:
    """A container's content lines, tracking lazy continuation line by line (block.ts)."""

    def __init__(self) -> None:
        self.lines: Lines = []
        self.fenced = False
        self.open = False

    def add(self, line: str, lazy: bool = False) -> None:
        self.lines.append(line)
        if lazy:
            return
        text = _innermost(line)
        if _FENCE.match(text):
            self.fenced = not self.fenced
        self.open = not self.fenced and not _blank(text) and not _match([text], 0)

    def continues(self, line: str) -> bool:
        return self.open and not _blank(line) and not _interrupts([line], 0)


def _expand_tabs(line: str) -> str:
    """Leading tabs become spaces, to the next 4-column stop."""
    lead = _EXPAND.match(line)
    lead_text = lead[0] if lead else ""
    if "\t" not in lead_text:
        return line
    spaces = ""
    for c in lead_text:
        spaces += " " * (4 - len(spaces) % 4) if c == "\t" else " "
    return spaces + line[len(lead_text) :]


def _trailing_attrs(text: str) -> str:
    """`text` without a trailing `{#id .class}`."""
    m = _TRAILING_ATTRS.search(text)
    return text[: m.start()] if m else text


class _Parser:
    def __init__(self) -> None:
        self.footnotes: dict[str, list[Node]] = {}
        self.depth = 0

    def blocks(self, lines: Lines) -> list[Node]:
        blocks: list[Node] = []
        i = 0
        while i < len(lines):
            if _blank(lines[i]):
                i += 1
                continue
            found = _match(lines, i)
            if found:
                block, i = getattr(self, found[0][2])(lines, i, found[1])
            else:
                block, i = self.paragraph(lines, i)
            if block:
                blocks.append(block)
        return blocks

    def nested(self, lines: Lines) -> list[Node]:
        """A container's content, one level deeper. The last level holds only text."""
        if self.depth >= MAX_NESTING - 1:
            text = _trim("\n".join(lines))
            return [{"type": "paragraph", "children": parse_inline(text)}] if text else []
        self.depth += 1
        try:
            return self.blocks(lines)
        finally:
            self.depth -= 1

    def paragraph(self, lines: Lines, i: int) -> tuple[Node, int]:
        j = i + 1
        while j < len(lines) and not _blank(lines[j]) and not _interrupts(lines, j):
            j += 1
        text = "\n".join(line.lstrip(_WS) for line in lines[i:j]).rstrip(_WS)
        return {"type": "paragraph", "children": parse_inline(text)}, j

    def heading(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        text = _trim(re.sub(r"(^|[ \t])#+\Z", "", _trim(m[2]), count=1))
        return {"type": "heading", "children": parse_inline(_trailing_attrs(text))}, i + 1

    def rule(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        return {"type": "rule"}, i + 1

    def toc(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        return {"type": "toc"}, i + 1

    def indented_code(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        j = i
        while j < len(lines) and (_blank(lines[j]) or _indent(lines[j]) >= 4):
            j += 1
        while j > i and _blank(lines[j - 1]):
            j -= 1
        return {"type": "code"}, j

    def fenced_code(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        fence = m[2]
        close = re.compile(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*\Z")
        j = i + 1
        while j < len(lines) and not close.match(lines[j]):
            j += 1
        return {"type": "code"}, j + 1

    def math_block(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        if m[1] is not None:
            return {"type": "math"}, i + 1
        j = i + 1
        while j < len(lines) and not _MATH_CLOSE.match(lines[j]):
            j += 1
        return {"type": "math"}, j + 1

    def blockquote(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        inner = _Content()
        j = i
        while j < len(lines):
            line = lines[j]
            q = _QUOTE.match(line)
            if q:
                inner.add(line[q.end() :])
            elif inner.continues(line):
                inner.add(line, lazy=True)
            else:
                break
            j += 1
        return {"type": "blockquote", "children": self.nested(inner.lines)}, j

    def div(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        """`{{.class` … `}}`; nested class blocks are counted, so their `}}` isn't this one's."""
        inner: Lines = []
        depth = 1
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if _DIV_OPEN.match(line):
                depth += 1
            elif _DIV_CLOSE.match(line):
                depth -= 1
                if depth == 0:
                    break
            inner.append(line)
            j += 1
        return {"type": "div", "children": self.nested(inner)}, j + 1

    def footnote(self, lines: Lines, i: int, m: Match) -> tuple[None, int]:
        inner, j = self.collect(lines, i, m[2], 4)
        label = normalize_label(m[1])
        if label not in self.footnotes:
            self.footnotes[label] = self.nested(inner)
        return None, j

    def abbreviation(self, lines: Lines, i: int, m: Match) -> tuple[None, int]:
        return None, i + 1

    def table(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        head = _cells(lines[i])
        rows: list[list[list[Node]]] = []
        j = i + 2
        while j < len(lines) and not _blank(lines[j]) and not _interrupts(lines, j):
            row = _cells(lines[j])
            rows.append([parse_inline(row[k] if k < len(row) else "") for k in range(len(head))])
            j += 1
        return {"type": "table", "head": [parse_inline(c) for c in head], "rows": rows}, j

    def list_block(self, lines: Lines, i: int, first: Match) -> tuple[Node, int]:
        items: list[Node] = []
        of = first[2] or first[4]
        m: Match | None = first
        while m:
            item, i = self.list_item(lines, i, m)
            items.append(item)
            j = i
            while j < len(lines) and _blank(lines[j]):
                j += 1
            m = _sibling(lines[j], of) if j < len(lines) else None
            if m:
                i = j
        return {"type": "list", "items": items}, i

    def list_item(self, lines: Lines, i: int, m: Match) -> tuple[Node, int]:
        line = lines[i]
        spaces = len(m[5] or "")
        marker_end = len(m[0]) - spaces
        empty = _blank(line[marker_end:])
        # More than 4 spaces after the marker means indented code, so only 1 counts.
        width = marker_end + (1 if empty or spaces > 4 else spaces)
        head = line[width:]
        task = _TASK.match(head)
        if task:
            head = head[task.end() :]
        inner, j = self.collect(lines, i, head, min(width, 4))
        return {"type": "item", "children": self.nested(inner)}, j

    def collect(self, lines: Lines, i: int, head: str, cont: int) -> tuple[Lines, int]:
        """A list item's or footnote's content lines (block.ts collect)."""
        inner = _Content()
        inner.add(head)
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if _blank(line):
                inner.add("")
            elif _indent(line) >= cont:
                inner.add(line[cont:])
            elif not _LIST.match(line) and inner.continues(line):
                inner.add(line, lazy=True)
            else:
                break
            j += 1
        while len(inner.lines) > 1 and _blank(inner.lines[-1]):
            inner.lines.pop()
            j -= 1
        return inner.lines, j


def _sibling(line: str, of: str) -> Match | None:
    m = _LIST.match(line)
    return m if m and (m[2] or m[4]) == of and not _RULE.match(line) else None


def parse(source: str) -> Node:
    """The syntax tree: `children` blocks, and `footnotes`, one per label, first wins."""
    text = re.sub(r"\r\n?", "\n", source).replace("\0", "\ufffd")
    # A final newline ends the last line; it doesn't start another one.
    if text.endswith("\n"):
        text = text[:-1]
    parser = _Parser()
    children = parser.blocks([_expand_tabs(line) for line in text.split("\n")])
    return {"children": children, "footnotes": list(parser.footnotes.values())}


def _all_blocks(doc: Node) -> Iterator[Node]:
    """Every block in document order, at any depth, then the footnotes' (block.ts allBlocks)."""

    def walk(blocks: list[Node]) -> Iterator[Node]:
        for b in blocks:
            yield b
            if b["type"] in ("blockquote", "div"):
                yield from walk(b["children"])
            elif b["type"] == "list":
                for item in b["items"]:
                    yield from walk(item["children"])

    yield from walk(doc["children"])
    for footnote in doc["footnotes"]:
        yield from walk(footnote)


def references(source: str) -> list[dict[str, str]]:
    """Every entity link, entity image, date, and calendar expression in `source`,
    footnotes included, once each, in order of first use - references.ts's output."""
    found: dict[tuple[str, ...], dict[str, str]] = {}

    def add(ref: dict[str, str]) -> None:
        found.setdefault(tuple(ref.values()), ref)

    def visit(nodes: list[Node]) -> None:
        for n in nodes:
            if n["type"] in ("link", "image") and "ref" in n:
                kind = "entity" if n["type"] == "link" else "image"
                add({"kind": kind, "hint": n["ref"]["hint"], "slug": n["ref"]["slug"]})
            elif n["type"] == "date":
                add({"kind": "date", "date": n["date"]})
            elif n["type"] == "calendar":
                add({"kind": "calendar", "expression": n["expression"]})
            if "children" in n:
                visit(n["children"])

    for block in _all_blocks(parse(source)):
        if block["type"] in ("paragraph", "heading"):
            visit(block["children"])
        elif block["type"] == "table":
            for cell in [*block["head"], *(c for row in block["rows"] for c in row)]:
                visit(cell)
    return list(found.values())
