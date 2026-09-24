// LorenzoScript's syntax tree: plain data, produced by `parse` and read by
// `render`. Later stages add node types and optional fields; they never remove
// or repurpose existing ones.

export type Document = {
  children: Block[];
  /** Collected wherever defined; the first definition of a label or term wins. */
  footnotes: Footnote[];
  abbreviations: Abbreviation[];
};

/** `label` is normalized: lowercase, whitespace collapsed. */
export type Footnote = { label: string; children: Block[] };
export type Abbreviation = { term: string; title: string };

/** From `{#id .class}`. An empty `id` means none. */
export type Attrs = { id: string; classes: string[] };

export type Align = 'left' | 'center' | 'right' | null;

export type Block =
  | { type: 'paragraph'; children: Inline[] }
  /** `attrs.id` is always set: the explicit id, else a slug of the heading's text. */
  | { type: 'heading'; level: number; attrs: Attrs; children: Inline[] }
  | { type: 'blockquote'; children: Block[] }
  | { type: 'list'; ordered: boolean; start: number; tight: boolean; items: Item[] }
  | { type: 'code'; lang: string; text: string; attrs?: Attrs }
  | { type: 'rule' }
  | { type: 'table'; align: Align[]; head: Inline[][]; rows: Inline[][][] }
  | { type: 'div'; attrs: Attrs; children: Block[] }
  | { type: 'math'; display: true; tex: string }
  | { type: 'toc' };

/** `checked` is `null` for an ordinary item, a boolean for a task item. */
export type Item = { type: 'item'; checked: boolean | null; children: Block[] };

/** Inline elements whose tag name is their type. */
export type Span = 'em' | 'strong' | 'i' | 'b' | 'del' | 'sub' | 'sup' | 'span';

export type Inline =
  | { type: 'text'; text: string }
  | { type: 'codespan'; text: string; attrs?: Attrs }
  | { type: Span; attrs?: Attrs; children: Inline[] }
  | { type: 'link' | 'image'; url: string; title: string; attrs?: Attrs; children: Inline[] }
  | { type: 'math'; display: boolean; tex: string; attrs?: Attrs }
  /** A `[^label]` reference, resolved against `Document.footnotes` when rendering. */
  | { type: 'footnote'; label: string }
  | { type: 'break' };
