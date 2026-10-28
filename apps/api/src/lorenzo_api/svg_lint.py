"""The one lint an SVG picture must pass (ADR 0360): reject, never rewrite.

Run by the upload of a picture payload and by the repository copy. It is pure, reads the document
once with the standard library's XML parser and never resolves anything. A document is accepted only
if every element is a drawing element of a fixed list, nothing in it can run or fetch, and it is not
deeper or larger than the limits below.
"""

from __future__ import annotations

import re
from xml.parsers import expat

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"

MAX_DEPTH = 64
MAX_ELEMENTS = 50_000

ALLOWED_ELEMENTS = frozenset(
    {
        "svg",
        "g",
        "defs",
        "title",
        "desc",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "use",
        "image",
        "linearGradient",
        "radialGradient",
        "stop",
        "clipPath",
        "mask",
        "pattern",
        "style",
    }
)

_DATA_IMAGE = re.compile(r"^data:image/(?:png|jpeg|gif|webp)[;,]", re.IGNORECASE)
_UNSAFE = re.compile(
    r"javascript:|vbscript:|data:text|@import|expression\(|url\(\s*(?![\"']?#)", re.IGNORECASE
)
_SPACE = re.compile(r"[\s\x00-\x1f]+")


class SvgRefused(Exception):
    """The one sentence the author is told; it repeats nothing of the document."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _unsafe(value: str) -> bool:
    # Whitespace and control characters are dropped first, as a browser does, so that
    # "java\tscript:" is read as what it is.
    return bool(_UNSAFE.search(_SPACE.sub("", value)))


def _split(name: str) -> tuple[str, str]:
    namespace, _, local = name.rpartition(" ")
    return namespace, local


def check_svg(data: bytes) -> None:
    """Returns when the document may be kept as a picture, else raises `SvgRefused`."""
    state = {"depth": 0, "elements": 0, "root": False}
    in_style: list[bool] = []
    style_text: list[str] = []

    def refuse(reason: str) -> None:
        raise SvgRefused(reason)

    def start(name: str, attributes: dict[str, str]) -> None:
        namespace, local = _split(name)
        state["depth"] += 1
        state["elements"] += 1
        if state["depth"] > MAX_DEPTH:
            refuse(f"The SVG is more than {MAX_DEPTH} levels deep.")
        if state["elements"] > MAX_ELEMENTS:
            refuse(f"The SVG has more than {MAX_ELEMENTS:,} elements.")
        if not state["root"]:
            state["root"] = True
            if namespace != SVG_NAMESPACE or local != "svg":
                refuse("The picture is not an SVG document.")
        if namespace != SVG_NAMESPACE or local not in ALLOWED_ELEMENTS:
            refuse(
                "The SVG holds an element that a picture may not (a script, a link, an animation "
                "or an editor's own element). Save it as a plain SVG."
            )
        in_style.append(local == "style")
        for key, value in attributes.items():
            attr_namespace, attr = _split(key)
            if attr_namespace not in ("", XLINK_NAMESPACE, XML_NAMESPACE):
                refuse("The SVG holds an attribute that a picture may not.")
            if attr.lower().startswith("on"):
                refuse("The SVG holds an event handler.")
            if attr == "href":
                target = _SPACE.sub("", value)
                if local == "image":
                    if not _DATA_IMAGE.match(target):
                        refuse("An image in the SVG must be inside it, as a data URL.")
                elif not target.startswith("#"):
                    refuse("A link in the SVG may only point at a part of itself.")
            elif _unsafe(value):
                refuse("The SVG holds a value that could run or fetch something.")

    def end(_name: str) -> None:
        state["depth"] -= 1
        if in_style.pop():
            if _unsafe("".join(style_text)):
                refuse("The SVG holds a style that could run or fetch something.")
            style_text.clear()

    def text(chunk: str) -> None:
        if in_style and in_style[-1]:
            style_text.append(chunk)

    def doctype(*_args: object) -> None:
        refuse("The SVG has a document type declaration, which a picture may not.")

    def instruction(*_args: object) -> None:
        refuse("The SVG has a processing instruction, which a picture may not.")

    parser = expat.ParserCreate(namespace_separator=" ")
    parser.buffer_text = True
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = doctype
    parser.EntityDeclHandler = doctype
    parser.ProcessingInstructionHandler = instruction
    try:
        parser.Parse(data, True)
    except expat.ExpatError:
        refuse("The SVG is not well-formed.")
    if not state["root"]:
        refuse("The picture is not an SVG document.")
