"""Conservative lossless paragraph boundaries, not a second LS parser (ADR 0346)."""

import re

_GAP = re.compile(r"(?:\r?\n)[ \t]*(?:\r?\n)(?:[ \t]*\r?\n)*")
_COMPOUND = re.compile(
    r"^ {0,3}(?:>|`{3,}|~{3,}|\$\$|\{\{|\}\}|[-+*](?:[ \t]|$)|[0-9]{1,9}[.)](?:[ \t]|$)|\*\[)"
)
_FOOTNOTE = re.compile(r"\[\^([^\]]+)\]")


def split_points(source: str) -> list[int]:
    """Offsets count Unicode code points; callers use server-provided offsets unchanged.

    Refuse compound/document-wide syntax conservatively. No text is rewritten. A label's
    first-to-last interval prevents separating a simple footnote from any of its uses.
    Canonical parser parity is tested against the same source fixtures in Writing.
    """
    if "#" in source or "|" in source or "\0" in source or "\r" in source.replace("\r\n", ""):
        return []
    for line in source.splitlines():
        expanded = line.expandtabs(4)
        if expanded.strip() and (expanded.startswith("    ") or _COMPOUND.match(expanded)):
            return []
    ranges: dict[str, tuple[int, int]] = {}
    for match in _FOOTNOTE.finditer(source):
        label = " ".join(match[1].lower().split())
        start, _ = ranges.get(label, (match.start(), match.end()))
        ranges[label] = (start, match.end())
    intervals: list[tuple[int, int]] = []
    for start, end in sorted(ranges.values()):
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
        if not first_content < offset < last_content:
            continue
        while interval < len(intervals) and intervals[interval][1] <= offset:
            interval += 1
        if interval < len(intervals) and intervals[interval][0] < offset < intervals[interval][1]:
            continue
        result.append(offset)
    return result
