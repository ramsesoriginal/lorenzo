// LorenzoScript's syntax tree: plain data, produced by `parse` and read by
// `render`. Later stages add node types; they never change existing ones.

export type Document = { children: Block[] };

export type Block =
  | { type: 'paragraph'; children: Inline[] }
  | { type: 'heading'; level: number; children: Inline[] }
  | { type: 'blockquote'; children: Block[] }
  | { type: 'list'; ordered: boolean; start: number; tight: boolean; items: Item[] }
  | { type: 'code'; lang: string; text: string }
  | { type: 'rule' };

/** `checked` is `null` for an ordinary item, a boolean for a task item. */
export type Item = { type: 'item'; checked: boolean | null; children: Block[] };

/** Inline elements whose tag name is their type. */
export type Span = 'em' | 'strong' | 'i' | 'b';

export type Inline =
  | { type: 'text'; text: string }
  | { type: 'codespan'; text: string }
  | { type: Span; children: Inline[] }
  | { type: 'link' | 'image'; url: string; title: string; children: Inline[] }
  | { type: 'break' };
