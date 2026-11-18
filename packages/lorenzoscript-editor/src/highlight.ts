// Quiet highlighting (ADR 0516): the markers of LorenzoScript shown in a softer colour behind the
// text, so a source reads at a glance. Colour only, never size or weight, so the text under the
// layer keeps its exact place. Opt-in: `highlight` on the editor.

export type Mark = 'mark' | 'code' | 'ref' | 'link' | 'quote';

const esc = (text: string) =>
  text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const span = (kind: Mark, text: string) => `<span class="ls-hl-${kind}">${esc(text)}</span>`;

const isSpace = (c: string | undefined) => c !== undefined && /\s/.test(c);
const isWord = (c: string | undefined) => c !== undefined && /[\w]/.test(c);

/** Where the marker starting at `i` ends, or null. Hand-scanned: every step only moves forward. */
function marker(line: string, i: number, closes: { [ch: string]: number }): [Mark, number] | null {
  const c = line[i] as string;
  // `closes[ch]` is a position from which `ch` was found nowhere, so later searches skip the scan.
  const find = (ch: string, from: number) => {
    const none = closes[ch];
    if (none !== undefined && from >= none) return -1;
    const at = line.indexOf(ch, from);
    if (at === -1) closes[ch] = from;
    return at;
  };
  if (c === '`') {
    const end = find('`', i + 1);
    if (end > i + 1) return ['code', end + 1];
    return null;
  }
  if (c === '[' && line[i + 1] === '[') {
    const end = find(']', i + 2);
    if (end !== -1 && line[end + 1] === ']') return ['ref', end + 2];
  }
  if (c === '[' || (c === '!' && line[i + 1] === '[')) {
    const open = c === '!' ? i + 1 : i;
    const close = find(']', open + 1);
    if (close !== -1 && line[close + 1] === '(') {
      const end = find(')', close + 2);
      if (end !== -1) return ['link', end + 1];
    }
    return null;
  }
  if ((c === '*' || c === '~' || c === '_') && line[i + 1] === c && c !== '*')
    return ['mark', i + 2];
  if (c === '*' && line[i + 1] === '*') return ['mark', i + 2];
  if (c === '*') {
    const before = line[i - 1];
    const after = line[i + 1];
    const opens = before !== '*' && !isWord(before) && after !== undefined && !isSpace(after);
    const shuts = before !== undefined && !isSpace(before) && !isWord(after) && after !== '*';
    if (opens || shuts) return ['mark', i + 1];
  }
  return null;
}

function inline(line: string): string {
  let out = '';
  let last = 0;
  const closes: { [ch: string]: number } = {};
  for (let i = 0; i < line.length; ) {
    const found = marker(line, i, closes);
    if (!found) {
      i += 1;
      continue;
    }
    out += esc(line.slice(last, i)) + span(found[0], line.slice(i, found[1]));
    i = found[1];
    last = i;
  }
  return out + esc(line.slice(last));
}

const skipSpaces = (line: string, max = line.length) => {
  let i = 0;
  while (i < max && line[i] === ' ') i += 1;
  return i;
};

/** The leading marker of a line (heading, quote or list item) and where the rest starts. */
function lead(line: string): [Mark, number] | null {
  const indent = skipSpaces(line, 3);
  if (line[indent] === '#') {
    let n = indent;
    while (line[n] === '#') n += 1;
    if (n - indent <= 6 && (n === line.length || isSpace(line[n]))) return ['mark', n];
    return null;
  }
  if (line[indent] === '>') {
    let n = indent;
    while (line[n] === '>') {
      n += 1;
      if (isSpace(line[n])) n += 1;
    }
    return ['quote', n];
  }
  let n = 0;
  while (isSpace(line[n])) n += 1;
  if (line[n] === '-' || line[n] === '*' || line[n] === '+') n += 1;
  else {
    const from = n;
    while (n < line.length && line.charCodeAt(n) >= 48 && line.charCodeAt(n) <= 57) n += 1;
    if (n === from || n - from > 9 || (line[n] !== '.' && line[n] !== ')')) return null;
    n += 1;
  }
  if (!isSpace(line[n])) return null;
  while (isSpace(line[n])) n += 1;
  if (
    line[n] === '[' &&
    /[ xX]/.test(line[n + 1] ?? '-') &&
    line[n + 2] === ']' &&
    isSpace(line[n + 3])
  ) {
    n += 3;
    while (isSpace(line[n])) n += 1;
  }
  return ['mark', n];
}

const isFence = (line: string) => {
  const at = skipSpaces(line, 3);
  const c = line[at];
  if (c !== '`' && c !== '~') return false;
  let n = at;
  while (line[n] === c) n += 1;
  return n - at >= 3;
};

/** The text as HTML in which only the markers are wrapped; escaped, and the same characters. */
export function highlightSource(source: string): string {
  let fenced = false;
  return source
    .split('\n')
    .map((line) => {
      if (isFence(line)) {
        fenced = !fenced;
        return span('code', line);
      }
      if (fenced) return span('code', line);
      const head = lead(line);
      if (head) return span(head[0], line.slice(0, head[1])) + inline(line.slice(head[1]));
      return inline(line);
    })
    .join('\n');
}
