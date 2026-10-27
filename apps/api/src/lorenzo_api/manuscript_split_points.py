"""Lossless boundaries between complete LorenzoScript blocks (ADRs 0346, 0347)."""

import re

from lorenzo_api.lorenzoscript import normalize_label, split_structure

_GAP = re.compile(r"(?:\r?\n)[ \t]*(?:\r?\n)(?:[ \t]*\r?\n)*")
_FOOTNOTE = re.compile(r"\[\^([^\]]+)\]")


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
    for match in _FOOTNOTE.finditer(source):
        label = normalize_label(match[1])
        start, _ = ranges.get(label, (match.start(), match.end()))
        ranges[label] = (start, match.end())
    dependencies = list(ranges.values())
    families: dict[str, list[int]] = {}
    for key, owners in structure.headings.items():
        # A suffix can collide only when its base also occurs. Section-1 and
        # Section-2 alone do not compete; Section plus Section-2 potentially do.
        family = candidate = key
        while (base := re.sub(r"-[0-9]+$", "", candidate)) != candidate:
            if base in structure.headings:
                family = base
            candidate = base
        families.setdefault(family, []).extend(owners)
    for owners in families.values():
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
