"""Lossless boundaries between complete LorenzoScript blocks (ADRs 0346, 0347)."""

import re
from dataclasses import dataclass, field

from lorenzo_api.lorenzoscript import normalize_label, split_structure

_GAP = re.compile(r"(?:\r?\n)[ \t]*(?:\r?\n)(?:[ \t]*\r?\n)*")


@dataclass
class _HeadingPrefix:
    children: dict[str, _HeadingPrefix] = field(default_factory=dict)
    key: str | None = None


def _heading_families(headings: dict[str, list[int]]) -> list[list[int]]:
    """Group potential anchor collisions without repeatedly scanning long suffixes."""
    root = _HeadingPrefix()
    for key in headings:
        node = root
        for part in key.split("-"):
            if part not in node.children:
                node.children[part] = _HeadingPrefix()
            node = node.children[part]
        node.key = key
    families: dict[str, list[int]] = {}
    for key, owners in headings.items():
        parts = key.split("-")
        tail = len(parts)
        while tail > 1 and parts[tail - 1].isascii() and parts[tail - 1].isdecimal():
            tail -= 1
        node = root
        family = key
        for index, part in enumerate(parts):
            node = node.children[part]
            if index + 1 >= tail and node.key is not None:
                family = node.key
                break
        families.setdefault(family, []).extend(owners)
    return list(families.values())


def split_points(source: str) -> list[int]:
    """Offsets count Unicode code points; callers use server-provided offsets unchanged.

    Parse once to find complete top-level blocks, then sweep dependency intervals.
    No text is rewritten and no candidate requires another parse of the manuscript.
    """
    if "\0" in source or "\r" in source.replace("\r\n", ""):
        return []
    structure = split_structure(source)
    if structure.document_wide:
        return []
    line_offsets = [0, *(match.end() for match in re.finditer("\n", source))]
    starts = {line_offsets[line] for line in structure.starts}
    ranges: dict[str, tuple[int, int]] = {}
    cursor = 0
    # A failed regex search for ] at every [^ would repeatedly scan the same tail.
    # Visit each closing-bracket-delimited piece once, including literal code text.
    pieces = source.split("]")
    for piece in pieces[:-1]:
        end = cursor + len(piece) + 1
        marker = piece.find("[^")
        if 0 <= marker < len(piece) - 2:
            label = normalize_label(piece[marker + 2 :])
            start, _ = ranges.get(label, (cursor + marker, end))
            ranges[label] = (start, end)
        cursor = end
    dependencies = list(ranges.values())
    for owners in _heading_families(structure.headings):
        if len(owners) > 1:
            # Include the later heading's start itself in the forbidden interval.
            dependencies.append((line_offsets[min(owners)], line_offsets[max(owners)] + 1))
    intervals: list[tuple[int, int]] = []
    for start, end in sorted(dependencies):
        if intervals and start <= intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], max(end, intervals[-1][1]))
        else:
            intervals.append((start, end))
    result = []
    interval = 0
    first_content = len(source) - len(source.lstrip())
    last_content = len(source.rstrip())
    for gap in _GAP.finditer(source):
        offset = gap.end()
        if offset not in starts or not first_content < offset < last_content:
            continue
        while interval < len(intervals) and intervals[interval][1] <= offset:
            interval += 1
        if interval < len(intervals) and intervals[interval][0] < offset < intervals[interval][1]:
            continue
        result.append(offset)
    return result
