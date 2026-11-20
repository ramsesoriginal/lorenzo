// Find and replace over the text (ADR 0512), as pure functions the editor's bar and its tests share.

export type FindOptions = { caseSensitive?: boolean; wholeWord?: boolean };

/** Every match of `query`, as `[start, end)` pairs, in order. An empty query matches nothing. */
export function findAll(
  text: string,
  query: string,
  options: FindOptions = {},
): [number, number][] {
  if (!query) return [];
  const haystack = options.caseSensitive ? text : text.toLocaleLowerCase();
  const needle = options.caseSensitive ? query : query.toLocaleLowerCase();
  const found: [number, number][] = [];
  const word = /[\p{L}\p{N}_]/u;
  for (
    let at = haystack.indexOf(needle);
    at >= 0;
    at = haystack.indexOf(needle, at + needle.length)
  ) {
    const end = at + needle.length;
    if (options.wholeWord && (word.test(text[at - 1] ?? '') || word.test(text[end] ?? '')))
      continue;
    found.push([at, end]);
  }
  return found;
}

/** The text with each match from `from` on replaced; with `once`, only the first one. */
export function replaceMatches(
  text: string,
  query: string,
  replacement: string,
  options: FindOptions & { from?: number; once?: boolean } = {},
): { text: string; count: number; end: number } {
  const matches = findAll(text, query, options).filter(([start]) => start >= (options.from ?? 0));
  const chosen = options.once ? matches.slice(0, 1) : matches;
  let out = '';
  let last = 0;
  for (const [start, end] of chosen) {
    out += text.slice(last, start) + replacement;
    last = end;
  }
  out += text.slice(last);
  const first = chosen[0];
  return {
    text: out,
    count: chosen.length,
    end: first ? first[0] + replacement.length : (options.from ?? 0),
  };
}
