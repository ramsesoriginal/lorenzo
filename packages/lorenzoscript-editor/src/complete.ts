// `[[` completion (ADR 0514): after `[[` and some letters, the names the app offers, picked by
// keyboard. The package has no client for names; the app passes the lookup. Opt-in.

/** Where a completion is being typed: the text after the last `[[` before the caret, or null. */
export function completionContext(
  text: string,
  caret: number,
): { start: number; query: string } | null {
  const before = text.slice(0, caret);
  const open = before.lastIndexOf('[[');
  if (open < 0) return null;
  const query = before.slice(open + 2);
  if (/[\]\n]/.test(query) || query.length > 60) return null;
  return { start: open + 2, query };
}

/** The text with the chosen name written in, closed with `]]`, and the caret after it. */
export function complete(
  text: string,
  caret: number,
  name: string,
): { text: string; caret: number } | null {
  const at = completionContext(text, caret);
  if (!at) return null;
  const after = text.slice(caret);
  const rest = after.startsWith(']]') ? after.slice(2) : after;
  const next = `${text.slice(0, at.start)}${name}]]${rest}`;
  return { text: next, caret: at.start + name.length + 2 };
}
