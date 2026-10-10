// Other ways to write a name (ADR 0193, ADR 0242): what is tried when a name matches no item.
//
// From one name, in order and without repeats: the name without a bracket or a length, as a
// singular, then each of those through the table of whole names and the table of words. Nothing is
// guessed that the table does not say. This is the same algorithm as
// apps/cli/src/lorenzo_cli/inventory/preprocess.py; `vectors.json` is what holds them together.
import { parse } from 'smol-toml';
import builtinText from '../preprocess.toml?raw';

export type Table = Readonly<{
  /** A whole name, and the titles it may be called, most likely first. */
  names: ReadonlyMap<string, readonly string[]>;
  /** One word and its translation. */
  words: ReadonlyMap<string, string>;
}>;

const BRACKETS = /\s*[([][^)\]]*[)\]]\s*/g;
const LENGTH = /(?:^|\s+)\d+(?:[.,]\d+)?\s*(?:ft\.?|feet|foot|m|meters?|metres?)\b/gi;
const MATH = /\s*\$[^$]*\$/g;
const SPACES = /\s+/g;

const clean = (name: string) => name.replace(SPACES, ' ').trim().toLowerCase();

function singular(name: string): string | null {
  if (name.endsWith('ies') && name.length > 4) return `${name.slice(0, -3)}y`;
  if (/(?:ches|shes|sses|xes|zes)$/.test(name)) return name.slice(0, -2);
  if (name.endsWith('s') && !name.endsWith('ss') && name.length > 3) return name.slice(0, -1);

  return null;
}

/** Other ways to write `name`, most likely first, never the name itself. */
export function alternatives(name: string, table: Table): string[] {
  const start = clean(name);
  const stems = [start];
  const stripped = name.replace(BRACKETS, ' ').replace(LENGTH, '').replace(MATH, '');
  const stem = clean(stripped.trim().replace(/^[ ,-]+|[ ,-]+$/g, ''));

  if (stem && !stems.includes(stem)) stems.push(stem);

  for (const each of [...stems]) {
    const one = singular(each);

    if (one && !stems.includes(one)) stems.push(one);
  }

  const out: string[] = [];
  const add = (candidate: string) => {
    if (candidate && candidate !== start && !out.includes(candidate)) out.push(candidate);
  };
  const translated = (candidate: string) => {
    add(candidate);

    const one = singular(candidate);

    if (one) add(one);
  };

  for (const each of stems) add(each);

  for (const each of stems) {
    for (const other of table.names.get(each) ?? []) translated(other);

    const words = each.split(' ');

    if (words.some((word) => table.words.has(word))) {
      translated(words.map((word) => table.words.get(word) ?? word).join(' '));
    }
  }

  return out;
}

/** A table from TOML text: `[names]` (a title or a list of them) and `[words]`. */
export function parseTable(text: string): Table {
  const data = parse(text) as {
    names?: Record<string, string | string[]>;
    words?: Record<string, string>;
  };
  const names = new Map<string, string[]>();
  const words = new Map<string, string>();

  for (const [key, value] of Object.entries(data.names ?? {})) {
    names.set(clean(key), (typeof value === 'string' ? [value] : value).map(clean));
  }

  for (const [key, value] of Object.entries(data.words ?? {})) words.set(clean(key), clean(value));

  return { names, words };
}

let builtin: Table | undefined;

/** The table that ships here, read once. */
export function builtinTable(): Table {
  builtin ??= parseTable(builtinText);

  return builtin;
}
