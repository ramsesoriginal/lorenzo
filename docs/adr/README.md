
- [0521 - Markdown in and out](0521-markdown-in-and-out.md) — ADR 0494 C3, the first format: Export downloads Markdown; the shelf imports Markdown files or a folder as Chapters (a Book for several), `[[links]]` kept for the link review.
- [0520 - Move a block to another Chapter](0520-move-a-block-to-another-chapter.md) — ADR 0494 Q1: `POST …/payloads/{payload_id}/move` moves a text or picture to another Chapter or Edition; Writing's block menu offers it.
- [0519 - The shelf shows when a work was edited](0519-the-shelf-shows-when-a-work-was-edited.md) — ADR 0494 Q4: entry list rows carry `updated_at`; the shelf says when, orders by it and counts the works.
- [0518 - Undo a join](0518-undo-a-join.md) — ADR 0494 Q2: `DELETE …/joins/{operation_id}` returns a joined Chapter's writing and restores the outlines; the receipt records the retargeted redirects.
- [0517 - Undo a Scene extraction](0517-undo-a-scene-extraction.md) — ADR 0494 Q2: the extraction undo also takes back a Scene extraction (telling and Scene removed, the writing returned).
- [0516 - Quiet highlighting in the LorenzoScript editor](0516-lorenzoscript-editor-quiet-highlighting.md) — ADR 0494 B4: the opt-in `highlight` option colours the markers in a layer behind the text area; colour only; `highlightSource` is pure.
