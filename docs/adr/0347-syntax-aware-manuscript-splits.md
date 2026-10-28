# 0347 - Syntax-aware manuscript splits

Status: accepted implementation of RFC 0047 W5d under ADR 0327.

## Decision

Extend ADR 0346 using the existing Python LorenzoScript parser (ADR 0110), which
shares the canonical grammar with the TypeScript parser. Record top-level source
line spans during parsing; offer blank-line boundaries only between complete
blocks. Lists, quotations, tables, fenced and indented code, display math and
class blocks no longer disqualify an entire manuscript. Never split inside them,
including nested containers or unfinished fences. Preserve the exact saved source.

Distinct headings can lie on opposite sides. Conservatively keep heading anchor
families together: an explicit id or generated slug and its numeric suffixes share
a family, so splitting cannot reset de-duplication and change an anchor. Keep every
occurrence of a normalized footnote label together, including nested notes.
Document-wide abbreviations, contents directives and local fragment links still
refuse splitting; handling their cross-document semantics is deferred. These limits
are explained without exposing offsets or markup implementation details in controls.

Parse once, record consumed boundaries and dependency intervals, and filter candidates
in a sweep. Do not reparse the complete text for each candidate. Parser analysis must
not change the existing public reference AST or reference extraction. No new schema,
API contract, editor, styles or runtime is needed. ADR 0346's locks, conditional writes,
shared description writer, revisions and retry receipts remain authoritative.

The cursor chooses a blank-line boundary before a complete section. Confirmation
shows the opening words of the second part. An unsafe internal boundary is refused,
never silently moved to a different section. Whole-element extraction remains usable.
Joins and guarded redirects remain subsequent W5 work.

## Validation

Expand shared source fixtures checked by Python and the canonical TypeScript parser:
complete and nested blocks, internal boundaries, incomplete fences, heading collisions,
footnote dependencies, Unicode and CRLF. Accepted halves must reproduce the original
AST and exact source. Cover a large manuscript and preserve existing parser/reference
SPEC tests. Exercise a compound manuscript through the conditional split API and the
real-browser split/extract/read flow, including accessibility.
