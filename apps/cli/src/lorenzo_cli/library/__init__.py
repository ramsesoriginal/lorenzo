"""The library document (ADR 0498): a system or the neutral vocabulary as one TOML file, planned
against a library, applied to it and exported from it.

- `document` is the file: its tables, and the checks that need no library.
- `state` reads what a library holds of it, in a few paged reads.
- `planner` works out what applying would create, change or remove, and what it cannot do.
- `writer` carries a plan out, level by level, a few requests at a time.
- `exporter` writes a library's system, or its neutral vocabulary, back as a document.
- `render` shows a plan or a result to a person or as `--json`.
"""
